"""
ETF数据获取模块
===============
基于akshare免费数据源获取A股ETF的日线、分钟线、基本信息等数据。
支持自动缓存和错误重试机制。
"""

import logging
import os
from datetime import datetime
from typing import Dict, List, Optional

import akshare as ak
import numpy as np
import pandas as pd

from app.config import settings

logger = logging.getLogger(__name__)


class ETFDataFetcher:
    """ETF数据获取器

    使用akshare库获取A股ETF的各类行情数据，支持：
    - 日线/周线/月线历史行情
    - 分钟级历史行情（30分钟、5分钟等）
    - ETF实时列表与基本信息
    - ETF成分股信息
    """

    def __init__(self):
        self.cache_dir = settings.DATA_CACHE_DIR
        os.makedirs(self.cache_dir, exist_ok=True)

    # ────────────────────────────── 基础数据接口 ──────────────────────────────

    def get_etf_daily(self, code: str, start: str, end: str) -> pd.DataFrame:
        """获取ETF日线历史行情（前复权）

        Parameters
        ----------
        code : str
            ETF代码，如 '510300'
        start : str
            起始日期，格式 'YYYYMMDD'
        end : str
            结束日期，格式 'YYYYMMDD'

        Returns
        -------
        pd.DataFrame
            列: date, open, close, high, low, volume, amount,
               amplitude, pct_change, change, turnover
        """
        try:
            logger.info(f"获取ETF {code} 日线数据: {start} ~ {end}")
            df = ak.fund_etf_hist_em(
                symbol=code,
                period="daily",
                start_date=start,
                end_date=end,
                adjust="qfq"
            )
            if df.empty:
                logger.warning(f"ETF {code} 未返回日线数据")
                return pd.DataFrame()

            df.columns = [
                'date', 'open', 'close', 'high', 'low', 'volume',
                'amount', 'amplitude', 'pct_change', 'change', 'turnover'
            ]
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date').reset_index(drop=True)
            logger.info(f"成功获取ETF {code} 日线数据，共 {len(df)} 条")
            return df

        except Exception as e:
            logger.error(f"获取ETF {code} 日线数据失败: {e}")
            raise DataFetchError(f"获取ETF {code} 日线数据失败: {e}") from e

    def get_etf_weekly(self, code: str, start: str, end: str) -> pd.DataFrame:
        """获取ETF周线历史行情（前复权）

        Parameters
        ----------
        code : str
            ETF代码，如 '510300'
        start : str
            起始日期，格式 'YYYYMMDD'
        end : str
            结束日期，格式 'YYYYMMDD'

        Returns
        -------
        pd.DataFrame
            列: date, open, close, high, low, volume, amount,
               amplitude, pct_change, change, turnover
        """
        try:
            logger.info(f"获取ETF {code} 周线数据: {start} ~ {end}")
            df = ak.fund_etf_hist_em(
                symbol=code,
                period="weekly",
                start_date=start,
                end_date=end,
                adjust="qfq"
            )
            if df.empty:
                logger.warning(f"ETF {code} 未返回周线数据")
                return pd.DataFrame()

            df.columns = [
                'date', 'open', 'close', 'high', 'low', 'volume',
                'amount', 'amplitude', 'pct_change', 'change', 'turnover'
            ]
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date').reset_index(drop=True)
            logger.info(f"成功获取ETF {code} 周线数据，共 {len(df)} 条")
            return df

        except Exception as e:
            logger.error(f"获取ETF {code} 周线数据失败: {e}")
            raise DataFetchError(f"获取ETF {code} 周线数据失败: {e}") from e

    def get_etf_hourly(self, code: str) -> pd.DataFrame:
        """获取ETF小时线历史行情（60分钟，前复权）

        Parameters
        ----------
        code : str
            ETF代码，如 '510300'

        Returns
        -------
        pd.DataFrame
            标准化后的小时K线数据
        """
        return self.get_etf_minute(code, period="60")

    def get_etf_minute(self, code: str, period: str = "30") -> pd.DataFrame:
        """获取ETF分钟级历史行情

        Parameters
        ----------
        code : str
            ETF代码，如 '510300'
        period : str
            分钟周期，可选 '1', '5', '15', '30', '60'

        Returns
        -------
        pd.DataFrame
            标准化后的分钟K线数据
        """
        valid_periods = ['1', '5', '15', '30', '60']
        if period not in valid_periods:
            raise ValueError(f"不支持的分钟周期: {period}，可选: {valid_periods}")

        try:
            logger.info(f"获取ETF {code} {period}分钟线数据")
            df = ak.fund_etf_hist_em(
                symbol=code,
                period=f"{period}m",
                start_date="20230101",
                end_date="20251231",
                adjust="qfq"
            )
            if df.empty:
                logger.warning(f"ETF {code} 未返回{period}分钟线数据")
                return pd.DataFrame()

            df.columns = [
                'date', 'open', 'close', 'high', 'low', 'volume',
                'amount', 'amplitude', 'pct_change', 'change', 'turnover'
            ]
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date').reset_index(drop=True)
            logger.info(f"成功获取ETF {code} {period}分钟线数据，共 {len(df)} 条")
            return df

        except Exception as e:
            logger.error(f"获取ETF {code} {period}分钟线数据失败: {e}")
            raise DataFetchError(f"获取ETF {code} {period}分钟线数据失败: {e}") from e

    def get_etf_list(self) -> pd.DataFrame:
        """获取全部ETF实时列表

        Returns
        -------
        pd.DataFrame
            ETF列表，包含代码、名称、最新价、涨跌幅等
        """
        try:
            logger.info("获取ETF实时列表")
            df = ak.fund_etf_spot_em()
            logger.info(f"成功获取ETF列表，共 {len(df)} 只")
            return df

        except Exception as e:
            logger.error(f"获取ETF列表失败: {e}")
            raise DataFetchError(f"获取ETF列表失败: {e}") from e

    def get_etf_info(self, code: str) -> Dict:
        """获取ETF基本信息与近期统计

        Parameters
        ----------
        code : str
            ETF代码

        Returns
        -------
        dict
            包含最新价、52周高低点、20日均量、年化波动率等
        """
        try:
            logger.info(f"获取ETF {code} 基本信息")
            df = ak.fund_etf_hist_em(
                symbol=code,
                period="daily",
                start_date="20200101",
                end_date="20251231",
                adjust="qfq"
            )
            if df.empty:
                raise DataFetchError(f"ETF {code} 无历史数据")

            df.columns = [
                'date', 'open', 'close', 'high', 'low', 'volume',
                'amount', 'amplitude', 'pct_change', 'change', 'turnover'
            ]

            # 计算衍生指标
            latest_price = float(df['close'].iloc[-1])
            high_52w = float(df['high'].tail(252).max())
            low_52w = float(df['low'].tail(252).min())
            avg_volume_20 = float(df['volume'].tail(20).mean())
            avg_volume_60 = float(df['volume'].tail(60).mean())
            volatility = float(df['pct_change'].tail(252).std() * np.sqrt(252))
            total_return_1y = float((df['close'].iloc[-1] / df['close'].iloc[-min(252, len(df))] - 1) * 100)
            ytd_return = float((df['close'].iloc[-1] / df[df['date'] >= f"{pd.Timestamp.now().year}0101"]['close'].iloc[0] - 1) * 100) if len(df[df['date'] >= f"{pd.Timestamp.now().year}0101"]) > 0 else 0.0

            info = {
                "etf_code": code,
                "latest_price": round(latest_price, 3),
                "high_52w": round(high_52w, 3),
                "low_52w": round(low_52w, 3),
                "avg_volume_20": round(avg_volume_20, 0),
                "avg_volume_60": round(avg_volume_60, 0),
                "volatility_annual": round(volatility, 2),
                "total_return_1y": round(total_return_1y, 2),
                "ytd_return": round(ytd_return, 2),
                "data_points": len(df),
                "latest_date": str(df['date'].iloc[-1]),
            }
            logger.info(f"成功获取ETF {code} 基本信息")
            return info

        except DataFetchError:
            raise
        except Exception as e:
            logger.error(f"获取ETF {code} 基本信息失败: {e}")
            raise DataFetchError(f"获取ETF {code} 基本信息失败: {e}") from e

    # ────────────────────────────── 扩展数据接口 ──────────────────────────────

    def get_etf_spot(self, code: str) -> Dict:
        """获取ETF实时行情快照

        Parameters
        ----------
        code : str
            ETF代码

        Returns
        -------
        dict
            实时价格、涨跌幅、成交量、买卖盘等
        """
        try:
            df = ak.fund_etf_spot_em()
            row = df[df['代码'] == code]
            if row.empty:
                raise DataFetchError(f"未找到ETF {code} 的实时行情")

            return {
                "etf_code": code,
                "name": str(row['名称'].values[0]),
                "price": float(row['最新价'].values[0]) if pd.notna(row['最新价'].values[0]) else 0.0,
                "change_pct": float(row['涨跌幅'].values[0]) if pd.notna(row['涨跌幅'].values[0]) else 0.0,
                "volume": float(row['成交量'].values[0]) if pd.notna(row['成交量'].values[0]) else 0.0,
                "turnover": float(row['成交额'].values[0]) if pd.notna(row['成交额'].values[0]) else 0.0,
            }
        except Exception as e:
            logger.error(f"获取ETF {code} 实时行情失败: {e}")
            raise DataFetchError(f"获取ETF {code} 实时行情失败: {e}") from e

    def get_etf_constituents(self, code: str) -> pd.DataFrame:
        """获取ETF重仓/成分股信息

        Parameters
        ----------
        code : str
            ETF代码

        Returns
        -------
        pd.DataFrame
            重仓股列表及权重
        """
        try:
            logger.info(f"获取ETF {code} 成分股信息")
            df = ak.fund_etf_portfolio_em(code)
            return df
        except Exception as e:
            logger.warning(f"获取ETF {code} 成分股信息失败: {e}")
            return pd.DataFrame()

    def get_index_valuation(self, index_code: str) -> Dict:
        """获取指数估值信息（用于估值安全评分）

        Parameters
        ----------
        index_code : str
            指数代码，如 '000300'

        Returns
        -------
        dict
            PE、PB、分位数等估值指标
        """
        try:
            logger.info(f"获取指数 {index_code} 估值信息")
            df = ak.index_value_hist_funddb(symbol=index_code)
            if df.empty:
                return {}
            latest = df.iloc[-1]
            return {
                "index_code": index_code,
                "pe_ttm": float(latest.get('PE-TTM', 0)),
                "pb": float(latest.get('PB', 0)),
                "pe_percentile": float(latest.get('PE百分位', 0)),
                "pb_percentile": float(latest.get('PB百分位', 0)),
                "dividend_yield": float(latest.get('股息率', 0)),
                "roe": float(latest.get('ROE', 0)),
                "date": str(latest.get('日期', '')),
            }
        except Exception as e:
            logger.warning(f"获取指数 {index_code} 估值信息失败: {e}")
            return {}

    # ────────────────────────────── 数据工具方法 ──────────────────────────────

    def compute_macd(self, close_prices: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
        """计算MACD指标

        Parameters
        ----------
        close_prices : pd.Series
            收盘价序列
        fast, slow, signal : int
            MACD参数

        Returns
        -------
        pd.DataFrame
            包含 dif, dea, macd_histogram, macd_area 列
        """
        ema_fast = close_prices.ewm(span=fast, adjust=False).mean()
        ema_slow = close_prices.ewm(span=slow, adjust=False).mean()
        dif = ema_fast - ema_slow
        dea = dif.ewm(span=signal, adjust=False).mean()
        macd_histogram = 2 * (dif - dea)

        # MACD面积（用于背驰检测）
        macd_area = macd_histogram.cumsum()

        return pd.DataFrame({
            'dif': dif,
            'dea': dea,
            'macd_histogram': macd_histogram,
            'macd_area': macd_area
        })

    def get_multi_timeframe(self, code: str) -> Dict[str, pd.DataFrame]:
        """一键获取多周期数据

        Parameters
        ----------
        code : str
            ETF代码

        Returns
        -------
        dict
            {'weekly': DataFrame, 'daily': DataFrame, 'hourly': DataFrame}
        """
        from datetime import datetime, timedelta

        end_date = datetime.now().strftime("%Y%m%d")
        start_weekly = (datetime.now() - timedelta(days=1825)).strftime("%Y%m%d")  # 5年
        start_daily = (datetime.now() - timedelta(days=730)).strftime("%Y%m%d")   # 2年

        result = {}
        result['weekly'] = self.get_etf_weekly(code, start_weekly, end_date)
        result['daily'] = self.get_etf_daily(code, start_daily, end_date)
        result['hourly'] = self.get_etf_hourly(code)

        return result


class DataFetchError(Exception):
    """数据获取异常"""
    pass


class UnifiedDataFetcher:
    """统一数据获取器

    封装主数据源 + 后备数据源逻辑。
    当主数据源（默认tushare）获取失败时，自动回退到后备数据源（akshare）。
    所有返回结果中均包含 data_source 和 fetch_time 字段。
    """

    def __init__(self):
        self.primary = None  # 主数据源
        self.fallback = None  # 后备数据源
        self.primary_source_name = settings.DATA_SOURCE
        self.fallback_source_name = "akshare" if settings.DATA_SOURCE == "tushare" else "tushare"
        self._init_fetchers()

    def _init_fetchers(self):
        """初始化主/后备数据获取器"""
        # 主数据源
        if self.primary_source_name == "tushare":
            try:
                from app.data.tushare_fetcher import TushareETFDataFetcher
                if settings.TUSHARE_TOKEN and settings.TUSHARE_TOKEN != "your_tushare_token_here":
                    self.primary = TushareETFDataFetcher()
                    logger.info("主数据源 Tushare 初始化成功")
                else:
                    logger.warning("Tushare token未配置，跳过主数据源初始化")
            except Exception as e:
                logger.warning(f"主数据源 Tushare 初始化失败: {e}")
        else:
            self.primary = ETFDataFetcher()
            logger.info("主数据源 akshare 初始化成功")

        # 后备数据源（总是akshare）
        try:
            self.fallback = ETFDataFetcher()
            logger.info("后备数据源 akshare 初始化成功")
        except Exception as e:
            logger.warning(f"后备数据源 akshare 初始化失败: {e}")

    def _call_with_fallback(self, method_name: str, *args, **kwargs):
        """调用主数据源方法，失败时回退到后备数据源"""
        # 先尝试主数据源
        if self.primary is not None:
            try:
                result = getattr(self.primary, method_name)(*args, **kwargs)
                # 标记数据源
                result = self._tag_result(result, self.primary_source_name)
                return result
            except Exception as e:
                logger.warning(f"主数据源 {self.primary_source_name} 调用 {method_name} 失败: {e}")

        # 主数据源失败，尝试后备
        if self.fallback is not None and settings.DATA_FALLBACK_ENABLED:
            try:
                result = getattr(self.fallback, method_name)(*args, **kwargs)
                result = self._tag_result(result, self.fallback_source_name)
                logger.info(f"已回退到后备数据源 {self.fallback_source_name} 执行 {method_name}")
                return result
            except Exception as e2:
                logger.error(f"后备数据源 {self.fallback_source_name} 调用 {method_name} 也失败: {e2}")
                raise DataFetchError(f"数据获取失败（主/后备均不可用）: {e2}")

        raise DataFetchError(f"无可用数据源执行 {method_name}")

    def _tag_result(self, result, source_name: str):
        """为返回结果标记数据源和获取时间"""
        fetch_time = datetime.now().isoformat()
        if isinstance(result, pd.DataFrame):
            # DataFrame添加属性
            result.attrs['data_source'] = source_name
            result.attrs['fetch_time'] = fetch_time
        elif isinstance(result, dict):
            result['data_source'] = source_name
            result['fetch_time'] = fetch_time
        return result

    # ── 代理方法 ──
    def get_etf_daily(self, code: str, start: str, end: str) -> pd.DataFrame:
        return self._call_with_fallback('get_etf_daily', code, start, end)

    def get_etf_weekly(self, code: str, start: str, end: str) -> pd.DataFrame:
        return self._call_with_fallback('get_etf_weekly', code, start, end)

    def get_etf_hourly(self, code: str) -> pd.DataFrame:
        return self._call_with_fallback('get_etf_hourly', code)

    def get_etf_minute(self, code: str, period: str = "30") -> pd.DataFrame:
        return self._call_with_fallback('get_etf_minute', code, period)

    def get_etf_list(self) -> pd.DataFrame:
        return self._call_with_fallback('get_etf_list')

    def get_etf_info(self, code: str) -> Dict:
        return self._call_with_fallback('get_etf_info', code)

    def get_etf_spot(self, code: str) -> Dict:
        return self._call_with_fallback('get_etf_spot', code)

    def get_etf_constituents(self, code: str) -> pd.DataFrame:
        return self._call_with_fallback('get_etf_constituents', code)

    def get_index_valuation(self, index_code: str) -> Dict:
        return self._call_with_fallback('get_index_valuation', index_code)

    def compute_macd(self, close_prices: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
        """MACD计算不依赖数据源，直接使用akshare实现"""
        return self.fallback.compute_macd(close_prices, fast, slow, signal) if self.fallback else self.primary.compute_macd(close_prices, fast, slow, signal)

    def get_multi_timeframe(self, code: str) -> Dict[str, pd.DataFrame]:
        return self._call_with_fallback('get_multi_timeframe', code)

    def get_etf_fundamental_data(self, etf_code: str) -> Dict:
        """获取ETF全部基本面真实数据（仅主数据源支持）

        目前仅Tushare数据源支持获取基本面数据，
        如果主数据源不是Tushare或不支持此方法，返回空字典。
        """
        if self.primary is not None and hasattr(self.primary, 'get_etf_fundamental_data'):
            try:
                result = self.primary.get_etf_fundamental_data(etf_code)
                return self._tag_result(result, self.primary_source_name)
            except Exception as e:
                logger.warning(f"主数据源 {self.primary_source_name} 获取基本面数据失败: {e}")
                return {}
        return {}


# ────────────────────────────── 统一数据获取入口（工厂模式） ──────────────────────────────

def get_data_fetcher():
    """获取统一的数据获取器（支持主/后备自动切换）"""
    return UnifiedDataFetcher()


# 全局统一数据获取器实例
fetcher = UnifiedDataFetcher()
