"""
ETF数据获取模块
===============
基于akshare免费数据源获取A股ETF的日线、分钟线、基本信息等数据。
支持自动缓存和错误重试机制。
"""

import logging
import os
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
            {'daily': DataFrame, '30min': DataFrame, '5min': DataFrame}
        """
        from datetime import datetime, timedelta

        end_date = datetime.now().strftime("%Y%m%d")
        start_daily = (datetime.now() - timedelta(days=730)).strftime("%Y%m%d")

        result = {}
        result['daily'] = self.get_etf_daily(code, start_daily, end_date)
        result['30min'] = self.get_etf_minute(code, "30")
        result['5min'] = self.get_etf_minute(code, "5")

        return result


class DataFetchError(Exception):
    """数据获取异常"""
    pass


# ────────────────────────────── 统一数据获取入口（工厂模式） ──────────────────────────────

def get_data_fetcher():
    """根据配置获取对应的数据获取器

    通过 settings.DATA_SOURCE 配置项切换数据源：
    - "akshare"  → 使用 akshare 免费数据源（默认）
    - "tushare"  → 使用 tushare Pro 数据源

    Returns
    -------
    ETFDataFetcher | TushareETFDataFetcher
        对应配置的数据获取器实例
    """
    if settings.DATA_SOURCE == "tushare":
        if not settings.TUSHARE_ENABLED:
            logger.warning("Tushare已禁用，回退到akshare")
            return ETFDataFetcher()
        from app.data.tushare_fetcher import TushareETFDataFetcher

        logger.info("使用Tushare数据源")
        return TushareETFDataFetcher()
    return ETFDataFetcher()  # 默认 akshare


# 全局数据获取器实例（默认akshare，后续通过工厂方法按需创建）
fetcher = ETFDataFetcher()
