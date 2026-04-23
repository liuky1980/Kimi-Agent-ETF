"""
笔划分模块
===========
根据缠论定义，将相邻的顶分型和底分型连接成"笔"（笔/pen strokes）。

笔的划分规则：
1. 相邻的顶分型和底分型可以连接成一笔
2. 顶分型连接到底分型构成"向下笔"
3. 底分型连接到顶分型构成"向上笔"
4. 两分型之间至少需要 min_klines 根独立K线（默认5根）
5. 后续分型必须突破前一笔的终点才能形成新笔
6. 笔之间不能重叠（新笔起点必须在前一笔终点之后）
"""

import logging
from typing import List, Optional, Tuple

import numpy as np
import pandas as pd

from app.config import settings
from app.models.chanlun import BiStroke, FractalPoint

logger = logging.getLogger(__name__)


class BiAnalyzer:
    """笔分析器

    负责将分型序列转化为笔序列，实现缠论笔划分规则。
    """

    def __init__(self, min_klines: int = None):
        """
        Parameters
        ----------
        min_klines : int
            两分型间最小K线间隔，默认从配置读取（5根）
        """
        self.min_klines = min_klines or settings.CHANLUN_MIN_KLINES

    def identify_bi(
        self,
        fractals: List[FractalPoint],
        prices: np.ndarray,
        dates: Optional[List[str]] = None
    ) -> List[BiStroke]:
        """识别笔序列

        将分型列表按缠论规则连接成笔。

        Parameters
        ----------
        fractals : List[FractalPoint]
            分型点列表（已合并顶底分型）
        prices : np.ndarray
            收盘价序列，用于辅助判断
        dates : Optional[List[str]]
            日期序列

        Returns
        -------
        List[BiStroke]
            笔列表
        """
        if len(fractals) < 2:
            logger.warning("分型数量不足2个，无法形成笔")
            return []

        if dates is None:
            dates = [str(i) for i in range(len(prices))]

        # 合并并按索引排序
        sorted_fractals = sorted(fractals, key=lambda f: f.index)

        bi_list: List[BiStroke] = []
        last_bi: Optional[BiStroke] = None

        i = 0
        while i < len(sorted_fractals) - 1:
            current = sorted_fractals[i]
            next_f = sorted_fractals[i + 1]

            # 规则1: 分型类型必须交替（顶->底 或 底->顶）
            if current.type == next_f.type:
                i += 1
                continue

            # 规则2: 两分型间至少 min_klines 根独立K线
            kline_gap = next_f.index - current.index - 1
            if kline_gap < self.min_klines:
                i += 1
                continue

            # 规则3: 新笔必须沿正确方向
            if current.type == "top" and next_f.type == "bottom":
                direction = "down"
            elif current.type == "bottom" and next_f.type == "top":
                direction = "up"
            else:
                i += 1
                continue

            # 规则4: 如果已有笔，新笔起点必须在上一笔终点之后
            if last_bi is not None and current.index <= last_bi.end_index:
                i += 1
                continue

            # 规则5: 价格必须实际移动（排除平走震荡中的无效笔）
            if direction == "down" and next_f.price >= current.price:
                i += 1
                continue
            if direction == "up" and next_f.price <= current.price:
                i += 1
                continue

            # 获取笔内价格极值
            start_idx = current.index
            end_idx = next_f.index
            segment_prices = prices[start_idx:end_idx + 1]

            if len(segment_prices) == 0:
                i += 1
                continue

            if direction == "up":
                bi_high = float(np.max(segment_prices))
                bi_low = float(current.price)
            else:
                bi_high = float(current.price)
                bi_low = float(np.min(segment_prices))

            bi = BiStroke(
                start_index=start_idx,
                end_index=end_idx,
                start_date=dates[start_idx] if start_idx < len(dates) else "",
                end_date=dates[end_idx] if end_idx < len(dates) else "",
                direction=direction,
                start_price=round(float(current.price), 3),
                end_price=round(float(next_f.price), 3),
                high=round(bi_high, 3),
                low=round(bi_low, 3),
                kline_count=end_idx - start_idx + 1
            )

            bi_list.append(bi)
            last_bi = bi
            i += 1

        # 后处理：合并过于短的笔
        bi_list = self._postprocess_bi(bi_list)

        logger.info(f"笔划分完成: 共 {len(bi_list)} 笔")
        return bi_list

    def _postprocess_bi(self, bi_list: List[BiStroke]) -> List[BiStroke]:
        """笔后处理

        合并过短的笔，确保笔序列的稳定性。

        Parameters
        ----------
        bi_list : List[BiStroke]
            原始笔列表

        Returns
        -------
        List[BiStroke]
            处理后的笔列表
        """
        if len(bi_list) <= 2:
            return bi_list

        processed = []
        i = 0
        while i < len(bi_list):
            current = bi_list[i]

            # 检查是否需要与下一笔合并（方向相同且过短）
            if i < len(bi_list) - 1 and current.direction == bi_list[i + 1].direction:
                next_bi = bi_list[i + 1]
                merged = BiStroke(
                    start_index=current.start_index,
                    end_index=next_bi.end_index,
                    start_date=current.start_date,
                    end_date=next_bi.end_date,
                    direction=current.direction,
                    start_price=current.start_price,
                    end_price=next_bi.end_price,
                    high=round(max(current.high, next_bi.high), 3),
                    low=round(min(current.low, next_bi.low), 3),
                    kline_count=next_bi.end_index - current.start_index + 1
                )
                processed.append(merged)
                i += 2
            else:
                processed.append(current)
                i += 1

        return processed

    def get_current_bi(self, bi_list: List[BiStroke]) -> Optional[BiStroke]:
        """获取当前（最新）笔

        Parameters
        ----------
        bi_list : List[BiStroke]
            笔列表

        Returns
        -------
        Optional[BiStroke]
            最新笔，如果没有则返回None
        """
        if not bi_list:
            return None
        return bi_list[-1]

    def get_direction(self, bi_list: List[BiStroke]) -> str:
        """获取当前笔方向

        Parameters
        ----------
        bi_list : List[BiStroke]
            笔列表

        Returns
        -------
        str
            'up', 'down', 或 'unknown'
        """
        current = self.get_current_bi(bi_list)
        if current is None:
            return "unknown"
        return current.direction

    def calculate_bi_stats(self, bi_list: List[BiStroke]) -> dict:
        """计算笔的统计信息

        Parameters
        ----------
        bi_list : List[BiStroke]
            笔列表

        Returns
        -------
        dict
            统计信息字典
        """
        if not bi_list:
            return {"count": 0}

        up_bi = [b for b in bi_list if b.direction == "up"]
        down_bi = [b for b in bi_list if b.direction == "down"]

        return {
            "count": len(bi_list),
            "up_count": len(up_bi),
            "down_count": len(down_bi),
            "current_direction": bi_list[-1].direction,
            "avg_length": sum(b.end_index - b.start_index for b in bi_list) / len(bi_list),
            "total_up": sum(b.end_price - b.start_price for b in up_bi) if up_bi else 0,
            "total_down": sum(b.start_price - b.end_price for b in down_bi) if down_bi else 0,
        }
