"""
API 路由模块
============
包含ETF分析系统的全部 API 路由：
- router: 基础ETF分析路由（李彪/丁昶）
- fusion_router: 五维融合分析路由
"""

from app.api.fusion_endpoints import fusion_router
from app.api.router import router

__all__ = ["router", "fusion_router"]
