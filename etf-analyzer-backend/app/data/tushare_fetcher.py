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

from app.config import settings

logger = logging.getLogger(__name__)

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

    使用tushare Pro接口获取A股ETF的各类行情数据，接口与ETFDataFetcher保持一致。
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

    # ────────────────────────────── 工具方法 ──────────────────────────────

    @staticmethod
    def _to_ts_code(code: str) -> str:
        """转换为tushare的ts_code格式

        上海ETF: 1、5、6开头 -> code.SH
        深圳ETF: 0、1、2、3开头 -> code.SZ
        北京ETF: 8、9开头 -> code.BJ
        """
        code = code.strip()
        if code.startswith("5") or code.startswith("6") or code.startswith("1"):
            return f"{code}.SH"
        elif code.startswith("8") or code.startswith("9"):
            return f"{code}.BJ"
        else:
            return f"{code}.SZ"

    @staticmethod
    def _from_ts_code(ts_code: str) -> str:
        """从tushare的ts_code格式还原为纯数字代码"""
        return ts_code.split(".")[0] if "." in ts_code else ts_code

    # ────────────────────────────── 基础数据接口 ──────────────────────────────

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

            df = self.pro.daily(ts_code=ts_code, start_date=start, end_date=end)
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
                }
            )
            df["date"] = pd.to_datetime(df["date"])
            df = df.sort_values("date").reset_index(drop=True)

            # 计算派生字段（amplitude, pct_change, change, turnover）
            df["change"] = df["close"].diff()
            df["pct_change"] = df["close"].pct_change() * 100
            df["amplitude"] = (
                (df["high"] - df["low"]) / df["low"].shift(1) * 100
            ).fillna(0)
            # turnover（换手率）tushare daily接口不直接提供，设为空
            df["turnover"] = 0.0

            # 选择并排序列，与akshare保持一致
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

    def get_etf_list(self) -> pd.DataFrame:
        """获取全部ETF实时列表

        Returns
        -------
        pd.DataFrame
            ETF列表，包含代码、名称等字段，列名与akshare尽量一致
        """
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

            # 添加tushare特有的列，便于前端识别
            if "上市日期" in df.columns:
                df["最新价"] = 0.0
                df["涨跌幅"] = 0.0
                df["成交量"] = 0.0
                df["成交额"] = 0.0

            logger.info(f"[Tushare] 成功获取ETF列表，共 {len(df)} 只")
            return df

        except Exception as e:
            logger.error(f"[Tushare] 获取ETF列表失败: {e}")
            raise DataFetchError(f"[Tushare] 获取ETF列表失败: {e}") from e

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
        end_date = pd.Timestamp.now().strftime("%Y%m%d")
        start_daily = (
            pd.Timestamp.now() - pd.Timedelta(days=730)
        ).strftime("%Y%m%d")

        result = {}
        result["daily"] = self.get_etf_daily(code, start_daily, end_date)
        result["30min"] = self.get_etf_minute(code, "30")
        result["5min"] = self.get_etf_minute(code, "5")

        return result


class DataFetchError(Exception):
    """数据获取异常"""
    pass
