"""
分型识别模块
=============
基于缠论定义的价格分型识别，从K线序列中找出顶分型和底分型。

分型定义（严格定义）：
- 顶分型: 中间K线的高点高于左右两侧K线的高点，且中间K线的低点也高于左右两侧K线的低点
- 底分型: 中间K线的低点低于左右两侧K线的低点，且中间K线的高点也低于左右两侧K线的高点

实现采用宽松分型与严格分型两种模式，默认使用严格分型。
"""

import logging
from typing import List, Optional, Tuple

import numpy as np
import pandas as pd

from app.models.chanlun import FractalPoint

logger = logging.getLogger(__name__)


def find_fractals(
    highs: np.ndarray,
    lows: np.ndarray,
    dates: Optional[List[str]] = None,
    strict: bool = True
) -> Tuple[List[FractalPoint], List[FractalPoint]]:
    """分型识别主函数

    从K线高低点序列中识别顶分型和底分型。
    严格模式下要求中间K线的high和low都满足条件；
    宽松模式下仅要求high条件满足即可判断顶分型。

    Parameters
    ----------
    highs : np.ndarray
        K线高点序列
    lows : np.ndarray
        K线低点序列
    dates : Optional[List[str]]
        对应的日期时间字符串列表
    strict : bool
        是否使用严格分型定义，默认True

    Returns
    -------
    Tuple[List[FractalPoint], List[FractalPoint]]
        (顶分型列表, 底分型列表)
    """
    n = len(highs)
    if n < 3:
        logger.warning("K线数量不足3根，无法识别分型")
        return [], []

    if dates is None:
        dates = [str(i) for i in range(n)]

    top_fractals: List[FractalPoint] = []
    bottom_fractals: List[FractalPoint] = []

    for i in range(1, n - 1):
        left_high = highs[i - 1]
        mid_high = highs[i]
        right_high = highs[i + 1]

        left_low = lows[i - 1]
        mid_low = lows[i]
        right_low = lows[i + 1]

        # 顶分型判断
        is_top = mid_high > left_high and mid_high > right_high
        if strict:
            is_top = is_top and mid_low > left_low and mid_low > right_low

        if is_top:
            confidence = _calc_fractal_confidence(
                mid_high, left_high, right_high, mid_low, left_low, right_low, "top"
            )
            top_fractals.append(FractalPoint(
                index=i,
                date=dates[i],
                price=round(float(mid_high), 3),
                type="top",
                confidence=confidence
            ))

        # 底分型判断
        is_bottom = mid_low < left_low and mid_low < right_low
        if strict:
            is_bottom = is_bottom and mid_high < left_high and mid_high < right_high

        if is_bottom:
            confidence = _calc_fractal_confidence(
                mid_high, left_high, right_high, mid_low, left_low, right_low, "bottom"
            )
            bottom_fractals.append(FractalPoint(
                index=i,
                date=dates[i],
                price=round(float(mid_low), 3),
                type="bottom",
                confidence=confidence
            ))

    # 过滤相邻的重复分型（保留更极端的那个）
    top_fractals = _filter_adjacent_fractals(top_fractals)
    bottom_fractals = _filter_adjacent_fractals(bottom_fractals)

    logger.info(
        f"分型识别完成: 顶分型 {len(top_fractals)} 个, 底分型 {len(bottom_fractals)} 个 "
        f"(严格模式={strict})"
    )
    return top_fractals, bottom_fractals


def _calc_fractal_confidence(
    mid_high: float, left_high: float, right_high: float,
    mid_low: float, left_low: float, right_low: float,
    ftype: str
) -> float:
    """计算分型置信度

    基于中间K线与两侧K线的价格差距比例计算。
    差距越大，分型越明确，置信度越高。

    Parameters
    ----------
    ftype : str
        'top' 或 'bottom'

    Returns
    -------
    float
        置信度 0~1
    """
    try:
        if ftype == "top":
            avg_neighbor_high = (left_high + right_high) / 2
            if avg_neighbor_high <= 0:
                return 0.5
            # 中间高点比邻居高出的比例
            spread_ratio = (mid_high - avg_neighbor_high) / avg_neighbor_high
            # 同时考虑低点的支撑
            low_spread = (mid_low - min(left_low, right_low)) / mid_low if mid_low > 0 else 0
            return min(1.0, 0.5 + spread_ratio * 10 + low_spread * 2)
        else:
            avg_neighbor_low = (left_low + right_low) / 2
            if avg_neighbor_low <= 0:
                return 0.5
            spread_ratio = (avg_neighbor_low - mid_low) / avg_neighbor_low
            high_spread = (min(left_high, right_high) - mid_high) / mid_high if mid_high > 0 else 0
            return min(1.0, 0.5 + spread_ratio * 10 + high_spread * 2)
    except Exception:
        return 0.5


def _filter_adjacent_fractals(fractals: List[FractalPoint], min_gap: int = 1) -> List[FractalPoint]:
    """过滤相邻重复的分型

    当两个同类型分型距离太近时，保留更极端（价格更高/更低）的那个。

    Parameters
    ----------
    fractals : List[FractalPoint]
        分型列表
    min_gap : int
        最小间隔K线数

    Returns
    -------
    List[FractalPoint]
        过滤后的分型列表
    """
    if len(fractals) <= 1:
        return fractals

    filtered = []
    i = 0
    while i < len(fractals):
        current = fractals[i]
        # 查找相邻的同类分型
        cluster = [current]
        j = i + 1
        while j < len(fractals) and fractals[j].index - cluster[-1].index <= min_gap:
            cluster.append(fractals[j])
            j += 1

        # 保留最极端的
        if current.type == "top":
            best = max(cluster, key=lambda f: f.price)
        else:
            best = min(cluster, key=lambda f: f.price)

        filtered.append(best)
        i = j

    return filtered


class FractalFinder:
    """分型查找器类

    封装分型识别功能，提供DataFrame直接接口。
    """

    def find(self, df: pd.DataFrame, strict: bool = True) -> Tuple[List[FractalPoint], List[FractalPoint]]:
        """从DataFrame中识别分型

        Parameters
        ----------
        df : pd.DataFrame
            包含 'high', 'low' 列的K线数据
        strict : bool
            是否严格模式

        Returns
        -------
        Tuple[List[FractalPoint], List[FractalPoint]]
            (顶分型, 底分型)
        """
        highs = df['high'].values
        lows = df['low'].values
        dates = df['date'].astype(str).tolist() if 'date' in df.columns else None
        return find_fractals(highs, lows, dates, strict)

    def get_latest_fractal(
        self,
        df: pd.DataFrame,
        strict: bool = True,
        lookback: int = 10
    ) -> Optional[FractalPoint]:
        """获取最近的活跃分型

        Parameters
        ----------
        df : pd.DataFrame
            K线数据
        strict : bool
            是否严格模式
        lookback : int
            向前查找的K线数量

        Returns
        -------
        Optional[FractalPoint]
            最近的分型点，如果没有则返回None
        """
        tops, bottoms = self.find(df.iloc[-lookback-2:], strict)
        all_fractals = sorted(tops + bottoms, key=lambda f: f.index)
        if not all_fractals:
            return None
        return all_fractals[-1]
