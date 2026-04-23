"""
股息质量评分模块 (权重30%)
==========================
丁昶五维评分体系 — 维度一：股息质量

评分逻辑（适用于通用ETF，非仅限于银行股）：
- 有分红的ETF：评估股息率高低、分红持续性、分红增长率
- 无分红/低分红ETF（科技、成长型）：评估资本回报效率替代指标
- 综合评分时根据ETF类型自动切换评估方式
"""

import logging
from typing import Dict, Optional

import numpy as np
import pandas as pd

from app.models.dingchang import DividendScore

logger = logging.getLogger(__name__)


class DividendQuality:
    """股息质量评分器

    评估ETF的股息分红质量或资本回报效率，
    适用于所有类型ETF（分红型、成长型、商品型等）。
    """

    # ETF类型分类与评估策略
    INCOME_TYPES = ["红利", "股息", "高股息", "分红", "债券", "货币"]  # 收益型
    GROWTH_TYPES = ["科技", "创新", "成长", "创业板", "科创板", "新能源"]  # 成长型
    COMMODITY_TYPES = ["商品", "黄金", "白银", "原油", "有色", "豆粕"]  # 商品型

    def __init__(self):
        pass

    def score(self, etf_code: str, df_daily: pd.DataFrame) -> DividendScore:
        """股息质量评分主函数

        Parameters
        ----------
        etf_code : str
            ETF代码
        df_daily : pd.DataFrame
            日线数据

        Returns
        -------
        DividendScore
            股息质量评分结果
        """
        logger.info(f"开始对 {etf_code} 进行股息质量评分")

        # 判断ETF类型（从名称或历史特征）
        etf_type = self._classify_etf_type(etf_code, df_daily)

        if etf_type == "income":
            return self._score_income_etf(etf_code, df_daily)
        elif etf_type == "commodity":
            return self._score_commodity_etf(etf_code, df_daily)
        else:
            # 成长型或其他类型：用资本回报效率替代
            return self._score_growth_etf(etf_code, df_daily)

    def _classify_etf_type(self, etf_code: str, df_daily: pd.DataFrame) -> str:
        """基于ETF名称和历史数据分类ETF类型

        Returns
        -------
        str
            'income' | 'growth' | 'commodity'
        """
        # 尝试从常见ETF代码判断
        code_prefix = etf_code[:3]

        # 根据历史价格特征判断
        returns = df_daily['close'].pct_change().dropna()
        annual_volatility = returns.std() * np.sqrt(252)

        # 高波动 + 高成长特征 → 成长型
        if annual_volatility > 0.30:
            return "growth"

        # 低波动 + 稳定 → 收益型
        if annual_volatility < 0.20:
            # 进一步检查是否有分红特征
            avg_return = returns.mean() * 252
            if avg_return > 0.02:  # 正收益倾向
                return "income"

        # 默认按成长型评估（更通用的方式）
        return "growth"

    def _score_income_etf(self, etf_code: str, df_daily: pd.DataFrame) -> DividendScore:
        """收益型ETF评分（有分红）"""
        close_prices = df_daily['close']

        # 计算总回报
        total_return = (close_prices.iloc[-1] / close_prices.iloc[0] - 1) if close_prices.iloc[0] > 0 else 0

        # 年化收益率（模拟股息率估算）
        years = len(df_daily) / 252
        if years > 0 and close_prices.iloc[0] > 0:
            cagr = (close_prices.iloc[-1] / close_prices.iloc[0]) ** (1 / years) - 1
        else:
            cagr = 0

        # 估算股息率（简化：假设价格增长主要来自分红再投资）
        estimated_yield = max(0, cagr * 0.4) * 100  # 假设40%回报来自分红

        # 5年平均（简化用全部历史替代）
        yield_5y = estimated_yield

        # 分红持续性评分（基于收益稳定性）
        monthly_returns = close_prices.pct_change(periods=20).dropna()
        positive_months = (monthly_returns > 0).sum() / len(monthly_returns) if len(monthly_returns) > 0 else 0.5
        payout_consistency = positive_months

        # 分红质量评分
        distribution_quality = min(1.0, estimated_yield / 5.0) if estimated_yield > 0 else 0.0

        # 资本回报效率
        capital_return_efficiency = min(1.0, max(0, cagr * 100) / 10.0)

        # 综合评分
        sub_scores = {
            "dividend_yield": min(100, estimated_yield * 10),
            "yield_5y_avg": min(100, yield_5y * 8),
            "payout_consistency": payout_consistency * 100,
            "distribution_quality": distribution_quality * 100,
            "capital_return": capital_return_efficiency * 100,
        }

        composite = (
            sub_scores["dividend_yield"] * 0.25 +
            sub_scores["yield_5y_avg"] * 0.20 +
            sub_scores["payout_consistency"] * 0.25 +
            sub_scores["distribution_quality"] * 0.15 +
            sub_scores["capital_return"] * 0.15
        )

        return DividendScore(
            score=round(min(100, max(0, composite)), 1),
            dividend_yield=round(estimated_yield, 2),
            yield_5y_avg=round(yield_5y, 2),
            payout_consistency=round(payout_consistency, 3),
            distribution_quality=round(distribution_quality, 3),
            capital_return_efficiency=round(capital_return_efficiency, 3),
            sub_scores=sub_scores,
            description=f"收益型ETF评估，估算股息率 {estimated_yield:.2f}%，分红持续性 {payout_consistency:.2f}"
        )

    def _score_growth_etf(self, etf_code: str, df_daily: pd.DataFrame) -> DividendScore:
        """成长型ETF评分（资本回报效率替代）"""
        close_prices = df_daily['close']

        # 计算多期收益率
        returns = close_prices.pct_change().dropna()
        total_return = (close_prices.iloc[-1] / close_prices.iloc[0] - 1) * 100 if close_prices.iloc[0] > 0 else 0

        # 年化收益率
        years = len(df_daily) / 252
        cagr = ((close_prices.iloc[-1] / close_prices.iloc[0]) ** (1 / max(years, 0.1)) - 1) * 100 if close_prices.iloc[0] > 0 else 0

        # 夏普比率近似（假设无风险利率3%）
        excess_return = returns.mean() * 252 - 0.03
        volatility = returns.std() * np.sqrt(252)
        sharpe_approx = excess_return / volatility if volatility > 0 else 0

        # 最大回撤恢复能力
        cummax = close_prices.cummax()
        drawdown = (close_prices - cummax) / cummax
        max_drawdown = drawdown.min()

        # 恢复时间评分
        recovery_score = 0.5
        if max_drawdown < -0.30:
            recovery_score = 0.3
        elif max_drawdown > -0.10:
            recovery_score = 0.9
        else:
            recovery_score = 0.5 + (-max_drawdown - 0.10) / 0.20 * 0.4

        # 资本回报效率
        capital_return_efficiency = min(1.0, max(0, sharpe_approx + 1) / 2.0)

        # 综合子得分
        sub_scores = {
            "total_return": min(100, max(0, total_return)),
            "cagr": min(100, max(0, cagr * 5)),
            "sharpe_approx": min(100, max(0, (sharpe_approx + 1) * 50)),
            "recovery_score": recovery_score * 100,
            "capital_return_efficiency": capital_return_efficiency * 100,
        }

        composite = (
            sub_scores["total_return"] * 0.20 +
            sub_scores["cagr"] * 0.25 +
            sub_scores["sharpe_approx"] * 0.25 +
            sub_scores["recovery_score"] * 0.15 +
            sub_scores["capital_return_efficiency"] * 0.15
        )

        return DividendScore(
            score=round(min(100, max(0, composite)), 1),
            dividend_yield=0.0,  # 成长型无分红
            yield_5y_avg=0.0,
            payout_consistency=0.0,
            distribution_quality=0.0,
            capital_return_efficiency=round(capital_return_efficiency, 3),
            sub_scores=sub_scores,
            description=f"成长型ETF评估，年化收益率 {cagr:.1f}%，夏普比率近似 {sharpe_approx:.2f}，"
                       f"最大回撤 {max_drawdown*100:.1f}%，资本回报效率 {capital_return_efficiency:.2f}"
        )

    def _score_commodity_etf(self, etf_code: str, df_daily: pd.DataFrame) -> DividendScore:
        """商品型ETF评分"""
        close_prices = df_daily['close']
        returns = close_prices.pct_change().dropna()

        # 商品ETF主要看持有成本和跟踪效率
        volatility = returns.std() * np.sqrt(252)
        total_return = (close_prices.iloc[-1] / close_prices.iloc[0] - 1) * 100 if close_prices.iloc[0] > 0 else 0

        # 波动率控制评分（商品波动通常较大）
        volatility_score = max(0, 1.0 - volatility) * 100 if volatility > 0 else 50

        # 趋势收益评分
        trend_score = min(100, max(0, total_return))

        # 综合
        capital_return_efficiency = min(1.0, max(0, total_return / 20.0))

        sub_scores = {
            "total_return": trend_score,
            "volatility_control": volatility_score,
            "capital_return_efficiency": capital_return_efficiency * 100,
        }

        composite = trend_score * 0.4 + volatility_score * 0.35 + capital_return_efficiency * 100 * 0.25

        return DividendScore(
            score=round(min(100, max(0, composite)), 1),
            dividend_yield=0.0,
            yield_5y_avg=0.0,
            payout_consistency=0.0,
            distribution_quality=0.0,
            capital_return_efficiency=round(capital_return_efficiency, 3),
            sub_scores=sub_scores,
            description=f"商品型ETF评估，总收益 {total_return:.1f}%，波动率 {volatility*100:.1f}%"
        )
