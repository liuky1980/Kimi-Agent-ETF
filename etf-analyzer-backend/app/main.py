"""
ETF多框架分析系统 — FastAPI 入口
=====================================
基于李彪分析框架与丁昶分析框架的ETF智能分析工具。

技术栈:
- FastAPI: 高性能异步Web框架
- akshare: 免费A股数据源
- pandas/numpy: 数据分析
- 李彪分析框架引擎: 分型/笔/线段/中枢/背驰/买卖点/共振
- 丁昶分析框架引擎: 五维评分体系
"""

import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.fusion_endpoints import fusion_router
from app.api.router import router
from app.config import settings

# ────────────────────────────── 日志配置 ──────────────────────────────

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
    format=settings.LOG_FORMAT,
    handlers=[
        logging.StreamHandler(sys.stdout),
    ]
)
logger = logging.getLogger(__name__)

# ────────────────────────────── 生命周期管理 ──────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理

    启动时执行初始化，关闭时执行清理。
    """
    # 启动
    logger.info("=" * 60)
    logger.info(f"启动 {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info(f"环境: {settings.ENV}")
    logger.info(f"调试模式: {settings.DEBUG}")
    logger.info("=" * 60)

    yield

    # 关闭
    logger.info("应用关闭，执行清理...")


# ────────────────────────────── FastAPI 应用 ──────────────────────────────

app = FastAPI(
    title=settings.APP_NAME,
    description="基于李彪分析框架与丁昶分析框架的ETF智能分析工具",
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# ────────────────────────────── CORS 中间件 ──────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOW_ORIGINS,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=settings.CORS_ALLOW_METHODS,
    allow_headers=settings.CORS_ALLOW_HEADERS,
)

# ────────────────────────────── 路由注册 ──────────────────────────────

app.include_router(router, tags=["ETF分析"])
app.include_router(fusion_router, tags=["融合分析"])


# ────────────────────────────── 根路由 ──────────────────────────────

@app.get("/", tags=["系统"])
async def root():
    """系统信息"""
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "env": settings.ENV,
        "docs": "/docs",
    }


@app.get("/health", tags=["系统"])
async def health():
    """健康检查"""
    return {
        "status": "ok",
        "timestamp": settings.__class__.__module__,
        "version": settings.APP_VERSION,
    }


# ────────────────────────────── 全局异常处理 ──────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """全局异常处理器"""
    logger.error(f"未捕获的异常: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": f"服务器内部错误: {str(exc)}",
            "detail": str(exc) if settings.DEBUG else "请联系管理员"
        }
    )
