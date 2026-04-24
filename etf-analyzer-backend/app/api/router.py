"""
API路由模块
============
提供ETF多框架分析系统的RESTful API接口：
- POST /api/v1/analyze — 多框架分析
- GET /api/v1/etf/list — ETF列表
- GET /api/v1/etf/{code}/basic — ETF基本信息
- GET /api/v1/etf/{code}/chanlun — 李彪分析框架单独分析
- GET /api/v1/etf/{code}/dingchang — 丁昶分析框架单独分析
- GET /api/v1/etf/{code}/multi-timeframe — 多周期数据
- GET /api/v1/health — 健康检查
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import pandas as pd
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from app.config import settings
from app.chanlun.engine import ChanlunEngine
from app.data.fetcher import get_data_fetcher, DataFetchError
from app.dingchang.engine import DingChangEngine
from app.models.chanlun import ChanlunResult
from app.models.dingchang import (
    DingChangResult,
    ETFAnalysisRequest,
    ETFAnalysisResponse,
    ETFListResponse,
    ETFSimpleInfo,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1")

# 全局引擎实例（单例）
chanlun_engine = ChanlunEngine()
data_fetcher = get_data_fetcher()
dingchang_engine = DingChangEngine(fetcher=data_fetcher)


# ────────────────────────────── 健康检查 ──────────────────────────────

@router.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "ok", "version": settings.APP_VERSION}


# ────────────────────────────── 核心分析接口 ──────────────────────────────

@router.post("/analyze", response_model=ETFAnalysisResponse)
async def analyze_etf(request: ETFAnalysisRequest):
    """ETF多框架综合分析

    同时对指定ETF执行李彪分析框架技术分析和丁昶分析框架五维评分，
    返回包含两种框架结果的综合分析报告。

    Parameters
    ----------
    request : ETFAnalysisRequest
        包含 etf_code, timeframe, include_minute, analysis_depth

    Returns
    -------
    ETFAnalysisResponse
        多框架综合分析结果
    """
    start_time = time.time()
    etf_code = request.etf_code.strip()

    logger.info(f"收到分析请求: ETF={etf_code}, depth={request.analysis_depth}")

    try:
        # 1. 获取日线数据
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=730)).strftime("%Y%m%d")
        df_daily = data_fetcher.get_etf_daily(etf_code, start_date, end_date)

        if df_daily.empty:
            raise HTTPException(status_code=404, detail=f"未找到ETF {etf_code} 的数据")

        # 2. 获取多周期数据
        df_weekly = None
        df_hourly = None
        if request.include_minute:
            try:
                start_weekly = (datetime.now() - timedelta(days=1825)).strftime("%Y%m%d")
                df_weekly = data_fetcher.get_etf_weekly(etf_code, start_weekly, end_date)
                df_hourly = data_fetcher.get_etf_hourly(etf_code)
            except Exception as e:
                logger.warning(f"获取多周期数据失败: {e}")

        # 3. 运行李栋分析框架分析
        try:
            chanlun_result = chanlun_engine.analyze(
                df_weekly=df_weekly,
                df_daily=df_daily,
                df_hourly=df_hourly,
                etf_code=etf_code,
                etf_name=""
            )
            chanlun_dict = chanlun_result.model_dump()
        except Exception as e:
            logger.error(f"李彪分析框架分析失败: {e}")
            chanlun_dict = {
                "error": str(e),
                "etf_code": etf_code,
                "warning": f"李彪分析框架分析失败: {str(e)}。该ETF可能数据不足或不符合分析条件。"
            }

        # 4. 运行丁昶分析框架分析
        try:
            dingchang_result = dingchang_engine.analyze(
                etf_code=etf_code,
                df_daily=df_daily,
                etf_name=""
            )
            dingchang_dict = dingchang_result.model_dump()
        except Exception as e:
            logger.error(f"丁昶分析框架分析失败: {e}")
            dingchang_dict = {
                "error": str(e),
                "etf_code": etf_code,
                "warning": f"丁昶分析框架分析失败: {str(e)}。该ETF可能数据不足或不符合分析条件。"
            }

        # 5. 生成综合分析摘要
        summary = _generate_dual_summary(chanlun_dict, dingchang_dict)
        action = _determine_dual_action(chanlun_dict, dingchang_dict)
        dual_signal = _assess_dual_alignment(chanlun_dict, dingchang_dict)
        confidence = _calc_dual_confidence(chanlun_dict, dingchang_dict)

        processing_time = int((time.time() - start_time) * 1000)

        # 检测实际使用的数据源
        actual_source = settings.DATA_SOURCE
        if hasattr(df_daily, 'attrs') and df_daily.attrs.get('data_source'):
            actual_source = df_daily.attrs['data_source']
        elif hasattr(data_fetcher, 'primary_source_name'):
            actual_source = data_fetcher.primary_source_name

        return ETFAnalysisResponse(
            success=True,
            message="分析完成",
            chanlun=chanlun_dict,
            dingchang=dingchang_dict,
            summary=summary,
            action=action,
            dual_signal=dual_signal,
            confidence=confidence,
            processing_time_ms=processing_time,
            data_source=actual_source,
            analysis_time=datetime.now()
        )

    except HTTPException:
        raise
    except DataFetchError as e:
        logger.error(f"数据获取失败: {e}")
        raise HTTPException(status_code=503, detail=f"数据获取失败: {e}")
    except Exception as e:
        logger.error(f"分析过程出错: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"分析过程出错: {e}")


@router.get("/etf/list")
async def get_etf_list(
    category: Optional[str] = Query(None, description="ETF类别筛选"),
    limit: int = Query(1000, ge=1, le=5000, description="返回数量限制")
):
    """获取ETF列表

    Parameters
    ----------
    category : str, optional
        ETF类别筛选（如 '股票型', '跨境型'）
    limit : int
        返回数量限制

    Returns
    -------
    ETFListResponse
        ETF列表
    """
    try:
        df = data_fetcher.get_etf_list()
        if df.empty:
            return ETFListResponse(count=0, etfs=[])

        # 筛选
        if category and '类型' in df.columns:
            df = df[df['类型'] == category]

        df = df.head(limit)

        etfs = []
        for _, row in df.iterrows():
            try:
                etfs.append(ETFSimpleInfo(
                    code=str(row.get('代码', '')),
                    name=str(row.get('名称', '')),
                    price=float(row.get('最新价', 0)) if pd.notna(row.get('最新价')) else 0.0,
                    change_pct=float(row.get('涨跌幅', 0)) if pd.notna(row.get('涨跌幅')) else 0.0,
                    volume=float(row.get('成交量', 0)) if pd.notna(row.get('成交量')) else 0.0,
                    category=str(row.get('类型', ''))
                ))
            except Exception:
                continue

        # 检测实际使用的数据源
        actual_source = settings.DATA_SOURCE
        if hasattr(data_fetcher, 'primary_source_name'):
            actual_source = data_fetcher.primary_source_name

        return ETFListResponse(
            count=len(etfs),
            etfs=etfs,
            data_source=actual_source,
            update_time=datetime.now()
        )

    except Exception as e:
        logger.error(f"获取ETF列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取ETF列表失败: {e}")


@router.get("/etf/{code}/basic")
async def get_etf_basic(code: str):
    """获取ETF基本信息

    Parameters
    ----------
    code : str
        ETF代码

    Returns
    -------
    dict
        ETF基本信息
    """
    try:
        info = data_fetcher.get_etf_info(code)
        return info
    except DataFetchError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"获取ETF {code} 基本信息失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取失败: {e}")


@router.get("/etf/{code}/chanlun")
async def get_chanlun_analysis(code: str):
    """获取ETF李彪分析框架单独分析

    Parameters
    ----------
    code : str
        ETF代码

    Returns
    -------
    dict
        李彪分析框架分析结果
    """
    try:
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=730)).strftime("%Y%m%d")

        df_daily = data_fetcher.get_etf_daily(code, start_date, end_date)
        if df_daily.empty:
            raise HTTPException(status_code=404, detail=f"未找到ETF {code} 数据")

        # 获取多周期数据
        try:
            start_weekly = (datetime.now() - timedelta(days=1825)).strftime("%Y%m%d")
            df_weekly = data_fetcher.get_etf_weekly(code, start_weekly, end_date)
            df_hourly = data_fetcher.get_etf_hourly(code)
        except Exception:
            df_weekly = None
            df_hourly = None

        result = chanlun_engine.analyze(
            df_weekly=df_weekly,
            df_daily=df_daily,
            df_hourly=df_hourly,
            etf_code=code
        )
        return result.model_dump()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"李彪分析框架分析ETF {code} 失败: {e}")
        raise HTTPException(status_code=500, detail=f"分析失败: {e}")


@router.get("/etf/{code}/dingchang")
async def get_dingchang_analysis(code: str):
    """获取ETF丁昶分析框架单独分析

    Parameters
    ----------
    code : str
        ETF代码

    Returns
    -------
    dict
        丁昶分析框架分析结果
    """
    try:
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=730)).strftime("%Y%m%d")

        df_daily = data_fetcher.get_etf_daily(code, start_date, end_date)
        if df_daily.empty:
            raise HTTPException(status_code=404, detail=f"未找到ETF {code} 数据")

        result = dingchang_engine.analyze(etf_code=code, df_daily=df_daily)
        return result.model_dump()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"丁昶分析框架分析ETF {code} 失败: {e}")
        raise HTTPException(status_code=500, detail=f"分析失败: {e}")


@router.get("/etf/{code}/multi-timeframe")
async def get_multi_timeframe_data(code: str):
    """获取ETF多周期数据

    Parameters
    ----------
    code : str
        ETF代码

    Returns
    -------
    dict
        多周期数据摘要
    """
    try:
        data = data_fetcher.get_multi_timeframe(code)

        result = {}
        for tf, df in data.items():
            if df is not None and not df.empty:
                result[tf] = {
                    "points": len(df),
                    "date_range": f"{df['date'].iloc[0]} ~ {df['date'].iloc[-1]}",
                    "latest_close": float(df['close'].iloc[-1]),
                    "latest_high": float(df['high'].iloc[-1]),
                    "latest_low": float(df['low'].iloc[-1]),
                    "volume": float(df['volume'].iloc[-1]),
                }
            else:
                result[tf] = {"points": 0, "error": "无数据"}

        return result

    except Exception as e:
        logger.error(f"获取多周期数据失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取失败: {e}")


# ────────────────────────────── 辅助函数 ──────────────────────────────

def _generate_dual_summary(chanlun: Dict, dingchang: Dict) -> str:
    """生成多框架综合分析摘要"""
    parts = []

    # 李彪分析框架摘要
    if "trend_position" in chanlun:
        parts.append(f"李彪: {chanlun['trend_position']}")
    if "divergence_type" in chanlun and chanlun["divergence_type"] != "none":
        parts.append(f"背驰: {chanlun['divergence_type']}")

    # 丁昶分析框架摘要
    if "composite_score" in dingchang:
        parts.append(f"丁昶分析框架: {dingchang['composite_score']:.0f}分/{dingchang.get('rating', 'N/A')}")

    return " | ".join(parts) if parts else "分析完成"


def _determine_dual_action(chanlun: Dict, dingchang: Dict) -> str:
    """确定多框架综合行动建议"""
    # 丁昶分析框架评级
    rating = dingchang.get("rating", "")
    composite = dingchang.get("composite_score", 50)

    # 李彪分析框架信号
    divergence = chanlun.get("divergence_type", "none")
    resonance = chanlun.get("composite_resonance", 0)

    # 综合判断
    if rating == "买入" and divergence in ("bullish", "none") and resonance >= 50:
        return "强烈关注"
    elif rating in ("买入", "持有") and (divergence != "none" or resonance >= 50):
        return "关注"
    elif composite >= 60 or resonance >= 60:
        return "关注"
    elif composite >= 40:
        return "观望"
    else:
        return "回避"


def _assess_dual_alignment(chanlun: Dict, dingchang: Dict) -> str:
    """评估多框架信号一致性"""
    # 李彪分析框架趋势
    trend = chanlun.get("trend_position", "")
    chanlun_bullish = "上升" in trend or "bullish" in chanlun.get("divergence_type", "")
    chanlun_bearish = "下跌" in trend or "bearish" in chanlun.get("divergence_type", "")

    # 丁昶分析框架信号
    signal = dingchang.get("composite_signal", "")
    dingchang_bullish = signal == "bullish"
    dingchang_bearish = signal == "bearish"

    # 判断一致性
    if (chanlun_bullish and dingchang_bullish) or (chanlun_bearish and dingchang_bearish):
        return "aligned"
    elif (chanlun_bullish and dingchang_bearish) or (chanlun_bearish and dingchang_bullish):
        return "conflicting"
    else:
        return "mixed"


def _calc_dual_confidence(chanlun: Dict, dingchang: Dict) -> float:
    """计算多框架综合置信度"""
    # 李彪分析框架置信度
    chanlun_conf = chanlun.get("trend_confidence", 0.5)
    resonance = chanlun.get("composite_resonance", 50) / 100

    # 丁昶分析框架置信度（信号强度）
    dingchang_conf = dingchang.get("signal_strength", 0.5)

    # 综合
    return round(min(1.0, (chanlun_conf + resonance + dingchang_conf) / 3), 3)
