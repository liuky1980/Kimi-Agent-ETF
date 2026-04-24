"""
李彪分析框架 Pydantic 模型
======================
定义李彪分析框架的请求/响应数据结构，
包括分型、笔、线段、中枢、背驰、买卖点及多周期共振结果。
"""

from datetime import datetime
from typing import Dict, List, Optional, Tuple

from pydantic import BaseModel, Field


# ────────────────────────────── 基础元素模型 ──────────────────────────────

class FractalPoint(BaseModel):
    """分型点"""
    index: int = Field(..., description="K线索引位置")
    date: str = Field(..., description="日期时间")
    price: float = Field(..., description="分型价格")
    type: str = Field(..., description="分型类型: top-顶分型, bottom-底分型")
    confidence: float = Field(1.0, ge=0.0, le=1.0, description="分型确认置信度")


class BiStroke(BaseModel):
    """笔（连接两个分型点的连线）"""
    start_index: int = Field(..., description="起始分型索引")
    end_index: int = Field(..., description="结束分型索引")
    start_date: str = Field(..., description="起始日期")
    end_date: str = Field(..., description="结束日期")
    direction: str = Field(..., description="方向: up-向上笔, down-向下笔")
    start_price: float = Field(..., description="起始价格")
    end_price: float = Field(..., description="结束价格")
    high: float = Field(..., description="笔内最高价")
    low: float = Field(..., description="笔内最低价")
    kline_count: int = Field(..., ge=5, description="笔包含的K线数")


class Segment(BaseModel):
    """线段（至少3笔构成的走势段）"""
    start_bi: int = Field(..., description="起始笔索引")
    end_bi: int = Field(..., description="结束笔索引")
    direction: str = Field(..., description="方向: up-上升线段, down-下降线段")
    start_price: float = Field(..., description="起始价格")
    end_price: float = Field(..., description="结束价格")
    high: float = Field(..., description="线段最高价")
    low: float = Field(..., description="线段最低价")
    bi_count: int = Field(..., ge=3, description="包含笔数")


class Center(BaseModel):
    """中枢（连续3笔以上重叠区域）"""
    start_bi: int = Field(..., description="进入笔索引")
    end_bi: int = Field(..., description="离开笔索引")
    zg: float = Field(..., description="中枢上轨 ZG (min of highs)")
    zd: float = Field(..., description="中枢下轨 ZD (max of lows)")
    level: int = Field(1, ge=1, description="中枢级别")
    start_date: str = Field(..., description="形成起始日期")
    end_date: Optional[str] = Field(None, description="结束日期（未结束则为null）")
    status: str = Field(..., description="状态: active-活跃, closed-已结束")


class DivergenceSignal(BaseModel):
    """背驰信号"""
    type: str = Field(..., description="背驰类型: bullish-底背驰(一买信号), bearish-顶背驰(一卖信号), none-无背驰")
    strength: float = Field(..., ge=0.0, le=1.0, description="背驰强度 0~1")
    macd_area_current: float = Field(..., description="当前段MACD面积")
    macd_area_previous: float = Field(..., description="前一段MACD面积")
    price_change_current: float = Field(..., description="当前段价格变动")
    price_change_previous: float = Field(..., description="前一段价格变动")
    confidence: float = Field(..., ge=0.0, le=1.0, description="背驰确认置信度")
    description: str = Field("", description="背驰描述说明")


class BuySellPoint(BaseModel):
    """买卖点"""
    type: str = Field(..., description="类型: 一买/二买/三买/一卖/二卖/三卖")
    bs_type: str = Field(..., description="买卖方向: buy-买点, sell-卖点")
    price: float = Field(..., description="触发价格")
    confidence: float = Field(..., ge=0.0, le=1.0, description="信号置信度")
    trigger_date: str = Field(..., description="触发日期")
    description: str = Field(..., description="信号详细描述")


class TimeframeSignal(BaseModel):
    """单周期信号"""
    timeframe: str = Field(..., description="周期名称: weekly/daily/hourly")
    trend: str = Field(..., description="趋势判断: up/down/consolidation/unknown")
    trend_confidence: float = Field(..., ge=0.0, le=1.0, description="趋势判断置信度")
    active_centers: int = Field(0, description="活跃中枢数量")
    divergence_present: bool = Field(False, description="是否存在背驰")
    nearest_bs_point: Optional[str] = Field(None, description="最近买卖点类型")
    resonance_score: float = Field(0.0, ge=0.0, le=100.0, description="该周期共振得分")


# ────────────────────────────── 共振分析模型 ──────────────────────────────

class ResonanceResult(BaseModel):
    """多周期共振分析结果"""
    weekly: TimeframeSignal = Field(..., description="周线周期信号")
    daily: TimeframeSignal = Field(..., description="日线周期信号")
    hourly: TimeframeSignal = Field(..., description="小时线周期信号")
    composite_score: float = Field(..., ge=0.0, le=100.0, description="综合共振得分")
    level: str = Field(..., description="共振等级: strong/medium-strong/medium/weak/none")
    alignment: str = Field(..., description="周期共振情况描述")
    recommendation: str = Field(..., description="共振策略建议")


# ────────────────────────────── 综合结果模型 ──────────────────────────────

class ChanlunResult(BaseModel):
    """李彪分析框架完整结果"""
    # 基础信息
    etf_code: str = Field(..., description="ETF代码")
    etf_name: str = Field("", description="ETF名称")
    analysis_time: datetime = Field(default_factory=datetime.now, description="分析时间")

    # 价格信息
    current_price: float = Field(..., description="当前价格")
    latest_date: str = Field(..., description="最新数据日期")

    # 分型识别结果
    top_fractals: List[FractalPoint] = Field(default_factory=list, description="顶分型列表")
    bottom_fractals: List[FractalPoint] = Field(default_factory=list, description="底分型列表")
    top_fractal: bool = Field(False, description="是否存在活跃顶分型")
    bottom_fractal: bool = Field(False, description="是否存在活跃底分型")

    # 笔划分结果
    bi_list: List[BiStroke] = Field(default_factory=list, description="笔列表")
    bi_count: int = Field(0, description="笔总数")
    bi_direction: str = Field("", description="当前笔方向: up/down/unknown")

    # 线段结果
    segments: List[Segment] = Field(default_factory=list, description="线段列表")
    segment_direction: str = Field("", description="当前线段方向")
    segment_count: int = Field(0, description="线段数量")

    # 中枢结果
    centers: List[Center] = Field(default_factory=list, description="中枢列表")
    active_center: Optional[Center] = Field(None, description="当前活跃中枢")
    center_range: Tuple[float, float] = Field((0.0, 0.0), description="中枢区间 [ZD, ZG]")
    center_count: int = Field(0, description="中枢数量")

    # 趋势判断
    trend_position: str = Field("", description="趋势位置: 上升趋势/下跌趋势/中枢震荡/趋势转折中/趋势不明")
    trend_confidence: float = Field(0.0, ge=0.0, le=1.0, description="趋势判断置信度")

    # 背驰检测
    divergence: DivergenceSignal = Field(default_factory=lambda: DivergenceSignal(
        type="none", strength=0.0, macd_area_current=0.0, macd_area_previous=0.0,
        price_change_current=0.0, price_change_previous=0.0, confidence=0.0
    ), description="背驰信号")
    divergence_type: str = Field("none", description="背驰类型")
    divergence_strength: float = Field(0.0, description="背驰强度")
    macd_area_current: float = Field(0.0, description="当前MACD面积")
    macd_area_previous: float = Field(0.0, description="前一段MACD面积")

    # 买卖点
    buy_sell_points: List[BuySellPoint] = Field(default_factory=list, description="买卖点列表")

    # 多周期共振
    weekly_resonance: float = Field(0.0, ge=0.0, le=100.0, description="周线共振得分")
    daily_resonance: float = Field(0.0, ge=0.0, le=100.0, description="日线共振得分")
    hourly_resonance: float = Field(0.0, ge=0.0, le=100.0, description="小时线共振得分")
    composite_resonance: float = Field(0.0, ge=0.0, le=100.0, description="综合共振得分")

    # 综合建议
    recommendation: str = Field("", description="李枛分析框架综合建议")
    summary: str = Field("", description="分析摘要")
    risk_level: str = Field("", description="风险等级: low/medium/high")

    # 历史数据用于图表展示
    macd_history: List[Dict] = Field(default_factory=list, description="MACD历史数据")
    price_history: List[Dict] = Field(default_factory=list, description="价格历史数据")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
