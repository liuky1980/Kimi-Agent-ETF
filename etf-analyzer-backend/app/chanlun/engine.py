"""
缠论分析引擎
=============
缠论分析的核心引擎，整合分型识别、笔划分、线段划分、
中枢识别、背驰检测、买卖点识别和多周期共振分析。

完整分析流程：
1. 分型识别 → 2. 笔划分 → 3. 线段划分 → 4. 中枢识别
→ 5. 趋势判断 → 6. 背驰检测 → 7. 买卖点识别 → 8. 多周期共振
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from app.chanlun.bi import BiAnalyzer
from app.chanlun.buypoint import BuyPointDetector
from app.chanlun.center import CenterAnalyzer
from app.chanlun.divergence import DivergenceDetector
from app.chanlun.fractal import FractalFinder
from app.chanlun.resonance import ResonanceAnalyzer
from app.chanlun.segment import SegmentAnalyzer
from app.data.fetcher import fetcher
from app.models.chanlun import (
    BiStroke,
    BuySellPoint,
    Center,
    ChanlunResult,
    DivergenceSignal,
    FractalPoint,
    ResonanceResult,
    Segment,
)

logger = logging.getLogger(__name__)


class ChanlunEngine:
    """缠论分析引擎

    整合缠论全部分析模块，提供一站式ETF技术分析能力。
    """

    def __init__(self):
        self.fractal_finder = FractalFinder()
        self.bi_analyzer = BiAnalyzer()
        self.segment_analyzer = SegmentAnalyzer()
        self.center_analyzer = CenterAnalyzer()
        self.divergence_detector = DivergenceDetector()
        self.buypoint_detector = BuyPointDetector()
        self.resonance_analyzer = ResonanceAnalyzer()

    def analyze(
        self,
        df_daily: pd.DataFrame,
        df_30min: Optional[pd.DataFrame] = None,
        df_5min: Optional[pd.DataFrame] = None,
        etf_code: str = "",
        etf_name: str = ""
    ) -> ChanlunResult:
        """执行完整的缠论分析流程

        Parameters
        ----------
        df_daily : pd.DataFrame
            日线K线数据
        df_30min : Optional[pd.DataFrame]
            30分钟K线数据
        df_5min : Optional[pd.DataFrame]
            5分钟K线数据
        etf_code : str
            ETF代码
        etf_name : str
            ETF名称

        Returns
        -------
        ChanlunResult
            完整的缠论分析结果
        """
        logger.info(f"开始对 {etf_code} 执行缠论分析")

        # Step 1: 分型识别
        top_fractals, bottom_fractals = self.fractal_finder.find(df_daily)

        # Step 2: 笔划分
        all_fractals = sorted(top_fractals + bottom_fractals, key=lambda f: f.index)
        bi_list = self.bi_analyzer.identify_bi(
            all_fractals,
            df_daily['close'].values,
            df_daily['date'].astype(str).tolist()
        )

        # Step 3: 线段划分
        segments = self.segment_analyzer.identify_segments(bi_list)

        # Step 4: 中枢识别
        centers = self.center_analyzer.find_centers(
            bi_list,
            df_daily['date'].astype(str).tolist()
        )

        # Step 5: 趋势判断
        trend_info = self._classify_trend(bi_list, segments, centers, df_daily)

        # Step 6: 背驰检测（MACD面积法）
        macd_df = fetcher.compute_macd(df_daily['close'])
        divergence = self.divergence_detector.detect_from_macd(
            df_daily['close'],
            macd_df['macd_histogram']
        )

        # Step 7: 买卖点识别
        current_price = float(df_daily['close'].iloc[-1])
        bi_direction = self.bi_analyzer.get_direction(bi_list)
        buy_points = self.buypoint_detector.detect_buy_points(
            centers, divergence, current_price, bi_direction
        )

        # Step 8: 多周期共振
        if df_30min is not None and df_5min is not None:
            resonance = self._calculate_multi_timeframe_resonance(
                df_daily, df_30min, df_5min
            )
        else:
            # 只有日线数据时，使用简化共振
            resonance = self._single_timeframe_resonance(trend_info, divergence, centers)

        # 生成综合建议
        recommendation = self._generate_recommendation(
            trend_info, divergence, buy_points, resonance
        )

        # 确定风险等级
        risk_level = self._determine_risk_level(trend_info, divergence, resonance)

        # 构建结果
        active_center = self.center_analyzer.get_active_center(centers)
        center_range = self.center_analyzer.get_center_range(centers)

        result = ChanlunResult(
            etf_code=etf_code,
            etf_name=etf_name,
            analysis_time=datetime.now(),
            current_price=round(current_price, 3),
            latest_date=str(df_daily['date'].iloc[-1]),
            top_fractals=top_fractals,
            bottom_fractals=bottom_fractals,
            top_fractal=len(top_fractals) > 0 and top_fractals[-1].index > len(df_daily) - 10,
            bottom_fractal=len(bottom_fractals) > 0 and bottom_fractals[-1].index > len(df_daily) - 10,
            bi_list=bi_list,
            bi_count=len(bi_list),
            bi_direction=bi_direction,
            segments=segments,
            segment_direction=self.segment_analyzer.get_trend_direction(segments),
            segment_count=len(segments),
            centers=centers,
            active_center=active_center,
            center_range=center_range,
            center_count=len(centers),
            trend_position=trend_info.get("position", "趋势不明"),
            trend_confidence=trend_info.get("confidence", 0.0),
            divergence=divergence,
            divergence_type=divergence.type,
            divergence_strength=divergence.strength,
            macd_area_current=divergence.macd_area_current,
            macd_area_previous=divergence.macd_area_previous,
            buy_sell_points=[self._bs_point_to_dict(bp) for bp in buy_points],
            daily_resonance=resonance.get("daily_score", 50.0),
            min30_resonance=resonance.get("min30_score", 0.0),
            min5_resonance=resonance.get("min5_score", 0.0),
            composite_resonance=resonance.get("composite_score", 50.0),
            recommendation=recommendation,
            summary=self._generate_summary(trend_info, divergence, buy_points, resonance),
            risk_level=risk_level
        )

        logger.info(f"缠论分析完成: {etf_code} - 趋势: {result.trend_position}, "
                    f"背驰: {result.divergence_type}, 买卖点: {len(buy_points)} 个")
        return result

    def analyze_single_timeframe(self, df: pd.DataFrame) -> Dict:
        """单周期快速分析

        Parameters
        ----------
        df : pd.DataFrame
            K线数据

        Returns
        -------
        dict
            简化分析结果
        """
        # 分型识别
        top_fractals, bottom_fractals = self.fractal_finder.find(df)
        all_fractals = sorted(top_fractals + bottom_fractals, key=lambda f: f.index)

        # 笔划分
        bi_list = self.bi_analyzer.identify_bi(
            all_fractals,
            df['close'].values,
            df['date'].astype(str).tolist()
        )

        # 中枢
        centers = self.center_analyzer.find_centers(bi_list)

        # MACD背驰
        macd_df = fetcher.compute_macd(df['close'])
        divergence = self.divergence_detector.detect_from_macd(
            df['close'],
            macd_df['macd_histogram']
        )

        # 趋势判断
        segments = self.segment_analyzer.identify_segments(bi_list)
        trend = self.segment_analyzer.get_trend_direction(segments)

        return {
            "trend": trend,
            "confidence": 0.7 if len(centers) >= 1 else 0.4,
            "centers": len(centers),
            "divergence": divergence.type != "none",
            "bs_point": None,
            "bi_count": len(bi_list),
            "fractal_count": len(all_fractals),
        }

    def _classify_trend(
        self,
        bi_list: List[BiStroke],
        segments: List[Segment],
        centers: List[Center],
        df: pd.DataFrame
    ) -> Dict:
        """趋势分类

        基于笔、线段和中枢综合判断当前趋势位置。

        Returns
        -------
        dict
            {position, confidence}
        """
        if not bi_list:
            return {"position": "趋势不明", "confidence": 0.0}

        current_price = float(df['close'].iloc[-1])

        # 基于线段方向
        seg_direction = self.segment_analyzer.get_trend_direction(segments) if segments else "unknown"

        # 基于笔方向
        bi_direction = self.bi_analyzer.get_direction(bi_list)

        # 基于中枢位置
        if centers:
            active = centers[-1]
            if active.zd <= current_price <= active.zg:
                center_position = "inside"
            elif current_price > active.zg:
                center_position = "above"
            else:
                center_position = "below"
        else:
            center_position = "none"

        # 综合判断
        if seg_direction == "up" and center_position in ("above", "none"):
            position = "上升趋势"
            confidence = 0.8
        elif seg_direction == "down" and center_position in ("below", "none"):
            position = "下跌趋势"
            confidence = 0.8
        elif center_position == "inside":
            position = "中枢震荡"
            confidence = 0.6
        elif seg_direction == "up" and center_position == "inside":
            position = "上升趋势中的中枢整理"
            confidence = 0.65
        elif seg_direction == "down" and center_position == "inside":
            position = "下跌趋势中的中枢整理"
            confidence = 0.65
        elif bi_direction != seg_direction and segments:
            position = "趋势转折中"
            confidence = 0.5
        else:
            position = "趋势不明"
            confidence = 0.3

        return {"position": position, "confidence": confidence}

    def _calculate_multi_timeframe_resonance(
        self,
        df_daily: pd.DataFrame,
        df_30min: pd.DataFrame,
        df_5min: pd.DataFrame
    ) -> Dict:
        """计算多周期共振"""
        daily_signal = self.analyze_single_timeframe(df_daily)
        min30_signal = self.analyze_single_timeframe(df_30min)
        min5_signal = self.analyze_single_timeframe(df_5min)

        result = self.resonance_analyzer.calculate_simple_resonance(
            daily_signal["trend"],
            min30_signal["trend"],
            min5_signal["trend"],
            daily_signal["divergence"],
            min30_signal["divergence"],
            min5_signal["divergence"]
        )

        return result

    def _single_timeframe_resonance(
        self,
        trend_info: Dict,
        divergence: DivergenceSignal,
        centers: List[Center]
    ) -> Dict:
        """只有日线数据时的简化共振"""
        trend = trend_info.get("position", "趋势不明")
        trend_simple = "up" if "上升" in trend else "down" if "下跌" in trend else "consolidation"

        return self.resonance_analyzer.calculate_simple_resonance(
            trend_simple, "consolidation", "consolidation",
            divergence.type != "none", False, False
        )

    def _generate_recommendation(
        self,
        trend_info: Dict,
        divergence: DivergenceSignal,
        buy_points: List[BuySellPoint],
        resonance: Dict
    ) -> str:
        """生成综合建议"""
        parts = []

        # 趋势建议
        position = trend_info.get("position", "")
        if "上升" in position:
            parts.append("趋势向上")
        elif "下跌" in position:
            parts.append("趋势向下")
        elif "震荡" in position:
            parts.append("中枢震荡")

        # 背驰建议
        if divergence.type == "bullish":
            parts.append(f"底背驰信号(强度{divergence.strength:.1f})")
        elif divergence.type == "bearish":
            parts.append(f"顶背驰信号(强度{divergence.strength:.1f})")

        # 买卖点建议
        if buy_points:
            primary = buy_points[0]
            parts.append(f"{primary.type}信号")

        # 共振建议
        level = resonance.get("level", "")
        if level in ("strong", "medium-strong"):
            parts.append(f"多周期{level}共振")

        return "；".join(parts) if parts else "暂无明确信号，建议观望"

    def _generate_summary(
        self,
        trend_info: Dict,
        divergence: DivergenceSignal,
        buy_points: List[BuySellPoint],
        resonance: Dict
    ) -> str:
        """生成分析摘要"""
        summary_parts = [f"趋势: {trend_info.get('position', '不明')}"]

        if divergence.type != "none":
            summary_parts.append(f"背驰: {divergence.type} (强度{divergence.strength:.2f})")

        if buy_points:
            bp = buy_points[0]
            summary_parts.append(f"信号: {bp.type} (置信度{bp.confidence:.2f})")

        summary_parts.append(f"共振: {resonance.get('level', 'unknown')} (得分{resonance.get('composite_score', 0):.1f})")

        return " | ".join(summary_parts)

    def _determine_risk_level(
        self,
        trend_info: Dict,
        divergence: DivergenceSignal,
        resonance: Dict
    ) -> str:
        """确定风险等级"""
        composite = resonance.get("composite_score", 50)

        if composite >= 80 and divergence.type != "none":
            return "medium"  # 信号强但需警惕背驰后的转折
        elif composite >= 60:
            return "medium"
        elif composite >= 40:
            return "medium-high"
        else:
            return "high"

    def _bs_point_to_dict(self, bp: BuySellPoint) -> Dict:
        """买卖点转字典"""
        return {
            "type": bp.type,
            "bs_type": bp.bs_type,
            "price": bp.price,
            "confidence": bp.confidence,
            "trigger_date": bp.trigger_date,
            "description": bp.description
        }
