"""
Tushare数据源ETF数据获取模块
===========================
基于Tushare Pro接口获取A股ETF数据。
与ETFDataFetcher接口保持一致，支持数据源切换。
"""

import logging
import os
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
from cachetools import TTLCache
from cachetools.keys import hashkey

from app.config import settings

logger = logging.getLogger(__name__)

# ────────────────────────────── 缓存配置 ──────────────────────────────
# 各类数据缓存（单位：秒）
_CACHE_ETF_LIST      = TTLCache(maxsize=1, ttl=300)      # ETF列表      5分钟
_CACHE_ETF_DAILY    = TTLCache(maxsize=100, ttl=300)     # 日线行情    5分钟
_CACHE_ETF_INFO     = TTLCache(maxsize=100, ttl=600)     # 基本信息   10分钟
_CACHE_INDEX_WEIGHT = TTLCache(maxsize=50, ttl=3600)     # 成分股权重  1小时
_CACHE_FUND_PORTFOLIO = TTLCache(maxsize=50, ttl=3600)   # 基金持仓   1小时
_CACHE_INDEX_DAILYBASIC = TTLCache(maxsize=50, ttl=300)  # 指数行情   5分钟
_CACHE_FUND_SHARE   = TTLCache(maxsize=50, ttl=3600)     # 基金份额   1小时
_CACHE_FUND_NAV     = TTLCache(maxsize=50, ttl=3600)     # 基金净值   1小时
_CACHE_SHIBOR       = TTLCache(maxsize=10, ttl=3600)     # SHIBOR利率  1小时
_CACHE_AUM          = TTLCache(maxsize=50, ttl=300)      # AUM数据    5分钟
_CACHE_MULTI_TF     = TTLCache(maxsize=50, ttl=300)      # 多周期数据 5分钟


def _cached(cache_store):
    """简单的方法级缓存装饰器（支持self参数）"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            # 构建 key: 忽略 self 参数，只保留实际参数
            key_args = args[1:] if len(args) > 0 and hasattr(args[0], func.__name__) else args
            key = hashkey(*key_args, **kwargs)
            try:
                return cache_store[key]
            except KeyError:
                result = func(*args, **kwargs)
                cache_store[key] = result
                return result
        return wrapper
    return decorator


# 延迟导入tushare，避免在模块加载时即初始化
ts = None
pro = None


def _init_tushare():
    """延迟初始化tushare客户端"""
    global ts, pro
    if ts is None:
        try:
            import tushare as _ts

            _ts.set_token(settings.TUSHARE_TOKEN)
            ts = _ts
            pro = _ts.pro_api()
            logger.info("Tushare客户端初始化成功")
        except Exception as e:
            logger.error(f"Tushare客户端初始化失败: {e}")
            raise DataFetchError(f"Tushare客户端初始化失败: {e}") from e


class TushareETFDataFetcher:
    """Tushare ETF数据获取器

    使tushare Pro接口获取A股ETF的各类行情数据，接口与ETFDataFetcher保持一致。
    支持：
    - 日线历史行情
    - 分钟级历史行情（通过通用行情接口）
    - ETF实时列表与基本信息
    """

    def __init__(self):
        self.token = settings.TUSHARE_TOKEN
        self.cache_dir = settings.DATA_CACHE_DIR
        os.makedirs(self.cache_dir, exist_ok=True)
        _init_tushare()
        self.pro = pro
        # ETF列表缓存
        self._etf_list_cache = None
        self._etf_list_cache_time = 0
        self._etf_list_cache_ttl = 300  # 5分钟缓存

    # ────────────────────────────── 工具方法 ──────────────────────────────

    @staticmethod
    def _to_ts_code(code: str) -> str:
        """转换为tushare的ts_code格式

        上海ETF: 51, 56, 58 开头 -> code.SH
        深圳ETF: 15, 16, 17, 18, 19 开头 -> code.SZ
        北京ETF: 8, 9 开头 -> code.BJ
        """
        code = code.strip()
        # 如果已经有后缀，直接返回
        if "." in code:
            return code
        # 深圳ETF: 15/16/17/18/19 开头
        if code.startswith("15") or code.startswith("16") or code.startswith("17") or code.startswith("18") or code.startswith("19"):
            return f"{code}.SZ"
        # 北京ETF: 8/9 开头
        elif code.startswith("8") or code.startswith("9"):
            return f"{code}.BJ"
        # 其他默认上海
        else:
            return f"{code}.SH"

    @staticmethod
    def _from_ts_code(ts_code: str) -> str:
        """从tushare的ts_code格式还原为纯数字代码"""
        return ts_code.split(".")[0] if "." in ts_code else ts_code

    # ────────────────────────────── 基础数据接口 ──────────────────────────────

    @_cached(_CACHE_ETF_DAILY)
    def get_etf_daily(self, code: str, start: str, end: str) -> pd.DataFrame:
        """获取ETF日线历史行情

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
            logger.info(f"[Tushare] 获取ETF {code} 日线数据: {start} ~ {end}")
            ts_code = self._to_ts_code(code)

            # 使用 fund_daily 接口获取ETF日线数据
            df = self.pro.fund_daily(ts_code=ts_code, start_date=start, end_date=end)
            if df is None or df.empty:
                logger.warning(f"[Tushare] ETF {code} 未返回日线数据")
                return pd.DataFrame()

            # 标准化列名与akshare一致
            df = df.rename(
                columns={
                    "trade_date": "date",
                    "open": "open",
                    "high": "high",
                    "low": "low",
                    "close": "close",
                    "vol": "volume",
                    "amount": "amount",
                    "change": "change",
                    "pct_chg": "pct_change",
                }
            )
            df["date"] = pd.to_datetime(df["date"])
            df = df.sort_values("date").reset_index(drop=True)

            # 计算派生字段
            df["amplitude"] = (
                (df["high"] - df["low"]) / df["low"].shift(1) * 100
            ).fillna(0)
            # turnover（换手率）tushare不直接提供，设为0
            df["turnover"] = 0.0

            # 确保列名与akshare保持一致
            result = df[
                [
                    "date",
                    "open",
                    "close",
                    "high",
                    "low",
                    "volume",
                    "amount",
                    "amplitude",
                    "pct_change",
                    "change",
                    "turnover",
                ]
            ].copy()

            logger.info(
                f"[Tushare] 成功获取ETF {code} 日线数据，共 {len(result)} 条"
            )
            return result

        except Exception as e:
            logger.error(f"[Tushare] 获取ETF {code} 日线数据失败: {e}")
            raise DataFetchError(
                f"[Tushare] 获取ETF {code} 日线数据失败: {e}"
            ) from e

    def get_etf_minute(self, code: str, period: str = "30") -> pd.DataFrame:
        """获取ETF分钟级历史行情

        使用tushare的stk_mins接口获取分钟线（Pro版需要300积分以上权限）。
        如果积分不足，抛出异常并回退到akshare。

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
        valid_periods = ["1", "5", "15", "30", "60"]
        if period not in valid_periods:
            raise ValueError(f"不支持的分钟周期: {period}，可选: {valid_periods}")

        try:
            logger.info(
                f"[Tushare] 获取ETF {code} {period}分钟线数据"
            )
            ts_code = self._to_ts_code(code)

            # tushare分钟线接口：stk_mins（需要足够积分）
            # freq: 1min/5min/15min/30min/60min
            freq_map = {
                "1": "1min",
                "5": "5min",
                "15": "15min",
                "30": "30min",
                "60": "60min",
            }
            freq = freq_map[period]

            df = self.pro.stk_mins(ts_code=ts_code, freq=freq)
            if df is None or df.empty:
                logger.warning(
                    f"[Tushare] ETF {code} 未返回{period}分钟线数据"
                )
                return pd.DataFrame()

            # 标准化列名
            df = df.rename(
                columns={
                    "trade_time": "date",
                    "open": "open",
                    "high": "high",
                    "low": "low",
                    "close": "close",
                    "vol": "volume",
                    "amount": "amount",
                }
            )
            df["date"] = pd.to_datetime(df["date"])
            df = df.sort_values("date").reset_index(drop=True)

            # 计算派生字段
            df["change"] = df["close"].diff()
            df["pct_change"] = df["close"].pct_change() * 100
            df["amplitude"] = (
                (df["high"] - df["low"]) / df["low"].shift(1) * 100
            ).fillna(0)
            df["turnover"] = 0.0

            result = df[
                [
                    "date",
                    "open",
                    "close",
                    "high",
                    "low",
                    "volume",
                    "amount",
                    "amplitude",
                    "pct_change",
                    "change",
                    "turnover",
                ]
            ].copy()

            logger.info(
                f"[Tushare] 成功获取ETF {code} {period}分钟线数据，共 {len(result)} 条"
            )
            return result

        except Exception as e:
            logger.error(
                f"[Tushare] 获取ETF {code} {period}分钟线数据失败: {e}"
            )
            raise DataFetchError(
                f"[Tushare] 获取ETF {code} {period}分钟线数据失败: {e}"
            ) from e

    @_cached(_CACHE_ETF_LIST)
    def get_etf_list(self) -> pd.DataFrame:
        """获取全部ETF实时列表

        Returns
        -------
        pd.DataFrame
            ETF列表，包含代码、名称等字段，列名与akshare尽量一致
        """
        import time

        # 检查缓存是否有效
        now = time.time()
        if self._etf_list_cache is not None and (now - self._etf_list_cache_time) < self._etf_list_cache_ttl:
            logger.info("[Tushare] 使用缓存的ETF列表")
            return self._etf_list_cache.copy()

        try:
            logger.info("[Tushare] 获取ETF列表")
            # 获取场内基金（ETF）基础信息
            df = self.pro.fund_basic(market="E")
            if df is None or df.empty:
                logger.warning("[Tushare] 未返回ETF列表")
                return pd.DataFrame()

            # 标准化列名：与akshare的fund_etf_spot_em尽量对齐
            rename_map = {
                "ts_code": "代码",
                "name": "名称",
                "found_date": "成立日期",
                "list_date": "上市日期",
                "issue_amount": "发行份额",
                "type": "类型",
                "status": "状态",
            }
            df = df.rename(columns=rename_map)

            # 从 ts_code 提取纯数字代码
            df["纯代码"] = df["代码"].str.split(".").str[0]

            # 尝试用 akshare 获取实时行情补充价格数据
            try:
                import akshare as ak
                spot_df = ak.fund_etf_spot_em()
                if spot_df is not None and not spot_df.empty:
                    # 合并实时行情
                    spot_df = spot_df.rename(columns={
                        "代码": "纯代码",
                        "最新价": "最新价_spot",
                        "涨跌幅": "涨跌幅_spot",
                        "成交量": "成交量_spot",
                        "成交额": "成交额_spot",
                    })
                    df = df.merge(
                        spot_df[["纯代码", "最新价_spot", "涨跌幅_spot", "成交量_spot", "成交额_spot"]],
                        on="纯代码",
                        how="left"
                    )
                    df["最新价"] = df["最新价_spot"].fillna(0.0)
                    df["涨跌幅"] = df["涨跌幅_spot"].fillna(0.0)
                    df["成交量"] = df["成交量_spot"].fillna(0.0)
                    df["成交额"] = df["成交额_spot"].fillna(0.0)
                    df = df.drop(columns=["最新价_spot", "涨跌幅_spot", "成交量_spot", "成交额_spot", "纯代码"])
                else:
                    df["最新价"] = 0.0
                    df["涨跌幅"] = 0.0
                    df["成交量"] = 0.0
                    df["成交额"] = 0.0
            except Exception as e:
                logger.warning(f"[Tushare] akshare 实时行情获取失败，使用空值: {e}")
                df["最新价"] = 0.0
                df["涨跌幅"] = 0.0
                df["成交量"] = 0.0
                df["成交额"] = 0.0

            # 更新缓存
            self._etf_list_cache = df.copy()
            self._etf_list_cache_time = now

            logger.info(f"[Tushare] 成功获取ETF列表，共 {len(df)} 只")
            return df

        except Exception as e:
            logger.error(f"[Tushare] 获取ETF列表失败: {e}")
            raise DataFetchError(f"[Tushare] 获取ETF列表失败: {e}") from e

    @_cached(_CACHE_ETF_INFO)
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
            logger.info(f"[Tushare] 获取ETF {code} 基本信息")
            ts_code = self._to_ts_code(code)

            # 获取历史日线数据（近2年）
            end_date = pd.Timestamp.now().strftime("%Y%m%d")
            start_date = (pd.Timestamp.now() - pd.Timedelta(days=730)).strftime("%Y%m%d")

            df = self.pro.daily(
                ts_code=ts_code, start_date=start_date, end_date=end_date
            )
            if df is None or df.empty:
                raise DataFetchError(f"[Tushare] ETF {code} 无历史数据")

            # 标准化列名
            df = df.rename(
                columns={
                    "trade_date": "date",
                    "open": "open",
                    "high": "high",
                    "low": "low",
                    "close": "close",
                    "vol": "volume",
                    "amount": "amount",
                }
            )
            df["date"] = pd.to_datetime(df["date"])
            df = df.sort_values("date").reset_index(drop=True)

            # 计算派生指标
            latest_price = float(df["close"].iloc[-1])
            high_52w = float(df["high"].tail(252).max())
            low_52w = float(df["low"].tail(252).min())
            avg_volume_20 = float(df["volume"].tail(20).mean())
            avg_volume_60 = float(df["volume"].tail(60).mean())

            # 计算涨跌幅
            df["pct_change"] = df["close"].pct_change() * 100
            volatility = float(df["pct_change"].tail(252).std() * np.sqrt(252))

            total_return_1y = float(
                (
                    df["close"].iloc[-1]
                    / df["close"].iloc[-min(252, len(df))]
                    - 1
                )
                * 100
            )
            ytd_data = df[df["date"] >= f"{pd.Timestamp.now().year}0101"]
            ytd_return = (
                float(
                    (
                        df["close"].iloc[-1] / ytd_data["close"].iloc[0] - 1
                    )
                    * 100
                )
                if not ytd_data.empty
                else 0.0
            )

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
                "latest_date": str(df["date"].iloc[-1]),
                "data_source": "tushare",
            }
            logger.info(f"[Tushare] 成功获取ETF {code} 基本信息")
            return info

        except DataFetchError:
            raise
        except Exception as e:
            logger.error(f"[Tushare] 获取ETF {code} 基本信息失败: {e}")
            raise DataFetchError(
                f"[Tushare] 获取ETF {code} 基本信息失败: {e}"
            ) from e

    # ────────────────────────────── 扩展数据接口 ──────────────────────────────

    def get_etf_spot(self, code: str) -> Dict:
        """获取ETF实时行情快照

        Tushare的实时行情接口有限，使用stk_limit或fund_nav近似。
        如果无法获取实时数据，返回空字典并记录警告。

        Parameters
        ----------
        code : str
            ETF代码

        Returns
        -------
        dict
            实时价格、涨跌幅等（如果接口可用）
        """
        try:
            ts_code = self._to_ts_code(code)
            # 尝试获取最新日线作为近似实时数据
            end_date = pd.Timestamp.now().strftime("%Y%m%d")
            df = self.pro.daily(ts_code=ts_code, start_date=end_date, end_date=end_date)
            if df is None or df.empty:
                raise DataFetchError(f"[Tushare] 未找到ETF {code} 的实时行情")

            latest = df.iloc[-1]
            return {
                "etf_code": code,
                "name": "",
                "price": float(latest.get("close", 0)),
                "change_pct": float(latest.get("pct_chg", 0)),
                "volume": float(latest.get("vol", 0)),
                "turnover": float(latest.get("amount", 0)),
            }
        except Exception as e:
            logger.warning(f"[Tushare] 获取ETF {code} 实时行情失败: {e}")
            return {}

    @_cached(_CACHE_FUND_PORTFOLIO)
    def get_etf_constituents(self, code: str) -> pd.DataFrame:
        """获取ETF重仓/成分股信息

        Tushare的ETF持仓数据接口（fund_portfolio）需要特定权限。
        如果权限不足，返回空DataFrame。

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
            logger.info(f"[Tushare] 获取ETF {code} 成分股信息")
            ts_code = self._to_ts_code(code)
            # fund_portfolio 获取基金持仓（季度披露，非实时）
            df = self.pro.fund_portfolio(ts_code=ts_code)
            if df is None or df.empty:
                return pd.DataFrame()
            return df
        except Exception as e:
            logger.warning(f"[Tushare] 获取ETF {code} 成分股信息失败: {e}")
            return pd.DataFrame()

    @_cached(_CACHE_INDEX_DAILYBASIC)
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
            logger.info(f"[Tushare] 获取指数 {index_code} 估值信息")
            # tushare的index_dailybasic接口获取指数估值
            ts_code = self._to_ts_code(index_code)
            df = self.pro.index_dailybasic(ts_code=ts_code)
            if df is None or df.empty:
                return {}
            latest = df.iloc[-1]
            return {
                "index_code": index_code,
                "pe_ttm": float(latest.get("pe", 0)),
                "pb": float(latest.get("pb", 0)),
                "pe_percentile": 0.0,  # tushare不直接提供百分位，需要自行计算
                "pb_percentile": 0.0,
                "dividend_yield": float(latest.get("dv_ratio", 0)),
                "roe": 0.0,
                "date": str(latest.get("trade_date", "")),
                "data_source": "tushare",
            }
        except Exception as e:
            logger.warning(f"[Tushare] 获取指数 {index_code} 估值信息失败: {e}")
            return {}

    # ────────────────────────────── 数据工具方法 ──────────────────────────────

    def compute_macd(
        self,
        close_prices: pd.Series,
        fast: int = 12,
        slow: int = 26,
        signal: int = 9,
    ) -> pd.DataFrame:
        """计算MACD指标

        与ETFDataFetcher.compute_macd实现完全一致，确保跨数据源计算结果一致。

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

        return pd.DataFrame(
            {
                "dif": dif,
                "dea": dea,
                "macd_histogram": macd_histogram,
                "macd_area": macd_area,
            }
        )

    @_cached(_CACHE_MULTI_TF)
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
        end_date = pd.Timestamp.now().strftime("%Y%m%d")
        start_weekly = (
            pd.Timestamp.now() - pd.Timedelta(days=1825)
        ).strftime("%Y%m%d")
        start_daily = (
            pd.Timestamp.now() - pd.Timedelta(days=730)
        ).strftime("%Y%m%d")

        result = {}
        # 周线：通过日线重采样构建（tushare无直接周线接口，用日线代替）
        result["fiveday"] = self.get_etf_daily(code, start_weekly, end_date)
        result["daily"] = self.get_etf_daily(code, start_daily, end_date)
        result["hourly"] = self.get_etf_minute(code, "60")

        return result

    # ────────────────────────────── 真实基本面数据接口（丁昶五维评分用）──────────────────────────────

    # 常见ETF → 跟踪指数映射
    ETF_INDEX_MAP = {
        "510300": "000300.SH",   # 沪深300ETF
        "510500": "000905.SH",   # 中证500ETF
        "510050": "000016.SH",   # 上证50ETF
        "510180": "000010.SH",   # 上证180ETF
        "510880": "000015.SH",   # 红利ETF
        "512880": "000016.SH",   # 证券ETF → 近似用上证50
        "512690": "399987.SZ",   # 酒ETF
        "512000": "000016.SH",   # 券商ETF → 近似
        "512010": "000300.SH",   # 医药ETF → 近似用沪深300
        "512480": "000016.SH",   # 半导体ETF → 近似
        "515030": "000300.SH",   # 新能源ETF → 近似
        "516160": "000300.SH",   # 新能源ETF → 近似
        "159915": "399006.SZ",   # 创业板ETF
        "159949": "399673.SZ",   # 创业板50ETF
        "159952": "399006.SZ",   # 创业板ETF
        "159901": "399330.SZ",   # 深证100ETF
        "159919": "000300.SH",   # 沪深300ETF(嘉实)
        "510310": "000300.SH",   # 沪深300ETF(易方达)
        "510330": "000300.SH",   # 沪深300ETF(华夏)
        "510360": "000300.SH",   # 沪深300ETF(广发)
        "510390": "000300.SH",   # 沪深300ETF(平安)
        "510500": "000905.SH",   # 中证500ETF(南方)
        "510510": "000905.SH",   # 中证500ETF(易方达)
        "510560": "000905.SH",   # 中证500ETF(兴业)
        "159922": "000905.SH",   # 中证500ETF(嘉实)
        "159928": "000300.SH",   # 消费ETF → 近似
        "159938": "000300.SH",   # 医药ETF → 近似
        "512170": "000300.SH",   # 医疗ETF → 近似
        "512200": "000016.SH",   # 地产ETF → 近似
        "512400": "000016.SH",   # 有色金属ETF → 近似
        "512660": "000016.SH",   # 军工ETF → 近似
        "512800": "000016.SH",   # 银行ETF → 近似
        "515050": "000016.SH",   # 5GETF → 近似
        "515210": "000016.SH",   # 钢铁ETF → 近似
        "515220": "000016.SH",   # 煤炭ETF → 近似
        "515880": "000016.SH",   # 通信ETF → 近似
        "516000": "000016.SH",   # 大数据ETF → 近似
        "516010": "000016.SH",   # 游戏ETF → 近似
        "516110": "000016.SH",   # 汽车ETF → 近似
        "516130": "000016.SH",   # 消费电子ETF → 近似
        "516150": "000016.SH",   # 光伏ETF → 近似
        "516220": "000016.SH",   # 化工ETF → 近似
        "516510": "000016.SH",   # 云计算ETF → 近似
        "516520": "000016.SH",   # 智能电车ETF → 近似
        "516560": "000016.SH",   # 养老ETF → 近似
        "516570": "000016.SH",   # 稀土ETF → 近似
        "516580": "000016.SH",   # 新材料ETF → 近似
        "516590": "000016.SH",   # 金融科技ETF → 近似
        "516620": "000016.SH",   # 影视ETF → 近似
        "516630": "000016.SH",   # 基建ETF → 近似
        "516640": "000016.SH",   # 建材ETF → 近似
        "516650": "000016.SH",   # 物联网ETF → 近似
        "516660": "000016.SH",   # 新能车ETF → 近似
        "516670": "000016.SH",   # 碳中和ETF → 近似
        "516680": "000016.SH",   # 生物科技ETF → 近似
        "516690": "000016.SH",   # 饮食ETF → 近似
        "516700": "000016.SH",   # 数据ETF → 近似
        "516710": "000016.SH",   # 物联网ETF → 近似
        "516720": "000016.SH",   # 新能源ETF → 近似
        "516730": "000016.SH",   # 新材料ETF → 近似
        "516740": "000016.SH",   # 稀土ETF → 近似
        "516750": "000016.SH",   # 消费电子ETF → 近似
        "516760": "000016.SH",   # 人工智能ETF → 近似
        "516770": "000016.SH",   # 游戏ETF → 近似
        "516780": "000016.SH",   # 金融科技ETF → 近似
        "516790": "000016.SH",   # 云计算ETF → 近似
        "516800": "000016.SH",   # 智能制造ETF → 近似
        "516810": "000016.SH",   # 食品饮料ETF → 近似
        "516820": "000016.SH",   # 生物科技ETF → 近似
        "516830": "000016.SH",   # 农业ETF → 近似
        "516840": "000016.SH",   # 医药ETF → 近似
        "516850": "000016.SH",   # 医疗器械ETF → 近似
        "516860": "000016.SH",   # 新材料ETF → 近似
        "516870": "000016.SH",   # 碳中和ETF → 近似
        "516880": "000016.SH",   # 光伏ETF → 近似
        "516890": "000016.SH",   # 储能ETF → 近似
        "516900": "000016.SH",   # 家电ETF → 近似
        "516910": "000016.SH",   # 智能电车ETF → 近似
        "516920": "000016.SH",   # 智能汽车ETF → 近似
        "516930": "000016.SH",   # 稀有金属ETF → 近似
        "516940": "000016.SH",   # 有色ETF → 近似
        "516950": "000016.SH",   # 基建ETF → 近似
        "516960": "000016.SH",   # 证券ETF → 近似
        "516970": "000016.SH",   # 银行ETF → 近似
        "516980": "000016.SH",   # 保险ETF → 近似
        "516990": "000016.SH",   # 房地产ETF → 近似
        "517000": "000016.SH",   # 金融ETF → 近似
        "517010": "000016.SH",   # 医药ETF → 近似
        "517020": "000016.SH",   # 消费ETF → 近似
        "517030": "000016.SH",   # 科技ETF → 近似
        "517040": "000016.SH",   # 新能源ETF → 近似
        "517050": "000016.SH",   # 军工ETF → 近似
        "517060": "000016.SH",   # 资源ETF → 近似
        "517070": "000016.SH",   # 制造ETF → 近似
        "517080": "000016.SH",   # 信息ETF → 近似
        "517090": "000016.SH",   # 传媒ETF → 近似
        "517100": "000016.SH",   # 环保ETF → 近似
        "517110": "000016.SH",   # 公用ETF → 近似
        "517120": "000016.SH",   # 交运ETF → 近似
        "517130": "000016.SH",   # 建筑ETF → 近似
        "517140": "000016.SH",   # 电力ETF → 近似
        "517150": "000016.SH",   # 煤炭ETF → 近似
        "517160": "000016.SH",   # 钢铁ETF → 近似
        "517170": "000016.SH",   # 石油ETF → 近似
        "517180": "000016.SH",   # 化工ETF → 近似
        "517190": "000016.SH",   # 农业ETF → 近似
        "517200": "000016.SH",   # 医药ETF → 近似
    }

    def _get_tracking_index(self, etf_code: str) -> Optional[str]:
        """获取ETF跟踪的指数代码

        优先使用内置映射表，其次尝试通过fund_basic接口查询benchmark字段。
        """
        code = etf_code.strip()
        if code in self.ETF_INDEX_MAP:
            return self.ETF_INDEX_MAP[code]
        # 尝试通过fund_basic查询
        try:
            df = self.pro.fund_basic(market="E")
            if df is not None and not df.empty:
                row = df[df["ts_code"] == self._to_ts_code(code)]
                if not row.empty:
                    benchmark = row.iloc[0].get("benchmark", "")
                    # 简单映射常见benchmark到指数代码
                    bm_map = {
                        "沪深300指数": "000300.SH",
                        "中证500指数": "000905.SH",
                        "上证50指数": "000016.SH",
                        "创业板指数": "399006.SZ",
                        "创业板50指数": "399673.SZ",
                        "深证100指数": "399330.SZ",
                        "中证1000指数": "000852.SH",
                        "中证红利指数": "000922.SH",
                        "上证红利指数": "000015.SH",
                        "科创50指数": "000688.SH",
                    }
                    for bm_name, idx_code in bm_map.items():
                        if bm_name in str(benchmark):
                            return idx_code
        except Exception as e:
            logger.warning(f"[Tushare] 查询ETF {code} benchmark失败: {e}")
        return None

    @_cached(_CACHE_INDEX_DAILYBASIC)
    def get_index_valuation_real(self, index_code: str) -> Dict:
        """获取指数真实估值数据（PE/PB/股息率）

        通过index_dailybasic接口获取指数最新估值。
        """
        try:
            ts_code = self._to_ts_code(index_code) if "." not in index_code else index_code
            # 获取近5年数据用于计算百分位
            end = pd.Timestamp.now().strftime("%Y%m%d")
            start = (pd.Timestamp.now() - pd.Timedelta(days=1825)).strftime("%Y%m%d")
            df = self.pro.index_dailybasic(ts_code=ts_code, start_date=start, end_date=end)
            if df is None or df.empty:
                return {}
            df = df.sort_values("trade_date")
            latest = df.iloc[-1]
            # 计算百分位
            pe_series = pd.to_numeric(df["pe_ttm"], errors="coerce").dropna()
            pb_series = pd.to_numeric(df["pb"], errors="coerce").dropna()
            pe_val = float(latest.get("pe_ttm", 0) or 0)
            pb_val = float(latest.get("pb", 0) or 0)
            pe_pct = 0.0
            pb_pct = 0.0
            if len(pe_series) > 20 and pe_val > 0:
                pe_pct = (pe_series < pe_val).sum() / len(pe_series) * 100
            if len(pb_series) > 20 and pb_val > 0:
                pb_pct = (pb_series < pb_val).sum() / len(pb_series) * 100
            # 估算股息率
            div_yield = 0.0
            if pe_val > 0:
                # 股息率 ≈ (1 - 留存率) / PE, 假设留存率60%
                div_yield = (1 - 0.6) / pe_val * 100
            return {
                "index_code": index_code,
                "pe_ttm": round(pe_val, 2),
                "pe_percentile": round(pe_pct, 1),
                "pb": round(pb_val, 2),
                "pb_percentile": round(pb_pct, 1),
                "dividend_yield": round(div_yield, 2),
                "date": str(latest.get("trade_date", "")),
                "data_source": "tushare_index_dailybasic",
            }
        except Exception as e:
            logger.warning(f"[Tushare] 获取指数 {index_code} 估值失败: {e}")
            return {}

    def get_etf_constituent_metrics(self, etf_code: str) -> Dict:
        """获取ETF成分股加权基本面指标

        通过fund_portfolio获取持仓，再用daily_basic获取个股指标，
        计算加权平均的PE、PB、ROE、股息率。
        """
        try:
            ts_code = self._to_ts_code(etf_code)
            # 获取最新持仓
            df_port = self.pro.fund_portfolio(ts_code=ts_code)
            if df_port is None or df_port.empty:
                return {}
            # 取最新报告期
            df_port = df_port.sort_values("end_date", ascending=False)
            latest_date = df_port.iloc[0]["end_date"]
            df_port = df_port[df_port["end_date"] == latest_date]
            if df_port.empty:
                return {}
            # 获取每只股票的daily_basic指标
            symbols = df_port["symbol"].unique().tolist()
            all_metrics = []
            for sym in symbols[:50]:  # 限制数量避免API限制
                try:
                    end = pd.Timestamp.now().strftime("%Y%m%d")
                    start = (pd.Timestamp.now() - pd.Timedelta(days=30)).strftime("%Y%m%d")
                    df_stock = self.pro.daily_basic(ts_code=sym, start_date=start, end_date=end)
                    if df_stock is not None and not df_stock.empty:
                        latest_stock = df_stock.iloc[-1]
                        # 获取该股票的持仓权重
                        weight_row = df_port[df_port["symbol"] == sym]
                        weight = float(weight_row.iloc[0].get("stk_mkv_ratio", 0)) if not weight_row.empty else 0
                        if weight <= 0:
                            # 用市值占比估算权重
                            mkv = float(weight_row.iloc[0].get("mkv", 0)) if not weight_row.empty else 0
                            total_mkv = df_port["mkv"].astype(float).sum()
                            weight = mkv / total_mkv if total_mkv > 0 else 0
                        all_metrics.append({
                            "symbol": sym,
                            "weight": weight,
                            "pe": float(latest_stock.get("pe_ttm", 0) or 0),
                            "pb": float(latest_stock.get("pb", 0) or 0),
                            "roe": float(latest_stock.get("dv_ratio", 0) or 0) * 5,  # ROE估算：股息率*5
                            "dividend_yield": float(latest_stock.get("dv_ratio", 0) or 0),
                            "total_mv": float(latest_stock.get("total_mv", 0) or 0),
                        })
                except Exception:
                    continue
            if not all_metrics:
                return {}
            metrics_df = pd.DataFrame(all_metrics)
            # 过滤无效值
            metrics_df = metrics_df[metrics_df["weight"] > 0]
            if metrics_df.empty:
                return {}
            total_weight = metrics_df["weight"].sum()
            # 加权计算（排除PE<=0的情况）
            pe_df = metrics_df[metrics_df["pe"] > 0]
            weighted_pe = (pe_df["pe"] * pe_df["weight"]).sum() / pe_df["weight"].sum() if not pe_df.empty else 0
            pb_df = metrics_df[metrics_df["pb"] > 0]
            weighted_pb = (pb_df["pb"] * pb_df["weight"]).sum() / pb_df["weight"].sum() if not pb_df.empty else 0
            roe_df = metrics_df[metrics_df["roe"] > 0]
            weighted_roe = (roe_df["roe"] * roe_df["weight"]).sum() / roe_df["weight"].sum() if not roe_df.empty else 0
            div_df = metrics_df[metrics_df["dividend_yield"] >= 0]
            weighted_div = (div_df["dividend_yield"] * div_df["weight"]).sum() / div_df["weight"].sum() if not div_df.empty else 0
            return {
                "pe_ttm": round(weighted_pe, 2),
                "pb": round(weighted_pb, 2),
                "roe": round(weighted_roe, 2),
                "dividend_yield": round(weighted_div, 2),
                "constituent_count": len(metrics_df),
                "report_date": str(latest_date),
                "data_source": "tushare_fund_portfolio+daily_basic",
            }
        except Exception as e:
            logger.warning(f"[Tushare] 获取ETF {etf_code} 成分股指标失败: {e}")
            return {}

    def get_etf_dividend_data(self, etf_code: str) -> Dict:
        """获取ETF股息相关真实数据

        综合指数估值股息率和成分股加权股息率。
        """
        result = {"dividend_yield": 0.0, "yield_source": "none", "report_date": ""}
        try:
            # 方法1：通过跟踪指数的股息率
            index_code = self._get_tracking_index(etf_code)
            if index_code:
                idx_val = self.get_index_valuation_real(index_code)
                if idx_val and idx_val.get("dividend_yield", 0) > 0:
                    result["dividend_yield"] = idx_val["dividend_yield"]
                    result["yield_source"] = "index_dividend"
                    result["report_date"] = idx_val.get("date", "")
            # 方法2：通过成分股加权股息率（更精确）
            const_metrics = self.get_etf_constituent_metrics(etf_code)
            if const_metrics and const_metrics.get("dividend_yield", 0) > 0:
                # 如果两种方法都有数据，取平均值
                if result["dividend_yield"] > 0:
                    result["dividend_yield"] = round((result["dividend_yield"] + const_metrics["dividend_yield"]) / 2, 2)
                else:
                    result["dividend_yield"] = const_metrics["dividend_yield"]
                result["yield_source"] = "constituent_weighted"
                result["report_date"] = const_metrics.get("report_date", "")
            return result
        except Exception as e:
            logger.warning(f"[Tushare] 获取ETF {etf_code} 股息数据失败: {e}")
            return result

    @_cached(_CACHE_AUM)
    def get_etf_aum_real(self, etf_code: str) -> Dict:
        """获取ETF真实AUM数据

        通过fund_nav和fund_share接口获取。
        fund_share返回的fd_share单位为"份"（万份），数据按日期降序排列。
        """
        try:
            ts_code = self._to_ts_code(etf_code)
            result = {"aum": 0.0, "aum_source": "none", "nav": 0.0}
            # 方法1：fund_nav获取最新净值
            end = pd.Timestamp.now().strftime("%Y%m%d")
            start = (pd.Timestamp.now() - pd.Timedelta(days=30)).strftime("%Y%m%d")
            df_nav = self.pro.fund_nav(ts_code=ts_code, start_date=start, end_date=end)
            if df_nav is not None and not df_nav.empty:
                # 按日期降序排列，取最新
                df_nav = df_nav.sort_values("nav_date", ascending=False)
                latest = df_nav.iloc[0]
                nav = float(latest.get("unit_nav", 0) or 0)
                result["nav"] = round(nav, 4)
                # total_netasset 字段通常为nan，尝试使用
                tna = latest.get("total_netasset", None)
                if pd.notna(tna) and float(tna) > 0:
                    result["aum"] = round(float(tna) / 1e8, 2)  # 转亿元
                    result["aum_source"] = "fund_nav_total_netasset"
            # 方法2：fund_share获取份额 × 净值
            if result["aum"] <= 0 and result["nav"] > 0:
                df_share = self.pro.fund_share(ts_code=ts_code)
                if df_share is not None and not df_share.empty:
                    # 按日期降序排列，取最新
                    df_share = df_share.sort_values("trade_date", ascending=False)
                    latest_share = df_share.iloc[0]
                    share = float(latest_share.get("fd_share", 0) or 0)
                    if share > 0:
                        # fd_share 单位为"万份"，AUM(元) = 份额(万份) × 10000 × 净值
                        # AUM(亿元) = 份额(万份) × 净值 / 10000
                        result["aum"] = round(share * result["nav"] / 10000, 2)
                        result["aum_source"] = f"fund_share({latest_share.get('trade_date','')})*nav"
            return result
        except Exception as e:
            logger.warning(f"[Tushare] 获取ETF {etf_code} AUM失败: {e}")
            return {"aum": 0.0, "aum_source": "none", "nav": 0.0}

    @_cached(_CACHE_SHIBOR)
    def get_macro_data(self) -> Dict:
        """获取宏观数据

        获取shibor利率等宏观指标。
        """
        try:
            end = pd.Timestamp.now().strftime("%Y%m%d")
            start = (pd.Timestamp.now() - pd.Timedelta(days=90)).strftime("%Y%m%d")
            df = self.pro.shibor(start_date=start, end_date=end)
            if df is None or df.empty:
                return {}
            df = df.sort_values("date")
            latest = df.iloc[-1]
            # 计算利率趋势（近3月vs前3月）
            rate_3m = float(latest.get("3m", 0) or 0)
            rate_1y = float(latest.get("1y", 0) or 0)
            # 趋势
            if len(df) >= 60:
                recent_3m = df.tail(30)["3m"].astype(float).mean()
                prev_3m = df.iloc[-60:-30]["3m"].astype(float).mean()
                rate_trend = recent_3m - prev_3m
            else:
                rate_trend = 0.0
            return {
                "shibor_3m": round(rate_3m, 3),
                "shibor_1y": round(rate_1y, 3),
                "rate_trend": round(rate_trend, 4),
                "rate_environment": "low" if rate_1y < 2.5 else ("medium" if rate_1y < 3.5 else "high"),
                "date": str(latest.get("date", "")),
                "data_source": "tushare_shibor",
            }
        except Exception as e:
            logger.warning(f"[Tushare] 获取宏观数据失败: {e}")
            return {}

    def get_etf_fundamental_data(self, etf_code: str) -> Dict:
        """一键获取ETF全部基本面真实数据

        这是丁昶五维评分引擎使用的主接口，一次性获取所有维度的真实数据。

        Returns
        -------
        dict
            {
                "dividend": {"dividend_yield": x, ...},
                "valuation": {"pe_ttm": x, "pb": x, "pe_percentile": x, ...},
                "profitability": {"roe": x, ...},
                "capital_flow": {"aum": x, ...},
                "macro": {"shibor_3m": x, ...},
                "constituent_metrics": {"pe_ttm": x, "pb": x, "roe": x, "dividend_yield": x},
            }
        """
        logger.info(f"[Tushare] 获取ETF {etf_code} 全部基本面数据")
        result = {
            "dividend": {},
            "valuation": {},
            "profitability": {},
            "capital_flow": {},
            "macro": {},
            "constituent_metrics": {},
        }
        try:
            # 1. 股息数据
            result["dividend"] = self.get_etf_dividend_data(etf_code)
            # 2. 估值数据（优先用跟踪指数）
            index_code = self._get_tracking_index(etf_code)
            if index_code:
                idx_val = self.get_index_valuation_real(index_code)
                if idx_val:
                    result["valuation"] = idx_val
            # 3. 成分股指标
            result["constituent_metrics"] = self.get_etf_constituent_metrics(etf_code)
            # 如果有成分股估值数据但指数估值失败，用成分股的
            if not result["valuation"] and result["constituent_metrics"]:
                cm = result["constituent_metrics"]
                result["valuation"] = {
                    "pe_ttm": cm.get("pe_ttm", 0),
                    "pb": cm.get("pb", 0),
                    "pe_percentile": 50.0,
                    "pb_percentile": 50.0,
                    "dividend_yield": cm.get("dividend_yield", 0),
                    "data_source": "constituent_weighted",
                }
            # 4. 盈利数据
            if result["constituent_metrics"]:
                result["profitability"] = {
                    "roe": result["constituent_metrics"].get("roe", 0),
                    "data_source": "constituent_weighted",
                }
            # 5. 资金流数据
            result["capital_flow"] = self.get_etf_aum_real(etf_code)
            # 6. 宏观数据（全局缓存，不需要每次都获取）
            result["macro"] = self.get_macro_data()
            logger.info(f"[Tushare] ETF {etf_code} 基本面数据获取完成")
            return result
        except Exception as e:
            logger.warning(f"[Tushare] 获取ETF {etf_code} 全部基本面数据失败: {e}")
            return result


class DataFetchError(Exception):
    """数据获取异常"""
    pass
