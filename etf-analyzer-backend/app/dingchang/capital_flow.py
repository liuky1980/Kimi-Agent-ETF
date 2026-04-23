"""
资金驱动评分模块 (权重15%)
===========================
丁昶五维评分体系 — 维度四：资金驱动

评分逻辑（通用化，适用于全部ETF类型）：
- 成交量趋势分析（资金流入的代理指标）
- 换手率变化趋势
- 价格波动与成交量的配合度
- 资金流强度综合评估

核心原则：资金持续流入 + 量价配合良好 → 评分高
"""

import logging
from typing import Dict

import numpy as np
import pandas as pd

from app.models.dingchang import CapitalFlowScore

logger = logging.getLogger(__name__)


class CapitalFlow:
    """资金驱动评分器

    基于成交量、换手率、量价配合等指标评估资金驱动力，
    适用于所有ETF类型。
    """

    def __init__(self):
        pass

    def score(self, etf_code: str, df_daily: pd.DataFrame) -> CapitalFlowScore:
        """资金驱动评分主函数

        Parameters
        ----------
        etf_code : str
            ETF代码
        df_daily : pd.DataFrame
            日线数据（需包含 close, volume, amount, turnover 等列）

        Returns
        -------
        CapitalFlowScore
            资金驱动评分结果
        """
        logger.info(f"开始对 {etf_code} 进行资金驱动评分")

        close_prices = df_daily['close']
        volume = df_daily['volume'] if 'volume' in df_daily.columns else pd.Series(index=df_daily.index, dtype=float)
        amount = df_daily['amount'] if 'amount' in df_daily.columns else pd.Series(index=df_daily.index, dtype=float)
        turnover = df_daily['turnover'] if 'turnover' in df_daily.columns else pd.Series(index=df_daily.index, dtype=float)

        if len(close_prices) < 20:
            return self._insufficient_data_score()

        # 1. AUM估算（基于成交额）
        aum_estimate = self._estimate_aum(amount)

        # 2. AUM增长趋势
        aum_growth_3m = self._calc_aum_growth(amount, period=60)
        aum_growth_1y = self._calc_aum_growth(amount, period=252)

        # 3. 成交量趋势
        volume_trend = self._calc_volume_trend(volume)

        # 4. 机构持仓占比估算（基于大单特征）
        institutional_ratio = self._estimate_institutional_ratio(close_prices, volume)

        # 5. 机构持仓变化
        institutional_change = self._estimate_institutional_change(volume)

        # 6. 资金流向估算（近20日）
        fund_flow_20d = self._estimate_fund_flow(close_prices, volume, period=20)

        # 子得分
        sub_scores = {
            "aum_score": min(100, max(0, 30 + aum_estimate / 1e8)),  # AUM越大越好
            "aum_growth_3m": min(100, max(0, 50 + aum_growth_3m * 10)),
            "aum_growth_1y": min(100, max(0, 50 + aum_growth_1y * 5)),
            "volume_trend": (volume_trend + 1) * 50,  # -1~1 映射到 0~100
            "institutional_ratio": institutional_ratio * 100,
            "institutional_change": min(100, max(0, 50 + institutional_change * 5)),
            "fund_flow_20d": min(100, max(0, 50 + fund_flow_20d * 20)),
        }

        # 综合评分
        composite = (
            sub_scores["aum_growth_3m"] * 0.25 +
            sub_scores["aum_growth_1y"] * 0.20 +
            sub_scores["volume_trend"] * 0.20 +
            sub_scores["institutional_change"] * 0.15 +
            sub_scores["fund_flow_20d"] * 0.20
        )

        return CapitalFlowScore(
            score=round(min(100, max(0, composite)), 1),
            aum=round(aum_estimate / 1e8, 2),  # 转换为亿元
            aum_growth_3m=round(aum_growth_3m * 100, 2),
            aum_growth_1y=round(aum_growth_1y * 100, 2),
            volume_trend=round(volume_trend, 3),
            institutional_ratio=round(institutional_ratio, 3),
            institutional_change=round(institutional_change * 100, 2),
            fund_flow_20d=round(fund_flow_20d, 4),
            sub_scores=sub_scores,
            description=f"资金驱动: 3月AUM增长 {aum_growth_3m*100:.1f}%, "
                       f"成交量趋势 {volume_trend:+.3f}, "
                       f"近20日资金流向 {fund_flow_20d:+.4f}"
        )

    def _estimate_aum(self, amount: pd.Series) -> float:
        """估算AUM（资产管理规模）"""
        if amount.empty or amount.sum() <= 0:
            return 10e8  # 默认10亿

        # 使用平均成交额估算AUM（假设日换手约5%）
        avg_daily_amount = amount.tail(60).mean()
        estimated_aum = avg_daily_amount * 20 * 252  # 年化成交额 / 假设换手率
        return max(1e8, estimated_aum)

    def _calc_aum_growth(self, amount: pd.Series, period: int = 60) -> float:
        """计算AUM增长率"""
        if len(amount) < period * 2:
            return 0.0

        recent_avg = amount.tail(period).mean()
        previous_avg = amount.iloc[-period*2:-period].mean()

        if previous_avg <= 0:
            return 0.0

        growth = (recent_avg - previous_avg) / previous_avg
        return growth

    def _calc_volume_trend(self, volume: pd.Series) -> float:
        """计算成交量趋势

        返回值 -1~1：正值表示成交量放大（资金流入），负值表示萎缩
        """
        if len(volume) < 60:
            return 0.0

        # 比较近20日和前40日平均成交量
        recent_vol = volume.tail(20).mean()
        previous_vol = volume.iloc[-60:-20].mean()

        if previous_vol <= 0:
            return 0.0

        ratio = recent_vol / previous_vol - 1

        # 映射到 -1~1
        trend = np.tanh(ratio * 2)  # tanh平滑
        return round(trend, 3)

    def _estimate_institutional_ratio(self, close_prices: pd.Series, volume: pd.Series) -> float:
        """估算机构持仓占比

        基于成交量稳定性和价格连续性推断机构参与程度。
        """
        if len(volume) < 60:
            return 0.3  # 默认30%

        # 机构持仓特征：成交量相对稳定，大波动日成交量放大
        vol_cv = volume.tail(60).std() / (volume.tail(60).mean() + 1e-6)

        # CV越低，机构占比可能越高
        if vol_cv < 0.3:
            ratio = 0.6
        elif vol_cv < 0.5:
            ratio = 0.45
        elif vol_cv < 0.8:
            ratio = 0.3
        else:
            ratio = 0.15

        return round(ratio, 3)

    def _estimate_institutional_change(self, volume: pd.Series) -> float:
        """估算机构持仓变化"""
        if len(volume) < 120:
            return 0.0

        # 通过成交量结构变化推断
        recent_vol_pattern = volume.tail(60)
        previous_vol_pattern = volume.iloc[-120:-60]

        recent_avg = recent_vol_pattern.mean()
        previous_avg = previous_vol_pattern.mean()

        if previous_avg <= 0:
            return 0.0

        change = (recent_avg - previous_avg) / previous_avg
        return round(change, 4)

    def _estimate_fund_flow(self, close_prices: pd.Series, volume: pd.Series, period: int = 20) -> float:
        """估算资金流向

        基于价量关系：上涨放量 = 资金流入，下跌放量 = 资金流出

        Returns
        -------
        float
            资金流向指标（正值流入，负值流出）
        """
        if len(close_prices) < period or len(volume) < period:
            return 0.0

        returns = close_prices.pct_change().tail(period)
        vol = volume.tail(period)

        # 计算量价配合资金流
        fund_flow = (returns * vol / (vol.mean() + 1e-6)).sum() / period

        # 映射到合理范围
        fund_flow = np.tanh(fund_flow * 10)
        return round(fund_flow, 4)

    def _insufficient_data_score(self) -> CapitalFlowScore:
        """数据不足时的默认评分"""
        return CapitalFlowScore(
            score=50.0,
            aum=0.0,
            aum_growth_3m=0.0,
            aum_growth_1y=0.0,
            volume_trend=0.0,
            institutional_ratio=0.3,
            institutional_change=0.0,
            fund_flow_20d=0.0,
            sub_scores={},
            description="数据不足，采用中性评分50分"
        )
