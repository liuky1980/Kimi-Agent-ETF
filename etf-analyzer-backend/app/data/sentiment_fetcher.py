"""
情绪数据获取器
==============
获取市场情绪相关数据，包括PCR(看跌看涨比)、融资余额变化、
北向资金流向、主力资金流向等。

所有数据获取均包含Fallback策略，确保在Tushare接口不可用
时返回默认值，不会抛异常导致上层服务500错误。
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import pandas as pd

from app.config import settings

logger = logging.getLogger(__name__)


class SentimentDataFetcher:
    """市场情绪数据获取器

    通过Tushare接口获取PCR、融资余额、北向资金、主力资金等数据。
    所有方法在获取失败时返回fallback默认值，确保服务稳定性。
    """

    def __init__(self):
        self.token = settings.TUSHARE_TOKEN
        self._pro = None
        self._tushare_available = False
        self._init_tushare()

    def _init_tushare(self) -> None:
        """延迟初始化Tushare客户端"""
        try:
            import tushare as ts

            ts.set_token(self.token)
            self._pro = ts.pro_api()
            self._tushare_available = True
            logger.info("[SentimentFetcher] Tushare客户端初始化成功")
        except Exception as e:
            self._tushare_available = False
            logger.warning(f"[SentimentFetcher] Tushare初始化失败，将使用fallback数据: {e}")

    # ────────────────────────────── PCR 数据 ──────────────────────────────

    def get_pcr(self, days: int = 5) -> float:
        """获取50ETF期权Put/Call Ratio

        通过Tushare的opt_daily接口获取50ETF期权日行情，
        分别计算put和call的成交量，得出PCR比值。

        Parameters
        ----------
        days : int
            计算PCR的交易日天数，默认5日

        Returns
        -------
        float
            Put/Call Ratio，获取失败返回fallback值1.0
        """
        if not self._tushare_available or self._pro is None:
            logger.warning("[SentimentFetcher] Tushare不可用，PCR使用fallback=1.0")
            return 1.0

        try:
            # 获取交易日历
            end_date = datetime.now().strftime("%Y%m%d")
            start_date = (datetime.now() - timedelta(days=days * 2 + 10)).strftime("%Y%m%d")

            # 获取50ETF期权日线数据（模拟用上证50ETF）
            # Tushare的opt_daily接口需要期权代码，50ETF期权代码以510050开头
            # 实际PCR计算需要分别获取call和put的成交量
            # 这里通过opt_daily获取全部期权数据后筛选

            df = self._pro.opt_daily(start_date=start_date, end_date=end_date)
            if df is None or df.empty:
                logger.warning("[SentimentFetcher] opt_daily返回空数据，PCR使用fallback=1.0")
                return 1.0

            # 筛选50ETF相关期权（标的为510050.SH）
            # opt_daily返回的字段包括 exchange, code, name, call_put 等
            if "exchange" not in df.columns or "call_put" not in df.columns:
                logger.warning("[SentimentFetcher] 期权数据字段缺失，PCR使用fallback=1.0")
                return 1.0

            # 筛选50ETF期权（上海交易所）
            df_50etf = df[df["exchange"] == "SSE"].copy()
            if df_50etf.empty:
                logger.warning("[SentimentFetcher] 无50ETF期权数据，PCR使用fallback=1.0")
                return 1.0

            # 取最近N个交易日
            df_50etf["trade_date"] = pd.to_datetime(df_50etf["trade_date"])
            df_50etf = df_50etf.sort_values("trade_date", ascending=False)
            recent_dates = df_50etf["trade_date"].unique()[:days]
            df_recent = df_50etf[df_50etf["trade_date"].isin(recent_dates)]

            if df_recent.empty:
                logger.warning("[SentimentFetcher] 近期无期权数据，PCR使用fallback=1.0")
                return 1.0

            # 分别计算put和call的成交量
            put_vol = df_recent[df_recent["call_put"] == "P"]["vol"].sum()
            call_vol = df_recent[df_recent["call_put"] == "C"]["vol"].sum()

            if call_vol == 0:
                logger.warning("[SentimentFetcher] Call成交量为0，PCR使用fallback=1.0")
                return 1.0

            pcr = float(put_vol / call_vol)
            logger.info(f"[SentimentFetcher] PCR计算成功: {pcr:.4f} (put_vol={put_vol}, call_vol={call_vol})")
            return round(pcr, 4)

        except Exception as e:
            logger.warning(f"[SentimentFetcher] PCR获取失败，使用fallback=1.0: {e}")
            return 1.0

    # ────────────────────────────── 融资余额 ──────────────────────────────

    def get_financing_change(self, days: int = 5) -> float:
        """获取融资余额5日变化率

        通过Tushare的margin接口获取融资融券数据，
        计算最近N日融资余额的变化百分比。

        Parameters
        ----------
        days : int
            计算变化率的交易日天数，默认5日

        Returns
        -------
        float
            融资余额变化率(小数形式，如0.03表示+3%)，获取失败返回0.0
        """
        if not self._tushare_available or self._pro is None:
            logger.warning("[SentimentFetcher] Tushare不可用，融资变化使用fallback=0.0")
            return 0.0

        try:
            end_date = datetime.now().strftime("%Y%m%d")
            start_date = (datetime.now() - timedelta(days=days * 2 + 10)).strftime("%Y%m%d")

            # Tushare的margin接口获取融资融券汇总数据
            df = self._pro.margin(start_date=start_date, end_date=end_date)
            if df is None or df.empty:
                logger.warning("[SentimentFetcher] margin返回空数据，融资变化使用fallback=0.0")
                return 0.0

            # 按日期排序，取最近days条
            df = df.sort_values("trade_date", ascending=True)
            if len(df) < 2:
                logger.warning("[SentimentFetcher] 融资数据不足，使用fallback=0.0")
                return 0.0

            # 计算融资余额变化率
            # 使用最早和最晚的融资余额计算
            latest_finance = float(df["fin_bal"].iloc[-1])
            previous_finance = float(df["fin_bal"].iloc[-min(days + 1, len(df))])

            if previous_finance == 0:
                logger.warning("[SentimentFetcher] 融资余额为0，使用fallback=0.0")
                return 0.0

            change_rate = (latest_finance - previous_finance) / previous_finance
            logger.info(f"[SentimentFetcher] 融资变化率计算成功: {change_rate:.4f}")
            return round(change_rate, 4)

        except Exception as e:
            logger.warning(f"[SentimentFetcher] 融资变化获取失败，使用fallback=0.0: {e}")
            return 0.0

    # ────────────────────────────── 北向资金 ──────────────────────────────

    def get_northbound_flow(self, days: int = 5) -> float:
        """获取北向资金N日净流入(亿元)

        通过Tushare的moneyflow_hsgt接口获取沪深港通资金流向。

        Parameters
        ----------
        days : int
            统计的交易日天数，默认5日

        Returns
        -------
        float
            北向资金N日净流入(亿元)，获取失败返回0.0
        """
        if not self._tushare_available or self._pro is None:
            logger.warning("[SentimentFetcher] Tushare不可用，北向资金使用fallback=0.0")
            return 0.0

        try:
            end_date = datetime.now().strftime("%Y%m%d")
            start_date = (datetime.now() - timedelta(days=days * 2 + 10)).strftime("%Y%m%d")

            df = self._pro.moneyflow_hsgt(start_date=start_date, end_date=end_date)
            if df is None or df.empty:
                logger.warning("[SentimentFetcher] moneyflow_hsgt返回空数据，使用fallback=0.0")
                return 0.0

            # 按日期排序，取最近days条
            df = df.sort_values("trade_date", ascending=True)
            df_recent = df.tail(days)

            if df_recent.empty:
                logger.warning("[SentimentFetcher] 北向资金数据不足，使用fallback=0.0")
                return 0.0

            # 北向资金净流入求和（单位：亿元）
            # hsgt_net代表沪深港通净流入
            if "hsgt_net" in df_recent.columns:
                total_flow = df_recent["hsgt_net"].astype(float).sum()
            elif "net_mf" in df_recent.columns:
                total_flow = df_recent["net_mf"].astype(float).sum()
            else:
                # 尝试用买入和卖出差额计算
                buy_col = [c for c in df_recent.columns if "buy" in c.lower()]
                sell_col = [c for c in df_recent.columns if "sell" in c.lower()]
                if buy_col and sell_col:
                    total_flow = (
                        df_recent[buy_col[0]].astype(float).sum()
                        - df_recent[sell_col[0]].astype(float).sum()
                    )
                else:
                    logger.warning("[SentimentFetcher] 北向资金字段无法识别，使用fallback=0.0")
                    return 0.0

            total_flow = float(total_flow)
            logger.info(f"[SentimentFetcher] 北向{days}日净流入: {total_flow:.2f}亿元")
            return round(total_flow, 2)

        except Exception as e:
            logger.warning(f"[SentimentFetcher] 北向资金获取失败，使用fallback=0.0: {e}")
            return 0.0

    # ────────────────────────────── 主力资金 ──────────────────────────────

    def get_main_force_flow(self, etf_code: str = "510300", days: int = 1) -> float:
        """获取主力资金净流入估算(亿元)

        通过Tushare的fund_daily或daily接口获取ETF成交数据，
        用大单成交额估算主力资金流向。

        Parameters
        ----------
        etf_code : str
            ETF代码，默认510300(沪深300ETF)
        days : int
            统计天数，默认1日

        Returns
        -------
        float
            主力资金净流入估算(亿元)，获取失败返回0.0
        """
        if not self._tushare_available or self._pro is None:
            logger.warning("[SentimentFetcher] Tushare不可用，主力资金使用fallback=0.0")
            return 0.0

        try:
            end_date = datetime.now().strftime("%Y%m%d")
            start_date = (datetime.now() - timedelta(days=days * 2 + 5)).strftime("%Y%m%d")

            # 转换ETF代码为tushare格式
            ts_code = self._to_ts_code(etf_code)

            # 获取ETF日线数据
            df = self._pro.fund_daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
            if df is None or df.empty:
                logger.warning(f"[SentimentFetcher] ETF {etf_code} 日线数据为空，主力资金fallback=0.0")
                return 0.0

            df = df.sort_values("trade_date", ascending=True)
            df_recent = df.tail(days)

            if df_recent.empty:
                logger.warning("[SentimentFetcher] 主力资金数据不足，使用fallback=0.0")
                return 0.0

            # 主力资金估算：使用成交额 * 价格变动方向作为近似
            # 涨时假设主力流入，跌时假设主力流出
            # 更精确的方法需要用tick数据计算大单，但这里用简化估算
            total_amount = df_recent["amount"].astype(float).sum()  # 单位：千元
            avg_pct_change = df_recent["pct_chg"].astype(float).mean()

            # 主力资金 ≈ 成交额 * 涨跌幅比例因子 (单位转换为亿元)
            # 假设涨跌幅的60%由主力资金驱动
            main_force_factor = 0.6
            main_force_flow = total_amount * (avg_pct_change / 100) * main_force_factor / 100000  # 千元->亿元

            result = float(main_force_flow)
            logger.info(f"[SentimentFetcher] 主力资金估算: {result:.2f}亿元 (基于{etf_code})")
            return round(result, 2)

        except Exception as e:
            logger.warning(f"[SentimentFetcher] 主力资金获取失败，使用fallback=0.0: {e}")
            return 0.0

    # ────────────────────────────── 批量获取 ──────────────────────────────

    def get_all_sentiment_data(self, etf_code: str = "510300") -> Dict:
        """批量获取所有情绪数据

        一次性获取PCR、融资变化、北向资金、主力资金全部数据，
        组织为字典返回。任一指标获取失败时使用fallback值。

        Parameters
        ----------
        etf_code : str
            ETF代码，用于主力资金估算，默认510300

        Returns
        -------
        dict
            包含所有情绪指标的字典:
            {
                "pcr": float,
                "financing_change": float,
                "northbound_5d": float,
                "main_force_flow": float,
            }
        """
        logger.info("[SentimentFetcher] 开始批量获取情绪数据...")

        data = {
            "pcr": self.get_pcr(days=5),
            "financing_change": self.get_financing_change(days=5),
            "northbound_5d": self.get_northbound_flow(days=5),
            "main_force_flow": self.get_main_force_flow(etf_code=etf_code, days=1),
        }

        logger.info(
            f"[SentimentFetcher] 情绪数据获取完成: "
            f"PCR={data['pcr']}, 融资变化={data['financing_change']:.4f}, "
            f"北向5日={data['northbound_5d']:.2f}亿, 主力={data['main_force_flow']:.2f}亿"
        )
        return data

    # ────────────────────────────── 工具方法 ──────────────────────────────

    @staticmethod
    def _to_ts_code(code: str) -> str:
        """转换为tushare的ts_code格式

        上海ETF: 51, 56, 58 开头 -> code.SH
        深圳ETF: 15, 16, 17, 18, 19 开头 -> code.SZ
        """
        code = code.strip()
        if "." in code:
            return code
        if code.startswith(("15", "16", "17", "18", "19")):
            return f"{code}.SZ"
        elif code.startswith(("8", "9")):
            return f"{code}.BJ"
        else:
            return f"{code}.SH"


# ────────────────────────────── 模块级便捷函数 ──────────────────────────────

_default_fetcher: Optional[SentimentDataFetcher] = None


def get_sentiment_fetcher() -> SentimentDataFetcher:
    """获取全局默认的SentimentDataFetcher单例"""
    global _default_fetcher
    if _default_fetcher is None:
        _default_fetcher = SentimentDataFetcher()
    return _default_fetcher
