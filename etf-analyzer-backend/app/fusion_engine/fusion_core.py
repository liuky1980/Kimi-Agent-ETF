"""
融合决策核心引擎
================
五维融合决策引擎的核心实现，负责整合宏观、缠论、情绪、波动率、丁昶五层信号，
生成最终的仓位计算与执行计划。

核心公式:
    raw_position = strategic_cap * valuation_weight * tactical_ratio * confidence * vol_coeff
    final_position = min(raw_position, 0.25)  # 单标的上限25%

依赖:
    - app.models.fusion_models: 全部数据模型（master definition）
    - app.config: 应用配置
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from app.models.fusion_models import (
    DecisionCard,
    ExecutionPlan,
    FusionConfig,
    MacroResult,
    PositionCalculation,
    PositionLimitConfig,
    SentimentResult,
    ValidatedSignal,
    VolatilityResult,
)

logger = logging.getLogger(__name__)


class FusionEngine:
    """五维融合决策引擎

    整合五个分析层的信号，通过量化公式计算最终仓位，并生成可执行的交易计划。

    五维输入:
        1. 宏观层 (MacroResult) — 决定战略仓位上限 position_limit
        2. 丁昶层 (Dict) — 提供估值权重 valuation_weight
        3. 缠论层 (Dict) — 提供战术比例 tactical_ratio（按级别映射）
        4. 情绪层 (SentimentResult) — 提供置信度 confidence
        5. 波动率层 (VolatilityResult) — 提供波动率系数 vol_coeff

    Attributes
    ----------
    config : FusionConfig
        融合引擎配置
    macro_layer : Optional[Any]
        宏观层分析器实例（可选，可外部注入）
    sentiment_layer : Optional[Any]
        情绪层分析器实例（可选，可外部注入）
    volatility_layer : Optional[Any]
        波动率层分析器实例（可选，可外部注入）
    """

    # 缠论级别 → 战术比例映射
    _TACTICAL_RATIO_MAP: Dict[str, float] = {
        "weekly": 0.60,
        "daily": 0.30,
        "30min": 0.10,
    }

    # 缠论级别 → 持仓周期映射
    _HOLDING_PERIOD_MAP: Dict[str, str] = {
        "weekly": "日线级别预期8-12周",
        "daily": "日线级别预期2-4周",
        "30min": "日线级别预期3-5日",
    }

    # 情绪等级 → 置信度映射（百分比）
    _SENTIMENT_CONFIDENCE_MAP: Dict[str, float] = {
        "A": 85.0,
        "B": 65.0,
        "C": 45.0,
        "D": 25.0,
    }

    def __init__(
        self,
        config: Optional[FusionConfig] = None,
        macro_layer: Optional[Any] = None,
        sentiment_layer: Optional[Any] = None,
        volatility_layer: Optional[Any] = None,
    ) -> None:
        """初始化融合引擎

        Parameters
        ----------
        config : FusionConfig, optional
            融合引擎配置，默认使用内置默认配置
        macro_layer : Any, optional
            宏观层分析器实例
        sentiment_layer : Any, optional
            情绪层分析器实例
        volatility_layer : Any, optional
            波动率层分析器实例
        """
        self.config = config or FusionConfig()
        self.macro_layer = macro_layer
        self.sentiment_layer = sentiment_layer
        self.volatility_layer = volatility_layer

        logger.info("FusionEngine initialized with config: fusion_enabled=%s",
                     self.config.fusion_enabled)

    # ────────────────────────────── 核心仓位计算 ──────────────────────────────

    def calculate_position(
        self,
        etf_code: str,
        chan_signal: Dict[str, Any],
        ding_signal: Dict[str, Any],
        macro_data: Optional[MacroResult] = None,
        sentiment_data: Optional[SentimentResult] = None,
        df_daily: Optional[Any] = None,
    ) -> PositionCalculation:
        """核心仓位计算 — 五维融合公式

        严格按照以下公式计算:
            strategic_cap = macro_result.position_limit
            valuation_weight = ding_signal.get('weight', 0.25)
            tactical_ratio = _TACTICAL_RATIO_MAP[chan_signal.get('level', 'daily')]
            confidence = validated_signal.final_confidence / 100
            vol_coeff = volatility_result.position_coefficient

            raw_position = strategic_cap * valuation_weight * tactical_ratio * confidence * vol_coeff
            final_position = min(raw_position, 0.25)

        Parameters
        ----------
        etf_code : str
            ETF代码
        chan_signal : dict
            缠论信号字典，至少包含 'level' 键 (weekly/daily/30min)
        ding_signal : dict
            丁昶信号字典，至少包含 'weight' 键
        macro_data : MacroResult, optional
            宏观层分析结果
        sentiment_data : SentimentResult, optional
            情绪层分析结果
        df_daily : DataFrame, optional
            日线数据（用于波动率计算，如未提供波动率数据时）

        Returns
        -------
        PositionCalculation
            仓位计算结果，包含五维因子和最终仓位
        """
        logger.debug("calculate_position called for %s", etf_code)

        # 1. 宏观层 — 战略仓位上限
        if macro_data is not None:
            strategic_cap = macro_data.position_limit
        else:
            # 无宏观数据时默认允许100%（后续由其他层限制）
            strategic_cap = 1.0
            logger.warning("宏观数据缺失，strategic_cap 默认使用 1.0")

        # 2. 丁昶层 — 估值权重
        valuation_weight = ding_signal.get("weight", 0.25)
        if valuation_weight <= 0:
            valuation_weight = 0.25
            logger.warning("丁昶权重异常(%s)，使用默认值 0.25", valuation_weight)

        # 3. 缠论层 — 战术比例（按级别映射）
        level = chan_signal.get("level", "daily")
        tactical_ratio = self._TACTICAL_RATIO_MAP.get(level, 0.10)

        # 4. 情绪层 — 置信度（归一化到0~1）
        if sentiment_data is not None:
            confidence = sentiment_data.final_confidence / 100.0
        else:
            # 无情绪数据时使用默认中等置信度
            confidence = 0.50
            logger.warning("情绪数据缺失，confidence 默认使用 0.50")

        # 5. 波动率层 — 波动率系数
        if sentiment_data is not None:
            # 从情绪数据中提取波动率信息，或独立传入
            vol_coeff = self._get_volatility_coefficient(sentiment_data)
        else:
            vol_coeff = 1.0
            logger.warning("波动率数据缺失，vol_coeff 默认使用 1.0")

        # 波动率层如果独立传入则更优先
        if hasattr(self, "_last_volatility_result") and self._last_volatility_result is not None:
            vol_coeff = self._last_volatility_result.position_coefficient

        # 核心公式计算
        raw_position = strategic_cap * valuation_weight * tactical_ratio * confidence * vol_coeff
        final_position = min(raw_position, self.config.position_limit.single_etf_max)

        # 格式化百分比
        position_pct = f"{final_position * 100:.2f}%"

        # 各层得分摘要
        layer_scores = {
            "strategic_cap": round(strategic_cap, 4),
            "valuation_weight": round(valuation_weight, 4),
            "tactical_ratio": round(tactical_ratio, 4),
            "confidence": round(confidence, 4),
            "vol_coeff": round(vol_coeff, 4),
        }

        calc = PositionCalculation(
            strategic_cap=round(strategic_cap, 6),
            valuation_weight=round(valuation_weight, 6),
            tactical_ratio=round(tactical_ratio, 6),
            confidence=round(confidence, 6),
            vol_coeff=round(vol_coeff, 6),
            raw_position=round(raw_position, 6),
            final_position=round(final_position, 6),
            position_pct=position_pct,
            layer_scores=layer_scores,
        )

        logger.info(
            "仓位计算完成 %s: raw=%.4f, final=%.4f (%s)",
            etf_code, raw_position, final_position, position_pct
        )
        return calc

    # ────────────────────────────── 决策卡片生成 ──────────────────────────────

    def generate_decision_card(
        self,
        etf_code: str,
        etf_name: str,
        chanlun_result: Dict[str, Any],
        dingchang_result: Dict[str, Any],
        macro_result: MacroResult,
        sentiment_result: SentimentResult,
        volatility_result: VolatilityResult,
        position_calc: PositionCalculation,
    ) -> DecisionCard:
        """生成融合决策卡片

        将五层分析结果、仓位计算、执行计划整合为最终的决策卡片。

        Parameters
        ----------
        etf_code : str
            ETF代码
        etf_name : str
            ETF名称
        chanlun_result : dict
            缠论分析结果字典
        dingchang_result : dict
            丁昶分析结果字典
        macro_result : MacroResult
            宏观层分析结果
        sentiment_result : SentimentResult
            情绪层分析结果
        volatility_result : VolatilityResult
            波动率层分析结果
        position_calc : PositionCalculation
            仓位计算结果

        Returns
        -------
        DecisionCard
            完整的融合决策卡片
        """
        logger.debug("generate_decision_card called for %s", etf_code)

        # 构建缠论信号摘要
        chan_layer_summary = self._extract_chanlun_summary(chanlun_result)

        # 信号验证
        chan_signal = chanlun_result.get("signal", {})
        validated_signal = self._validate_signal(
            chan_signal, macro_result, sentiment_result, volatility_result
        )

        # 生成执行计划
        execution = self._build_execution_plan(
            position_calc, sentiment_result, macro_result, chan_signal
        )

        # 生成综合摘要
        summary = self._generate_summary(
            etf_code, etf_name, position_calc, macro_result, sentiment_result,
            validated_signal
        )

        # 生成风险警告
        risk_warning = self._generate_risk_warning(
            macro_result, sentiment_result, volatility_result
        )

        # 计算下次复核时间
        next_review = self._calculate_next_review(sentiment_result)

        card = DecisionCard(
            decision_id=str(uuid.uuid4())[:8],
            etf_code=etf_code,
            etf_name=etf_name,
            timestamp=datetime.now().isoformat(),
            macro_layer=macro_result,
            chan_layer=chan_layer_summary,
            sentiment_layer=sentiment_result,
            volatility_layer=volatility_result,
            validated_signal=validated_signal,
            position_calculation=position_calc,
            execution=execution,
            summary=summary,
            risk_warning=risk_warning,
            next_review=next_review,
        )

        logger.info("决策卡片生成完成 %s: action=%s, position=%s",
                     etf_code, execution.action, position_calc.position_pct)
        return card

    # ────────────────────────────── 便捷方法 ──────────────────────────────

    def quick_analyze(
        self,
        etf_code: str,
        chanlun_result: Dict[str, Any],
        dingchang_result: Dict[str, Any],
        macro_result: Optional[MacroResult] = None,
        sentiment_result: Optional[SentimentResult] = None,
        volatility_result: Optional[VolatilityResult] = None,
    ) -> DecisionCard:
        """快速分析 — 一站式生成决策卡片

        将仓位计算和决策卡片生成合并为单步调用。

        Parameters
        ----------
        etf_code : str
            ETF代码
        chanlun_result : dict
            缠论完整分析结果
        dingchang_result : dict
            丁昶完整分析结果
        macro_result : MacroResult, optional
            宏观层结果
        sentiment_result : SentimentResult, optional
            情绪层结果
        volatility_result : VolatilityResult, optional
            波动率层结果

        Returns
        -------
        DecisionCard
            完整的融合决策卡片
        """
        # 提供默认结果
        if macro_result is None:
            macro_result = MacroResult(
                position_limit=1.0,
                position_limit_pct="100%",
                summary="宏观数据未接入，默认允许满仓"
            )
        if sentiment_result is None:
            sentiment_result = SentimentResult(
                grade="C",
                final_confidence=50.0,
                summary="情绪数据未接入，默认C级"
            )
        if volatility_result is None:
            volatility_result = VolatilityResult(
                position_coefficient=1.0,
                summary="波动率数据未接入，默认正常"
            )

        # 提取信号
        chan_signal = chanlun_result.get("signal", chanlun_result)
        ding_signal = dingchang_result.get("signal", dingchang_result)

        # 缓存波动率结果供 calculate_position 使用
        self._last_volatility_result = volatility_result

        # 1. 仓位计算
        etf_name = chanlun_result.get("etf_name", dingchang_result.get("etf_name", ""))
        position_calc = self.calculate_position(
            etf_code=etf_code,
            chan_signal=chan_signal,
            ding_signal=ding_signal,
            macro_data=macro_result,
            sentiment_data=sentiment_result,
        )

        # 2. 生成决策卡片
        card = self.generate_decision_card(
            etf_code=etf_code,
            etf_name=etf_name,
            chanlun_result=chanlun_result,
            dingchang_result=dingchang_result,
            macro_result=macro_result,
            sentiment_result=sentiment_result,
            volatility_result=volatility_result,
            position_calc=position_calc,
        )

        return card

    # ────────────────────────────── 内部辅助方法 ──────────────────────────────

    def _get_volatility_coefficient(self, sentiment_data: SentimentResult) -> float:
        """获取波动率调整系数

        优先使用独立波动率层结果，否则从情绪层推断。
        """
        # 如果波动率层已独立计算，优先使用
        if hasattr(self, "_last_volatility_result") and self._last_volatility_result is not None:
            return self._last_volatility_result.position_coefficient

        # 从情绪层指标推断波动率状态
        metrics = sentiment_data.metrics
        if metrics.greed_fear_index > 90 or metrics.greed_fear_index < 10:
            return 0.50  # 极端情绪 → 大幅降低仓位
        elif metrics.greed_fear_index > 75 or metrics.greed_fear_index < 25:
            return 0.75  # 高/低情绪 → 适度降低仓位
        return 1.0  # 正常

    def _extract_chanlun_summary(self, chanlun_result: Dict[str, Any]) -> Dict[str, Any]:
        """从缠论完整结果中提取信号摘要"""
        summary: Dict[str, Any] = {}

        # 趋势位置
        summary["trend_position"] = chanlun_result.get("trend_position", "")

        # 背驰信息
        divergence = chanlun_result.get("divergence", {})
        if isinstance(divergence, dict):
            summary["divergence_type"] = divergence.get("type", "none")
            summary["divergence_strength"] = divergence.get("strength", 0.0)
        else:
            summary["divergence_type"] = chanlun_result.get("divergence_type", "none")
            summary["divergence_strength"] = chanlun_result.get("divergence_strength", 0.0)

        # 共振信息
        summary["composite_resonance"] = chanlun_result.get("composite_resonance", 0.0)

        # 买卖点
        bs_points = chanlun_result.get("buy_sell_points", [])
        if bs_points:
            summary["latest_bs_point"] = bs_points[0] if isinstance(bs_points[0], str) else bs_points[0].get("type", "")

        # 当前价格
        summary["current_price"] = chanlun_result.get("current_price", 0.0)

        # 信号级别
        signal = chanlun_result.get("signal", {})
        if isinstance(signal, dict):
            summary["signal_level"] = signal.get("level", "daily")
            summary["signal_direction"] = signal.get("direction", "")
        else:
            summary["signal_level"] = "daily"
            summary["signal_direction"] = ""

        return summary

    def _validate_signal(
        self,
        chan_signal: Dict[str, Any],
        macro_result: MacroResult,
        sentiment_result: SentimentResult,
        volatility_result: VolatilityResult,
    ) -> ValidatedSignal:
        """验证缠论信号是否通过三层过滤

        三层过滤规则:
        - 宏观层: position_limit < 0.2 时过滤
        - 情绪层: D级 时过滤
        - 波动率层: extreme 状态时过滤
        """
        # 原始信号
        original_direction = chan_signal.get("direction", "")
        original_level = chan_signal.get("level", "daily")
        original_strength = chan_signal.get("strength", 0.0)

        # 宏观过滤
        macro_pass = macro_result.position_limit >= 0.2

        # 情绪过滤
        sentiment_pass = sentiment_result.grade not in ("D",)

        # 波动率过滤
        vol_metrics = volatility_result.metrics
        vol_regime = vol_metrics.vol_regime
        volatility_pass = vol_regime != "extreme"

        # 综合判断
        final_valid = macro_pass and sentiment_pass and volatility_pass

        # 过滤原因
        filter_reasons: List[str] = []
        if not macro_pass:
            filter_reasons.append(f"宏观仓位限制过低({macro_result.position_limit_pct})")
        if not sentiment_pass:
            filter_reasons.append(f"市场情绪D级，禁止建仓")
        if not volatility_pass:
            filter_reasons.append("波动率极端状态")

        # 最终置信度 = 宏观允许比例 * 情绪置信度 * 波动率系数
        macro_contrib = macro_result.position_limit
        sentiment_contrib = sentiment_result.final_confidence / 100.0
        volatility_contrib = volatility_result.position_coefficient
        chanlun_contrib = original_strength

        final_confidence = macro_contrib * sentiment_contrib * volatility_contrib * chanlun_contrib * 100.0
        final_confidence = min(final_confidence, 100.0)

        return ValidatedSignal(
            original_signal=original_direction,
            original_level=original_level,
            original_strength=original_strength,
            macro_filter_passed=macro_pass,
            sentiment_filter_passed=sentiment_pass,
            volatility_filter_passed=volatility_pass,
            filter_reason="; ".join(filter_reasons),
            final_valid=final_valid,
            final_confidence=round(final_confidence, 2),
            macro_contrib=round(macro_contrib, 4),
            sentiment_contrib=round(sentiment_contrib, 4),
            volatility_contrib=round(volatility_contrib, 4),
            chanlun_contrib=round(chanlun_contrib, 4),
            summary="信号验证通过" if final_valid else f"信号被过滤: {'; '.join(filter_reasons)}",
        )

    def _build_execution_plan(
        self,
        position_calc: PositionCalculation,
        sentiment_result: SentimentResult,
        macro_result: MacroResult,
        chan_signal: Dict[str, Any],
    ) -> ExecutionPlan:
        """构建执行计划 — 根据情绪等级、宏观状态、仓位生成交易指令

        action映射规则:
        - 情绪A级 + 宏观允许 > 70% → "满仓执行，允许杠杆"
        - 情绪B级 + 宏观允许 40-70% → "正常执行，收紧止损"
        - 情绪C级 → "试仓1/3，观察3日"
        - 情绪D级 或 宏观limit<20% → "屏蔽信号，反向对冲或空仓"
        - 宏观冻结(IV) → "冻结，仅记录不执行"
        """
        grade = sentiment_result.grade
        position_limit = macro_result.position_limit
        level = chan_signal.get("level", "daily")
        final_position = position_calc.final_position

        # 判断宏观冻结状态（衰退期IV）
        if macro_result.quadrant == "IV":
            return ExecutionPlan(
                action="冻结，仅记录不执行",
                stop_loss=0.0,
                target_1=0.0,
                target_2=0.0,
                holding_period="不确定",
                batch_info="不执行",
                max_leverage=1.0,
                position_adjust_rules="衰退期冻结，等待宏观改善",
            )

        # 情绪D级 或 宏观仓位限制 < 20%
        if grade == "D" or position_limit < 0.2:
            action = "屏蔽信号，反向对冲或空仓"
            batch_info = "保持空仓或开反向对冲仓位"
            max_leverage = 1.0

        # 情绪C级
        elif grade == "C":
            action = "试仓1/3，观察3日"
            batch_info = f"先建目标仓位的1/3（约{final_position / 3 * 100:.2f}%），3日后评估加仓"
            max_leverage = 1.0

        # 情绪B级 + 宏观允许 40-70%
        elif grade == "B":
            action = "正常执行，收紧止损"
            batch_info = f"分批建仓，目标仓位{position_calc.position_pct}"
            max_leverage = 1.0

        # 情绪A级 + 宏观允许 > 70%
        elif grade == "A" and position_limit > 0.7:
            action = "满仓执行，允许杠杆"
            batch_info = f"全额建仓，目标仓位{position_calc.position_pct}，可适度加杠杆"
            max_leverage = self.config.position_limit.leverage_max

        # 情绪A级但宏观限制
        elif grade == "A":
            action = "正常执行，收紧止损"
            batch_info = f"情绪良好但宏观受限({macro_result.position_limit_pct})，谨慎建仓"
            max_leverage = 1.0

        else:
            action = "观望"
            batch_info = "条件不满足，暂不操作"
            max_leverage = 1.0

        # 持仓周期
        holding_period = self._HOLDING_PERIOD_MAP.get(level, "日线级别预期2-4周")

        # 止损/目标价（简化计算，实际应由缠论中枢和ATR确定）
        current_price = chan_signal.get("price", 0.0)
        if current_price > 0:
            atr_ratio = position_calc.vol_coeff  # 使用波动率系数作为ATR比例代理
            stop_loss = current_price * (1 - 0.03 * (1 + atr_ratio))
            target_1 = current_price * 1.05
            target_2 = current_price * 1.10
        else:
            stop_loss = 0.0
            target_1 = 0.0
            target_2 = 0.0

        # 仓位调整规则
        position_adjust_rules = self._build_position_adjust_rules(grade, macro_result)

        return ExecutionPlan(
            action=action,
            stop_loss=round(stop_loss, 4),
            target_1=round(target_1, 4),
            target_2=round(target_2, 4),
            holding_period=holding_period,
            batch_info=batch_info,
            max_leverage=max_leverage,
            position_adjust_rules=position_adjust_rules,
        )

    def _build_position_adjust_rules(
        self, grade: str, macro_result: MacroResult
    ) -> str:
        """生成仓位动态调整规则"""
        rules: List[str] = []

        if grade == "A":
            rules.append("情绪A级: 允许满仓，若情绪降至B级减仓1/3")
        elif grade == "B":
            rules.append("情绪B级: 正常持仓，若情绪降至C级减仓一半")
        elif grade == "C":
            rules.append("情绪C级: 仅试仓，若情绪不改善于3日内平仓")
        else:
            rules.append("情绪D级: 禁止新增仓位")

        if macro_result.quadrant == "IV":
            rules.append("宏观衰退期: 逐步清仓，转向防御资产")
        elif macro_result.quadrant == "III":
            rules.append("宏观滞胀期: 控制总仓位不超过40%")

        return "; ".join(rules) if rules else "按默认规则调整"

    def _generate_summary(
        self,
        etf_code: str,
        etf_name: str,
        position_calc: PositionCalculation,
        macro_result: MacroResult,
        sentiment_result: SentimentResult,
        validated_signal: ValidatedSignal,
    ) -> str:
        """生成综合决策摘要"""
        parts: List[str] = []

        parts.append(f"ETF {etf_code}({etf_name})")
        parts.append(f"宏观周期: {macro_result.quadrant_name}({macro_result.position_limit_pct})")
        parts.append(f"情绪等级: {sentiment_result.grade}级")
        parts.append(f"建议仓位: {position_calc.position_pct}")

        if validated_signal.final_valid:
            parts.append("信号有效，建议执行")
        else:
            parts.append(f"信号被过滤: {validated_signal.filter_reason}")

        return " | ".join(parts)

    def _generate_risk_warning(
        self,
        macro_result: MacroResult,
        sentiment_result: SentimentResult,
        volatility_result: VolatilityResult,
    ) -> str:
        """生成风险警告文本"""
        warnings: List[str] = []

        # 宏观风险
        if macro_result.macro_risks:
            warnings.extend(macro_result.macro_risks[:3])  # 最多取3条

        # 情绪风险
        if sentiment_result.grade == "D":
            warnings.append("市场情绪极度悲观，流动性风险上升")
        elif sentiment_result.grade == "A":
            warnings.append("市场情绪极度乐观，注意回调风险")

        # 波动率风险
        vol_metrics = volatility_result.metrics
        if vol_metrics.vol_regime == "extreme":
            warnings.append("波动率处于极端状态，价格可能剧烈波动")
        elif vol_metrics.vol_regime == "high":
            warnings.append("波动率偏高，持仓风险较大")

        if not warnings:
            return "暂无显著风险警告"

        return "; ".join(warnings)

    def _calculate_next_review(self, sentiment_result: SentimentResult) -> str:
        """计算下次复核时间

        根据情绪等级确定复核间隔:
        - A级: 1天后复核（情绪可能快速变化）
        - B级: 3天后复核
        - C级: 3天后复核（试仓观察期）
        - D级: 7天后复核（空仓期可减少关注）
        """
        grade = sentiment_result.grade
        review_days = {"A": 1, "B": 3, "C": 3, "D": 7}.get(grade, 3)
        next_time = datetime.now() + timedelta(days=review_days)
        return next_time.isoformat()
