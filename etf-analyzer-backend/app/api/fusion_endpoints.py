"""
融合引擎 API 路由
==================
提供五维融合决策引擎的 RESTful API 接口：
- POST /api/v1/analyze-fusion — 五维融合分析
- GET /api/v1/macro/status — 当前宏观周期
- GET /api/v1/sentiment/status — 当前市场情绪
- GET /api/v1/volatility/{code} — ETF波动率状态

新增接口不破坏现有 /api/v1/analyze 的行为。
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException

from app.config import settings
from app.fusion_engine.fusion_core import FusionEngine
from app.models.fusion_models import (
    DecisionCard,
    FusionAnalysisRequest,
    FusionAnalysisResponse,
    MacroLayerConfig,
    MacroResult,
    PositionCalculation,
    SentimentLayerConfig,
    SentimentMetrics,
    SentimentResult,
    ValidatedSignal,
    VolatilityLayerConfig,
    VolatilityMetrics,
    VolatilityResult,
)

logger = logging.getLogger(__name__)

# 融合引擎路由（使用独立前缀，避免与现有路由冲突）
fusion_router = APIRouter(prefix="/api/v1")

# 全局融合引擎实例（单例）
fusion_engine = FusionEngine()

# ────────────────────────────── 融合分析核心接口 ──────────────────────────────


@fusion_router.post("/analyze-fusion", response_model=FusionAnalysisResponse)
async def analyze_fusion(request: FusionAnalysisRequest):
    """五维融合分析

    对指定ETF执行五维融合分析，整合宏观、缠论、情绪、波动率、丁昶五层信号，
    生成融合决策卡片（DecisionCard），包含仓位计算和执行计划。

    Parameters
    ----------
    request : FusionAnalysisRequest
        包含 etf_code, timeframe, include_minute, analysis_depth

    Returns
    -------
    FusionAnalysisResponse
        五维融合分析结果，包含决策卡片和各层独立结果
    """
    start_time = time.time()
    etf_code = request.etf_code.strip()
    timeframe = request.timeframe

    logger.info("收到五维融合分析请求: ETF=%s, timeframe=%s", etf_code, timeframe)

    # 模拟/构造各层分析结果
    # 注：实际生产环境中，这些应由对应的子代理（宏观/情绪/波动率）提供
    # 当前版本使用模拟数据演示融合引擎的完整流程

    # 1. 宏观层结果（模拟）
    macro_result = _mock_macro_result()

    # 2. 情绪层结果（模拟）
    sentiment_result = _mock_sentiment_result()

    # 3. 波动率层结果（模拟）
    volatility_result = _mock_volatility_result(etf_code)

    # 4. 缠论结果（模拟信号部分）
    chanlun_result = _mock_chanlun_result(etf_code, timeframe)

    # 5. 丁昶结果（模拟信号部分）
    dingchang_result = _mock_dingchang_result(etf_code)

    # 执行融合分析
    try:
        decision_card = fusion_engine.quick_analyze(
            etf_code=etf_code,
            chanlun_result=chanlun_result,
            dingchang_result=dingchang_result,
            macro_result=macro_result,
            sentiment_result=sentiment_result,
            volatility_result=volatility_result,
        )

        processing_time = int((time.time() - start_time) * 1000)

        return FusionAnalysisResponse(
            success=True,
            message="五维融合分析完成",
            decision_card=decision_card,
            macro_result=macro_result,
            sentiment_result=sentiment_result,
            volatility_result=volatility_result,
            validated_signal=decision_card.validated_signal,
            processing_time_ms=processing_time,
            data_source=settings.DATA_SOURCE,
            analysis_time=datetime.now(),
        )

    except Exception as e:
        logger.error("五维融合分析失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"融合分析失败: {e}")


# ────────────────────────────── 宏观层状态接口 ──────────────────────────────


@fusion_router.get("/macro/status")
async def get_macro_status():
    """获取当前宏观周期状态

    Returns
    -------
    dict
        宏观周期状态，包含周期名称、仓位限制、资产配置建议等
    """
    logger.debug("获取宏观周期状态")

    macro_result = _mock_macro_result()

    return {
        "success": True,
        "cycle": {
            "name": macro_result.cycle.cycle_name,
            "code": macro_result.cycle.cycle_code,
            "confidence": macro_result.cycle.confidence,
        },
        "position_limit": macro_result.position_limit,
        "position_limit_pct": macro_result.position_limit_pct,
        "policy_stance": macro_result.policy_stance,
        "rate_direction": macro_result.rate_direction,
        "asset_favor": macro_result.asset_favor,
        "asset_avoid": macro_result.asset_avoid,
        "macro_risks": macro_result.macro_risks,
        "summary": macro_result.summary,
        "update_time": macro_result.update_time,
    }


# ────────────────────────────── 情绪层状态接口 ──────────────────────────────


@fusion_router.get("/sentiment/status")
async def get_sentiment_status():
    """获取当前市场情绪状态

    Returns
    -------
    dict
        市场情绪状态，包含情绪等级、贪婪恐惧指数、各市场信号等
    """
    logger.debug("获取市场情绪状态")

    sentiment_result = _mock_sentiment_result()

    return {
        "success": True,
        "grade": sentiment_result.grade,
        "grade_description": sentiment_result.grade_description,
        "metrics": {
            "greed_fear_index": sentiment_result.metrics.greed_fear_index,
            "a_share_sentiment": sentiment_result.metrics.a_share_sentiment,
            "northbound_sentiment": sentiment_result.metrics.northbound_sentiment,
            "margin_sentiment": sentiment_result.metrics.margin_sentiment,
            "options_skew": sentiment_result.metrics.options_skew,
            "fund_flow_5d": sentiment_result.metrics.fund_flow_5d,
        },
        "final_confidence": sentiment_result.final_confidence,
        "market_signals": sentiment_result.market_signals,
        "summary": sentiment_result.summary,
        "update_time": sentiment_result.update_time,
    }


# ────────────────────────────── 波动率层状态接口 ──────────────────────────────


@fusion_router.get("/volatility/{code}")
async def get_volatility_status(code: str):
    """获取ETF波动率状态

    Parameters
    ----------
    code : str
        ETF代码

    Returns
    -------
    dict
        ETF波动率状态，包含历史波动率、ATR、波动率区间等
    """
    logger.debug("获取ETF %s 波动率状态", code)

    volatility_result = _mock_volatility_result(code)

    return {
        "success": True,
        "etf_code": code,
        "position_coefficient": volatility_result.position_coefficient,
        "metrics": {
            "hv_20": volatility_result.metrics.hv_20,
            "hv_60": volatility_result.metrics.hv_60,
            "iv_proxy": volatility_result.metrics.iv_proxy,
            "atr_14": volatility_result.metrics.atr_14,
            "atr_ratio": volatility_result.metrics.atr_ratio,
            "vol_regime": volatility_result.metrics.vol_regime,
            "vol_trend": volatility_result.metrics.vol_trend,
        },
        "vol_risk_flag": volatility_result.vol_risk_flag,
        "vol_risk_description": volatility_result.vol_risk_description,
        "summary": volatility_result.summary,
        "update_time": volatility_result.update_time,
    }


# ────────────────────────────── 模拟数据生成（演示用） ──────────────────────────────

# 在实际生产环境中，以下函数应由真实的宏观/情绪/波动率子代理替代


def _mock_macro_result() -> MacroResult:
    """生成模拟宏观层结果（演示用）"""
    return MacroResult(
        quadrant="I_recovery",
        quadrant_name="复苏期",
        position_limit=0.9,
        position_limit_pct="90%",
        chan_enabled=True,
        ding_style="growth",
        credit_status="expansion",
        inventory_status="destocking",
        asset_favor=["股票型ETF", "科创ETF", "纳指ETF"],
        asset_avoid=["长期国债ETF"],
        policy_stance="宽松",
        rate_direction="下降",
        macro_risks=["地缘政治不确定性"],
        description="信用扩张+库存去化，经济复苏初期",
        summary="复苏期-积极配置",
    )


def _mock_sentiment_result() -> SentimentResult:
    """生成模拟情绪层结果（演示用）

    实际生产环境应调用情绪分析子代理获取真实数据。
    """
    return SentimentResult(
        grade="B",
        grade_description="B级: 市场情绪中性偏多，适合正常执行",
        metrics=SentimentMetrics(
            greed_fear_index=62.5,
            a_share_sentiment=0.25,
            northbound_sentiment=0.35,
            margin_sentiment=0.15,
            options_skew=-0.02,
            fund_flow_5d=45.2,
        ),
        final_confidence=65.0,
        market_signals={
            "a_share": "偏多",
            "northbound": "流入",
            "margin": "谨慎",
            "options": "中性",
        },
        summary="市场情绪B级，中性偏多。贪婪恐惧指数62.5，北向资金持续流入，"
                "但融资情绪偏谨慎。适合正常执行交易策略。",
    )


def _mock_volatility_result(code: str) -> VolatilityResult:
    """生成模拟波动率层结果（演示用）

    实际生产环境应调用波动率分析子代理获取真实数据。
    """
    # 模拟正常波动率状态
    return VolatilityResult(
        position_coefficient=0.85,  # 正常波动率 → 略微降低仓位
        metrics=VolatilityMetrics(
            hv_20=0.18,
            hv_60=0.20,
            iv_proxy=0.19,
            atr_14=0.45,
            atr_ratio=0.012,
            vol_regime="normal",
            vol_trend="stable",
        ),
        vol_risk_flag="",
        vol_risk_description="波动率处于正常区间，无特殊风险",
        summary=f"ETF {code} 20日历史波动率18%，60日20%，波动率趋势稳定。"
                "当前处于正常波动率区间，仓位系数0.85。",
    )


def _mock_chanlun_result(code: str, timeframe: str) -> Dict[str, Any]:
    """生成模拟缠论分析结果（演示用）

    实际生产环境应调用缠论引擎获取真实分析结果。
    """
    return {
        "etf_code": code,
        "etf_name": f"ETF-{code}",
        "signal": {
            "direction": "buy",
            "level": timeframe,
            "strength": 0.72,
            "price": 4.235,
        },
        "trend_position": "上升趋势",
        "divergence": {
            "type": "bullish",
            "strength": 0.65,
        },
        "divergence_type": "bullish",
        "divergence_strength": 0.65,
        "composite_resonance": 68.5,
        "current_price": 4.235,
        "buy_sell_points": [
            {"type": "二买", "price": 4.15, "confidence": 0.75},
        ],
    }


def _mock_dingchang_result(code: str) -> Dict[str, Any]:
    """生成模拟丁昶分析结果（演示用）

    实际生产环境应调用丁昶引擎获取真实分析结果。
    """
    return {
        "etf_code": code,
        "signal": {
            "weight": 0.28,  # 估值权重
            "direction": "bullish",
            "strength": 0.68,
        },
        "composite_score": 75.5,
        "rating": "买入",
    }
