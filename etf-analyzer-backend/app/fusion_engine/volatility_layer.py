"""
波动率风险预算层 - Volatility Risk Budget Layer

基于ATR（真实波动幅度均值）的波动率分析与仓位管理系统。
计算波动率状态、仓位系数、止损乘数及凯利比例，为交易决策提供
风险预算依据。

ATR-based volatility analysis and position sizing management system.
Computes volatility state, position coefficient, stop-loss multiplier,
and Kelly ratio to provide risk budget basis for trading decisions.
"""

import logging
from typing import Dict, Literal, Optional, Tuple

import numpy as np
import pandas as pd

from app.models.fusion_models import VolatilityResult

logger = logging.getLogger(__name__)

# 波动率状态常量 - Volatility state constants
VOL_STATE_LOW = "低波动"
VOL_STATE_NORMAL = "正常波动"
VOL_STATE_HIGH = "高波动"
VOL_STATE_EXTREME = "极端波动"

# 缠论级别常量 - Chan theory level constants
CHAN_LEVEL_WEEKLY = "周线背驰"
CHAN_LEVEL_DAILY = "日线背驰"
CHAN_LEVEL_30MIN = "30分钟"

# 情绪评级常量 - Sentiment rating constants
SENTIMENT_A = "A"
SENTIMENT_B = "B"


class VolatilityLayer:
    """
    波动率风险预算层核心类 - Volatility Risk Budget Layer Core Class

    提供基于ATR的波动率分析全套功能，包括：
    - ATR(14) 计算
    - ATR历史分位数计算
    - 波动率状态判定（低/正常/高/极端）
    - 仓位系数与止损乘数映射
    - 凯利比例计算与波动率调整

    Provides comprehensive ATR-based volatility analysis features:
    - ATR(14) calculation
    - ATR historical percentile computation
    - Volatility state classification (low/normal/high/extreme)
    - Position coefficient and stop-loss multiplier mapping
    - Kelly ratio calculation with volatility adjustment
    """

    # 波动率状态分位阈值 - Volatility state percentile thresholds
    _VOL_THRESHOLDS: Dict[str, Tuple[float, float]] = {
        VOL_STATE_LOW: (0.0, 0.20),
        VOL_STATE_NORMAL: (0.20, 0.60),
        VOL_STATE_HIGH: (0.60, 0.85),
        VOL_STATE_EXTREME: (0.85, 1.0),
    }

    # 波动率状态 → 仓位系数 映射 - Vol state → position coefficient mapping
    _POSITION_COEF_MAP: Dict[str, float] = {
        VOL_STATE_LOW: 1.2,
        VOL_STATE_NORMAL: 1.0,
        VOL_STATE_HIGH: 0.6,
        VOL_STATE_EXTREME: 0.3,
    }

    # 波动率状态 → ATR止损乘数 映射 - Vol state → ATR stop-loss multiplier mapping
    _ATR_MULTIPLIER_MAP: Dict[str, float] = {
        VOL_STATE_LOW: 1.5,
        VOL_STATE_NORMAL: 2.0,
        VOL_STATE_HIGH: 2.5,
        VOL_STATE_EXTREME: 3.0,
    }

    # 凯利参数表 (缠论级别, 情绪评级) → (胜率p, 盈亏比b, 经验调整凯利f*) - Kelly parameter table
    # 注: 表中f*为经验保守调整值（约半凯利至四分之一凯利），非公式直接计算结果
    # Note: f* values are empirically adjusted (half to quarter Kelly), not raw formula output
    _KELLY_TABLE: Dict[Tuple[str, str], Tuple[float, float, float]] = {
        (CHAN_LEVEL_WEEKLY, SENTIMENT_A): (0.65, 3.0, 0.30),
        (CHAN_LEVEL_DAILY, SENTIMENT_A): (0.55, 2.5, 0.22),
        (CHAN_LEVEL_DAILY, SENTIMENT_B): (0.48, 2.0, 0.14),
        (CHAN_LEVEL_30MIN, SENTIMENT_A): (0.45, 1.8, 0.08),
    }

    # 单标的上限 - Single ticker maximum position limit
    _SINGLE_TICKER_MAX: float = 0.25

    def __init__(self, config: Optional[Dict] = None) -> None:
        """
        初始化波动率风险预算层 - Initialize volatility risk budget layer

        Args:
            config: 可选配置字典，可覆盖默认阈值和参数。
                    Optional configuration dict to override default thresholds.
                    支持的键(Supported keys):
                    - 'position_coef_map': 自定义仓位系数映射
                    - 'atr_multiplier_map': 自定义ATR止损乘数映射
                    - 'single_ticker_max': 单标的上限
                    - 'kelly_table': 自定义凯利参数表
        """
        self.config = config or {}

        # 应用自定义配置 - Apply custom configurations
        if "position_coef_map" in self.config:
            self._POSITION_COEF_MAP.update(self.config["position_coef_map"])
            logger.info("应用自定义仓位系数映射 - Applied custom position coefficient map")

        if "atr_multiplier_map" in self.config:
            self._ATR_MULTIPLIER_MAP.update(self.config["atr_multiplier_map"])
            logger.info("应用自定义ATR止损乘数映射 - Applied custom ATR multiplier map")

        if "single_ticker_max" in self.config:
            self._SINGLE_TICKER_MAX = self.config["single_ticker_max"]

        if "kelly_table" in self.config:
            self._KELLY_TABLE.update(self.config["kelly_table"])

        logger.info("波动率风险预算层初始化完成 - VolatilityLayer initialized")

    def calculate_atr(self, df: pd.DataFrame, period: int = 14) -> float:
        """
        计算ATR(真实波动幅度均值) - Calculate Average True Range

        公式:
            TR = max(High-Low, |High-PreClose|, |Low-PreClose|)
            ATR = SMA(TR, period)

        Args:
            df: K线数据DataFrame，必须包含 'high', 'low', 'close' 列
                OHLC DataFrame with required columns: 'high', 'low', 'close'
            period: ATR计算周期，默认14
                ATR calculation period, default 14

        Returns:
            float: ATR值，如果数据不足返回0.0
                ATR value, returns 0.0 if insufficient data

        Raises:
            ValueError: 如果DataFrame缺少必要的列
                If DataFrame is missing required columns
        """
        required_cols = {"high", "low", "close"}
        if not required_cols.issubset(df.columns):
            missing = required_cols - set(df.columns)
            raise ValueError(f"DataFrame缺少必要列(Missing columns): {missing}")

        if len(df) < period + 1:
            logger.warning(f"数据不足(Insufficient data): 需要{period+1}行，实际{len(df)}行")
            return 0.0

        # 计算真实波幅 TR - Calculate True Range
        high = df["high"]
        low = df["low"]
        close = df["close"]

        # 前收盘价序列 - Previous close prices
        prev_close = close.shift(1)

        # TR = max(High-Low, |High-PreClose|, |Low-PreClose|)
        tr1 = high - low  # 当日高低波幅
        tr2 = (high - prev_close).abs()  # 高点与前收盘的gap
        tr3 = (low - prev_close).abs()  # 低点与前收盘的gap

        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        # ATR = SMA(TR, period) - 简单移动平均
        atr_series = tr.rolling(window=period, min_periods=period).mean()

        # 返回最新的ATR值 - Return the latest ATR value
        latest_atr = float(atr_series.iloc[-1])

        if np.isnan(latest_atr):
            logger.warning("ATR计算结果为NaN，数据可能不足 - ATR is NaN, data may be insufficient")
            return 0.0

        logger.debug(f"ATR({period}) = {latest_atr:.4f}")
        return latest_atr

    def calculate_atr_percentile(
        self, df: pd.DataFrame, period: int = 14, lookback: int = 252
    ) -> float:
        """
        计算ATR(14)/Close的历史分位数 - Calculate ATR/Close historical percentile

        使用ATR与收盘价的比值来衡量相对波动率水平，
        并在lookback窗口内计算当前值的历史分位。

        Uses the ratio of ATR to closing price to measure relative volatility level,
        and computes the historical percentile of the current value within the lookback window.

        Args:
            df: K线数据DataFrame，必须包含 'high', 'low', 'close' 列
                OHLC DataFrame with required columns: 'high', 'low', 'close'
            period: ATR计算周期，默认14
                ATR calculation period, default 14
            lookback: 历史分位回看窗口，默认252（约一年交易日）
                Historical percentile lookback window, default 252 (~1 year trading days)

        Returns:
            float: ATR百分位 [0, 1]，数据不足返回0.5
                ATR percentile in [0, 1], returns 0.5 if insufficient data
        """
        required_cols = {"high", "low", "close"}
        if not required_cols.issubset(df.columns):
            missing = required_cols - set(df.columns)
            raise ValueError(f"DataFrame缺少必要列(Missing columns): {missing}")

        min_required = period + lookback + 1
        if len(df) < min_required:
            logger.warning(
                f"数据不足计算历史分位(Insufficient data for percentile): "
                f"需要{min_required}行，实际{len(df)}行，返回默认值0.5"
            )
            return 0.5

        high = df["high"]
        low = df["low"]
        close = df["close"]
        prev_close = close.shift(1)

        # 计算TR序列 - Calculate TR series
        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        # 计算ATR序列 - Calculate ATR series
        atr_series = tr.rolling(window=period, min_periods=period).mean()

        # ATR/Close 相对波动率序列 - Relative volatility series
        relative_vol = atr_series / close

        # 获取有效数据（去掉NaN）- Get valid data (drop NaN)
        valid_vol = relative_vol.dropna()

        if len(valid_vol) < lookback:
            logger.warning(
                f"有效数据不足(Insufficient valid data): "
                f"需要{lookback}个，实际{len(valid_vol)}个，返回默认值0.5"
            )
            return 0.5

        # 取最近lookback个数据 - Take recent lookback data
        recent_vol = valid_vol.iloc[-lookback:]
        current_vol = float(recent_vol.iloc[-1])

        if np.isnan(current_vol) or current_vol <= 0:
            logger.warning("当前相对波动率为无效值 - Current relative volatility is invalid")
            return 0.5

        # 计算分位数: 当前值在历史分布中的排名 - Compute percentile rank
        percentile = (recent_vol < current_vol).mean()

        # 确保在[0, 1]范围内 - Clamp to [0, 1]
        percentile = float(np.clip(percentile, 0.0, 1.0))

        logger.debug(f"ATR百分位(ATR percentile) = {percentile:.4f} (当前={current_vol:.6f})")
        return percentile

    def get_vol_state(self, atr_percentile: float) -> str:
        """
        根据ATR分位数判定波动率状态 - Determine volatility state from ATR percentile

        分位阈值划分:
            - 低波动:   分位 < 20%
            - 正常波动: 20% <= 分位 < 60%
            - 高波动:   60% <= 分位 < 85%
            - 极端波动: 分位 >= 85%

        Args:
            atr_percentile: ATR历史分位 [0, 1]
                ATR historical percentile in [0, 1]

        Returns:
            str: 波动率状态标签
                Volatility state label string
        """
        if atr_percentile < 0.20:
            return VOL_STATE_LOW
        elif atr_percentile < 0.60:
            return VOL_STATE_NORMAL
        elif atr_percentile < 0.85:
            return VOL_STATE_HIGH
        else:
            return VOL_STATE_EXTREME

    def get_position_coefficient(self, vol_state: str) -> float:
        """
        根据波动率状态获取仓位系数 - Get position coefficient for volatility state

        波动率越高，仓位系数越低，以控制整体风险暴露。
        Higher volatility results in lower position coefficient to control risk exposure.

        Args:
            vol_state: 波动率状态字符串
                Volatility state label

        Returns:
            float: 仓位系数 [0.3, 1.2]
                Position sizing coefficient
        """
        coef = self._POSITION_COEF_MAP.get(vol_state, 1.0)
        logger.debug(f"波动率状态={vol_state} -> 仓位系数={coef}")
        return coef

    def get_atr_multiplier(self, vol_state: str) -> float:
        """
        根据波动率状态获取ATR止损乘数 - Get ATR stop-loss multiplier

        波动率越高，止损距离越远，避免正常波动触发止损。
        Higher volatility requires wider stop-loss to avoid normal noise triggering.

        Args:
            vol_state: 波动率状态字符串
                Volatility state label

        Returns:
            float: ATR止损乘数 [1.5, 3.0]
                ATR-based stop loss multiplier
        """
        multiplier = self._ATR_MULTIPLIER_MAP.get(vol_state, 2.0)
        logger.debug(f"波动率状态={vol_state} -> ATR止损乘数={multiplier}")
        return multiplier

    def calculate_kelly_position(
        self,
        chan_level: str = CHAN_LEVEL_DAILY,
        sentiment_rating: str = SENTIMENT_A,
    ) -> float:
        """
        计算凯利比例 - Calculate Kelly criterion ratio

        使用经验调整的凯利参数表直接查询，表中f*值基于简化凯利公式:
            f* = (b * p - q) / b
        但经过保守调整（约半凯利至四分之一凯利），更适合实际交易。

        Uses empirically-adjusted Kelly lookup table. The f* values are derived from
        the simplified Kelly formula but conservatively adjusted for practical trading.

        Args:
            chan_level: 缠论级别，可选 "周线背驰"/"日线背驰"/"30分钟"
                Chan theory level
            sentiment_rating: 情绪评级，可选 "A"/"B"
                Sentiment rating

        Returns:
            float: 凯利比例 f*，如果参数组合不存在则回退到日线背驰/A
                Kelly ratio, falls back to daily/A if combination not found
        """
        key = (chan_level, sentiment_rating)

        if key not in self._KELLY_TABLE:
            logger.warning(
                f"凯利参数表中没有该组合(No Kelly params for): {chan_level}/{sentiment_rating}，"
                f"使用默认日线背驰/A"
            )
            key = (CHAN_LEVEL_DAILY, SENTIMENT_A)

        p, b, kelly_f = self._KELLY_TABLE[key]

        # 确保非负 - Ensure non-negative
        kelly_f = max(0.0, kelly_f)

        logger.debug(
            f"凯利计算(Kelly): 级别={chan_level}, 情绪={sentiment_rating}, "
            f"p={p}, b={b}, f*={kelly_f:.4f}"
        )
        return kelly_f

    def _generate_description(
        self,
        vol_state: str,
        atr14: float,
        atr_percentile: float,
        position_coefficient: float,
        kelly_adjusted: float,
    ) -> str:
        """
        生成分析描述文本 - Generate human-readable analysis description

        Args:
            vol_state: 波动率状态
            atr14: ATR(14)值
            atr_percentile: ATR百分位
            position_coefficient: 仓位系数
            kelly_adjusted: 调整后凯利比例

        Returns:
            str: 描述文本
        """
        percentile_pct = atr_percentile * 100

        if vol_state == VOL_STATE_LOW:
            desc = (
                f"当前处于低波动区间(第{percentile_pct:.0f}百分位)，"
                f"ATR(14)={atr14:.4f}。建议积极仓位({position_coefficient:.1f}x)，"
                f"止损设于1.5x ATR。调整凯利比例={kelly_adjusted:.4f}。"
            )
        elif vol_state == VOL_STATE_NORMAL:
            desc = (
                f"当前处于正常波动区间(第{percentile_pct:.0f}百分位)，"
                f"ATR(14)={atr14:.4f}。建议标准仓位({position_coefficient:.1f}x)，"
                f"止损设于2.0x ATR。调整凯利比例={kelly_adjusted:.4f}。"
            )
        elif vol_state == VOL_STATE_HIGH:
            desc = (
                f"当前处于高波动区间(第{percentile_pct:.0f}百分位)，"
                f"ATR(14)={atr14:.4f}。建议保守仓位({position_coefficient:.1f}x)，"
                f"止损设于2.5x ATR。调整凯利比例={kelly_adjusted:.4f}。"
            )
        else:  # 极端波动
            desc = (
                f"当前处于极端波动区间(第{percentile_pct:.0f}百分位)，"
                f"ATR(14)={atr14:.4f}。建议极小仓位({position_coefficient:.1f}x)或空仓观望，"
                f"止损设于3.0x ATR。调整凯利比例={kelly_adjusted:.4f}。"
            )

        return desc

    def analyze(
        self,
        df: pd.DataFrame,
        chan_level: str = CHAN_LEVEL_DAILY,
        sentiment_rating: str = SENTIMENT_A,
    ) -> VolatilityResult:
        """
        执行完整波动率分析 - Execute complete volatility analysis

        依次计算ATR、ATR历史分位、波动率状态、仓位系数、
        止损乘数和凯利比例，返回完整的 VolatilityResult。

        Sequentially computes ATR, ATR historical percentile, volatility state,
        position coefficient, stop-loss multiplier, and Kelly ratio,
        returning a complete VolatilityResult.

        Args:
            df: K线数据DataFrame，必须包含 'high', 'low', 'close' 列
                OHLC DataFrame with required columns: 'high', 'low', 'close'
            chan_level: 缠论级别，默认"日线背驰"
                Chan theory level, default "日线背驰"
            sentiment_rating: 情绪评级，默认"A"
                Sentiment rating, default "A"

        Returns:
            VolatilityResult: 波动率分析结果
                Volatility analysis result object
        """
        logger.info("开始波动率分析 - Starting volatility analysis")

        # 1. 计算ATR(14) - Calculate ATR(14)
        atr14 = self.calculate_atr(df, period=14)

        # 2. 计算ATR历史分位 - Calculate ATR historical percentile
        atr_percentile = self.calculate_atr_percentile(df, period=14, lookback=252)

        # 3. 判定波动率状态 - Determine volatility state
        vol_state = self.get_vol_state(atr_percentile)

        # 4. 获取仓位系数 - Get position coefficient
        position_coefficient = self.get_position_coefficient(vol_state)

        # 5. 获取ATR止损乘数 - Get ATR stop-loss multiplier
        atr_multiplier = self.get_atr_multiplier(vol_state)

        # 6. 计算凯利比例 - Calculate Kelly ratio
        kelly_ratio = self.calculate_kelly_position(chan_level, sentiment_rating)

        # 7. 波动率调整后的凯利比例 - Volatility-adjusted Kelly ratio
        kelly_adjusted = kelly_ratio * position_coefficient

        # 8. 应用上限约束 - Apply cap constraints
        # 不超过单标的上限25%
        kelly_adjusted = min(kelly_adjusted, self._SINGLE_TICKER_MAX)

        # 9. 生成描述文本 - Generate description
        description = self._generate_description(
            vol_state, atr14, atr_percentile, position_coefficient, kelly_adjusted
        )

        result = VolatilityResult(
            atr14=round(atr14, 4),
            atr_percentile=round(atr_percentile, 4),
            vol_state=vol_state,
            position_coefficient=round(position_coefficient, 2),
            atr_multiplier=round(atr_multiplier, 2),
            kelly_ratio=round(kelly_ratio, 4),
            kelly_adjusted=round(kelly_adjusted, 4),
            description=description,
        )

        logger.info(
            f"波动率分析完成 - Analysis complete: 状态={vol_state}, "
            f"ATR={atr14:.4f}, 分位={atr_percentile:.4f}, "
            f"仓位系数={position_coefficient:.2f}, 凯利={kelly_adjusted:.4f}"
        )

        return result
