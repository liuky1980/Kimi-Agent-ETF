"""
估值安全评分模块 (权重25%)
===========================
丁昶五维评分体系 — 维度二：估值安全

评分逻辑（通用化，适用于全部ETF类型）：
- 宽基指数ETF：PE/PB历史百分位
- 行业主题ETF：相对估值 + 历史百分位
- 商品ETF：净值折溢价率
- Smart Beta ETF：多因子估值综合

核心原则：估值越低、安全边际越高，评分越高。
"""

import logging
from typing import Dict, Optional

import numpy as np
import pandas as pd

from app.models.dingchang import ValuationScore

logger = logging.getLogger(__name__)


class ValuationSafety:
    """估值安全评分器

    基于ETF历史价格数据和多维度估值指标评估估值安全性，
    适用于全部ETF类型（宽基、行业、商品、跨境等）。
    """

    def __init__(self):
        pass

    def score(self, etf_code: str, df_daily: pd.DataFrame, real_data: Optional[Dict] = None) -> ValuationScore:
        """估值安全评分主函数

        Parameters
        ----------
        etf_code : str
            ETF代码
        df_daily : pd.DataFrame
            日线数据（需包含 close, high, low, volume 等列）
        real_data : dict, optional
            真实估值数据（从tushare获取）

        Returns
        -------
        ValuationScore
            估值安全评分结果
        """
        logger.info(f"开始对 {etf_code} 进行估值安全评分")

        close_prices = df_daily['close']

        if len(close_prices) < 60:
            return self._insufficient_data_score()

        # 优先使用真实估值数据
        use_real = real_data and (real_data.get("pe_ttm", 0) > 0 or real_data.get("pb", 0) > 0)

        if use_real:
            logger.info(f"[ValuationSafety] 使用真实估值数据: PE={real_data.get('pe_ttm')}, PB={real_data.get('pb')}")
            return self._score_with_real_data(etf_code, df_daily, real_data)

        # 回退到价格估算模式
        return self._score_with_estimated_data(etf_code, df_daily)

    def _score_with_real_data(self, etf_code: str, df_daily: pd.DataFrame, real_data: Dict) -> ValuationScore:
        """使用真实估值数据评分"""
        close_prices = df_daily['close']

        pe_ttm = real_data.get("pe_ttm", 0)
        pb = real_data.get("pb", 0)
        pe_percentile = real_data.get("pe_percentile", 50.0)
        pb_percentile = real_data.get("pb_percentile", 50.0)
        div_yield = real_data.get("dividend_yield", 0)

        # 利差（假设3%无风险利率）
        risk_free_rate = 0.03
        earnings_yield = 1 / pe_ttm * 100 if pe_ttm > 0 else 0
        spread = earnings_yield - risk_free_rate * 100

        # 净值折溢价估算
        nav_premium = self._estimate_nav_premium(close_prices)

        # 各子项评分（估值越低 → 分数越高）
        sub_scores = {
            "pe_percentile_score": 100 - pe_percentile,
            "pb_percentile_score": 100 - pb_percentile,
            "peg_score": min(100, max(0, 100 - (pe_ttm / max(earnings_yield, 1)) * 20)) if pe_ttm > 0 and earnings_yield > 0 else 50,
            "spread_score": min(100, max(0, 50 + spread * 5)),
            "nav_premium_score": min(100, max(0, 100 - abs(nav_premium) * 2)),
            "price_vs_ma": self._price_vs_moving_average_score(close_prices),
        }

        # 综合评分
        composite = (
            sub_scores["pe_percentile_score"] * 0.30 +
            sub_scores["pb_percentile_score"] * 0.25 +
            sub_scores["peg_score"] * 0.15 +
            sub_scores["spread_score"] * 0.10 +
            sub_scores["nav_premium_score"] * 0.10 +
            sub_scores["price_vs_ma"] * 0.10
        )

        source = real_data.get("data_source", "真实数据")

        return ValuationScore(
            score=round(min(100, max(0, composite)), 1),
            pe_ttm=round(pe_ttm, 1),
            pe_percentile=round(pe_percentile, 1),
            pb=round(pb, 2),
            pb_percentile=round(pb_percentile, 1),
            peg=round(pe_ttm / max(earnings_yield, 1), 2) if pe_ttm > 0 and earnings_yield > 0 else 0,
            spread_risk_free=round(spread, 2),
            nav_discount_premium=round(nav_premium, 2),
            valuation_method=f"真实数据估值法（{source}）",
            sub_scores=sub_scores,
            description=f"真实估值评分: PE百分位 {pe_percentile:.1f}%, PB百分位 {pb_percentile:.1f}%, "
                       f"PE_TTM={pe_ttm:.1f}, PB={pb:.2f} (来源: {source})"
        )

    def _score_with_estimated_data(self, etf_code: str, df_daily: pd.DataFrame) -> ValuationScore:
        """使用价格估算的估值数据评分（回退模式）"""
        close_prices = df_daily['close']

        # 计算PE近似
        pe_approx = self._estimate_pe(close_prices)

        # 计算价格历史百分位
        pe_percentile = self._calc_price_percentile(close_prices)

        # 计算PB近似
        pb_approx = self._estimate_pb(close_prices)
        pb_percentile = self._calc_pb_percentile(close_prices)

        # PEG近似
        peg_approx = self._estimate_peg(close_prices)

        # 净值折溢价估算
        nav_premium = self._estimate_nav_premium(close_prices)

        # 利差估算
        risk_free_rate = 0.03
        estimated_yield = pe_approx / 100 * risk_free_rate if pe_approx > 0 else 0
        spread = estimated_yield - risk_free_rate

        # 各子项评分
        sub_scores = {
            "pe_percentile_score": 100 - pe_percentile,
            "pb_percentile_score": 100 - pb_percentile,
            "peg_score": min(100, max(0, 100 - peg_approx * 20)) if peg_approx > 0 else 50,
            "spread_score": min(100, max(0, 50 + spread * 500)),
            "nav_premium_score": min(100, max(0, 100 - abs(nav_premium) * 2)),
            "price_vs_ma": self._price_vs_moving_average_score(close_prices),
        }

        # 综合评分
        composite = (
            sub_scores["pe_percentile_score"] * 0.30 +
            sub_scores["pb_percentile_score"] * 0.25 +
            sub_scores["peg_score"] * 0.15 +
            sub_scores["spread_score"] * 0.10 +
            sub_scores["nav_premium_score"] * 0.10 +
            sub_scores["price_vs_ma"] * 0.10
        )

        valuation_method = self._determine_valuation_method(etf_code, close_prices)

        return ValuationScore(
            score=round(min(100, max(0, composite)), 1),
            pe_ttm=round(pe_approx, 1),
            pe_percentile=round(pe_percentile, 1),
            pb=round(pb_approx, 2),
            pb_percentile=round(pb_percentile, 1),
            peg=round(peg_approx, 2),
            spread_risk_free=round(spread * 100, 2),
            nav_discount_premium=round(nav_premium, 2),
            valuation_method=f"价格估算法（{valuation_method}）",
            sub_scores=sub_scores,
            description=f"价格估算评分: PE百分位 {pe_percentile:.1f}%, PB百分位 {pb_percentile:.1f}%"
        )

    def _estimate_pe(self, close_prices: pd.Series) -> float:
        """估算PE（基于价格趋势的粗略估算）"""
        returns = close_prices.pct_change().dropna()
        if len(returns) < 20:
            return 15.0  # 默认PE

        annual_return = returns.mean() * 252
        if annual_return > 0.01:  # 至少1%的年化收益
            pe = 1 / annual_return
        else:
            pe = 15.0  # 默认PE

        return max(5.0, min(50.0, pe))

    def _estimate_pb(self, close_prices: pd.Series) -> float:
        """估算PB（基于PE和ROE估算）"""
        pe = self._estimate_pe(close_prices)
        roe_estimate = 0.12  # 假设ROE约12%
        pb = pe * roe_estimate
        return max(0.5, min(10.0, pb))

    def _estimate_peg(self, close_prices: pd.Series) -> float:
        """估算PEG"""
        pe = self._estimate_pe(close_prices)

        # 估算增长率：基于过去120日价格趋势
        if len(close_prices) >= 120:
            growth = (close_prices.iloc[-1] / close_prices.iloc[-120] - 1) * (252 / 120)
        elif len(close_prices) >= 60:
            growth = (close_prices.iloc[-1] / close_prices.iloc[-60] - 1) * (252 / 60)
        else:
            growth = 0.05

        if growth > 0:
            peg = pe / (growth * 100)
        else:
            peg = 5.0  # 负增长时PEG设为高值

        return max(0.1, min(10.0, peg))

    def _calc_price_percentile(self, close_prices: pd.Series) -> float:
        """计算当前价格历史百分位（近似PE百分位）"""
        if len(close_prices) < 20:
            return 50.0

        current = close_prices.iloc[-1]
        historical = close_prices.iloc[:-1]

        percentile = (historical < current).sum() / len(historical) * 100
        return max(0.0, min(100.0, percentile))

    def _calc_pb_percentile(self, close_prices: pd.Series) -> float:
        """计算PB历史百分位"""
        # 使用价格/均线比率的百分位作为PB百分位代理
        if len(close_prices) < 20:
            return 50.0

        ma120 = close_prices.rolling(120).mean()
        ratio = close_prices / ma120

        current_ratio = ratio.iloc[-1]
        historical_ratio = ratio.dropna().iloc[:-1]

        if len(historical_ratio) == 0:
            return 50.0

        percentile = (historical_ratio < current_ratio).sum() / len(historical_ratio) * 100
        return max(0.0, min(100.0, percentile))

    def _estimate_nav_premium(self, close_prices: pd.Series) -> float:
        """估算净值折溢价率 (%)

        使用价格与长周期均线的偏离度估算。
        """
        if len(close_prices) < 60:
            return 0.0

        ma120 = close_prices.rolling(120).mean().iloc[-1]
        current = close_prices.iloc[-1]

        if ma120 <= 0:
            return 0.0

        premium = (current - ma120) / ma120 * 100
        return round(premium, 2)

    def _price_vs_moving_average_score(self, close_prices: pd.Series) -> float:
        """基于价格与均线关系的评分"""
        if len(close_prices) < 60:
            return 50.0

        current = close_prices.iloc[-1]
        ma60 = close_prices.rolling(60).mean().iloc[-1]
        ma120 = close_prices.rolling(120).mean().iloc[-1]

        # 价格低于长期均线 → 估值偏低 → 分数高
        vs_ma60 = (ma60 - current) / current * 100 if current > 0 else 0
        vs_ma120 = (ma120 - current) / current * 100 if current > 0 else 0

        # 转换为分数（低于均线越多，分数越高，最高100）
        score = 50 + (vs_ma60 * 2 + vs_ma120 * 2) / 2
        return min(100, max(0, score))

    def _determine_valuation_method(self, etf_code: str, close_prices: pd.Series) -> str:
        """确定适用的估值方法"""
        volatility = close_prices.pct_change().dropna().std() * np.sqrt(252)

        if volatility > 0.35:
            return "波动率调整估值法（高波动ETF适用）"
        elif volatility < 0.15:
            return "固收类估值法（低波动ETF适用）"
        else:
            return "PE/PB历史百分位法（标准指数估值）"

    def _insufficient_data_score(self) -> ValuationScore:
        """数据不足时的默认评分"""
        return ValuationScore(
            score=50.0,
            pe_ttm=0.0,
            pe_percentile=50.0,
            pb=0.0,
            pb_percentile=50.0,
            peg=0.0,
            spread_risk_free=0.0,
            nav_discount_premium=0.0,
            valuation_method="数据不足，默认中值评分",
            sub_scores={},
            description="历史数据不足，采用中性评分50分"
        )
