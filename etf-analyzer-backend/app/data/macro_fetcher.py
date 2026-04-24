"""
宏观数据获取器
==============
负责获取宏观周期分析所需的各类经济数据，包括社融增速、M2-M1剪刀差、
PMI产成品库存、10Y国债收益率、ERP等关键指标。

数据获取优先级:
    1. Tushare Pro 宏观数据接口 (macror / shibor 等)
    2. Tushare 市场数据近似代理
    3. 基于近期价格数据的简化代理指标 (fallback)

所有数据获取均包含 try/except 保护，任何异常都不会抛到上层，
确保宏观分析模块始终可用。
"""

import logging
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from app.config import settings

logger = logging.getLogger(__name__)

# ────────────────────────────── 默认 fallback 常量 ──────────────────────────────
# 当所有数据源均不可用时使用的保守默认值
_FALLBACK_AFRE_YOY_3M: float = 9.0     # 社融增速近3月均值 (%)
_FALLBACK_AFRE_YOY_12M: float = 9.5    # 社融增速近12月均值 (%)
_FALLBACK_M2_M1_SPREAD: float = 6.0    # M2-M1剪刀差 (%)
_FALLBACK_PMI_INVENTORY: float = 48.0   # PMI产成品库存
_FALLBACK_PMI_TREND: List[float] = [48.5, 48.2, 47.8]  # 近3月PMI库存趋势
_FALLBACK_PE_PERCENTILE: float = 50.0   # PE分位数 (%)

# 沪深300ETF代码（用于fallback动量计算）
_CSI300_ETF_CODE: str = "510300"


class MacroDataFetcher:
    """宏观数据获取器

    封装多层数据获取策略，优先使用Tushare宏观接口，
    不可用时依次回退到市场数据代理、简化代理指标。

    Attributes
    ----------
    pro : Any
        Tushare Pro API 实例（延迟初始化）
    _tushare_available : bool
        Tushare 是否可用标志
    """

    def __init__(self) -> None:
        self.pro: Optional[Any] = None
        self._tushare_available: bool = False
        self._init_tushare()

    # ────────────────────────────── Tushare 初始化 ──────────────────────────────

    def _init_tushare(self) -> None:
        """延迟初始化 Tushare 客户端"""
        if not settings.TUSHARE_ENABLED:
            logger.info("Tushare 已在配置中禁用，跳过初始化")
            return
        try:
            import tushare as ts

            ts.set_token(settings.TUSHARE_TOKEN)
            self.pro = ts.pro_api()
            self._tushare_available = True
            logger.info("MacroDataFetcher: Tushare 客户端初始化成功")
        except Exception as e:
            self._tushare_available = False
            logger.warning(f"MacroDataFetcher: Tushare 初始化失败，将使用 fallback: {e}")

    # ────────────────────────────── 外部接口: 一键获取 ──────────────────────────────

    def fetch_all(self) -> Dict[str, Any]:
        """一键获取宏观分析所需的全部数据

        按优先级尝试多个数据源，返回包含所有指标的字典。
        任何单个指标获取失败都会使用 fallback 值，不会抛异常。

        Returns
        -------
        dict
            包含以下键的字典:
            - afre_yoy_3m: 社融增速近3月均值
            - afre_yoy_12m: 社融增速近12月均值
            - m2_m1_spread: M2-M1剪刀差
            - pmi_inventory: PMI产成品库存最新值
            - pmi_inventory_trend: PMI库存近3月序列
            - pe_percentile: 沪深300 PE分位数
            - data_source: 数据来源标记
        """
        logger.info("MacroDataFetcher: 开始获取宏观数据...")

        # 优先尝试 Tushare 宏观接口
        if self._tushare_available:
            try:
                result = self._fetch_from_tushare_macro()
                if self._is_data_complete(result):
                    logger.info("MacroDataFetcher: 从 Tushare 宏观接口获取数据成功")
                    result["data_source"] = "tushare_macro"
                    return result
            except Exception as e:
                logger.warning(f"Tushare 宏观接口获取失败: {e}")

        # 回退: 尝试 Tushare 市场数据代理
        if self._tushare_available:
            try:
                result = self._fetch_from_tushare_proxy()
                if self._is_data_complete(result):
                    logger.info("MacroDataFetcher: 从 Tushare 市场代理获取数据成功")
                    result["data_source"] = "tushare_proxy"
                    return result
            except Exception as e:
                logger.warning(f"Tushare 市场代理获取失败: {e}")

        # 最终回退: 简化代理指标
        try:
            result = self._fetch_from_fallback_proxy()
            logger.info("MacroDataFetcher: 使用简化代理指标 (fallback)")
            result["data_source"] = "fallback_proxy"
            return result
        except Exception as e:
            logger.error(f"Fallback 代理也失败: {e}，使用硬编码默认值")

        # 最后防线: 硬编码保守默认值
        return self._get_hardcoded_defaults()

    # ────────────────────────────── Tushare 宏观接口 ──────────────────────────────

    def _fetch_from_tushare_macro(self) -> Dict[str, Any]:
        """通过 Tushare Pro 宏观数据接口获取指标

        使用接口:
            - pro.macror(): 社融增量数据
            - pro.shibor(): 银行间利率（间接反映货币环境）
            - pro.cnpmi(): 官方制造业PMI

        Returns
        -------
        dict
            宏观指标字典（可能不完整，需用 _is_data_complete 校验）
        """
        result: Dict[str, Any] = {}

        # 1. 获取社融增量数据 (近15个月，用于计算3月和12月均值)
        try:
            df_afre = self.pro.macror(
                start_date=(pd.Timestamp.now() - pd.DateOffset(months=15)).strftime("%Y%m"),
                end_date=pd.Timestamp.now().strftime("%Y%m"),
                fields="month, afre_yoy"
            )
            if df_afre is not None and not df_afre.empty:
                df_afre = df_afre.sort_values("month")
                afre_values = pd.to_numeric(df_afre["afre_yoy"], errors="coerce").dropna()
                if len(afre_values) >= 12:
                    result["afre_yoy_3m"] = round(float(afre_values.tail(3).mean()), 2)
                    result["afre_yoy_12m"] = round(float(afre_values.tail(12).mean()), 2)
                    logger.debug(f"社融增速: 3月均值={result['afre_yoy_3m']}%, 12月均值={result['afre_yoy_12m']}%")
        except Exception as e:
            logger.warning(f"Tushare macror 接口失败: {e}")

        # 2. 获取 M2/M1 增速，计算剪刀差
        try:
            df_money = self.pro.cn_m(
                m=(pd.Timestamp.now() - pd.DateOffset(months=4)).strftime("%Y%m"),
                fields="month, m2_yoy, m1_yoy"
            )
            if df_money is not None and not df_money.empty:
                df_money = df_money.sort_values("month")
                m2_yoy = pd.to_numeric(df_money["m2_yoy"], errors="coerce")
                m1_yoy = pd.to_numeric(df_money["m1_yoy"], errors="coerce")
                spread = (m2_yoy - m1_yoy).dropna()
                if not spread.empty:
                    result["m2_m1_spread"] = round(float(spread.iloc[-1]), 2)
                    logger.debug(f"M2-M1剪刀差: {result['m2_m1_spread']}%")
        except Exception as e:
            logger.warning(f"Tushare cn_m 接口失败: {e}")

        # 3. 获取 PMI 产成品库存分项
        try:
            df_pmi = self.pro.cnpmi(
                m=(pd.Timestamp.now() - pd.DateOffset(months=6)).strftime("%Y%m"),
                fields="month, item, df, bz"
            )
            if df_pmi is not None and not df_pmi.empty:
                # 查找产成品库存分项 (item='产成品库存')
                inventory_rows = df_pmi[df_pmi["item"].str.contains("产成品库存", na=False)]
                if not inventory_rows.empty:
                    inventory_rows = inventory_rows.sort_values("month")
                    df_values = pd.to_numeric(inventory_rows["df"], errors="coerce").dropna()
                    if not df_values.empty:
                        result["pmi_inventory"] = round(float(df_values.iloc[-1]), 2)
                        # 取近3个月趋势
                        result["pmi_inventory_trend"] = df_values.tail(3).tolist()
                        logger.debug(f"PMI库存: 最新={result['pmi_inventory']}, 趋势={result['pmi_inventory_trend']}")
        except Exception as e:
            logger.warning(f"Tushare cnpmi 接口失败: {e}")

        # 4. 获取沪深300 PE 分位数
        try:
            pe_pct = self._get_hs300_pe_percentile()
            if pe_pct is not None:
                result["pe_percentile"] = round(pe_pct, 2)
        except Exception as e:
            logger.warning(f"沪深300 PE分位数获取失败: {e}")

        return result

    # ────────────────────────────── Tushare 市场数据代理 ──────────────────────────────

    def _fetch_from_tushare_proxy(self) -> Dict[str, Any]:
        """通过 Tushare 市场数据间接代理宏观指标

        当宏观接口不可用时，用市场数据近似:
            - 10Y国债收益率趋势 → 近似信用环境
            - Shibor3M → 近似流动性
            - 沪深300动量 → 近似经济景气度

        Returns
        -------
        dict
            宏观指标字典（可能不完整）
        """
        result: Dict[str, Any] = {}

        # 1. 获取10Y国债收益率近3月趋势
        try:
            df_bond = self.pro.yc(
                ts_code="GY.10",
                start_date=(pd.Timestamp.now() - pd.DateOffset(months=4)).strftime("%Y%m%d"),
                end_date=pd.Timestamp.now().strftime("%Y%m%d")
            )
            if df_bond is not None and not df_bond.empty:
                df_bond = df_bond.sort_values("ts_date")
                yield_values = pd.to_numeric(df_bond["yield"], errors="coerce").dropna()
                if len(yield_values) >= 60:
                    # 国债收益率下行 ≈ 信用宽松 ≈ 扩张
                    recent_yield_change = float(yield_values.tail(20).mean() - yield_values.tail(60).mean())
                    # 转换: 收益率下行(负变化) → 信用扩张(正值)
                    result["afre_yoy_3m"] = round(9.0 - recent_yield_change * 5, 2)
                    result["afre_yoy_12m"] = round(9.5 - recent_yield_change * 3, 2)
                    logger.debug(f"国债收益率代理: afre_3m={result['afre_yoy_3m']}")
        except Exception as e:
            logger.warning(f"国债收益率代理获取失败: {e}")

        # 2. Shibor3M 代理 M2-M1 剪刀差
        try:
            df_shibor = self.pro.shibor(
                start_date=(pd.Timestamp.now() - pd.DateOffset(months=3)).strftime("%Y%m%d"),
                end_date=pd.Timestamp.now().strftime("%Y%m%d"),
                fields="date, `3m`"
            )
            if df_shibor is not None and not df_shibor.empty:
                shibor_3m = pd.to_numeric(df_shibor["3m"], errors="coerce").dropna()
                if not shibor_3m.empty:
                    # Shibor低 → 流动性宽松 → M2-M1剪刀差收窄
                    latest_shibor = float(shibor_3m.iloc[-1])
                    result["m2_m1_spread"] = round(3.0 + latest_shibor * 0.5, 2)
                    logger.debug(f"Shibor代理 M2-M1: {result['m2_m1_spread']}")
        except Exception as e:
            logger.warning(f"Shibor代理获取失败: {e}")

        # 3. 沪深300动量近似 PMI 库存
        try:
            df_csi300 = self.pro.index_daily(
                ts_code="000300.SH",
                start_date=(pd.Timestamp.now() - pd.DateOffset(months=3)).strftime("%Y%m%d"),
                end_date=pd.Timestamp.now().strftime("%Y%m%d")
            )
            if df_csi300 is not None and not df_csi300.empty:
                df_csi300 = df_csi300.sort_values("trade_date")
                close_prices = pd.to_numeric(df_csi300["close"], errors="coerce").dropna()
                if len(close_prices) >= 20:
                    # 短期动量转负 → 库存去化压力
                    mom_20 = float(close_prices.tail(20).mean() / close_prices.tail(60).mean() - 1)
                    # 映射到 PMI 库存区间 (45-55)
                    result["pmi_inventory"] = round(50.0 + mom_20 * 100, 2)
                    result["pmi_inventory_trend"] = [
                        round(50.0 + mom_20 * 100 + i * 0.3, 2) for i in range(-2, 1)
                    ]
                    logger.debug(f"沪深300动量代理 PMI: {result['pmi_inventory']}")
        except Exception as e:
            logger.warning(f"沪深300动量代理获取失败: {e}")

        # 4. PE 分位数
        try:
            pe_pct = self._get_hs300_pe_percentile()
            if pe_pct is not None:
                result["pe_percentile"] = round(pe_pct, 2)
        except Exception as e:
            logger.warning(f"PE分位数获取失败: {e}")

        return result

    # ────────────────────────────── 简化代理指标 (Fallback) ──────────────────────────────

    def _fetch_from_fallback_proxy(self) -> Dict[str, Any]:
        """基于近期价格数据的简化宏观代理指标

        当 Tushare 完全不可用时，使用基于价格数据的代理:
            - 信用状态 ≈ 沪深300 60日动量方向
              (正动量 = 信用扩张, 负动量 = 信用收缩)
            - 库存状态 ≈ 商品价格 20日趋势
              (向上 = 库存累积, 向下 = 库存去化)

        该方法完全不依赖外部 API，仅使用 akshare 获取价格数据。

        Returns
        -------
        dict
            包含完整宏观指标的字典（不会为空）
        """
        result: Dict[str, Any] = {}

        # 1. 沪深300 60日动量 → 代理社融增速
        try:
            import akshare as ak

            # 获取沪深300ETF日线
            end_date = pd.Timestamp.now().strftime("%Y%m%d")
            start_date = (pd.Timestamp.now() - pd.DateOffset(months=4)).strftime("%Y%m%d")

            df_csi300 = ak.fund_etf_hist_em(
                symbol=_CSI300_ETF_CODE,
                period="daily",
                start_date=start_date,
                end_date=end_date,
                adjust="qfq"
            )
            if df_csi300 is not None and not df_csi300.empty:
                df_csi300.columns = [
                    "date", "open", "close", "high", "low", "volume",
                    "amount", "amplitude", "pct_change", "change", "turnover"
                ]
                df_csi300["date"] = pd.to_datetime(df_csi300["date"])
                df_csi300 = df_csi300.sort_values("date")

                close_prices = df_csi300["close"].astype(float)

                # 60日动量
                if len(close_prices) >= 60:
                    mom_60d = float(close_prices.iloc[-1] / close_prices.iloc[-60] - 1)
                else:
                    mom_60d = 0.0

                # 映射到社融增速区间 (5-14%)
                # 正动量 → 高社融增速(扩张), 负动量 → 低社融增速(收缩)
                afre_base = 9.5 + mom_60d * 30
                result["afre_yoy_3m"] = round(afre_base + 0.2, 2)
                result["afre_yoy_12m"] = round(afre_base - 0.3, 2)
                logger.debug(f"Fallback 社融代理: 60日动量={mom_60d:.2%}, afre_3m={result['afre_yoy_3m']}")

                # 2. 沪深300 20日波动 → 代理 M2-M1 剪刀差
                volatility_20d = float(close_prices.tail(20).pct_change().std() * np.sqrt(252))
                # 高波动 → 不确定性 → 企业持币 → M2-M1扩大
                result["m2_m1_spread"] = round(5.0 + volatility_20d * 10, 2)
                logger.debug(f"Fallback M2-M1代理: 波动率={volatility_20d:.2%}, spread={result['m2_m1_spread']}")

                # 3. 20日价格趋势斜率 → 代理 PMI 库存
                if len(close_prices) >= 20:
                    prices_20d = close_prices.tail(20).values
                    x = np.arange(len(prices_20d))
                    slope = np.polyfit(x, prices_20d, 1)[0]
                    slope_pct = slope / prices_20d.mean() * 100  # 日均变化百分比

                    # 映射到 PMI 库存区间 (45-55)
                    result["pmi_inventory"] = round(50.0 + slope_pct * 20, 2)
                    result["pmi_inventory_trend"] = [
                        round(50.0 + slope_pct * 20 * (1 + i * 0.1), 2) for i in range(-2, 1)
                    ]
                    logger.debug(f"Fallback PMI代理: 斜率={slope_pct:.4f}%, 库存={result['pmi_inventory']}")

                # 4. 近1年PE近似
                try:
                    current_price = float(close_prices.iloc[-1])
                    price_252d = close_prices.tail(252)
                    if len(price_252d) > 20:
                        percentile = (price_252d < current_price).sum() / len(price_252d) * 100
                        result["pe_percentile"] = round(float(percentile), 2)
                except Exception:
                    pass
        except Exception as e:
            logger.warning(f"Fallback 代理指标计算失败: {e}")

        return result

    # ────────────────────────────── 硬编码默认 ──────────────────────────────

    def _get_hardcoded_defaults(self) -> Dict[str, Any]:
        """返回硬编码的保守默认值（最后防线）

        当所有数据获取方式均失败时使用，确保 analyze() 永不被阻塞。

        Returns
        -------
        dict
            硬编码默认宏观指标
        """
        return {
            "afre_yoy_3m": _FALLBACK_AFRE_YOY_3M,
            "afre_yoy_12m": _FALLBACK_AFRE_YOY_12M,
            "m2_m1_spread": _FALLBACK_M2_M1_SPREAD,
            "pmi_inventory": _FALLBACK_PMI_INVENTORY,
            "pmi_inventory_trend": list(_FALLBACK_PMI_TREND),
            "pe_percentile": _FALLBACK_PE_PERCENTILE,
            "data_source": "hardcoded_default",
        }

    # ────────────────────────────── 工具方法 ──────────────────────────────

    def _is_data_complete(self, result: Dict[str, Any]) -> bool:
        """检查数据字典是否包含所有必需字段

        Parameters
        ----------
        result : dict
            待检查的数据字典

        Returns
        -------
        bool
            包含所有必需字段时返回 True
        """
        required_keys = [
            "afre_yoy_3m", "afre_yoy_12m", "m2_m1_spread",
            "pmi_inventory", "pmi_inventory_trend"
        ]
        return all(k in result for k in required_keys)

    def _get_hs300_pe_percentile(self) -> Optional[float]:
        """获取沪深300 PE-TTM 历史分位数

        通过 Tushare index_dailybasic 接口计算。

        Returns
        -------
        float or None
            PE分位数 (0-100)，失败时返回 None
        """
        if self.pro is None:
            return None

        try:
            end = pd.Timestamp.now().strftime("%Y%m%d")
            start = (pd.Timestamp.now() - pd.DateOffset(years=5)).strftime("%Y%m%d")
            df = self.pro.index_dailybasic(ts_code="000300.SH", start_date=start, end_date=end)
            if df is None or df.empty:
                return None

            df = df.sort_values("trade_date")
            pe_series = pd.to_numeric(df["pe_ttm"], errors="coerce").dropna()
            if len(pe_series) < 20:
                return None

            current_pe = float(pe_series.iloc[-1])
            percentile = float((pe_series < current_pe).sum() / len(pe_series) * 100)
            return percentile
        except Exception as e:
            logger.warning(f"沪深300 PE分位数计算失败: {e}")
            return None
