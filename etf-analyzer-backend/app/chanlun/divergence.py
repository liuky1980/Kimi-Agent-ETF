"""
背驰检测模块
=============
缠论中的"背驰"是判断走势转折的核心工具。

背驰定义：
- 价格创新高/新低，但对应的技术指标（如MACD面积）未能同步创新高/新低
- 顶背驰（顶背离）：价格新高 + MACD面积缩小 → 卖出信号
- 底背驰（底背离）：价格新低 + MACD面积缩小 → 买入信号

本模块采用MACD面积法进行背驰检测，通过比较相邻两段走势的
价格变化与MACD面积变化来判断是否发生背驰。
"""

import logging
from typing import List, Optional

import numpy as np
import pandas as pd

from app.models.chanlun import DivergenceSignal, Segment

logger = logging.getLogger(__name__)


class DivergenceDetector:
    """背驰检测器

    使用MACD面积法检测价格与动能之间的背驰现象，
    为买卖点识别提供核心依据。
    """

    def __init__(self, sensitivity: float = 1.0):
        """
        Parameters
        ----------
        sensitivity : float
            检测灵敏度，越高越严格（默认1.0）
        """
        self.sensitivity = sensitivity

    def detect_divergence(
        self,
        prices: np.ndarray,
        macd_areas: np.ndarray,
        segments: List[Segment]
    ) -> DivergenceSignal:
        """检测背驰信号

        比较最近两段走势的价格变化与MACD面积变化。

        Parameters
        ----------
        prices : np.ndarray
            收盘价序列
        macd_areas : np.ndarray
            MACD面积累积序列
        segments : List[Segment]
            已识别的线段列表

        Returns
        -------
        DivergenceSignal
            背驰检测结果
        """
        if len(segments) < 2 or len(prices) < 2:
            return self._no_divergence()

        # 获取最近两段走势
        last_seg = segments[-1]
        prev_seg = segments[-2]

        # 获取两段对应的价格和MACD区域
        last_price_start = prices[min(last_seg.start_bi, len(prices) - 1)]
        last_price_end = prices[min(last_seg.end_bi, len(prices) - 1)]
        prev_price_start = prices[min(prev_seg.start_bi, len(prices) - 1)]
        prev_price_end = prices[min(prev_seg.end_bi, len(prices) - 1)]

        last_macd_start = macd_areas[min(last_seg.start_bi, len(macd_areas) - 1)]
        last_macd_end = macd_areas[min(last_seg.end_bi, len(macd_areas) - 1)]
        prev_macd_start = macd_areas[min(prev_seg.start_bi, len(macd_areas) - 1)]
        prev_macd_end = macd_areas[min(prev_seg.end_bi, len(macd_areas) - 1)]

        # 计算价格变化
        last_price_change = abs(last_price_end - last_price_start)
        prev_price_change = abs(prev_price_end - prev_price_start)

        # 计算MACD面积变化（取绝对值）
        last_macd_area = abs(last_macd_end - last_macd_start)
        prev_macd_area = abs(prev_macd_end - prev_macd_start)

        # 判断背驰类型
        if last_seg.direction == "up" and prev_seg.direction == "down":
            # 上升段 vs 下降段：检查顶背驰（价格新高但MACD不新高）
            is_divergence = self._check_bearish_divergence(
                last_price_change, prev_price_change,
                last_macd_area, prev_macd_area
            )
            if is_divergence:
                strength = self._calc_divergence_strength(
                    last_price_change, prev_price_change,
                    last_macd_area, prev_macd_area
                )
                return DivergenceSignal(
                    type="bearish",
                    strength=strength,
                    macd_area_current=round(last_macd_area, 4),
                    macd_area_previous=round(prev_macd_area, 4),
                    price_change_current=round(last_price_change, 3),
                    price_change_previous=round(prev_price_change, 3),
                    confidence=min(1.0, strength * 1.2),
                    description=f"顶背驰: 价格变动 {last_price_change:.2f} vs 前段 {prev_price_change:.2f}, "
                               f"MACD面积 {last_macd_area:.2f} vs 前段 {prev_macd_area:.2f}"
                )

        elif last_seg.direction == "down" and prev_seg.direction == "up":
            # 下降段 vs 上升段：检查底背驰（价格新低但MACD不新低）
            is_divergence = self._check_bullish_divergence(
                last_price_change, prev_price_change,
                last_macd_area, prev_macd_area
            )
            if is_divergence:
                strength = self._calc_divergence_strength(
                    last_price_change, prev_price_change,
                    last_macd_area, prev_macd_area
                )
                return DivergenceSignal(
                    type="bullish",
                    strength=strength,
                    macd_area_current=round(last_macd_area, 4),
                    macd_area_previous=round(prev_macd_area, 4),
                    price_change_current=round(last_price_change, 3),
                    price_change_previous=round(prev_price_change, 3),
                    confidence=min(1.0, strength * 1.2),
                    description=f"底背驰: 价格变动 {last_price_change:.2f} vs 前段 {prev_price_change:.2f}, "
                               f"MACD面积 {last_macd_area:.2f} vs 前段 {prev_macd_area:.2f}"
                )

        return self._no_divergence(
            last_macd_area, prev_macd_area,
            last_price_change, prev_price_change
        )

    def detect_from_macd(
        self,
        close_prices: pd.Series,
        macd_histogram: pd.Series,
        lookback_periods: int = 2
    ) -> DivergenceSignal:
        """基于MACD直方图直接检测背驰（简化方法）

        不需要线段，直接从价格和MACD柱状图判断背驰。

        Parameters
        ----------
        close_prices : pd.Series
            收盘价序列
        macd_histogram : pd.Series
            MACD柱状图值（DIF-DEA）
        lookback_periods : int
            回溯比较几个周期

        Returns
        -------
        DivergenceSignal
            背驰检测结果
        """
        if len(close_prices) < 20 or len(macd_histogram) < 20:
            return self._no_divergence()

        # 找到近期极值点
        window = 20
        recent_prices = close_prices.iloc[-window:]
        recent_macd = macd_histogram.iloc[-window:]

        # 价格极值
        price_max_idx = recent_prices.idxmax()
        price_min_idx = recent_prices.idxmin()
        price_max = recent_prices.max()
        price_min = recent_prices.min()

        # 对应位置的MACD
        macd_at_price_max = recent_macd.loc[price_max_idx]
        macd_at_price_min = recent_macd.loc[price_min_idx]

        # 检查顶背驰
        if len(close_prices) >= 40:
            prev_window = close_prices.iloc[-window*2:-window]
            prev_macd_window = macd_histogram.iloc[-window*2:-window]
            if len(prev_window) > 0:
                prev_price_max = prev_window.max()
                prev_macd_max = prev_macd_window.loc[prev_window.idxmax()]

                if price_max > prev_price_max and abs(macd_at_price_max) < abs(prev_macd_max) * 0.8:
                    strength = 0.5 + 0.3 * (1 - abs(macd_at_price_max) / (abs(prev_macd_max) + 1e-6))
                    return DivergenceSignal(
                        type="bearish",
                        strength=round(min(1.0, strength), 3),
                        macd_area_current=round(float(macd_at_price_max), 4),
                        macd_area_previous=round(float(prev_macd_max), 4),
                        price_change_current=round(float(price_max - prev_price_max), 3),
                        price_change_previous=0.0,
                        confidence=round(min(1.0, strength * 1.1), 3),
                        description="顶背驰: 价格创新高但MACD未能同步新高"
                    )

        # 检查底背驰
        if len(close_prices) >= 40:
            prev_window = close_prices.iloc[-window*2:-window]
            prev_macd_window = macd_histogram.iloc[-window*2:-window]
            if len(prev_window) > 0:
                prev_price_min = prev_window.min()
                prev_macd_min = prev_macd_window.loc[prev_window.idxmin()]

                if price_min < prev_price_min and abs(macd_at_price_min) < abs(prev_macd_min) * 0.8:
                    strength = 0.5 + 0.3 * (1 - abs(macd_at_price_min) / (abs(prev_macd_min) + 1e-6))
                    return DivergenceSignal(
                        type="bullish",
                        strength=round(min(1.0, strength), 3),
                        macd_area_current=round(float(macd_at_price_min), 4),
                        macd_area_previous=round(float(prev_macd_min), 4),
                        price_change_current=round(float(price_min - prev_price_min), 3),
                        price_change_previous=0.0,
                        confidence=round(min(1.0, strength * 1.1), 3),
                        description="底背驰: 价格创新低但MACD未能同步新低"
                    )

        return self._no_divergence(
            float(abs(macd_at_price_max)), float(abs(macd_at_price_min)),
            float(price_max), float(price_min)
        )

    def _check_bearish_divergence(
        self,
        last_price_change: float,
        prev_price_change: float,
        last_macd_area: float,
        prev_macd_area: float
    ) -> bool:
        """检查顶背驰

        条件：价格上升更多但MACD面积反而更小
        """
        # 价格需要创新高
        price_making_new_high = last_price_change >= prev_price_change * 0.8
        # MACD面积缩小（考虑灵敏度）
        macd_shrinking = last_macd_area < prev_macd_area * (1.0 - 0.1 * self.sensitivity)

        return price_making_new_high and macd_shrinking

    def _check_bullish_divergence(
        self,
        last_price_change: float,
        prev_price_change: float,
        last_macd_area: float,
        prev_macd_area: float
    ) -> bool:
        """检查底背驰

        条件：价格下降更多但MACD面积反而更小
        """
        # 价格需要创新低
        price_making_new_low = last_price_change >= prev_price_change * 0.8
        # MACD面积缩小（绝对值）
        macd_shrinking = last_macd_area < prev_macd_area * (1.0 - 0.1 * self.sensitivity)

        return price_making_new_low and macd_shrinking

    def _calc_divergence_strength(
        self,
        last_price_change: float,
        prev_price_change: float,
        last_macd_area: float,
        prev_macd_area: float
    ) -> float:
        """计算背驰强度

        Returns
        -------
        float
            0~1 的强度值
        """
        if prev_macd_area <= 0:
            return 0.5

        # MACD面积缩减比例
        macd_shrink_ratio = 1.0 - (last_macd_area / prev_macd_area)
        # 价格变动维持比例
        price_maintain_ratio = min(1.0, last_price_change / (prev_price_change + 1e-6))

        # 面积缩减越多、价格维持越强 → 背驰越强
        strength = 0.3 + macd_shrink_ratio * 0.5 + price_maintain_ratio * 0.2
        return round(min(1.0, max(0.0, strength)), 3)

    def _no_divergence(
        self,
        macd_current: float = 0.0,
        macd_previous: float = 0.0,
        price_current: float = 0.0,
        price_previous: float = 0.0
    ) -> DivergenceSignal:
        """返回无背驰信号"""
        return DivergenceSignal(
            type="none",
            strength=0.0,
            macd_area_current=round(macd_current, 4),
            macd_area_previous=round(macd_previous, 4),
            price_change_current=round(price_current, 3),
            price_change_previous=round(price_previous, 3),
            confidence=0.0,
            description="未检测到明显背驰信号"
        )
