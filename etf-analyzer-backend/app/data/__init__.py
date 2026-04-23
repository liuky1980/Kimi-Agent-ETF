"""数据获取模块统一入口"""

from app.config import settings
from app.data.fetcher import ETFDataFetcher, DataFetchError

# 根据 settings.DATA_SOURCE 动态选择数据源（由 get_data_fetcher 工厂方法统一处理）
# from app.data.tushare_fetcher import TushareETFDataFetcher

__all__ = ["ETFDataFetcher", "DataFetchError"]
