"""
中枢识别模块
=============
缠论中的"中枢"是指连续3笔以上重叠的价格区间，
是走势分析的核心概念。

中枢定义：
- 至少3笔的价格重叠区域
- 中枢区间 [ZD, ZG]，其中 ZG = min(各笔高点), ZD = max(各笔低点)
- 中枢有方向、级别和状态（活跃/已结束）
- 中枢的结束需要被第三类买卖点确认

中枢的识别对于判断趋势、寻找买卖点至关重要。
"""

import logging
from typing import List, Optional, Tuple

import numpy as np

from app.config import settings
from app.models.chanlun import BiStroke, Center

logger = logging.getLogger(__name__)


class CenterAnalyzer:
    """中枢分析器

    负责从笔序列中识别中枢，判断中枢状态，
    并提供中枢相关的分析辅助方法。
    """

    def __init__(self, min_overlap: int = None):
        """
        Parameters
        ----------
        min_overlap : int
            构成中枢的最少重叠笔数，默认3笔
        """
        self.min_overlap = min_overlap or settings.CHANLUN_CENTER_OVERLAP

    def find_centers(
        self,
        bi_list: List[BiStroke],
        dates: Optional[List[str]] = None
    ) -> List[Center]:
        """从笔序列中识别中枢

        采用滑动窗口方法，检查连续N笔是否有重叠区间。

        Parameters
        ----------
        bi_list : List[BiStroke]
            笔列表
        dates : Optional[List[str]]
            日期序列，用于记录中枢时间

        Returns
        -------
        List[Center]
            中枢列表
        """
        if len(bi_list) < self.min_overlap:
            logger.warning(f"笔数量不足 {self.min_overlap} 根，无法形成中枢")
            return []

        if dates is None:
            dates = [str(i) for i in range(len(bi_list))]

        centers: List[Center] = []
        i = 0

        while i <= len(bi_list) - self.min_overlap:
            # 取连续N笔检查重叠
            window = bi_list[i:i + self.min_overlap]

            overlap = self._check_overlap(window)
            if overlap is not None:
                zg, zd = overlap  # zg=上轨, zd=下轨

                # 找到中枢的结束位置（向后延伸）
                end_bi = i + self.min_overlap - 1
                for j in range(i + self.min_overlap, len(bi_list)):
                    extended_window = bi_list[i:j + 1]
                    extended_overlap = self._check_overlap(extended_window)
                    if extended_overlap is not None:
                        zg, zd = extended_overlap
                        end_bi = j
                    else:
                        break

                # 创建中枢
                center = Center(
                    start_bi=i,
                    end_bi=end_bi,
                    zg=round(zg, 3),
                    zd=round(zd, 3),
                    level=1,  # 简化实现，默认1级中枢
                    start_date=dates[bi_list[i].start_index] if bi_list[i].start_index < len(dates) else "",
                    end_date=dates[bi_list[end_bi].end_index] if bi_list[end_bi].end_index < len(dates) else None,
                    status="active" if end_bi == len(bi_list) - 1 else "closed"
                )
                centers.append(center)

                # 跳过已使用的笔
                i = end_bi + 1
            else:
                i += 1

        # 标记最后一个活跃中枢
        if centers:
            for c in centers[:-1]:
                c.status = "closed"
            centers[-1].status = "active"

        logger.info(f"中枢识别完成: 共 {len(centers)} 个中枢")
        return centers

    def _check_overlap(self, bi_window: List[BiStroke]) -> Optional[Tuple[float, float]]:
        """检查笔窗口是否有重叠区间

        Parameters
        ----------
        bi_window : List[BiStroke]
            笔序列窗口

        Returns
        -------
        Optional[Tuple[float, float]]
            (ZG, ZD) 重叠区间，如果没有重叠则返回None
        """
        if len(bi_window) < self.min_overlap:
            return None

        # ZG = 各笔低点的最大值 (中枢上轨)
        # ZD = 各笔高点的最小值 (中枢下轨)
        zd = max(b.low for b in bi_window)   # 下轨
        zg = min(b.high for b in bi_window)  # 上轨

        # 有重叠的条件：上轨 > 下轨
        if zg > zd:
            return (zg, zd)
        return None

    def get_active_center(self, centers: List[Center]) -> Optional[Center]:
        """获取当前活跃中枢

        Parameters
        ----------
        centers : List[Center]
            中枢列表

        Returns
        -------
        Optional[Center]
            当前活跃中枢，如果没有则返回None
        """
        if not centers:
            return None
        return centers[-1] if centers[-1].status == "active" else None

    def get_center_range(self, centers: List[Center]) -> Tuple[float, float]:
        """获取最新中枢区间

        Parameters
        ----------
        centers : List[Center]
            中枢列表

        Returns
        -------
        Tuple[float, float]
            (ZD, ZG) 区间
        """
        if not centers:
            return (0.0, 0.0)
        latest = centers[-1]
        return (latest.zd, latest.zg)

    def calculate_center_strength(self, center: Center) -> float:
        """计算中枢强度

        中枢越窄（ZG-ZD越小），重叠笔越多，强度越高。

        Parameters
        ----------
        center : Center
            中枢对象

        Returns
        -------
        float
            强度值 0~1
        """
        if center.zg <= center.zd:
            return 0.0

        width = center.zg - center.zd
        mid_price = (center.zg + center.zd) / 2
        relative_width = width / mid_price if mid_price > 0 else 1.0

        # 相对宽度越小，强度越高
        strength = max(0.0, min(1.0, 1.0 - relative_width * 10))
        return round(strength, 3)

    def is_price_in_center(self, price: float, center: Center) -> bool:
        """判断价格是否在中枢区间内

        Parameters
        ----------
        price : float
            当前价格
        center : Center
            中枢

        Returns
        -------
        bool
            是否在区间内
        """
        return center.zd <= price <= center.zg

    def calculate_center_stats(self, centers: List[Center]) -> dict:
        """计算中枢统计信息

        Parameters
        ----------
        centers : List[Center]
            中枢列表

        Returns
        -------
        dict
            统计信息
        """
        if not centers:
            return {"count": 0}

        widths = [c.zg - c.zd for c in centers]
        active = sum(1 for c in centers if c.status == "active")

        return {
            "count": len(centers),
            "active": active,
            "closed": len(centers) - active,
            "avg_width": round(sum(widths) / len(widths), 3),
            "max_width": round(max(widths), 3),
            "min_width": round(min(widths), 3),
            "avg_bi_count": sum(c.end_bi - c.start_bi + 1 for c in centers) / len(centers),
        }
