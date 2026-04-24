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

    def score(self, etf_code: str, df_daily: pd.DataFrame, real_data: Optional[Dict] = None) -> DividendScore:
        """股息质量评分主函数

        Parameters
        ----------
        etf_code : str
            ETF代码
        df_daily : pd.DataFrame
            日线数据
        real_data : dict, optional
            真实基本面数据（从tushare获取）

        Returns
        -------
        DividendScore
            股息质量评分结果
        """
        logger.info(f"开始对 {etf_code} 进行股息质量评分")

        # 判断ETF类型（从名称或历史特征）
        etf_type = self._classify_etf_type(etf_code, df_daily)

        if etf_type == "income":
            return self._score_income_etf(etf_code, df_daily, real_data)
        elif etf_type == "commodity":
            return self._score_commodity_etf(etf_code, df_daily)
        else:
            # 成长型或其他类型：用资本回报效率替代
            return self._score_growth_etf(etf_code, df_daily, real_data)

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

    def _score_income_etf(self, etf_code: str, df_daily: pd.DataFrame, real_data: Optional[Dict] = None) -> DividendScore:
        """收益型ETF评分（有分红）— 丁昶报告阈值版"""
        close_prices = df_daily['close']

        # 优先使用真实股息率数据
        real_dividend_yield = 0.0
        real_yield_source = "价格估算"
        if real_data and real_data.get("dividend_yield", 0) > 0:
            real_dividend_yield = real_data["dividend_yield"]
            real_yield_source = real_data.get("yield_source", "真实数据")
            logger.info(f"[DividendQuality] 使用真实股息率 {real_dividend_yield:.2f}% (来源: {real_yield_source})")

        # 股息率水平 (10分) — 丁昶报告阈值
        dividend_yield = real_dividend_yield
        if dividend_yield > 7:
            yield_score = 10
        elif dividend_yield > 5:
            yield_score = 8
        elif dividend_yield > 4:
            yield_score = 6
        elif dividend_yield > 3:
            yield_score = 3
        else:
            yield_score = 0

        # 股息增长率 (8分)
        div_growth = 0.0
        growth_source = "估算"
        if real_data and real_data.get("dividend_growth_3y", 0) != 0:
            div_growth = real_data["dividend_growth_3y"]
            growth_source = "真实数据"
        else:
            # 回退：基于价格趋势估算
            years = len(df_daily) / 252
            if years > 1 and close_prices.iloc[0] > 0:
                cagr = (close_prices.iloc[-1] / close_prices.iloc[0]) ** (1 / years) - 1
                div_growth = max(0, cagr * 100 * 0.5)  # 假设一半回报来自分红增长

        if div_growth > 10:
            growth_score = 8
        elif div_growth > 5:
            growth_score = 6
        elif div_growth > 0:
            growth_score = 3
        else:
            growth_score = 0

        # 股息支付率稳定性 (7分)
        payout_stability = 0.0
        if real_data and real_data.get("payout_ratio_stability", 0) > 0:
            payout_stability = real_data["payout_ratio_stability"]
            # 已经是0-1的稳定性评分，直接映射
            payout_score = round(payout_stability * 7)
        else:
            # 回退：基于收益稳定性估算
            returns = close_prices.pct_change().dropna()
            if len(returns) >= 60:
                cv = returns.std() / (abs(returns.mean()) + 1e-6)
                payout_stability = max(0, min(1, 1.0 / (1 + cv * 5)))
                payout_score = round(payout_stability * 7)
            else:
                payout_score = 3  # 中性

        # 股息持续性 (5分)
        continuity = 0
        if real_data and real_data.get("dividend_continuity_years", 0) > 0:
            continuity = real_data["dividend_continuity_years"]
        if continuity > 10:
            cont_score = 5
        elif continuity >= 5:
            cont_score = 3
        elif continuity > 0:
            cont_score = 1
        else:
            # 回退：基于历史数据长度估算
            years = len(df_daily) / 252
            if years > 5:
                cont_score = 3
            elif years > 2:
                cont_score = 1
            else:
                cont_score = 0

        # 综合子得分
        sub_scores = {
            "dividend_yield_level": yield_score * 10,   # 扩展到100分制
            "dividend_growth": growth_score * 12.5,
            "payout_stability": payout_score * 14.28,
            "dividend_continuity": cont_score * 20,
        }

        # 综合评分（丁昶报告权重：股息率 33.3% + 增长率 26.7% + 支付率稳定性 23.3% + 持续性 16.7%）
        composite = (
            yield_score * 10 * 0.333 +
            growth_score * 12.5 * 0.267 +
            payout_score * 14.28 * 0.233 +
            cont_score * 20 * 0.167
        )

        desc = (f"收益型ETF评估，股息率 {dividend_yield:.2f}%(得分{yield_score}/10), "
                f"增长率 {div_growth:.1f}%(得分{growth_score}/8,来源:{growth_source}), "
                f"支付率稳定性 {payout_stability:.2f}(得分{payout_score}/7), "
                f"连续分红{continuity}年(得分{cont_score}/5)")
        if real_dividend_yield > 0:
            desc += f" | 股息率来源: {real_yield_source}"

        return DividendScore(
            score=round(min(100, max(0, composite)), 1),
            dividend_yield=round(dividend_yield, 2),
            yield_5y_avg=round(dividend_yield, 2),
            payout_consistency=round(payout_stability, 3),
            distribution_quality=round(yield_score / 10, 3),
            capital_return_efficiency=0.0,
            dividend_growth_3y=round(div_growth, 2),
            payout_ratio_stability=round(payout_stability, 3),
            dividend_continuity_years=continuity,
            sub_scores=sub_scores,
            description=desc
        )

    def _score_growth_etf(self, etf_code: str, df_daily: pd.DataFrame, real_data: Optional[Dict] = None) -> DividendScore:
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

        # 如果有真实股息率数据（成长型ETF可能也有），记录一下
        real_dividend_yield = 0.0
        if real_data and real_data.get("dividend_yield", 0) > 0:
            real_dividend_yield = real_data["dividend_yield"]

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

        desc = f"成长型ETF评估，年化收益率 {cagr:.1f}%，夏普比率近似 {sharpe_approx:.2f}"
        if real_dividend_yield > 0:
            desc += f"，真实股息率 {real_dividend_yield:.2f}%"

        return DividendScore(
            score=round(min(100, max(0, composite)), 1),
            dividend_yield=round(real_dividend_yield, 2),
            yield_5y_avg=0.0,
            payout_consistency=0.0,
            distribution_quality=0.0,
            capital_return_efficiency=round(capital_return_efficiency, 3),
            sub_scores=sub_scores,
            description=desc
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
