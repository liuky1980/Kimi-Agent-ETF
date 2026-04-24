"""
盈利质地评分模块 (权重20%)
===========================
丁昶五维评分体系 — 维度三：盈利质地

评分逻辑（通用化，适用于全部ETF类型）：
- 基于ETF价格走势推断底层资产的盈利质量
- 评估收益稳定性、增长趋势、风险调整后收益
- 对不同ETF类型采用适配的评估方式
"""

import logging
from typing import Dict, Optional

import numpy as np
import pandas as pd

from app.models.dingchang import ProfitabilityScore

logger = logging.getLogger(__name__)


class ProfitabilityQuality:
    """盈利质地评分器

    基于ETF历史收益特征评估底层资产的盈利质量，
    适用于所有ETF类型（宽基、行业、商品、跨境等）。
    """

    def __init__(self):
        pass

    def score(self, etf_code: str, df_daily: pd.DataFrame, real_data: Optional[Dict] = None) -> ProfitabilityScore:
        """盈利质地评分主函数

        Parameters
        ----------
        etf_code : str
            ETF代码
        df_daily : pd.DataFrame
            日线数据
        real_data : dict, optional
            真实盈利数据（从tushare获取）

        Returns
        -------
        ProfitabilityScore
            盈利质地评分结果
        """
        logger.info(f"开始对 {etf_code} 进行盈利质地评分")

        close_prices = df_daily['close']
        returns = close_prices.pct_change().dropna()

        if len(returns) < 60:
            return self._insufficient_data_score()

        # 优先使用真实ROE数据
        real_roe = 0.0
        roe_source = "价格估算"
        if real_data and real_data.get("roe", 0) > 0:
            real_roe = real_data["roe"]
            roe_source = real_data.get("data_source", "真实数据")
            logger.info(f"[ProfitabilityQuality] 使用真实ROE {real_roe:.2f}% (来源: {roe_source})")

        # 1. ROE（优先真实数据，否则估算）
        if real_roe > 0:
            roe = real_roe
        else:
            roe = self._estimate_roe(close_prices, returns)

        # 2. ROIC近似
        roic_approx = roe * 0.8  # 简化：ROIC通常略低于ROE

        # 3. 盈利稳定性
        earnings_stability = self._calc_earnings_stability(returns)

        # 4. 收益增长趋势
        earnings_growth_3y = self._calc_growth_trend(close_prices)

        # 5. 营收增长趋势
        revenue_growth_3y = earnings_growth_3y * 0.9  # 简化

        # 6. 现金流质量
        cash_flow_quality = self._calc_cash_flow_quality(returns)

        # 子得分
        sub_scores = {
            "roe_score": min(100, max(0, roe * 4)),  # ROE 25% → 100分
            "roic_score": min(100, max(0, roic_approx * 4)),
            "earnings_stability": earnings_stability * 100,
            "earnings_growth": min(100, max(0, 50 + earnings_growth_3y * 5)),
            "revenue_growth": min(100, max(0, 50 + revenue_growth_3y * 5)),
            "cash_flow_quality": cash_flow_quality * 100,
        }

        # 综合评分
        composite = (
            sub_scores["roe_score"] * 0.25 +
            sub_scores["roic_score"] * 0.15 +
            sub_scores["earnings_stability"] * 0.25 +
            sub_scores["earnings_growth"] * 0.15 +
            sub_scores["revenue_growth"] * 0.10 +
            sub_scores["cash_flow_quality"] * 0.10
        )

        desc = (f"盈利质地: {('真实' if real_roe > 0 else '估算')}ROE {roe:.1f}%, 盈利稳定性 {earnings_stability:.2f}, "
                f"3年增长趋势 {earnings_growth_3y:.1f}%")
        if real_roe > 0:
            desc += f" (来源: {roe_source})"

        return ProfitabilityScore(
            score=round(min(100, max(0, composite)), 1),
            roe=round(roe, 2),
            roic=round(roic_approx, 2),
            earnings_stability=round(earnings_stability, 3),
            earnings_growth_3y=round(earnings_growth_3y, 2),
            revenue_growth_3y=round(revenue_growth_3y, 2),
            cash_flow_quality=round(cash_flow_quality, 3),
            sub_scores=sub_scores,
            description=desc
        )

    def _estimate_roe(self, close_prices: pd.Series, returns: pd.Series) -> float:
        """估算ROE

        使用年化收益率作为ROE的代理指标。
        """
        years = len(close_prices) / 252
        if years < 0.5 or close_prices.iloc[0] <= 0:
            return 10.0  # 默认值

        cagr = (close_prices.iloc[-1] / close_prices.iloc[0]) ** (1 / years) - 1

        # ROE ≈ CAGR + 分红率（简化假设分红率2%）
        roe_proxy = cagr * 100 + 2.0
        return max(-5.0, min(40.0, roe_proxy))

    def _calc_earnings_stability(self, returns: pd.Series) -> float:
        """计算盈利稳定性

        使用变异系数的倒数来度量稳定性。
        返回值 0~1，越高越稳定。
        """
        if len(returns) < 20:
            return 0.5

        mean_return = abs(returns.mean())
        std_return = returns.std()

        if std_return <= 0:
            return 1.0

        cv = std_return / (mean_return + 1e-6)

        # CV越小越稳定，映射到0~1
        stability = max(0, min(1, 1.0 / (1 + cv * 10)))
        return round(stability, 3)

    def _calc_growth_trend(self, close_prices: pd.Series) -> float:
        """计算增长趋势

        使用线性回归斜率估算年化增长率。
        """
        if len(close_prices) < 60:
            return 0.0

        # 使用对数价格的线性回归
        log_prices = np.log(close_prices.replace(0, np.nan).dropna())
        if len(log_prices) < 60:
            return 0.0

        x = np.arange(len(log_prices))
        slope, intercept = np.polyfit(x, log_prices, 1)

        # 转换为年化增长率
        daily_growth = slope
        annual_growth = daily_growth * 252 * 100  # 百分比

        # 对极端值截断
        return max(-30.0, min(50.0, annual_growth))

    def _calc_cash_flow_quality(self, returns: pd.Series) -> float:
        """计算现金流质量

        基于正收益持续性评估现金流质量。
        """
        if len(returns) < 20:
            return 0.5

        # 月度正收益比例
        monthly_returns = returns.resample('ME').apply(lambda x: (1 + x).prod() - 1) if hasattr(returns.index, 'freq') or hasattr(returns.index, 'inferred_freq') else returns.rolling(20).apply(lambda x: (1 + x).prod() - 1).dropna()

        if len(monthly_returns) < 6:
            # 使用20日滚动收益
            rolling_returns = returns.rolling(20).apply(lambda x: (1 + x).prod() - 1).dropna()
            positive_ratio = (rolling_returns > 0).sum() / len(rolling_returns) if len(rolling_returns) > 0 else 0.5
        else:
            positive_ratio = (monthly_returns > 0).sum() / len(monthly_returns)

        # 正收益比例越高，现金流质量越好
        quality = 0.3 + positive_ratio * 0.7
        return round(min(1.0, max(0.0, quality)), 3)

    def _insufficient_data_score(self) -> ProfitabilityScore:
        """数据不足时的默认评分"""
        return ProfitabilityScore(
            score=50.0,
            roe=0.0,
            roic=0.0,
            earnings_stability=0.5,
            earnings_growth_3y=0.0,
            revenue_growth_3y=0.0,
            cash_flow_quality=0.5,
            sub_scores={},
            description="历史数据不足，采用中性评分50分"
        )
