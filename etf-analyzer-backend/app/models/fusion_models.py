"""
融合引擎 Pydantic 模型（主定义文件）
===================================
定义五维融合决策引擎的全部数据模型。
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field, model_validator


# ────────────────────────────── 宏观层模型 ──────────────────────────────


class MacroResult(BaseModel):
    """宏观周期定位层分析结果"""

    quadrant: str = Field(
        default="III_stagflation",
        description="象限编码: I_recovery / II_overheat / III_stagflation / IV_recession"
    )
    quadrant_name: str = Field(default="滞胀期", description="象限中文名称")
    credit_status: str = Field(default="contraction", description="信用周期: expansion/contraction")
    inventory_status: str = Field(default="destocking", description="库存周期: destocking/accumulation")
    exception_applied: bool = Field(default=False, description="衰退期PE例外")

    position_limit: float = Field(0.4, ge=0.0, le=1.0, description="战略仓位上限")
    position_limit_pct: str = Field("40%", description="格式化仓位限制")
    chan_enabled: bool = Field(default=True, description="缠论信号开关")
    ding_style: str = Field(default="defensive", description="丁昶风格: growth/balanced/defensive/cash")

    asset_favor: List[str] = Field(default_factory=list, description="利好资产类别")
    asset_avoid: List[str] = Field(default_factory=list, description="回避资产类别")
    policy_stance: str = Field("", description="政策立场")
    rate_direction: str = Field("", description="利率方向")
    macro_risks: List[str] = Field(default_factory=list, description="宏观风险因素")
    description: str = Field("", description="象限描述")
    summary: str = Field("", description="分析摘要")
    update_time: str = Field(default_factory=lambda: datetime.now().isoformat(), description="更新时间")

    class Config:
        json_schema_extra = {
            "example": {
                "quadrant": "I_recovery",
                "quadrant_name": "复苏期",
                "position_limit": 0.90,
                "chan_enabled": True,
                "ding_style": "growth",
                "credit_status": "expansion",
                "inventory_status": "destocking",
                "exception_applied": False,
                "description": "信用扩张+库存去化，经济复苏初期",
            }
        }


class MacroLayerConfig(BaseModel):
    """宏观层配置参数"""
    cycle_position_limit_map: Dict[str, float] = Field(default_factory=lambda: {
        "I_recovery": 0.90, "II_overheat": 0.70, "III_stagflation": 0.40, "IV_recession": 0.20,
    })
    cycle_chan_enabled_map: Dict[str, bool] = Field(default_factory=lambda: {
        "I_recovery": True, "II_overheat": True, "III_stagflation": True, "IV_recession": False,
    })
    cycle_ding_style_map: Dict[str, str] = Field(default_factory=lambda: {
        "I_recovery": "growth", "II_overheat": "balanced", "III_stagflation": "defensive", "IV_recession": "cash",
    })
    credit_expansion_threshold: float = Field(0.0)
    m2_m1_spread_limit_expansion: float = Field(5.0)
    m2_m1_spread_limit_contraction: float = Field(8.0)
    pmi_destocking: float = Field(48.0)
    pmi_accumulation: float = Field(50.0)
    recession_exception_pe: float = Field(0.10)
    risk_free_rate: float = Field(0.025)


# ────────────────────────────── 情绪层模型 ──────────────────────────────


class SentimentMetrics(BaseModel):
    """情绪量化指标"""
    greed_fear_index: float = Field(50.0, ge=0.0, le=100.0)
    a_share_sentiment: float = Field(0.0, ge=-1.0, le=1.0)
    northbound_sentiment: float = Field(0.0, ge=-1.0, le=1.0)
    margin_sentiment: float = Field(0.0, ge=-1.0, le=1.0)
    options_skew: float = Field(0.0)
    fund_flow_5d: float = Field(0.0)
    pcr: float = Field(1.0)
    pcr_score: float = Field(50.0, ge=0.0, le=100.0)
    financing_change: float = Field(0.0)
    financing_score: float = Field(40.0, ge=0.0, le=100.0)
    northbound_5d: float = Field(0.0)
    main_force_flow: float = Field(0.0)
    fund_flow_score: float = Field(40.0, ge=0.0, le=100.0)


class SentimentResult(BaseModel):
    """情绪层分析结果"""
    grade: str = Field("C", description="情绪等级: A/B/C/D")
    grade_description: str = Field("")
    metrics: SentimentMetrics = Field(default_factory=SentimentMetrics)
    sentiment_score: float = Field(50.0, ge=0.0, le=100.0)
    final_confidence: float = Field(50.0, ge=0.0, le=100.0)
    market_signals: Dict[str, str] = Field(default_factory=dict)
    rating: str = Field("C")
    description: str = Field("")
    summary: str = Field("")
    update_time: str = Field(default_factory=lambda: datetime.now().isoformat())


class SentimentLayerConfig(BaseModel):
    """情绪层配置参数"""
    grade_confidence_map: Dict[str, float] = Field(default_factory=lambda: {
        "A": 85.0, "B": 65.0, "C": 45.0, "D": 25.0,
    })
    pcr_extreme_fear: float = Field(1.2)
    pcr_extreme_greed: float = Field(0.7)
    financing_inflow_threshold: float = Field(0.03)
    financing_outflow_threshold: float = Field(-0.02)
    northbound_active: float = Field(50.0)
    weights: Dict[str, float] = Field(default_factory=lambda: {
        "fund_flow": 0.4, "pcr": 0.3, "financing": 0.3,
    })
    greed_fear_threshold_high: float = Field(75.0)
    greed_fear_threshold_low: float = Field(25.0)
    northbound_window_days: int = Field(5)


# ────────────────────────────── 波动率层模型 ──────────────────────────────


class VolatilityMetrics(BaseModel):
    """波动率量化指标"""
    hv_20: float = Field(0.0)
    hv_60: float = Field(0.0)
    iv_proxy: float = Field(0.0)
    atr_14: float = Field(0.0)
    atr_ratio: float = Field(0.0)
    vol_regime: str = Field("")
    vol_trend: str = Field("")


class VolatilityResult(BaseModel):
    """波动率层分析结果"""
    position_coefficient: float = Field(1.0, ge=0.0, le=2.0)
    atr14: float = Field(0.0)
    atr_percentile: float = Field(0.5, ge=0.0, le=1.0)
    vol_state: str = Field("正常波动")
    atr_multiplier: float = Field(2.0)
    kelly_ratio: float = Field(0.0)
    kelly_adjusted: float = Field(0.0)
    metrics: VolatilityMetrics = Field(default_factory=VolatilityMetrics)
    vol_risk_flag: str = Field("")
    vol_risk_description: str = Field("")
    description: str = Field("")
    summary: str = Field("")
    update_time: str = Field(default_factory=lambda: datetime.now().isoformat())


class VolatilityLayerConfig(BaseModel):
    """波动率层配置参数"""
    atr_period: int = Field(14)
    lookback_days: int = Field(252)
    low_vol_percentile: float = Field(0.20)
    high_vol_percentile: float = Field(0.60)
    extreme_vol_percentile: float = Field(0.85)
    regime_coefficient_map: Dict[str, float] = Field(default_factory=lambda: {
        "low": 1.2, "normal": 1.0, "high": 0.6, "extreme": 0.3,
    })
    atr_multipliers: Dict[str, float] = Field(default_factory=lambda: {
        "low": 1.5, "normal": 2.0, "high": 2.5, "extreme": 3.0,
    })
    kelly_table: Dict[str, Dict[str, float]] = Field(default_factory=lambda: {
        "weekly_A": {"p": 0.65, "b": 3.0, "f": 0.30},
        "daily_A": {"p": 0.55, "b": 2.5, "f": 0.22},
        "daily_B": {"p": 0.48, "b": 2.0, "f": 0.14},
        "30min_A": {"p": 0.45, "b": 1.8, "f": 0.08},
    })
    hv_extreme_threshold: float = Field(0.40)
    hv_high_threshold: float = Field(0.25)
    hv_low_threshold: float = Field(0.10)


# ────────────────────────────── 信号验证模型 ──────────────────────────────


class ValidatedSignal(BaseModel):
    """跨层信号验证结果"""
    original_signal: str = Field("")
    original_level: str = Field("daily")
    original_strength: float = Field(0.0)
    macro_filter_passed: bool = Field(True)
    sentiment_filter_passed: bool = Field(True)
    volatility_filter_passed: bool = Field(True)
    filter_reason: str = Field("")
    final_valid: bool = Field(False)
    final_confidence: float = Field(0.0, ge=0.0, le=100.0)
    execution_mode: str = Field("full")
    bonus_applied: bool = Field(False)
    macro_contrib: float = Field(0.0)
    sentiment_contrib: float = Field(0.0)
    volatility_contrib: float = Field(0.0)
    chanlun_contrib: float = Field(0.0)
    sentiment_rating: str = Field("C")
    summary: str = Field("")


# ────────────────────────────── 仓位计算与执行计划 ──────────────────────────────


class PositionCalculation(BaseModel):
    """仓位计算结果"""
    strategic_cap: float = Field(0.0, ge=0.0, le=1.0)
    valuation_weight: float = Field(0.25, ge=0.0, le=1.0)
    tactical_ratio: float = Field(0.30, ge=0.0, le=1.0)
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    vol_coeff: float = Field(1.0, ge=0.0, le=2.0)
    raw_position: float = Field(0.0)
    final_position: float = Field(0.0, ge=0.0, le=0.25)
    position_pct: str = Field("0.00%")
    layer_scores: Dict[str, float] = Field(default_factory=dict)

    @model_validator(mode="after")
    def ensure_position_cap(self) -> "PositionCalculation":
        if self.final_position > 0.25:
            self.final_position = 0.25
        return self


class ExecutionPlan(BaseModel):
    """执行计划"""
    action: str = Field("屏蔽信号，反向对冲或空仓")
    stop_loss: float = Field(0.0)
    target_1: float = Field(0.0)
    target_2: float = Field(0.0)
    holding_period: str = Field("")
    batch_info: str = Field("")
    max_leverage: float = Field(1.0)
    position_adjust_rules: str = Field("")


# ────────────────────────────── 决策卡片 ──────────────────────────────


class DecisionCard(BaseModel):
    """融合决策卡片"""
    decision_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    etf_code: str = Field(...)
    etf_name: str = Field("")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())

    macro_layer: MacroResult = Field(default_factory=MacroResult)
    chan_layer: Dict[str, Any] = Field(default_factory=dict)
    sentiment_layer: SentimentResult = Field(default_factory=SentimentResult)
    volatility_layer: VolatilityResult = Field(default_factory=VolatilityResult)
    validated_signal: ValidatedSignal = Field(default_factory=ValidatedSignal)
    position_calculation: PositionCalculation = Field(default_factory=PositionCalculation)
    execution: ExecutionPlan = Field(default_factory=ExecutionPlan)

    summary: str = Field("")
    risk_warning: str = Field("")
    next_review: str = Field("")


# ────────────────────────────── API 请求/响应模型 ──────────────────────────────


class FusionAnalysisRequest(BaseModel):
    """五维融合分析请求"""
    etf_code: str = Field(..., min_length=1)
    timeframe: str = Field("daily")
    include_minute: bool = Field(True)
    analysis_depth: str = Field("full")
    use_fusion: bool = Field(True)


class FusionAnalysisResponse(BaseModel):
    """五维融合分析响应"""
    success: bool = Field(True)
    message: str = Field("")
    decision_card: Optional[DecisionCard] = None
    macro_result: Optional[MacroResult] = None
    sentiment_result: Optional[SentimentResult] = None
    volatility_result: Optional[VolatilityResult] = None
    validated_signal: Optional[ValidatedSignal] = None
    processing_time_ms: int = Field(0)
    data_source: str = Field("tushare")
    analysis_time: datetime = Field(default_factory=datetime.now)

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


# ────────────────────────────── 全局融合配置模型 ──────────────────────────────


class PositionLimitConfig(BaseModel):
    """仓位限制配置"""
    single_etf_max: float = Field(0.25)
    sector_max: float = Field(0.50)
    total_max: float = Field(1.00)
    kelly_max: float = Field(0.30)
    kelly_min: float = Field(0.02)


class FusionConfig(BaseModel):
    """融合引擎全局配置"""
    fusion_enabled: bool = Field(True)
    macro_layer_enabled: bool = Field(True)
    sentiment_layer_enabled: bool = Field(True)
    volatility_layer_enabled: bool = Field(True)
    position_limit: PositionLimitConfig = Field(default_factory=PositionLimitConfig)
    macro_config: MacroLayerConfig = Field(default_factory=MacroLayerConfig)
    sentiment_config: SentimentLayerConfig = Field(default_factory=SentimentLayerConfig)
    volatility_config: VolatilityLayerConfig = Field(default_factory=VolatilityLayerConfig)
    tactical_ratio_map: Dict[str, float] = Field(default_factory=lambda: {
        "weekly": 0.60, "daily": 0.30, "30min": 0.10,
    })
    holding_period_map: Dict[str, str] = Field(default_factory=lambda: {
        "weekly": "日线级别预期8-12周",
        "daily": "日线级别预期2-4周",
        "30min": "日线级别预期3-5日",
    })
