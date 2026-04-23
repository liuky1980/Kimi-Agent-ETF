"""
多周期共振分析模块
===================
缠论多周期共振分析，通过对比不同时间周期的信号一致性，
提高交易决策的可靠性。

多周期共振体系：
- 日线周期：确定大趋势方向
- 30分钟周期：识别结构、中枢和买卖点
- 5分钟周期：精确入场时机

共振等级：
- Strong (90-100): 三周期完全一致
- Medium-Strong (70-89): 两周期一致
- Medium (50-69): 结构清晰但存在分歧
- Weak (<50): 单周期信号，不确定性高
"""

import logging
from typing import Dict, List, Optional

import numpy as np

from app.config import settings
from app.models.chanlun import (
    BiStroke,
    Center,
    DivergenceSignal,
    ResonanceResult,
    TimeframeSignal,
)

logger = logging.getLogger(__name__)


class ResonanceAnalyzer:
    """共振分析器

    对不同时间周期的缠论分析结果进行综合评估，
    判断多周期共振程度和交易信号可靠性。
    """

    def __init__(self):
        self.threshold = settings.CHANLUN_RESonance_THRESHOlD

    def calculate_resonance(
        self,
        daily_signal: Dict,
        min30_signal: Dict,
        min5_signal: Dict
    ) -> ResonanceResult:
        """计算多周期共振

        Parameters
        ----------
        daily_signal : dict
            日线周期分析结果，包含 trend, confidence, centers, divergence, bs_point
        min30_signal : dict
            30分钟周期分析结果
        min5_signal : dict
            5分钟周期分析结果

        Returns
        -------
        ResonanceResult
            共振分析结果
        """
        # 构建单周期信号
        daily = self._parse_signal(daily_signal, "daily")
        min30 = self._parse_signal(min30_signal, "30min")
        min5 = self._parse_signal(min5_signal, "5min")

        # 计算各周期独立得分
        daily_score = self._score_timeframe(daily)
        min30_score = self._score_timeframe(min30)
        min5_score = self._score_timeframe(min5)

        daily.resonance_score = daily_score
        min30.resonance_score = min30_score
        min5.resonance_score = min5_score

        # 计算综合共振得分
        composite = self._calc_composite_score(daily, min30, min5)

        # 确定共振等级
        level, alignment = self._determine_level(daily, min30, min5, composite)

        # 生成建议
        recommendation = self._generate_recommendation(daily, min30, min5, composite, level)

        return ResonanceResult(
            daily=daily,
            min30=min30,
            min5=min5,
            composite_score=round(composite, 1),
            level=level,
            alignment=alignment,
            recommendation=recommendation
        )

    def calculate_simple_resonance(
        self,
        daily_trend: str,
        min30_trend: str,
        min5_trend: str,
        daily_divergence: bool = False,
        min30_divergence: bool = False,
        min5_divergence: bool = False
    ) -> dict:
        """简化版共振计算（用于快速评估）

        Parameters
        ----------
        daily_trend, min30_trend, min5_trend : str
            各周期趋势方向 'up'/'down'/'consolidation'
        daily_divergence, min30_divergence, min5_divergence : bool
            各周期是否有背驰

        Returns
        -------
        dict
            简化共振结果
        """
        trends = [daily_trend, min30_trend, min5_trend]
        divergences = [daily_divergence, min30_divergence, min5_divergence]

        # 趋势一致性
        up_count = sum(1 for t in trends if t == "up")
        down_count = sum(1 for t in trends if t == "down")
        consolidation_count = sum(1 for t in trends if t == "consolidation")

        # 共振得分
        if up_count == 3 or down_count == 3:
            base_score = 95
        elif up_count >= 2 or down_count >= 2:
            base_score = 80
        elif up_count >= 1 or down_count >= 1:
            base_score = 60
        else:
            base_score = 40

        # 背驰加分
        divergence_bonus = sum(divergences) * 5
        composite = min(100, base_score + divergence_bonus)

        # 确定等级
        if composite >= 90:
            level = "strong"
        elif composite >= 70:
            level = "medium-strong"
        elif composite >= 50:
            level = "medium"
        elif composite >= 30:
            level = "weak"
        else:
            level = "none"

        # 确定方向
        if up_count > down_count:
            direction = "up"
        elif down_count > up_count:
            direction = "down"
        else:
            direction = "consolidation"

        # 周期对齐描述
        aligned_periods = []
        if daily_trend == direction:
            aligned_periods.append("日线")
        if min30_trend == direction:
            aligned_periods.append("30分钟")
        if min5_trend == direction:
            aligned_periods.append("5分钟")

        return {
            "composite_score": round(composite, 1),
            "level": level,
            "direction": direction,
            "aligned_periods": aligned_periods,
            "alignment": f"{'/'.join(aligned_periods)} 周期共振 ({len(aligned_periods)}/3)",
            "daily_score": base_score if daily_trend == direction else 30,
            "min30_score": base_score if min30_trend == direction else 30,
            "min5_score": base_score if min5_trend == direction else 30,
            "recommendation": self._quick_recommendation(direction, level)
        }

    def _parse_signal(self, signal: Dict, timeframe: str) -> TimeframeSignal:
        """解析信号字典为TimeframeSignal对象"""
        return TimeframeSignal(
            timeframe=timeframe,
            trend=signal.get("trend", "unknown"),
            trend_confidence=signal.get("confidence", 0.0),
            active_centers=signal.get("centers", 0),
            divergence_present=signal.get("divergence", False),
            nearest_bs_point=signal.get("bs_point")
        )

    def _score_timeframe(self, signal: TimeframeSignal) -> float:
        """计算单周期信号得分

        基于趋势清晰度、中枢结构、背驰信号综合评分。

        Parameters
        ----------
        signal : TimeframeSignal
            单周期信号

        Returns
        -------
        float
            0~100 得分
        """
        score = 50.0  # 基础分

        # 趋势清晰度加分
        if signal.trend in ("up", "down"):
            score += signal.trend_confidence * 30
        else:
            score += signal.trend_confidence * 10

        # 中枢结构加分
        if signal.active_centers >= 2:
            score += 10  # 多中枢趋势更明确
        elif signal.active_centers >= 1:
            score += 5

        # 背驰信号加分
        if signal.divergence_present:
            score += 5

        # 买卖点加分
        if signal.nearest_bs_point:
            score += 5

        return round(min(100, max(0, score)), 1)

    def _calc_composite_score(
        self,
        daily: TimeframeSignal,
        min30: TimeframeSignal,
        min5: TimeframeSignal
    ) -> float:
        """计算综合共振得分

        权重分配：
        - 日线：50%（趋势决定）
        - 30分钟：30%（结构识别）
        - 5分钟：20%（精确时机）

        Parameters
        ----------
        daily, min30, min5 : TimeframeSignal
            三个周期的信号

        Returns
        -------
        float
            综合共振得分 0~100
        """
        # 基础加权得分
        base_score = (
            daily.resonance_score * 0.5 +
            min30.resonance_score * 0.3 +
            min5.resonance_score * 0.2
        )

        # 方向一致性加成
        trends = [daily.trend, min30.trend, min5.trend]
        up_count = sum(1 for t in trends if t == "up")
        down_count = sum(1 for t in trends if t == "down")
        max_aligned = max(up_count, down_count)

        # 一致周期越多，加成越高
        alignment_bonus = {
            3: 15,
            2: 5,
            1: -10,
            0: -15
        }.get(max_aligned, 0)

        # 背驰共振加成
        divergence_count = sum([
            daily.divergence_present,
            min30.divergence_present,
            min5.divergence_present
        ])
        divergence_bonus = divergence_count * 3

        composite = base_score + alignment_bonus + divergence_bonus
        return min(100, max(0, composite))

    def _determine_level(
        self,
        daily: TimeframeSignal,
        min30: TimeframeSignal,
        min5: TimeframeSignal,
        composite: float
    ) -> tuple:
        """确定共振等级和描述"""
        trends = [daily.trend, min30.trend, min5.trend]
        up_count = sum(1 for t in trends if t == "up")
        down_count = sum(1 for t in trends if t == "down")

        # 确定共振等级
        if composite >= 90:
            level = "strong"
        elif composite >= 70:
            level = "medium-strong"
        elif composite >= 50:
            level = "medium"
        elif composite >= 30:
            level = "weak"
        else:
            level = "none"

        # 周期对齐描述
        aligned = []
        majority = "up" if up_count >= down_count else "down"
        if daily.trend == majority:
            aligned.append("日线")
        if min30.trend == majority:
            aligned.append("30分钟")
        if min5.trend == majority:
            aligned.append("5分钟")

        alignment = f"{'、'.join(aligned)} 周期方向一致 ({len(aligned)}/3)"
        if len(aligned) == 3:
            alignment = "三周期完全一致共振"
        elif len(aligned) == 0:
            alignment = "三周期方向分歧"

        return level, alignment

    def _generate_recommendation(
        self,
        daily: TimeframeSignal,
        min30: TimeframeSignal,
        min5: TimeframeSignal,
        composite: float,
        level: str
    ) -> str:
        """生成共振策略建议"""
        trends = [daily.trend, min30.trend, min5_trend := min5.trend]
        up_count = sum(1 for t in trends if t == "up")
        down_count = sum(1 for t in trends if t == "down")

        if up_count >= 2 and composite >= 70:
            return "多周期共振向上，关注回调买入机会"
        elif down_count >= 2 and composite >= 70:
            return "多周期共振向下，关注反弹卖出机会"
        elif composite >= 50:
            return "结构清晰但周期存在分歧，建议观察等待"
        elif up_count >= 2:
            return "日线趋势向上但短周期不配合，谨慎追涨"
        elif down_count >= 2:
            return "日线趋势向下但短周期不配合，谨慎杀跌"
        else:
            return "多周期震荡，方向不明，建议观望"

    def _quick_recommendation(self, direction: str, level: str) -> str:
        """快速生成建议"""
        if level == "strong":
            if direction == "up":
                return "强烈共振向上，积极关注买入机会"
            elif direction == "down":
                return "强烈共振向下，积极关注卖出机会"
        elif level == "medium-strong":
            if direction == "up":
                return "较强共振向上，回调可考虑布局"
            elif direction == "down":
                return "较强共振向下，反弹可考虑减仓"
        elif level == "medium":
            return "结构清晰但存在分歧，控制仓位参与"
        elif level == "weak":
            return "共振信号弱，建议观望或轻仓参与"
        return "方向不明，建议观望"
