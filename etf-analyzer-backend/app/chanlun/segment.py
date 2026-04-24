"""
线段划分模块
=============
线段是缠论中比笔更高一级的结构单元。

线段定义：
- 至少由3笔构成的走势结构
- 线段的起始和终止必须是顶/底分型
- 线段有明确的方向（上升线段/下降线段）
- 线段的结束需要被反向线段破坏才能确认

简化实现：基于笔序列自动构建线段，要求至少3笔构成一线段。
"""

import logging
from typing import List, Optional

from app.models.chanlun import BiStroke, Segment

logger = logging.getLogger(__name__)


class SegmentAnalyzer:
    """线段分析器

    将笔序列组合为线段，识别更高级别的走势结构。
    """

    def identify_segments(self, bi_list: List[BiStroke]) -> List[Segment]:
        """从笔序列中识别线段

        使用简化规则：
        1. 至少3笔构成一线段
        2. 线段方向由前3笔的方向决定
        3. 反向线段破坏当前线段时确认结束

        Parameters
        ----------
        bi_list : List[BiStroke]
            笔列表

        Returns
        -------
        List[Segment]
            线段列表
        """
        if len(bi_list) < 3:
            logger.warning("笔数量不足3根，无法构成线段")
            return []

        segments: List[Segment] = []
        start_idx = 0

        while start_idx < len(bi_list) - 2:
            # 取前3笔确定线段方向
            first_three = bi_list[start_idx:start_idx + 3]

            # 确定线段方向：由第一笔方向决定
            direction = first_three[0].direction

            # 找到线段的极值点
            if direction == "up":
                seg_high = max(b.high for b in first_three)
                seg_low = min(b.low for b in first_three)
                seg_start_price = first_three[0].start_price
                # 找到最高点对应的笔作为结束
                end_bi_offset = max(range(3), key=lambda i: first_three[i].high)
            else:
                seg_high = max(b.high for b in first_three)
                seg_low = min(b.low for b in first_three)
                seg_start_price = first_three[0].start_price
                end_bi_offset = max(range(3), key=lambda i: -first_three[i].low)

            end_bi_idx = start_idx + end_bi_offset

            # 尝试延伸线段：向后查找同方向的笔
            current_end = end_bi_idx
            for i in range(end_bi_idx + 1, len(bi_list)):
                if bi_list[i].direction == direction:
                    # 同方向笔可以延伸线段
                    if direction == "up" and bi_list[i].high > seg_high:
                        seg_high = bi_list[i].high
                        current_end = i
                    elif direction == "down" and bi_list[i].low < seg_low:
                        seg_low = bi_list[i].low
                        current_end = i
                else:
                    # 反向笔出现，检查是否破坏线段
                    if self._is_segment_broken(bi_list, start_idx, current_end, i):
                        break
                    else:
                        # 未破坏，继续延伸
                        current_end = i

            # 创建线段（确保至少3笔）
            bi_count = current_end - start_idx + 1
            if bi_count < 3:
                logger.warning(f"笔数量不足{bi_count}根，跳过线段创建")
                start_idx = current_end + 1
                continue

            segment = Segment(
                start_bi=start_idx,
                end_bi=current_end,
                direction=direction,
                start_price=round(seg_start_price, 3),
                end_price=round(bi_list[current_end].end_price, 3),
                high=round(seg_high, 3),
                low=round(seg_low, 3),
                bi_count=bi_count
            )
            segments.append(segment)

            # 下一线段从当前线段结束后开始
            start_idx = current_end + 1

        logger.info(f"线段划分完成: 共 {len(segments)} 条线段")
        return segments

    def _is_segment_broken(
        self,
        bi_list: List[BiStroke],
        seg_start: int,
        seg_end: int,
        reverse_bi_idx: int
    ) -> bool:
        """判断线段是否被反向笔破坏

        简化判断：反向笔突破了当前线段的起点/终点

        Parameters
        ----------
        bi_list : List[BiStroke]
            笔列表
        seg_start : int
            线段起始笔索引
        seg_end : int
            线段结束笔索引
        reverse_bi_idx : int
            反向笔索引

        Returns
        -------
        bool
            是否被破坏
        """
        if reverse_bi_idx >= len(bi_list):
            return False

        reverse_bi = bi_list[reverse_bi_idx]
        segment_bi = bi_list[seg_start:seg_end + 1]

        if not segment_bi:
            return False

        seg_direction = segment_bi[0].direction

        if seg_direction == "up":
            # 上升线段被向下笔破坏：低点低于线段起点
            return reverse_bi.low < segment_bi[0].start_price
        else:
            # 下降线段被向上笔破坏：高点高于线段起点
            return reverse_bi.high > segment_bi[0].start_price

    def get_current_segment(self, segments: List[Segment]) -> Optional[Segment]:
        """获取当前活跃线段

        Parameters
        ----------
        segments : List[Segment]
            线段列表

        Returns
        -------
        Optional[Segment]
            最新线段
        """
        return segments[-1] if segments else None

    def get_trend_direction(self, segments: List[Segment]) -> str:
        """基于线段判断趋势方向

        Parameters
        ----------
        segments : List[Segment]
            线段列表

        Returns
        -------
        str
            'up', 'down', 或 'consolidation'
        """
        if not segments:
            return "unknown"

        if len(segments) >= 3:
            # 比较最近两段的价格变化
            last_seg = segments[-1]
            prev_seg = segments[-2]

            if last_seg.direction == "up" and prev_seg.direction == "down":
                if last_seg.end_price > prev_seg.start_price:
                    return "up"
            elif last_seg.direction == "down" and prev_seg.direction == "up":
                if last_seg.end_price < prev_seg.start_price:
                    return "down"

        return segments[-1].direction
