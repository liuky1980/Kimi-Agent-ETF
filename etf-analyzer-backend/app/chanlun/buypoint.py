"""
买卖点识别模块
===============
基于缠论定义的三类买卖点识别系统。

缠论买卖点体系：

第一类买卖点（一买/一卖）：
- 一买：趋势背驰后的转折点，至少经历2个中枢后的底背驰
- 一卖：趋势背驰后的转折点，至少经历2个中枢后的顶背驰

第二类买卖点（二买/二卖）：
- 二买：一买后回调不创新低的位置
- 二卖：一卖后反弹不创新高的位置

第三类买卖点（三买/三卖）：
- 三买：向上突破中枢后回调不回到中枢
- 三卖：向下跌破中枢后反弹不回到中枢

本模块基于中枢和背驰检测结果，识别上述三类买卖点。
"""

import logging
from typing import List, Optional

from app.models.chanlun import BuySellPoint, Center, DivergenceSignal

logger = logging.getLogger(__name__)


class BuyPointDetector:
    """买卖点检测器

    基于中枢结构、背驰信号和当前价格位置，
    识别缠论定义的三类买卖点。
    """

    def __init__(self):
        self._recent_buy_point: Optional[float] = None  # 记录最近一买价格
        self._recent_sell_point: Optional[float] = None  # 记录最近一卖价格

    def detect_buy_points(
        self,
        centers: List[Center],
        divergence: DivergenceSignal,
        current_price: float,
        bi_direction: str = ""
    ) -> List[BuySellPoint]:
        """识别买卖点

        Parameters
        ----------
        centers : List[Center]
            中枢列表
        divergence : DivergenceSignal
            背驰检测结果
        current_price : float
            当前价格
        bi_direction : str
            当前笔方向

        Returns
        -------
        List[BuySellPoint]
            识别的买卖点列表
        """
        points: List[BuySellPoint] = []

        # 1. 识别第一类买卖点（基于背驰）
        first_class = self._detect_first_class(centers, divergence, current_price)
        if first_class:
            points.append(first_class)
            if first_class.type == "一买":
                self._recent_buy_point = first_class.price
            elif first_class.type == "一卖":
                self._recent_sell_point = first_class.price

        # 2. 识别第二类买卖点（基于一买/一卖后的回调）
        second_class = self._detect_second_class(centers, current_price, bi_direction)
        if second_class:
            points.append(second_class)

        # 3. 识别第三类买卖点（基于中枢突破）
        third_class = self._detect_third_class(centers, current_price)
        if third_class:
            points.append(third_class)

        # 按置信度排序
        points.sort(key=lambda p: p.confidence, reverse=True)

        logger.info(f"买卖点识别完成: 共 {len(points)} 个信号")
        return points

    def _detect_first_class(
        self,
        centers: List[Center],
        divergence: DivergenceSignal,
        current_price: float
    ) -> Optional[BuySellPoint]:
        """识别第一类买卖点

        条件：
        - 至少2个中枢构成的趋势
        - 趋势背驰（底背驰/顶背驰）

        Parameters
        ----------
        centers : List[Center]
            中枢列表
        divergence : DivergenceSignal
            背驰信号
        current_price : float
            当前价格

        Returns
        -------
        Optional[BuySellPoint]
            第一类买卖点，不满足条件则返回None
        """
        # 需要至少2个中枢才可能是趋势背驰
        if len(centers) < 1:
            return None

        # 活跃中枢
        active = centers[-1] if centers else None

        if divergence.type == "bullish" and divergence.strength > 0.3:
            # 底背驰 → 一买
            confidence = divergence.confidence * min(1.0, len(centers) / 3)
            return BuySellPoint(
                type="一买",
                bs_type="buy",
                price=round(current_price, 3),
                confidence=round(confidence, 3),
                trigger_date=active.start_date if active else "",
                description=f"底背驰形成第一类买点，背驰强度 {divergence.strength:.2f}, "
                           f"中枢数量 {len(centers)}, MACD面积缩减"
            )

        elif divergence.type == "bearish" and divergence.strength > 0.3:
            # 顶背驰 → 一卖
            confidence = divergence.confidence * min(1.0, len(centers) / 3)
            return BuySellPoint(
                type="一卖",
                bs_type="sell",
                price=round(current_price, 3),
                confidence=round(confidence, 3),
                trigger_date=active.start_date if active else "",
                description=f"顶背驰形成第一类卖点，背驰强度 {divergence.strength:.2f}, "
                           f"中枢数量 {len(centers)}, MACD面积缩减"
            )

        return None

    def _detect_second_class(
        self,
        centers: List[Center],
        current_price: float,
        bi_direction: str
    ) -> Optional[BuySellPoint]:
        """识别第二类买卖点

        条件：
        - 二买：一买之后回调不创新低
        - 二卖：一卖之后反弹不创新高

        简化实现：基于中枢区间和笔方向判断

        Parameters
        ----------
        centers : List[Center]
            中枢列表
        current_price : float
            当前价格
        bi_direction : str
            当前笔方向

        Returns
        -------
        Optional[BuySellPoint]
            第二类买卖点
        """
        if not centers:
            return None

        active = centers[-1]

        # 二买条件：当前价格在 中枢下轨附近，笔方向向上，有过底背驰记录
        if bi_direction == "up" and self._recent_buy_point is not None:
            # 价格在中枢下轨附近但未跌破前低
            if active.zd * 0.98 <= current_price <= active.zd * 1.05:
                if current_price >= self._recent_buy_point * 0.98:
                    return BuySellPoint(
                        type="二买",
                        bs_type="buy",
                        price=round(current_price, 3),
                        confidence=0.6,
                        trigger_date="",
                        description=f"回调未创新低，中枢下轨 {active.zd:.2f} 附近形成第二类买点"
                    )

        # 二卖条件
        if bi_direction == "down" and self._recent_sell_point is not None:
            if active.zg * 0.95 <= current_price <= active.zg * 1.02:
                if current_price <= self._recent_sell_point * 1.02:
                    return BuySellPoint(
                        type="二卖",
                        bs_type="sell",
                        price=round(current_price, 3),
                        confidence=0.6,
                        trigger_date="",
                        description=f"反弹未创新高，中枢上轨 {active.zg:.2f} 附近形成第二类卖点"
                    )

        return None

    def _detect_third_class(
        self,
        centers: List[Center],
        current_price: float
    ) -> Optional[BuySellPoint]:
        """识别第三类买卖点

        条件：
        - 三买：向上突破中枢后回调不回到中枢内
        - 三卖：向下跌破中枢后反弹不回到中枢内

        Parameters
        ----------
        centers : List[Center]
            中枢列表
        current_price : float
            当前价格

        Returns
        -------
        Optional[BuySellPoint]
            第三类买卖点
        """
        if not centers:
            return None

        # 查找最近已结束的中枢（用于判断三买/三卖）
        closed_centers = [c for c in centers if c.status == "closed"]
        if not closed_centers:
            # 用活跃中枢的边界作为参考
            active = centers[-1]
            # 三买：价格向上突破中枢上轨
            if current_price > active.zg * 1.01:
                return BuySellPoint(
                    type="三买",
                    bs_type="buy",
                    price=round(current_price, 3),
                    confidence=0.55,
                    trigger_date="",
                    description=f"价格 {current_price:.2f} 向上突破中枢上轨 {active.zg:.2f}，"
                               f"若回调不回到中枢则确认第三类买点"
                )
            # 三卖：价格向下突破中枢下轨
            if current_price < active.zd * 0.99:
                return BuySellPoint(
                    type="三卖",
                    bs_type="sell",
                    price=round(current_price, 3),
                    confidence=0.55,
                    trigger_date="",
                    description=f"价格 {current_price:.2f} 向下跌破中枢下轨 {active.zd:.2f}，"
                               f"若反弹不回到中枢则确认第三类卖点"
                )
            return None

        # 使用最近已结束中枢
        last_closed = closed_centers[-1]

        # 三买判断
        if current_price > last_closed.zg * 1.02:
            return BuySellPoint(
                type="三买",
                bs_type="buy",
                price=round(current_price, 3),
                confidence=0.65,
                trigger_date="",
                description=f"价格突破中枢上轨 {last_closed.zg:.2f} 后未回落，"
                           f"第三类买点确认"
            )

        # 三卖判断
        if current_price < last_closed.zd * 0.98:
            return BuySellPoint(
                type="三卖",
                bs_type="sell",
                price=round(current_price, 3),
                confidence=0.65,
                trigger_date="",
                description=f"价格跌破中枢下轨 {last_closed.zd:.2f} 后未回升，"
                           f"第三类卖点确认"
            )

        return None

    def get_primary_signal(self, points: List[BuySellPoint]) -> Optional[str]:
        """获取主要买卖信号

        Parameters
        ----------
        points : List[BuySellPoint]
            买卖点列表

        Returns
        -------
        Optional[str]
            主要信号描述
        """
        if not points:
            return None
        return points[0].type
