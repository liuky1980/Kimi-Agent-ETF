"""
多周期共振分析模块
===================
缠论多周期共振分析，通过对比不同时间周期的信号一致性，
提高交易决策的可靠性。

多周期共振体系：
- 周线周期：确定大趋势方向
- 日线周期：识别结构、中枢和买卖点
- 小时线周期：精确入场时机

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
        self.threshold = settings.CHANLUN_RESONANCE_THRESHOLD

    def calculate_resonance(
        self,
        weekly_signal: Dict,
        daily_signal: Dict,
        hourly_signal: Dict
    ) -> ResonanceResult:
        """计算多周期共振

        Parameters
        ----------
        weekly_signal : dict
            周线周期分析结果，包含 trend, confidence, centers, divergence, bs_point
        daily_signal : dict
            日线周期分析结果
        hourly_signal : dict
            小时线周期分析结果

        Returns
        -------
        ResonanceResult
            共振分析结果
        """
        # 构建单周期信号
        weekly = self._parse_signal(weekly_signal, "weekly")
        daily = self._parse_signal(daily_signal, "daily")
        hourly = self._parse_signal(hourly_signal, "hourly")

        # 计算各周期独立得分
        weekly_score = self._score_timeframe(weekly)
        daily_score = self._score_timeframe(daily)
        hourly_score = self._score_timeframe(hourly)

        weekly.resonance_score = weekly_score
        daily.resonance_score = daily_score
        hourly.resonance_score = hourly_score

        # 计算综合共振得分
        composite = self._calc_composite_score(weekly, daily, hourly)

        # 确定共振等级
        level, alignment = self._determine_level(weekly, daily, hourly, composite)

        # 生成建议
        recommendation = self._generate_recommendation(weekly, daily, hourly, composite, level)

        return ResonanceResult(
            weekly=weekly,
            daily=daily,
            hourly=hourly,
            composite_score=round(composite, 1),
            level=level,
            alignment=alignment,
            recommendation=recommendation
        )

    def calculate_simple_resonance(
        self,
        weekly_trend: str,
        daily_trend: str,
        hourly_trend: str,
        weekly_divergence: bool = False,
        daily_divergence: bool = False,
        hourly_divergence: bool = False
    ) -> dict:
        """简化版共振计算（用于快速评估）

        Parameters
        ----------
        weekly_trend, daily_trend, hourly_trend : str
            各周期趋势方向 'up'/'down'/'consolidation'
        weekly_divergence, daily_divergence, hourly_divergence : bool
            各周期是否有背驰

        Returns
        -------
        dict
            简化共振结果
        """
        trends = [weekly_trend, daily_trend, hourly_trend]
        divergences = [weekly_divergence, daily_divergence, hourly_divergence]

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
        if weekly_trend == direction:
            aligned_periods.append("周线")
        if daily_trend == direction:
            aligned_periods.append("日线")
        if hourly_trend == direction:
            aligned_periods.append("小时线")

        return {
            "composite_score": round(composite, 1),
            "level": level,
            "direction": direction,
            "aligned_periods": aligned_periods,
            "alignment": f"{'/'.join(aligned_periods)} 周期共振 ({len(aligned_periods)}/3)",
            "weekly_score": base_score if weekly_trend == direction else 30,
            "daily_score": base_score if daily_trend == direction else 30,
            "hourly_score": base_score if hourly_trend == direction else 30,
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
        weekly: TimeframeSignal,
        daily: TimeframeSignal,
        hourly: TimeframeSignal
    ) -> float:
        """计算综合共振得分

        权重分配：
        - 周线：50%（大趋势决定）
        - 日线：30%（结构识别）
        - 小时线：20%（精确时机）

        Parameters
        ----------
        weekly, daily, hourly : TimeframeSignal
            三个周期的信号

        Returns
        -------
        float
            综合共振得分 0~100
        """
        # 基础加权得分
        base_score = (
            weekly.resonance_score * 0.5 +
            daily.resonance_score * 0.3 +
            hourly.resonance_score * 0.2
        )

        # 方向一致性加成
        trends = [weekly.trend, daily.trend, hourly.trend]
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
            weekly.divergence_present,
            daily.divergence_present,
            hourly.divergence_present
        ])
        divergence_bonus = divergence_count * 3

        composite = base_score + alignment_bonus + divergence_bonus
        return min(100, max(0, composite))

    def _determine_level(
        self,
        weekly: TimeframeSignal,
        daily: TimeframeSignal,
        hourly: TimeframeSignal,
        composite: float
    ) -> tuple:
        """确定共振等级和描述"""
        trends = [weekly.trend, daily.trend, hourly.trend]
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
        if weekly.trend == majority:
            aligned.append("周线")
        if daily.trend == majority:
            aligned.append("日线")
        if hourly.trend == majority:
            aligned.append("小时线")

        alignment = f"{'、'.join(aligned)} 周期方向一致 ({len(aligned)}/3)"
        if len(aligned) == 3:
            alignment = "三周期完全一致共振"
        elif len(aligned) == 0:
            alignment = "三周期方向分歧"

        return level, alignment

    def _generate_recommendation(
        self,
        weekly: TimeframeSignal,
        daily: TimeframeSignal,
        hourly: TimeframeSignal,
        composite: float,
        level: str
    ) -> str:
        """生成共振策略建议"""
        trends = [weekly.trend, daily.trend, hourly.trend]
        up_count = sum(1 for t in trends if t == "up")
        down_count = sum(1 for t in trends if t == "down")

        if up_count >= 2 and composite >= 70:
            return "多周期共振向上，关注回调买入机会"
        elif down_count >= 2 and composite >= 70:
            return "多周期共振向下，关注反弹卖出机会"
        elif composite >= 50:
            return "结构清晰但周期存在分歧，建议观察等待"
        elif up_count >= 2:
            return "周线趋势向上但短周期不配合，谨慎追涨"
        elif down_count >= 2:
            return "周线趋势向下但短周期不配合，谨慎杀跌"
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
