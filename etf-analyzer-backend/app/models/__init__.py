"""
数据模型模块
============
Pydantic 模型定义，用于 API 请求/响应的数据验证和序列化。
"""

from app.models.chanlun import (
    ChanlunResult,
    FractalPoint,
    BiStroke,
    Segment,
    Center,
    DivergenceSignal,
    BuySellPoint,
    ResonanceResult,
)
from app.models.dingchang import (
    DingChangResult,
    DingChangDimensions,
    DividendScore,
    ValuationScore,
    ProfitabilityScore,
    CapitalFlowScore,
    MacroScore,
    ETFAnalysisRequest,
    ETFAnalysisResponse,
    ETFSimpleInfo,
    ETFListResponse,
)

__all__ = [
    "ChanlunResult",
    "FractalPoint",
    "BiStroke",
    "Segment",
    "Center",
    "DivergenceSignal",
    "BuySellPoint",
    "ResonanceResult",
    "DingChangResult",
    "DingChangDimensions",
    "DividendScore",
    "ValuationScore",
    "ProfitabilityScore",
    "CapitalFlowScore",
    "MacroScore",
    "ETFAnalysisRequest",
    "ETFAnalysisResponse",
    "ETFSimpleInfo",
    "ETFListResponse",
]
