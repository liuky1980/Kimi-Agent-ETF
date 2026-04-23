"""
应用配置文件
============
包含ETF分析系统的全局配置项，包括数据源、缓存、日志等级等参数。
"""

import os
from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用配置类，支持从环境变量读取"""

    # 应用基础配置
    APP_NAME: str = "ETF多框架分析系统"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    ENV: str = os.getenv("ENV", "development")

    # 服务器配置
    HOST: str = "0.0.0.0"
    PORT: int = int(os.getenv("PORT", "8000"))

    # 数据源配置
    # 可选值: "akshare" | "tushare" — 通过环境变量 DATA_SOURCE 切换
    DATA_SOURCE: str = os.getenv("DATA_SOURCE", "akshare")
    DATA_CACHE_DIR: str = os.path.join(os.path.dirname(__file__), "..", ".cache")
    DATA_CACHE_TTL: int = 3600  # 数据缓存时间(秒)

    # Tushare数据源配置
    TUSHARE_TOKEN: str = os.getenv(
        "TUSHARE_TOKEN",
        "61afcb2ebd9cad58a493f4802bf88c8936e91dcb2dd82495075a88bc",
    )
    TUSHARE_ENABLED: bool = os.getenv("TUSHARE_ENABLED", "true").lower() == "true"

    # 李彪分析框架配置
    CHANLUN_MIN_KLINES: int = 5  # 笔划分的最小K线间隔
    CHANLUN_CENTER_OVERLAP: int = 3  # 中枢最少重叠笔数
    CHANLUN_DIVERGENCE_METHOD: str = "macd_area"  # 背驰检测方法: macd_area | macd_slope
    CHANLUN_RESonance_THRESHOlD: float = 70.0  # 共振信号阈值

    # 丁昶分析框架配置
    DINGCHANG_COMPOSITE_THRESHOLD_BUY: float = 80.0  # 综合评分买入阈值
    DINGCHANG_COMPOSITE_THRESHOLD_HOLD: float = 60.0  # 综合评分持有阈值
    DINGCHANG_COMPOSITE_THRESHOLD_WATCH: float = 40.0  # 综合评分观察阈值

    # 权重配置 (丁昶分析框架五维评分权重)
    WEIGHT_DIVIDEND: float = 0.30  # 股息质量权重
    WEIGHT_VALUATION: float = 0.25  # 估值安全权重
    WEIGHT_PROFITABILITY: float = 0.20  # 盈利质地权重
    WEIGHT_CAPITAL_FLOW: float = 0.15  # 资金驱动权重
    WEIGHT_MACRO: float = 0.10  # 宏观适配权重

    # CORS配置
    CORS_ALLOW_ORIGINS: list = ["*"]
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: list = ["*"]
    CORS_ALLOW_HEADERS: list = ["*"]

    # 日志配置
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # 请求限流配置
    RATE_LIMIT_PER_MINUTE: int = 60

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """获取配置单例（缓存）"""
    return Settings()


settings = get_settings()
