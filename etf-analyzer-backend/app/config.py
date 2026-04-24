"""
应用配置文件
============
包含ETF分析系统的全局配置项，包括数据源、缓存、日志等级、融合引擎等参数。
"""

import os
from functools import lru_cache
from typing import Dict

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
    DATA_SOURCE: str = os.getenv("DATA_SOURCE", "tushare")
    DATA_FALLBACK_ENABLED: bool = True
    DATA_CACHE_DIR: str = os.path.join(os.path.dirname(__file__), "..", ".cache")
    DATA_CACHE_TTL: int = 3600

    # Tushare数据源配置
    TUSHARE_TOKEN: str = os.getenv(
        "TUSHARE_TOKEN",
        "61afcb2ebd9cad58a493f4802bf88c8936e91dcb2dd82495075a88bc",
    )
    TUSHARE_ENABLED: bool = os.getenv("TUSHARE_ENABLED", "true").lower() == "true"

    # 李彪分析框架配置
    CHANLUN_MIN_KLINES: int = 5
    CHANLUN_CENTER_OVERLAP: int = 3
    CHANLUN_DIVERGENCE_METHOD: str = "macd_area"
    CHANLUN_RESONANCE_THRESHOLD: float = 70.0

    # 丁昶分析框架配置
    DINGCHANG_COMPOSITE_THRESHOLD_BUY: float = 80.0
    DINGCHANG_COMPOSITE_THRESHOLD_HOLD: float = 60.0
    DINGCHANG_COMPOSITE_THRESHOLD_WATCH: float = 40.0

    # 权重配置
    WEIGHT_DIVIDEND: float = 0.30
    WEIGHT_VALUATION: float = 0.25
    WEIGHT_PROFITABILITY: float = 0.20
    WEIGHT_CAPITAL_FLOW: float = 0.15
    WEIGHT_MACRO: float = 0.10

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

    # ────────────────────────────── 融合引擎配置 ──────────────────────────────

    # 引擎主开关
    FUSION_ENABLED: bool = os.getenv("FUSION_ENABLED", "true").lower() == "true"
    FUSION_MACRO_LAYER_ENABLED: bool = os.getenv("FUSION_MACRO_LAYER_ENABLED", "true").lower() == "true"
    FUSION_SENTIMENT_LAYER_ENABLED: bool = os.getenv("FUSION_SENTIMENT_LAYER_ENABLED", "true").lower() == "true"
    FUSION_VOLATILITY_LAYER_ENABLED: bool = os.getenv("FUSION_VOLATILITY_LAYER_ENABLED", "true").lower() == "true"

    # 仓位限制（融合引擎）
    FUSION_SINGLE_ETF_MAX: float = float(os.getenv("FUSION_SINGLE_ETF_MAX", "0.25"))  # 单ETF上限25%
    FUSION_SECTOR_MAX: float = float(os.getenv("FUSION_SECTOR_MAX", "0.50"))  # 单行业上限50%
    FUSION_TOTAL_MAX: float = float(os.getenv("FUSION_TOTAL_MAX", "1.00"))  # 总仓位上限100%
    FUSION_LEVERAGE_MAX: float = float(os.getenv("FUSION_LEVERAGE_MAX", "1.50"))  # 最大杠杆1.5x

    # 宏观层配置（融合引擎）
    FUSION_MACRO_CYCLE_I_LIMIT: float = 1.00  # 复苏期仓位限制
    FUSION_MACRO_CYCLE_II_LIMIT: float = 0.70  # 过热期仓位限制
    FUSION_MACRO_CYCLE_III_LIMIT: float = 0.40  # 滞胀期仓位限制
    FUSION_MACRO_CYCLE_IV_LIMIT: float = 0.20  # 衰退期仓位限制
    FUSION_MACRO_RISK_FREE_RATE: float = float(os.getenv("FUSION_MACRO_RISK_FREE_RATE", "0.025"))
    FUSION_MACRO_RISK_PREMIUM: float = float(os.getenv("FUSION_MACRO_RISK_PREMIUM", "0.030"))

    # 情绪层配置（融合引擎）
    FUSION_SENTIMENT_A_CONFIDENCE: float = 85.0  # A级置信度
    FUSION_SENTIMENT_B_CONFIDENCE: float = 65.0  # B级置信度
    FUSION_SENTIMENT_C_CONFIDENCE: float = 45.0  # C级置信度
    FUSION_SENTIMENT_D_CONFIDENCE: float = 25.0  # D级置信度
    FUSION_SENTIMENT_GREED_THRESHOLD: float = float(os.getenv("FUSION_SENTIMENT_GREED_THRESHOLD", "75.0"))
    FUSION_SENTIMENT_FEAR_THRESHOLD: float = float(os.getenv("FUSION_SENTIMENT_FEAR_THRESHOLD", "25.0"))

    # 波动率层配置（融合引擎）
    FUSION_VOL_LOW_COEFF: float = 1.00  # 低波动率系数
    FUSION_VOL_NORMAL_COEFF: float = 0.85  # 正常波动率系数
    FUSION_VOL_HIGH_COEFF: float = 0.60  # 高波动率系数
    FUSION_VOL_EXTREME_COEFF: float = 0.30  # 极端波动率系数
    FUSION_VOL_EXTREME_THRESHOLD: float = float(os.getenv("FUSION_VOL_EXTREME_THRESHOLD", "0.40"))
    FUSION_VOL_HIGH_THRESHOLD: float = float(os.getenv("FUSION_VOL_HIGH_THRESHOLD", "0.25"))
    FUSION_VOL_LOW_THRESHOLD: float = float(os.getenv("FUSION_VOL_LOW_THRESHOLD", "0.10"))

    # 战术比例映射（融合引擎）
    FUSION_TACTICAL_WEEKLY: float = 0.60  # 周线级别战术比例
    FUSION_TACTICAL_DAILY: float = 0.30  # 日线级别战术比例
    FUSION_TACTICAL_30MIN: float = 0.10  # 30分钟级别战术比例

    # 持仓周期映射（融合引擎）
    FUSION_HOLDING_WEEKLY: str = "日线级别预期8-12周"
    FUSION_HOLDING_DAILY: str = "日线级别预期2-4周"
    FUSION_HOLDING_30MIN: str = "日线级别预期3-5日"

    # 融合引擎参数配置文件路径
    FUSION_PARAMS_FILE: str = os.getenv(
        "FUSION_PARAMS_FILE",
        os.path.join(os.path.dirname(__file__), "..", "config", "fusion_params.yaml")
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    # ────────────────────────────── 融合引擎便捷方法 ──────────────────────────────

    def get_fusion_config(self) -> Dict:
        """获取融合引擎配置字典

        将 Settings 中的融合引擎相关配置项打包为字典，
        便于 FusionEngine 和 FusionConfig 模型初始化使用。

        Returns
        -------
        dict
            融合引擎完整配置字典
        """
        return {
            "fusion_enabled": self.FUSION_ENABLED,
            "macro_layer_enabled": self.FUSION_MACRO_LAYER_ENABLED,
            "sentiment_layer_enabled": self.FUSION_SENTIMENT_LAYER_ENABLED,
            "volatility_layer_enabled": self.FUSION_VOLATILITY_LAYER_ENABLED,
            "position_limit": {
                "single_etf_max": self.FUSION_SINGLE_ETF_MAX,
                "sector_max": self.FUSION_SECTOR_MAX,
                "total_max": self.FUSION_TOTAL_MAX,
                "leverage_max": self.FUSION_LEVERAGE_MAX,
            },
            "macro_config": {
                "cycle_position_limit_map": {
                    "I": self.FUSION_MACRO_CYCLE_I_LIMIT,
                    "II": self.FUSION_MACRO_CYCLE_II_LIMIT,
                    "III": self.FUSION_MACRO_CYCLE_III_LIMIT,
                    "IV": self.FUSION_MACRO_CYCLE_IV_LIMIT,
                },
                "risk_free_rate": self.FUSION_MACRO_RISK_FREE_RATE,
                "risk_premium_required": self.FUSION_MACRO_RISK_PREMIUM,
            },
            "sentiment_config": {
                "grade_confidence_map": {
                    "A": self.FUSION_SENTIMENT_A_CONFIDENCE,
                    "B": self.FUSION_SENTIMENT_B_CONFIDENCE,
                    "C": self.FUSION_SENTIMENT_C_CONFIDENCE,
                    "D": self.FUSION_SENTIMENT_D_CONFIDENCE,
                },
                "greed_fear_threshold_high": self.FUSION_SENTIMENT_GREED_THRESHOLD,
                "greed_fear_threshold_low": self.FUSION_SENTIMENT_FEAR_THRESHOLD,
            },
            "volatility_config": {
                "regime_coefficient_map": {
                    "low": self.FUSION_VOL_LOW_COEFF,
                    "normal": self.FUSION_VOL_NORMAL_COEFF,
                    "high": self.FUSION_VOL_HIGH_COEFF,
                    "extreme": self.FUSION_VOL_EXTREME_COEFF,
                },
                "hv_extreme_threshold": self.FUSION_VOL_EXTREME_THRESHOLD,
                "hv_high_threshold": self.FUSION_VOL_HIGH_THRESHOLD,
                "hv_low_threshold": self.FUSION_VOL_LOW_THRESHOLD,
            },
            "tactical_ratio_map": {
                "weekly": self.FUSION_TACTICAL_WEEKLY,
                "daily": self.FUSION_TACTICAL_DAILY,
                "30min": self.FUSION_TACTICAL_30MIN,
            },
            "holding_period_map": {
                "weekly": self.FUSION_HOLDING_WEEKLY,
                "daily": self.FUSION_HOLDING_DAILY,
                "30min": self.FUSION_HOLDING_30MIN,
            },
        }


@lru_cache()
def get_settings() -> Settings:
    """获取配置单例（缓存）"""
    return Settings()


settings = get_settings()
