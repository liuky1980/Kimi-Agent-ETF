"""
丁昶五维评分引擎
=================
丁昶投资框架的核心引擎，整合五个维度的评分：
1. 股息质量 (30%) - 分红质量或资本回报效率
2. 估值安全 (25%) - PE/PB历史百分位、PEG
3. 盈利质地 (20%) - ROE、收益稳定性、增长趋势
4. 资金驱动 (15%) - AUM趋势、成交量、资金流向
5. 宏观适配 (10%) - 周期定位、利率环境、政策支持

综合评分范围 0~100，分为四个评级：
- 买入 (>=80分)
- 持有 (60-79分)
- 观察 (40-59分)
- 回避 (<40分)
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional

import pandas as pd

from app.config import settings
from app.dingchang.capital_flow import CapitalFlow
from app.dingchang.dividend import DividendQuality
from app.dingchang.macro import MacroAdaptation
from app.dingchang.profitability import ProfitabilityQuality
from app.dingchang.valuation import ValuationSafety
from app.models.dingchang import (
    CapitalFlowScore,
    DingChangDimensions,
    DingChangResult,
    DividendScore,
    MacroScore,
    ProfitabilityScore,
    ValuationScore,
)

logger = logging.getLogger(__name__)


class DingChangEngine:
    """丁昶五维评分引擎

    对ETF从五个维度进行全面评估，生成综合评分和投资建议。
    """

    def __init__(self):
        self.dividend = DividendQuality()
        self.valuation = ValuationSafety()
        self.profitability = ProfitabilityQuality()
        self.capital_flow = CapitalFlow()
        self.macro = MacroAdaptation()

        # 阈值配置
        self.threshold_buy = settings.DINGCHANG_COMPOSITE_THRESHOLD_BUY
        self.threshold_hold = settings.DINGCHANG_COMPOSITE_THRESHOLD_HOLD
        self.threshold_watch = settings.DINGCHANG_COMPOSITE_THRESHOLD_WATCH

        # 权重配置
        self.weights = {
            'dividend': settings.WEIGHT_DIVIDEND,
            'valuation': settings.WEIGHT_VALUATION,
            'profitability': settings.WEIGHT_PROFITABILITY,
            'capital_flow': settings.WEIGHT_CAPITAL_FLOW,
            'macro': settings.WEIGHT_MACRO,
        }

    def analyze(
        self,
        etf_code: str,
        df_daily: pd.DataFrame,
        etf_name: str = ""
    ) -> DingChangResult:
        """执行完整的五维评分分析

        Parameters
        ----------
        etf_code : str
            ETF代码
        df_daily : pd.DataFrame
            日线数据
        etf_name : str
            ETF名称（可选）

        Returns
        -------
        DingChangResult
            完整的五维评分结果
        """
        logger.info(f"开始对 {etf_code} 执行丁昶五维评分")

        # 执行五个维度的独立评分
        dividend_score = self.dividend.score(etf_code, df_daily)
        valuation_score = self.valuation.score(etf_code, df_daily)
        profitability_score = self.profitability.score(etf_code, df_daily)
        capital_flow_score = self.capital_flow.score(etf_code, df_daily)
        macro_score = self.macro.score(etf_code, df_daily)

        # 构建维度结果
        dimensions = DingChangDimensions(
            dividend=dividend_score,
            valuation=valuation_score,
            profitability=profitability_score,
            capital_flow=capital_flow_score,
            macro=macro_score
        )

        # 计算综合评分
        composite = self._calculate_composite({
            'dividend': dividend_score.score,
            'valuation': valuation_score.score,
            'profitability': profitability_score.score,
            'capital_flow': capital_flow_score.score,
            'macro': macro_score.score,
        })

        # 确定评级
        rating = self._determine_rating(composite)

        # 生成综合信号
        signal, signal_strength, signal_factors = self._generate_signal(
            dimensions, composite
        )

        # 识别风险因素
        risks = self._identify_risks(dimensions, composite)

        # 识别机会因素
        opportunities = self._identify_opportunities(dimensions, composite)

        # 生成建议
        recommendation = self._generate_recommendation(rating, dimensions, composite)

        # 生成摘要
        summary = self._generate_summary(
            etf_code, composite, rating, dimensions, signal
        )

        result = DingChangResult(
            etf_code=etf_code,
            etf_name=etf_name,
            analysis_time=datetime.now(),
            composite_score=round(composite, 1),
            rating=rating,
            dimensions=dimensions,
            weights=self.weights.copy(),
            composite_signal=signal,
            signal_strength=round(signal_strength, 3),
            signal_factors=signal_factors,
            risks=risks,
            opportunities=opportunities,
            recommendation=recommendation,
            summary=summary,
            benchmark_comparison=None
        )

        logger.info(
            f"丁昶五维评分完成: {etf_code} - 综合 {composite:.1f}分, "
            f"评级 {rating}, 信号 {signal}"
        )
        return result

    def _calculate_composite(self, scores: Dict[str, float]) -> float:
        """计算加权综合评分

        Parameters
        ----------
        scores : dict
            各维度得分

        Returns
        -------
        float
            综合评分 0~100
        """
        composite = sum(
            scores.get(dim, 0) * weight
            for dim, weight in self.weights.items()
        )
        return min(100, max(0, composite))

    def _determine_rating(self, composite: float) -> str:
        """确定投资评级

        Parameters
        ----------
        composite : float
            综合评分

        Returns
        -------
        str
            买入 / 持有 / 观察 / 回避
        """
        if composite >= self.threshold_buy:
            return "买入"
        elif composite >= self.threshold_hold:
            return "持有"
        elif composite >= self.threshold_watch:
            return "观察"
        else:
            return "回避"

    def _generate_signal(
        self,
        dimensions: DingChangDimensions,
        composite: float
    ) -> tuple:
        """生成综合信号

        Returns
        -------
        tuple
            (信号方向, 信号强度, 信号因子)
        """
        scores = {
            'dividend': dimensions.dividend.score,
            'valuation': dimensions.valuation.score,
            'profitability': dimensions.profitability.score,
            'capital_flow': dimensions.capital_flow.score,
            'macro': dimensions.macro.score,
        }

        # 判断信号方向
        bullish_count = sum(1 for s in scores.values() if s >= 60)
        bearish_count = sum(1 for s in scores.values() if s < 40)

        if composite >= 70 and bullish_count >= 3:
            signal = "bullish"
        elif composite <= 45 or bearish_count >= 3:
            signal = "bearish"
        else:
            signal = "neutral"

        # 信号强度
        if composite >= 80:
            strength = 0.9
        elif composite >= 65:
            strength = 0.7
        elif composite >= 50:
            strength = 0.5
        else:
            strength = 0.3

        # 信号因子说明
        factors = {}
        for dim, score in scores.items():
            if score >= 70:
                factors[dim] = "强势"
            elif score >= 50:
                factors[dim] = "中性"
            else:
                factors[dim] = "弱势"

        return signal, strength, factors

    def _identify_risks(
        self,
        dimensions: DingChangDimensions,
        composite: float
    ) -> List[str]:
        """识别风险因素"""
        risks = []

        if dimensions.valuation.score < 40:
            risks.append("估值偏高，安全边际不足")
        if dimensions.profitability.score < 40:
            risks.append("盈利质地较弱，收益稳定性差")
        if dimensions.capital_flow.score < 40:
            risks.append("资金流出明显，市场关注度下降")
        if dimensions.macro.score < 40:
            risks.append("宏观环境不利，可能面临系统性风险")
        if dimensions.dividend.score < 30:
            risks.append("分红回报低，资本效率不足")
        if composite < 50:
            risks.append("综合评分偏低，整体风险大于机会")

        return risks if risks else ["未发现显著风险因素"]

    def _identify_opportunities(
        self,
        dimensions: DingChangDimensions,
        composite: float
    ) -> List[str]:
        """识别机会因素"""
        opportunities = []

        if dimensions.valuation.score >= 70:
            opportunities.append("估值处于历史低位，安全边际较高")
        if dimensions.profitability.score >= 70:
            opportunities.append("盈利质地优秀，长期价值突出")
        if dimensions.capital_flow.score >= 70:
            opportunities.append("资金持续流入，市场认可度高")
        if dimensions.macro.score >= 70:
            opportunities.append("宏观环境友好，政策支持力度大")
        if dimensions.dividend.score >= 70:
            opportunities.append("分红回报丰厚，现金流稳定")
        if composite >= 75:
            opportunities.append("综合评分优秀，投资价值显著")

        return opportunities if opportunities else ["未发现突出机会因素"]

    def _generate_recommendation(
        self,
        rating: str,
        dimensions: DingChangDimensions,
        composite: float
    ) -> str:
        """生成投资建议"""
        parts = [f"丁昶框架综合评级：{rating} ({composite:.1f}分)"]

        # 找出最强和最弱维度
        scores = {
            '股息质量': dimensions.dividend.score,
            '估值安全': dimensions.valuation.score,
            '盈利质地': dimensions.profitability.score,
            '资金驱动': dimensions.capital_flow.score,
            '宏观适配': dimensions.macro.score,
        }

        best_dim = max(scores, key=scores.get)
        worst_dim = min(scores, key=scores.get)

        parts.append(f"优势维度：{best_dim} ({scores[best_dim]:.1f}分)")
        parts.append(f"劣势维度：{worst_dim} ({scores[worst_dim]:.1f}分)")

        if rating == "买入":
            parts.append("五维评分支持积极配置，建议在回调时分批建仓")
        elif rating == "持有":
            parts.append("整体质地尚可，建议继续持有观察")
        elif rating == "观察":
            parts.append("存在不确定因素，建议观望等待更明确信号")
        else:
            parts.append("多项指标偏弱，建议回避或减仓")

        return "；".join(parts)

    def _generate_summary(
        self,
        etf_code: str,
        composite: float,
        rating: str,
        dimensions: DingChangDimensions,
        signal: str
    ) -> str:
        """生成分析摘要"""
        signal_map = {
            "bullish": "看多",
            "bearish": "看空",
            "neutral": "中性"
        }

        return (
            f"ETF {etf_code} 丁昶五维评分 {composite:.1f}分，"
            f"评级 {rating}，信号 {signal_map.get(signal, signal)} | "
            f"股息 {dimensions.dividend.score:.0f} / "
            f"估值 {dimensions.valuation.score:.0f} / "
            f"盈利 {dimensions.profitability.score:.0f} / "
            f"资金 {dimensions.capital_flow.score:.0f} / "
            f"宏观 {dimensions.macro.score:.0f}"
        )
