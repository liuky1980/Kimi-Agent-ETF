"""
宏观适配评分模块 (权重10%)
===========================
丁昶五维评分体系 — 维度五：宏观适配

评分逻辑（通用化，适用于全部ETF类型）：
- 周期定位：评估当前经济周期对该ETF的友好程度
- 利率环境：评估利率走势对ETF的影响
- 政策支持：评估相关政策对该ETF的利好程度
- 全球比较：评估该资产在全球的估值吸引力

宏观适配的通用化实现：
- 不依赖具体宏观数据API
- 基于价格走势和波动特征推断宏观环境适配度
- 通过趋势强度和稳定性评估周期定位
"""

import logging
from typing import Dict, Optional

import numpy as np
import pandas as pd

from app.models.dingchang import MacroScore

logger = logging.getLogger(__name__)


class MacroAdaptation:
    """宏观适配评分器

    基于ETF价格走势特征推断宏观环境适配度，
    适用于所有ETF类型，不依赖外部宏观数据API。
    """

    def __init__(self):
        pass

    def score(self, etf_code: str, df_daily: pd.DataFrame, real_data: Optional[Dict] = None) -> MacroScore:
        """宏观适配评分主函数

        Parameters
        ----------
        etf_code : str
            ETF代码
        df_daily : pd.DataFrame
            日线数据
        real_data : dict, optional
            真实宏观数据（从tushare获取）

        Returns
        -------
        MacroScore
            宏观适配评分结果
        """
        logger.info(f"开始对 {etf_code} 进行宏观适配评分")

        close_prices = df_daily['close']
        returns = close_prices.pct_change().dropna()

        if len(returns) < 60:
            return self._insufficient_data_score()

        # 优先使用真实宏观数据（shibor利率）
        use_real_macro = real_data and real_data.get("shibor_1y", 0) > 0

        # 1. 周期定位
        cycle_position, cycle_fit_score = self._determine_cycle_position(close_prices, returns)

        # 2. 利率环境适配
        if use_real_macro:
            rate_environment_fit = self._assess_rate_environment_real(real_data)
            logger.info(f"[MacroAdaptation] 使用真实利率数据: shibor_1y={real_data.get('shibor_1y')}")
        else:
            rate_environment_fit = self._assess_rate_environment(close_prices, returns)

        # 3. 政策支持度估算
        policy_support = self._estimate_policy_support(close_prices, returns)

        # 4. 全球比较优势
        global_comparison = self._estimate_global_comparison(close_prices, returns)

        # 5. 宏观风险评分
        macro_risk_score = self._assess_macro_risk(close_prices, returns)

        # 子得分
        sub_scores = {
            "cycle_fit": cycle_fit_score * 100,
            "rate_environment": rate_environment_fit * 100,
            "policy_support": policy_support * 100,
            "global_comparison": global_comparison * 100,
            "macro_risk": (1 - macro_risk_score) * 100,  # 风险越低分越高
        }

        # 综合评分
        composite = (
            sub_scores["cycle_fit"] * 0.30 +
            sub_scores["rate_environment"] * 0.25 +
            sub_scores["policy_support"] * 0.20 +
            sub_scores["global_comparison"] * 0.15 +
            sub_scores["macro_risk"] * 0.10
        )

        desc = f"宏观适配: 周期定位 '{cycle_position}', 适配度 {cycle_fit_score:.2f}, "
        if use_real_macro:
            desc += f"真实利率环境 {rate_environment_fit:.2f} (shibor_1y={real_data.get('shibor_1y')}), "
        else:
            desc += f"估算利率环境 {rate_environment_fit:.2f}, "
        desc += f"政策支持 {policy_support:.2f}"

        return MacroScore(
            score=round(min(100, max(0, composite)), 1),
            cycle_position=cycle_position,
            cycle_fit_score=round(cycle_fit_score, 3),
            rate_environment_fit=round(rate_environment_fit, 3),
            policy_support=round(policy_support, 3),
            global_comparison=round(global_comparison, 3),
            macro_risk_score=round(macro_risk_score, 3),
            sub_scores=sub_scores,
            description=desc
        )

    def _assess_rate_environment_real(self, real_data: Dict) -> float:
        """基于真实利率数据评估利率环境适配度

        使用shibor数据评估当前利率环境。
        """
        rate_1y = real_data.get("shibor_1y", 0)
        rate_trend = real_data.get("rate_trend", 0)
        rate_env = real_data.get("rate_environment", "medium")

        # 基于利率水平的基础适配度
        if rate_env == "low":
            base_fit = 0.80  # 低利率利好权益
        elif rate_env == "medium":
            base_fit = 0.60
        else:
            base_fit = 0.40  # 高利率不利

        # 利率趋势调整
        if rate_trend < -0.1:
            base_fit += 0.15  # 降息趋势
        elif rate_trend > 0.1:
            base_fit -= 0.15  # 加息趋势

        return round(max(0.1, min(1.0, base_fit)), 3)

    def _determine_cycle_position(self, close_prices: pd.Series, returns: pd.Series) -> tuple:
        """确定周期定位

        基于趋势强度和持续性的周期推断。

        Returns
        -------
        tuple
            (周期描述, 适配度评分)
        """
        # 计算不同周期的收益率
        if len(close_prices) >= 252:
            ret_1y = close_prices.iloc[-1] / close_prices.iloc[-252] - 1
        else:
            ret_1y = close_prices.iloc[-1] / close_prices.iloc[0] - 1

        if len(close_prices) >= 60:
            ret_3m = close_prices.iloc[-1] / close_prices.iloc[-60] - 1
        else:
            ret_3m = ret_1y

        ret_1m = close_prices.iloc[-1] / close_prices.iloc[-min(20, len(close_prices))] - 1

        # 趋势一致性判断
        trend_aligned = (ret_1y > 0 and ret_3m > 0 and ret_1m > 0) or (ret_1y < 0 and ret_3m < 0 and ret_1m < 0)

        # 周期定位
        if trend_aligned and ret_1y > 0.10:
            cycle = "扩张期（利好风险资产）"
            fit = 0.85
        elif trend_aligned and ret_1y > 0:
            cycle = "复苏期（利好权益资产）"
            fit = 0.75
        elif trend_aligned and ret_1y < -0.10:
            cycle = "衰退期（利好避险资产）"
            fit = 0.40 if ret_1y < 0 else 0.60
        elif trend_aligned and ret_1y < 0:
            cycle = "调整期（关注防御配置）"
            fit = 0.50
        else:
            cycle = "转折期（方向不明）"
            fit = 0.55

        return cycle, round(fit, 3)

    def _assess_rate_environment(self, close_prices: pd.Series, returns: pd.Series) -> float:
        """评估利率环境适配度

        基于波动率和趋势稳定性推断利率环境适配度。
        简化假设：低波动趋势 → 利率环境友好。
        """
        volatility = returns.std() * np.sqrt(252)

        # 波动率越低，利率环境越可能友好
        if volatility < 0.15:
            base_fit = 0.8
        elif volatility < 0.25:
            base_fit = 0.65
        elif volatility < 0.35:
            base_fit = 0.5
        else:
            base_fit = 0.35

        # 趋势加分
        if len(close_prices) >= 60:
            trend_3m = close_prices.iloc[-1] / close_prices.iloc[-60] - 1
            if trend_3m > 0.05:
                base_fit += 0.1
            elif trend_3m < -0.05:
                base_fit -= 0.1

        return round(max(0.1, min(1.0, base_fit)), 3)

    def _estimate_policy_support(self, close_prices: pd.Series, returns: pd.Series) -> float:
        """估算政策支持度

        基于市场活跃度和趋势健康度推断政策支持程度。
        持续稳定的上涨趋势通常受益于有利政策环境。
        """
        if len(close_prices) < 60:
            return 0.5

        # 价格持续上涨且回撤可控 → 政策支持度较高
        cummax = close_prices.cummax()
        drawdown = (close_prices - cummax) / cummax
        max_dd = drawdown.min()

        # 趋势斜率
        x = np.arange(min(60, len(close_prices)))
        y = close_prices.tail(60).values
        slope = np.polyfit(x, y, 1)[0] if len(x) > 1 else 0
        normalized_slope = slope / y.mean() if y.mean() > 0 else 0

        # 综合判断
        if normalized_slope > 0 and max_dd > -0.10:
            support = 0.75
        elif normalized_slope > 0:
            support = 0.60
        elif max_dd > -0.15:
            support = 0.50
        else:
            support = 0.35

        return round(support, 3)

    def _estimate_global_comparison(self, close_prices: pd.Series, returns: pd.Series) -> float:
        """估算全球比较优势

        基于收益/风险比率相对于简单买入持有策略的比较。
        """
        if len(returns) < 60:
            return 0.5

        # 夏普比率近似
        annual_return = returns.mean() * 252
        annual_vol = returns.std() * np.sqrt(252)

        if annual_vol <= 0:
            return 0.5

        sharpe = annual_return / annual_vol

        # 夏普比率越高，全球比较优势越大
        if sharpe > 1.0:
            advantage = 0.85
        elif sharpe > 0.5:
            advantage = 0.70
        elif sharpe > 0:
            advantage = 0.55
        elif sharpe > -0.5:
            advantage = 0.40
        else:
            advantage = 0.25

        return round(advantage, 3)

    def _assess_macro_risk(self, close_prices: pd.Series, returns: pd.Series) -> float:
        """评估宏观风险

        基于尾部风险和极端波动频率评估宏观层面的系统性风险。

        Returns
        -------
        float
            风险评分 0~1，越高风险越大
        """
        if len(returns) < 60:
            return 0.3

        # 最大回撤
        cummax = close_prices.cummax()
        drawdown = (close_prices - cummax) / cummax
        max_dd = abs(drawdown.min())

        # 极端波动频率（超过2个标准差的次数）
        threshold = 2 * returns.std()
        extreme_count = (abs(returns) > threshold).sum()
        extreme_ratio = extreme_count / len(returns)

        # 下行波动占比
        downside_returns = returns[returns < 0]
        downside_ratio = len(downside_returns) / len(returns) if len(returns) > 0 else 0.5

        # 综合风险
        risk = (
            min(1.0, max_dd / 0.50) * 0.4 +  # 最大回撤贡献
            min(1.0, extreme_ratio * 20) * 0.3 +  # 极端波动贡献
            abs(downside_ratio - 0.5) * 2 * 0.3  # 非对称下行贡献
        )

        return round(min(1.0, max(0.0, risk)), 3)

    def _insufficient_data_score(self) -> MacroScore:
        """数据不足时的默认评分"""
        return MacroScore(
            score=50.0,
            cycle_position="数据不足",
            cycle_fit_score=0.5,
            rate_environment_fit=0.5,
            policy_support=0.5,
            global_comparison=0.5,
            macro_risk_score=0.3,
            sub_scores={},
            description="历史数据不足，采用中性评分50分"
        )
