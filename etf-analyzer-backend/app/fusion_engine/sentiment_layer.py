"""
市场情绪验证层
==============
综合PCR(看跌看涨比)、融资余额变化、资金流向(北向+主力)等多维数据，
计算情绪综合评分(A/B/C/D)，并据此验证和修正缠论信号的置信度。

评分规则:
- 资金流分: 北向+主力双流入>100亿=100, 单一流入>50亿=70, 震荡±30亿=40, 双流出=0
- 期权PCR分: PCR>1.3=100(极端恐惧), 1.0-1.3=80, 0.8-1.0=50, <0.7=0
- 融资变化分: >+3%=100, +1~+3%=70, -1~+1%=40, <-2%=0
- 情绪验证分 = 资金流×0.4 + PCR×0.3 + 融资×0.3
- A级: 80-100, B级: 50-79, C级: 20-49, D级: 0-19

缠论信号融合规则:
- final_confidence = base_score * sentiment_score / 100
- 日线底背驰 + PCR>1.2 → 置信度×1.1（额外+10%）
- 周线背驰 + 资金流出 → execution_mode='batch_3'
- D级情绪 → 屏蔽缠论信号
"""

import logging
from typing import Any, Dict, Optional

from app.models.fusion_models import SentimentResult, ValidatedSignal

logger = logging.getLogger(__name__)


class SentimentLayer:
    """市场情绪验证层

    负责计算多维情绪指标的综合评分，并将情绪评级与缠论信号融合，
    输出带有置信度和执行模式的验证信号。

    Parameters
    ----------
    config : dict, optional
        配置字典，可覆盖默认评分阈值和权重
    fetcher : Any, optional
        外部数据获取器，如SentimentDataFetcher实例
    """

    # 默认评分权重
    DEFAULT_WEIGHTS = {
        "fund_flow": 0.4,
        "pcr": 0.3,
        "financing": 0.3,
    }

    # 评级阈值
    DEFAULT_RATING_THRESHOLDS = {
        "A": (80.0, 100.0),
        "B": (50.0, 79.0),
        "C": (20.0, 49.0),
        "D": (0.0, 19.0),
    }

    # 资金流评分阈值
    FUND_FLOW_THRESHOLDS = {
        "dual_inflow_strong": 100.0,   # 双流入门槛(亿元)
        "single_inflow_strong": 50.0,  # 单一流入门槛(亿元)
        "oscillation": 30.0,           # 震荡区间(亿元)
    }

    # PCR评分阈值
    PCR_THRESHOLDS = {
        "extreme_fear": 1.3,   # 极端恐惧
        "fear": 1.0,           # 恐惧
        "neutral_high": 0.8,   # 中性偏恐惧
        "greed": 0.7,          # 贪婪阈值
    }

    # 融资评分阈值
    FINANCING_THRESHOLDS = {
        "strong_inflow": 0.03,   # 强流入 +3%
        "mild_inflow": 0.01,     # 温和流入 +1%
        "mild_outflow": -0.01,   # 温和流出 -1%
        "strong_outflow": -0.02, # 强流出 -2%
    }

    def __init__(self, config: Optional[Dict] = None, fetcher: Optional[Any] = None):
        self.config = config or {}
        self.fetcher = fetcher

        # 从config加载权重，使用默认值
        self.weights = self.config.get("weights", self.DEFAULT_WEIGHTS.copy())
        self.rating_thresholds = self.config.get(
            "rating_thresholds", self.DEFAULT_RATING_THRESHOLDS.copy()
        )

        logger.info(
            f"[SentimentLayer] 初始化完成，权重配置: "
            f"fund_flow={self.weights['fund_flow']}, "
            f"pcr={self.weights['pcr']}, "
            f"financing={self.weights['financing']}"
        )

    # ────────────────────────────── 子评分计算 ──────────────────────────────

    def calculate_fund_flow_score(self, northbound_5d: float, main_force_flow: float) -> float:
        """计算资金流评分

        根据北向资金和主力资金的流向及规模，计算0-100的资金流评分。

        评分规则:
        - 双流入且合计>100亿: 100分 (资金大幅流入)
        - 单一流入且>50亿: 70分 (资金温和流入)
        - 震荡区间±30亿: 40分 (资金平衡)
        - 双流出: 0分 (资金流出)

        Parameters
        ----------
        northbound_5d : float
            北向资金5日净流入(亿元)
        main_force_flow : float
            主力资金净流入(亿元)

        Returns
        -------
        float
            资金流评分 0-100
        """
        total_flow = northbound_5d + main_force_flow

        # 判断流入流出方向
        north_in = northbound_5d > 0
        main_in = main_force_flow > 0

        if north_in and main_in:
            # 双流入
            if total_flow > self.FUND_FLOW_THRESHOLDS["dual_inflow_strong"]:
                score = 100.0
            elif total_flow > self.FUND_FLOW_THRESHOLDS["single_inflow_strong"]:
                score = 85.0
            else:
                score = 70.0
        elif north_in or main_in:
            # 单一流入
            single_flow = max(northbound_5d, main_force_flow)
            if single_flow > self.FUND_FLOW_THRESHOLDS["single_inflow_strong"]:
                score = 70.0
            elif single_flow > self.FUND_FLOW_THRESHOLDS["oscillation"]:
                score = 55.0
            else:
                score = 40.0
        else:
            # 双流出或零流入
            if abs(total_flow) > self.FUND_FLOW_THRESHOLDS["dual_inflow_strong"]:
                score = 0.0
            elif abs(total_flow) > self.FUND_FLOW_THRESHOLDS["single_inflow_strong"]:
                score = 15.0
            elif abs(total_flow) > self.FUND_FLOW_THRESHOLDS["oscillation"]:
                score = 25.0
            else:
                score = 40.0

        logger.debug(
            f"[SentimentLayer] 资金流评分: {score} "
            f"(北向={northbound_5d:.2f}, 主力={main_force_flow:.2f}, 合计={total_flow:.2f})"
        )
        return score

    def calculate_pcr_score(self, pcr: float) -> float:
        """计算PCR(看跌看涨比)评分

        PCR>1表示恐慌(put多于call)，PCR<1表示贪婪。
        反向指标：PCR越高(越恐慌)，评分越高(未来反弹概率大)。

        评分规则:
        - PCR>1.3: 100分 (极端恐惧， contrarian买入信号)
        - 1.0-1.3: 80分 (恐惧区域)
        - 0.8-1.0: 50分 (中性区域)
        - <0.7: 0分 (极端贪婪， contrarian卖出信号)

        Parameters
        ----------
        pcr : float
            Put/Call Ratio

        Returns
        -------
        float
            PCR评分 0-100
        """
        if pcr > self.PCR_THRESHOLDS["extreme_fear"]:
            score = 100.0
        elif pcr > self.PCR_THRESHOLDS["fear"]:
            # 1.0-1.3 之间线性插值到80-100
            score = 80.0 + (pcr - 1.0) / 0.3 * 20.0
        elif pcr > self.PCR_THRESHOLDS["neutral_high"]:
            # 0.8-1.0 之间线性插值到50-80
            score = 50.0 + (pcr - 0.8) / 0.2 * 30.0
        elif pcr > self.PCR_THRESHOLDS["greed"]:
            # 0.7-0.8 之间线性插值到20-50
            score = 20.0 + (pcr - 0.7) / 0.1 * 30.0
        else:
            # <0.7 贪婪区域
            score = 0.0

        logger.debug(f"[SentimentLayer] PCR评分: {score:.1f} (PCR={pcr:.4f})")
        return round(score, 1)

    def calculate_financing_score(self, financing_5d_change: float) -> float:
        """计算融资余额变化评分

        融资余额增加表示杠杆资金看多，减少表示去杠杆。
        反向指标：融资大幅减少(恐慌去杠杆)反而 contrarian 看多。

        评分规则:
        - >+3%: 100分 (极端去杠杆， contrarian信号)
        - +1%~+3%: 70分 (温和去杠杆)
        - -1%~+1%: 40分 (中性)
        - <-2%: 0分 (大幅加杠杆，情绪过热)

        Parameters
        ----------
        financing_5d_change : float
            融资余额5日变化率(小数形式，如0.03表示+3%)

        Returns
        -------
        float
            融资评分 0-100
        """
        if financing_5d_change > self.FINANCING_THRESHOLDS["strong_inflow"]:
            # >+3%: 极端去杠杆(恐慌)， contrarian 看多
            score = 100.0
        elif financing_5d_change > self.FINANCING_THRESHOLDS["mild_inflow"]:
            # +1%~+3%: 温和去杠杆
            score = 70.0 + (financing_5d_change - 0.01) / 0.02 * 30.0
        elif financing_5d_change > self.FINANCING_THRESHOLDS["mild_outflow"]:
            # -1%~+1%: 中性区域
            score = 40.0 + (financing_5d_change + 0.01) / 0.02 * 30.0
        elif financing_5d_change > self.FINANCING_THRESHOLDS["strong_outflow"]:
            # -2%~-1%: 温和加杠杆
            score = 20.0 + (financing_5d_change + 0.02) / 0.01 * 20.0
        else:
            # <-2%: 大幅加杠杆(情绪过热)
            score = 0.0

        logger.debug(
            f"[SentimentLayer] 融资评分: {score:.1f} (变化率={financing_5d_change:.4f})"
        )
        return round(score, 1)

    # ────────────────────────────── 综合情绪计算 ──────────────────────────────

    def _get_rating(self, sentiment_score: float) -> str:
        """根据情绪综合分获取评级

        Parameters
        ----------
        sentiment_score : float
            情绪综合分 0-100

        Returns
        -------
        str
            评级 A/B/C/D
        """
        for rating, (low, high) in self.rating_thresholds.items():
            if low <= sentiment_score <= high:
                return rating
        # 超出范围时根据边界值返回
        if sentiment_score >= 80:
            return "A"
        elif sentiment_score >= 50:
            return "B"
        elif sentiment_score >= 20:
            return "C"
        else:
            return "D"

    def _generate_description(
        self,
        rating: str,
        pcr: float,
        northbound_5d: float,
        main_force_flow: float,
        financing_change: float,
        sentiment_score: float,
    ) -> str:
        """生成情绪状态描述文本

        Parameters
        ----------
        rating : str
            情绪评级
        pcr : float
            PCR值
        northbound_5d : float
            北向资金5日净流入
        main_force_flow : float
            主力资金净流入
        financing_change : float
            融资余额变化率
        sentiment_score : float
            情绪综合分

        Returns
        -------
        str
            描述文本
        """
        rating_desc = {
            "A": "情绪极佳，Contrarian指标显示恐慌已到极致，反弹概率高",
            "B": "情绪良好，资金面有支撑，适合顺势操作",
            "C": "情绪中性，市场震荡，建议观望或轻仓试探",
            "D": "情绪极差，资金持续流出，需严控风险",
        }

        desc_parts = [f"[{rating}级] {rating_desc.get(rating, '未知状态')}"]

        # PCR描述
        if pcr > 1.3:
            desc_parts.append(f"PCR={pcr:.2f}处于极端恐惧区")
        elif pcr > 1.0:
            desc_parts.append(f"PCR={pcr:.2f}显示市场恐慌")
        elif pcr < 0.7:
            desc_parts.append(f"PCR={pcr:.2f}显示市场贪婪")
        else:
            desc_parts.append(f"PCR={pcr:.2f}处于中性区")

        # 资金流向描述
        total_flow = northbound_5d + main_force_flow
        if total_flow > 100:
            desc_parts.append(f"资金大幅流入{total_flow:.0f}亿")
        elif total_flow > 30:
            desc_parts.append(f"资金温和流入{total_flow:.0f}亿")
        elif total_flow < -50:
            desc_parts.append(f"资金流出{abs(total_flow):.0f}亿")
        elif total_flow < -30:
            desc_parts.append(f"资金温和流出{abs(total_flow):.0f}亿")
        else:
            desc_parts.append("资金流向平衡")

        # 融资描述
        if financing_change > 0.03:
            desc_parts.append(f"融资余额大增+{financing_change*100:.1f}%(去杠杆)")
        elif financing_change < -0.02:
            desc_parts.append(f"融资余额大减{financing_change*100:.1f}%(加杠杆)")

        desc_parts.append(f"综合评分={sentiment_score:.1f}")
        return "; ".join(desc_parts)

    def calculate_sentiment(self, sentiment_data: Optional[Dict] = None) -> SentimentResult:
        """计算市场情绪综合评分

        综合PCR、融资变化、资金流向三项子评分，加权计算情绪综合分，
        并输出评级和描述。

        Parameters
        ----------
        sentiment_data : dict, optional
            预获取的情绪数据字典，包含pcr/financing_change/northbound_5d/main_force_flow。
            如果未提供，会尝试通过fetcher获取。

        Returns
        -------
        SentimentResult
            情绪验证结果模型
        """
        # 获取原始数据
        if sentiment_data is None:
            if self.fetcher is not None:
                try:
                    sentiment_data = self.fetcher.get_all_sentiment_data()
                except Exception as e:
                    logger.warning(f"[SentimentLayer] fetcher获取数据失败，使用全fallback: {e}")
                    sentiment_data = {}
            else:
                logger.info("[SentimentLayer] 未提供数据且未配置fetcher，使用全fallback默认值")
                sentiment_data = {}

        # 提取原始数据(带fallback)
        pcr = float(sentiment_data.get("pcr", 1.0))
        financing_change = float(sentiment_data.get("financing_change", 0.0))
        northbound_5d = float(sentiment_data.get("northbound_5d", 0.0))
        main_force_flow = float(sentiment_data.get("main_force_flow", 0.0))

        logger.info(
            f"[SentimentLayer] 开始计算情绪评分，原始数据: "
            f"PCR={pcr:.4f}, 融资变化={financing_change:.4f}, "
            f"北向={northbound_5d:.2f}亿, 主力={main_force_flow:.2f}亿"
        )

        # 计算各项子评分
        fund_flow_score = self.calculate_fund_flow_score(northbound_5d, main_force_flow)
        pcr_score = self.calculate_pcr_score(pcr)
        financing_score = self.calculate_financing_score(financing_change)

        # 加权计算综合分
        sentiment_score = (
            fund_flow_score * self.weights["fund_flow"]
            + pcr_score * self.weights["pcr"]
            + financing_score * self.weights["financing"]
        )
        sentiment_score = max(0.0, min(100.0, sentiment_score))

        # 评级
        rating = self._get_rating(sentiment_score)

        # 描述
        description = self._generate_description(
            rating, pcr, northbound_5d, main_force_flow, financing_change, sentiment_score
        )

        result = SentimentResult(
            pcr=pcr,
            financing_change=financing_change,
            northbound_5d=northbound_5d,
            main_force_flow=main_force_flow,
            fund_flow_score=round(fund_flow_score, 1),
            pcr_score=round(pcr_score, 1),
            financing_score=round(financing_score, 1),
            sentiment_score=round(sentiment_score, 1),
            rating=rating,
            description=description,
        )

        logger.info(
            f"[SentimentLayer] 情绪计算完成: 综合分={sentiment_score:.1f}, "
            f"评级={rating}, 资金流分={fund_flow_score:.1f}, "
            f"PCR分={pcr_score:.1f}, 融资分={financing_score:.1f}"
        )
        return result

    # ────────────────────────────── 缠论信号验证 ──────────────────────────────

    def validate_chan_signal(
        self, chan_signal: Dict, sentiment_result: SentimentResult
    ) -> ValidatedSignal:
        """验证缠论信号，融合情绪评级

        将缠论原始信号与情绪验证结果融合，输出最终置信度和执行模式。

        融合规则:
        1. final_confidence = base_score * sentiment_score / 100
        2. 日线底背驰 + PCR>1.2 → 置信度×1.1 (极端恐惧加分)
        3. 周线背驰 + 资金流出 → execution_mode='batch_3' (分批建仓)
        4. D级情绪 → 屏蔽信号 (execution_mode='skip')

        Parameters
        ----------
        chan_signal : dict
            缠论信号字典，需包含:
            - level: str - 信号级别 (daily/weekly/30min)
            - base_score: float - 基础置信度 0-100
            - signal_type: str, optional - 信号类型 (底背驰/顶背驰等)
            - is_divergence: bool, optional - 是否为背驰信号
        sentiment_result : SentimentResult
            情绪验证结果

        Returns
        -------
        ValidatedSignal
            验证后的信号
        """
        level = chan_signal.get("level", "daily")
        base_score = float(chan_signal.get("base_score", 0.0))
        signal_type = chan_signal.get("signal_type", "")
        is_divergence = chan_signal.get("is_divergence", False)

        sentiment_rating = sentiment_result.rating
        sentiment_score = sentiment_result.sentiment_score
        pcr = sentiment_result.pcr
        northbound_5d = sentiment_result.northbound_5d
        main_force_flow = sentiment_result.main_force_flow

        logger.info(
            f"[SentimentLayer] 验证缠论信号: level={level}, base_score={base_score}, "
            f"sentiment_rating={sentiment_rating}, sentiment_score={sentiment_score}"
        )

        # 规则4: D级情绪 → 直接屏蔽信号
        if sentiment_rating == "D":
            validated = ValidatedSignal(
                original_level=level,
                sentiment_rating=sentiment_rating,
                final_confidence=0.0,
                execution_mode="skip",
                bonus_applied=False,
                description=f"D级情绪({sentiment_score:.1f})屏蔽缠论信号，建议观望",
            )
            logger.info("[SentimentLayer] D级情绪 → 信号已屏蔽")
            return validated

        # 基础融合: final_confidence = base_score * sentiment_score / 100
        final_confidence = base_score * sentiment_score / 100.0
        bonus_applied = False
        execution_mode = "full"

        # 规则2: 日线底背驰 + PCR>1.2 → 置信度×1.1 (极端恐惧加分)
        if (
            level == "daily"
            and is_divergence
            and "底" in str(signal_type)
            and pcr > 1.2
        ):
            final_confidence *= 1.1
            bonus_applied = True
            logger.info(
                f"[SentimentLayer] 触发极端恐惧加分: 日线底背驰+PCR={pcr:.2f}>1.2, "
                f"置信度×1.1"
            )

        # 规则3: 周线背驰 + 资金流出 → batch_3
        total_flow = northbound_5d + main_force_flow
        if level == "weekly" and is_divergence and total_flow < 0:
            execution_mode = "batch_3"
            logger.info(
                f"[SentimentLayer] 周线背驰+资金流出{total_flow:.2f}亿 → batch_3"
            )

        # C级情绪也降低执行力度
        if sentiment_rating == "C":
            if execution_mode == "full":
                execution_mode = "batch_3"
            logger.info("[SentimentLayer] C级情绪 → 降低执行力度")

        # 封顶
        final_confidence = max(0.0, min(100.0, final_confidence))

        # 生成描述
        if bonus_applied:
            desc = (
                f"[{level}]底背驰+PCR>{pcr:.2f}触发极端恐惧加分，"
                f"情绪{sentiment_rating}级({sentiment_score:.1f}分)，"
                f"最终置信度={final_confidence:.1f}，执行={execution_mode}"
            )
        elif execution_mode == "skip":
            desc = f"情绪{sentiment_rating}级({sentiment_score:.1f}分) → 信号已屏蔽"
        elif execution_mode == "batch_3":
            desc = (
                f"[{level}]情绪{sentiment_rating}级({sentiment_score:.1f}分)，"
                f"最终置信度={final_confidence:.1f}，建议分批建仓(1/3)"
            )
        else:
            desc = (
                f"[{level}]情绪{sentiment_rating}级({sentiment_score:.1f}分)，"
                f"最终置信度={final_confidence:.1f}，满仓执行"
            )

        validated = ValidatedSignal(
            original_level=level,
            sentiment_rating=sentiment_rating,
            final_confidence=round(final_confidence, 1),
            execution_mode=execution_mode,
            bonus_applied=bonus_applied,
            description=desc,
        )

        logger.info(
            f"[SentimentLayer] 信号验证完成: final_confidence={final_confidence:.1f}, "
            f"mode={execution_mode}, bonus={bonus_applied}"
        )
        return validated
