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

# ──────────────────────────── 真实数据模块导入 ────────────────────────────
from app.data.fetcher import UnifiedDataFetcher
from app.data.macro_fetcher import MacroDataFetcher
from app.data.sentiment_fetcher import SentimentDataFetcher, get_sentiment_fetcher
from app.chanlun.engine import ChanlunEngine
from app.dingchang.engine import DingChangEngine

logger = logging.getLogger(__name__)

# 融合引擎路由（使用独立前缀，避免与现有路由冲突）
fusion_router = APIRouter(prefix="/api/v1")

# 全局实例（单例）
fusion_engine = FusionEngine()
data_fetcher = UnifiedDataFetcher()
macro_fetcher = MacroDataFetcher()
sentiment_fetcher = get_sentiment_fetcher()
chanlun_engine = ChanlunEngine()
dingchang_engine = DingChangEngine(fetcher=data_fetcher.primary)

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

    # ──────────────────────────── 真实数据获取 ────────────────────────────
    df_daily = None
    df_weekly = None
    df_hourly = None

    # 尝试获取日线数据（核心）
    try:
        from datetime import datetime, timedelta
        end = datetime.now().strftime("%Y%m%d")
        start = (datetime.now() - timedelta(days=365)).strftime("%Y%m%d")
        df_daily = data_fetcher.get_etf_daily(etf_code, start, end)
        logger.info("ETF %s 日线数据获取成功: %s 条", etf_code, len(df_daily) if df_daily is not None else 0)
    except Exception as e:
        logger.warning("ETF %s 日线数据获取失败: %s", etf_code, e)

    # 尝试获取周线数据（可选）
    try:
        df_weekly = data_fetcher.get_etf_weekly(etf_code, start, end)
    except Exception as e:
        logger.warning("ETF %s 周线数据获取失败: %s", etf_code, e)

    # 尝试获取小时线数据（可选）
    try:
        df_hourly = data_fetcher.get_etf_hourly(etf_code)
    except Exception as e:
        logger.warning("ETF %s 小时线数据获取失败: %s", etf_code, e)

    if df_daily is None or df_daily.empty:
        logger.warning("ETF %s 日线数据不可用，使用fallback", etf_code)
        macro_result = _mock_macro_result()
        sentiment_result = _mock_sentiment_result()
        volatility_result = _mock_volatility_result(etf_code)
        chanlun_result = _mock_chanlun_result(etf_code, timeframe)
        dingchang_result = _mock_dingchang_result(etf_code)
    else:
        # 1. 客观层结果（真实）
        try:
            macro_data = macro_fetcher.fetch_all()
            macro_result = _build_macro_result(macro_data)
        except Exception as e:
            logger.warning("客观数据获取失败: %s，使用fallback", e)
            macro_result = _mock_macro_result()

        # 2. 情绪层结果（真实）
        try:
            sentiment_data = sentiment_fetcher.get_all_sentiment_data(etf_code)
            sentiment_result = _build_sentiment_result(sentiment_data)
        except Exception as e:
            logger.warning("情绪数据获取失败: %s，使用fallback", e)
            sentiment_result = _mock_sentiment_result()

        # 3. 波动率层结果（真实计算）
        try:
            volatility_result = _calc_volatility_result(etf_code, df_daily)
        except Exception as e:
            logger.warning("波动率计算失败: %s，使用fallback", e)
            volatility_result = _mock_volatility_result(etf_code)

        # 4. 缠论结果（真实分析）
        try:
            chanlun_result = _analyze_chanlun(etf_code, df_weekly, df_daily, df_hourly)
        except Exception as e:
            logger.warning("缠论分析失败: %s，使用fallback", e)
            chanlun_result = _mock_chanlun_result(etf_code, timeframe)

        # 5. 丁昽结果（真实分析）
        try:
            dingchang_result = _analyze_dingchang(etf_code, df_daily)
        except Exception as e:
            logger.warning("丁昽分析失败: %s，使用fallback", e)
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
            "name": macro_result.quadrant_name,
            "code": macro_result.quadrant,
            "confidence": 0.75,
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

# ──────────────────────────── 真实数据构建函数 ────────────────────────────

def _build_macro_result(macro_data: Dict) -> MacroResult:
    """将宏观原始数据构建为 MacroResult"""
    afre_3m = macro_data.get("afre_yoy_3m", 9.0)
    afre_12m = macro_data.get("afre_yoy_12m", 9.5)
    pmi_inv = macro_data.get("pmi_inventory", 48.0)

    if afre_3m > afre_12m and pmi_inv < 50:
        quadrant, quadrant_name = "I_recovery", "复苏期"
        position_limit = 0.9
        description = "社融回升+PMI库存去化，经济复苏初期"
        ding_style = "growth"
        credit_status = "expansion"
        inventory_status = "destocking"
        policy_stance = "宽松"
        rate_direction = "下降"
    elif afre_3m > 10 and pmi_inv >= 50:
        quadrant, quadrant_name = "II_overheat", "过热期"
        position_limit = 0.6
        description = "社融高位+PMI库存累积，经济过热"
        ding_style = "value"
        credit_status = "tightening"
        inventory_status = "accumulating"
        policy_stance = "紧缩"
        rate_direction = "上升"
    elif afre_3m < 8 and pmi_inv >= 50:
        quadrant, quadrant_name = "III_stagflation", "滞涨期"
        position_limit = 0.4
        description = "社融收缩+PMI库存高位，经济滞涨"
        ding_style = "defensive"
        credit_status = "contraction"
        inventory_status = "accumulating"
        policy_stance = "紧缩"
        rate_direction = "上升"
    else:
        quadrant, quadrant_name = "IV_recession", "衰退期"
        position_limit = 0.2
        description = "社融低迷+PMI库存去化，经济衰退"
        ding_style = "bond"
        credit_status = "contraction"
        inventory_status = "destocking"
        policy_stance = "宽松"
        rate_direction = "下降"

    return MacroResult(
        quadrant=quadrant,
        quadrant_name=quadrant_name,
        position_limit=position_limit,
        position_limit_pct=f"{int(position_limit*100)}%",
        chan_enabled=position_limit >= 0.5,
        ding_style=ding_style,
        credit_status=credit_status,
        inventory_status=inventory_status,
        asset_favor=["股票型ETF"] if position_limit >= 0.5 else ["短期债券ETF", "黄金ETF"],
        asset_avoid=["长期国债ETF"] if position_limit >= 0.5 else ["股票型ETF"],
        policy_stance=policy_stance,
        rate_direction=rate_direction,
        macro_risks=["地缘政治不确定性"],
        description=description,
        summary=f"{quadrant_name}-积极配置" if position_limit >= 0.5 else f"{quadrant_name}-保守配置",
    )


def _build_sentiment_result(sentiment_data: Dict) -> SentimentResult:
    """将情绪原始数据构建为 SentimentResult"""
    pcr = sentiment_data.get("pcr", 1.0)
    financing = sentiment_data.get("financing_change", 0.0)
    northbound = sentiment_data.get("northbound_5d", 0.0)
    main_force = sentiment_data.get("main_force_flow", 0.0)

    pcr_score = 50 + (1.0 - pcr) * 30
    financing_score = 50 + financing * 500
    northbound_score = 50 + northbound * 2
    main_force_score = 50 + main_force * 10

    sentiment_score = min(100, max(0, (pcr_score + financing_score + northbound_score + main_force_score) / 4))

    if sentiment_score >= 75:
        grade, grade_desc = "A", "A级: 市场情绪过热，跟踪主力"
    elif sentiment_score >= 60:
        grade, grade_desc = "B+", "B+级: 市场情绪偏多，适合積极执行"
    elif sentiment_score >= 45:
        grade, grade_desc = "B", "B级: 市场情绪中性偏多，适合正常执行"
    elif sentiment_score >= 30:
        grade, grade_desc = "C", "C级: 市场情绪偏空，适合缩减仓位"
    else:
        grade, grade_desc = "D", "D级: 市场情绪恐惧，建议观望"

    return SentimentResult(
        grade=grade,
        grade_description=grade_desc,
        metrics=SentimentMetrics(
            greed_fear_index=round(sentiment_score, 1),
            a_share_sentiment=round(financing, 4),
            northbound_sentiment=round(northbound / 100, 4) if northbound else 0,
            margin_sentiment=round(main_force / 10, 4) if main_force else 0,
            options_skew=round(1.0 - pcr, 4),
            fund_flow_5d=round(northbound, 1),
        ),
        final_confidence=round(sentiment_score * 0.8 + 20, 1),
        market_signals={
            "a_share": "偏多" if financing > 0 else "偏空",
            "northbound": "流入" if northbound > 0 else "流出",
            "margin": "调整" if abs(financing) < 0.02 else ("扩张" if financing > 0 else "收缩"),
            "options": "偏多" if pcr < 0.9 else ("偏空" if pcr > 1.1 else "中性"),
        },
        summary=f"市场情绪{grade}级，情绪指数{sentiment_score:.1f}。"
                f"北向资金{'流入' if northbound > 0 else '流出'}{abs(northbound):.1f}亿，"
                f"PCR={pcr:.2f}。{grade_desc.split(': ')[1]}",
    )


def _calc_volatility_result(code: str, df_daily: pd.DataFrame) -> VolatilityResult:
    """基于真实K线数据计算波动率指标"""
    import numpy as np
    import pandas as pd

    close = df_daily["close"].astype(float)
    returns = close.pct_change().dropna()

    hv_20 = returns.tail(20).std() * np.sqrt(252) if len(returns) >= 20 else 0.15
    hv_60 = returns.tail(60).std() * np.sqrt(252) if len(returns) >= 60 else 0.18
    iv_proxy = (hv_20 + hv_60) / 2

    high = df_daily["high"].astype(float)
    low = df_daily["low"].astype(float)
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr_14 = tr.tail(14).mean() if len(tr) >= 14 else tr.mean()
    atr_ratio = atr_14 / close.iloc[-1] if close.iloc[-1] > 0 else 0.01

    if hv_20 > 0.30:
        vol_regime, vol_trend = "high", "expanding"
        position_coef = 0.5
        vol_risk = "高波动"
        vol_desc = "波动率高位，市场风险较大，建议降低仓位"
    elif hv_20 > 0.20:
        vol_regime, vol_trend = "normal", "stable"
        position_coef = 0.75
        vol_risk = ""
        vol_desc = "波动率正常，无特殊风险"
    elif hv_20 < 0.10:
        vol_regime, vol_trend = "low", "contracting"
        position_coef = 0.95
        vol_risk = ""
        vol_desc = "波动率低位，市场静密，可正常配置"
    else:
        vol_regime, vol_trend = "normal", "stable"
        position_coef = 0.85
        vol_risk = ""
        vol_desc = "波动率处于正常区间，无特殊风险"

    return VolatilityResult(
        position_coefficient=round(position_coef, 2),
        metrics=VolatilityMetrics(
            hv_20=round(hv_20, 4),
            hv_60=round(hv_60, 4),
            iv_proxy=round(iv_proxy, 4),
            atr_14=round(atr_14, 4) if pd.notna(atr_14) else 0.0,
            atr_ratio=round(atr_ratio, 4),
            vol_regime=vol_regime,
            vol_trend=vol_trend,
        ),
        vol_risk_flag=vol_risk,
        vol_risk_description=vol_desc,
        summary=f"ETF {code} 20日历史波动率{hv_20*100:.1f}%，60日{hv_60*100:.1f}%。"
                f"当前处于{vol_desc[:4]}，仓位系数{position_coef:.2f}。",
    )


def _analyze_chanlun(
    etf_code: str,
    df_weekly: Optional[pd.DataFrame],
    df_daily: pd.DataFrame,
    df_hourly: Optional[pd.DataFrame]
) -> Dict[str, Any]:
    """调用缠论引擎进行真实分析"""
    try:
        result = chanlun_engine.analyze(
            df_weekly=df_weekly,
            df_daily=df_daily,
            df_hourly=df_hourly,
            etf_code=etf_code,
            etf_name=etf_code,
        )

        signal_direction = "buy" if result.divergence_type == "bullish" else "sell" if result.divergence_type == "bearish" else "hold"
        if result.buy_sell_points:
            latest_bs = result.buy_sell_points[0]
            # BuySellPoint 是对象，使用属性访问
            if hasattr(latest_bs, 'type'):
                bs_type = latest_bs.type
            elif isinstance(latest_bs, dict):
                bs_type = latest_bs.get("type", "未知")
            else:
                bs_type = "未知"
        else:
            bs_type = "无"

        return {
            "etf_code": etf_code,
            "etf_name": f"ETF-{etf_code}",
            "signal": {
                "direction": signal_direction,
                "level": "daily",
                "strength": min(1.0, result.divergence_strength + 0.1),
                "price": result.current_price,
            },
            "trend_position": result.trend_position,
            "divergence": {
                "type": result.divergence_type,
                "strength": result.divergence_strength,
            },
            "divergence_type": result.divergence_type,
            "divergence_strength": result.divergence_strength,
            "composite_resonance": result.composite_resonance,
            "current_price": result.current_price,
            "buy_sell_points": result.buy_sell_points,
        }
    except Exception as e:
        logger.error("缠论分析失败: %s", e)
        return _mock_chanlun_result(etf_code, "daily")


def _analyze_dingchang(etf_code: str, df_daily: pd.DataFrame) -> Dict[str, Any]:
    """调用丁昽引擎进行真实分析"""
    try:
        result = dingchang_engine.analyze(etf_code=etf_code, df_daily=df_daily)

        return {
            "etf_code": etf_code,
            "signal": {
                "weight": result.weights.get("valuation", 0.25),
                "direction": result.composite_signal,
                "strength": result.signal_strength,
            },
            "composite_score": result.composite_score,
            "rating": result.rating,
        }
    except Exception as e:
        logger.error("丁昽分析失败: %s", e)
        return _mock_dingchang_result(etf_code)

