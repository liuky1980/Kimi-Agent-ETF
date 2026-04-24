"""
宏观周期定位层
==============
基于信用-库存四象限模型对宏观经济周期进行定位，输出战略仓位上限、
缠论信号开关、丁昶风格映射等关键决策参数。

四象限判定逻辑:
    - 信用扩张: 社融增速近3月均值 > 近12月均值 且 M2-M1剪刀差 < 5%
    - 信用收缩: 社融增速近3月均值 < 近12月均值 或 M2-M1剪刀差 > 8%
    - 库存去化: PMI产成品库存 < 48 且 近3月呈下降趋势
    - 库存累积: PMI产成品库存 > 50 或 近3月呈上升趋势

象限与策略映射:
    I_recovery    (复苏期):   扩张+去化 → limit=0.90, chan=true,  growth
    II_overheat   (过热期):   扩张+累积 → limit=0.70, chan=true,  balanced
    III_stagflation(滞胀期):  收缩+去化 → limit=0.40, chan=true,  defensive
    IV_recession  (衰退期):   收缩+累积 → limit=0.20, chan=false, cash

衰退期例外:
    若沪深300 PE分位数 < 10%，仓位上限从 0.20 提升至 0.40，
    但缠论信号仍保持关闭。
"""

import logging
from typing import Any, Dict, List, Literal, Optional

from app.models.fusion_models import MacroResult

logger = logging.getLogger(__name__)

# ────────────────────────────── 默认配置常量 ──────────────────────────────

# 信用状态判定阈值
_DEFAULT_CREDIT_EXPANSION_THRESHOLD: float = 0.0       # 社融增速3月vs12月差值阈值
_DEFAULT_M2_M1_SPREAD_EXPANSION_LIMIT: float = 5.0      # M2-M1扩张上限 (%)
_DEFAULT_M2_M1_SPREAD_CONTRACTION_LIMIT: float = 8.0    # M2-M1收缩下限 (%)

# 库存状态判定阈值
_DEFAULT_PMI_DESTOCKING: float = 48.0   # PMI去库阈值
_DEFAULT_PMI_ACCUMULATION: float = 50.0 # PMI累库阈值

# 衰退期例外
_DEFAULT_RECESSION_EXCEPTION_PE: float = 0.10  # 衰退期例外PE分位 (10%)

# 象限 → 战略仓位上限映射
_QUADRANT_POSITION_LIMITS: Dict[str, float] = {
    "I_recovery": 0.90,
    "II_overheat": 0.70,
    "III_stagflation": 0.40,
    "IV_recession": 0.20,
}

# 象限 → 丁昶风格映射
_QUADRANT_DING_STYLE: Dict[str, str] = {
    "I_recovery": "growth",
    "II_overheat": "balanced",
    "III_stagflation": "defensive",
    "IV_recession": "cash",
}

# 象限 → 中文名称映射
_QUADRANT_NAMES: Dict[str, str] = {
    "I_recovery": "复苏期",
    "II_overheat": "过热期",
    "III_stagflation": "滞胀期",
    "IV_recession": "衰退期",
}

# 象限 → 描述模板
_QUADRANT_DESCRIPTIONS: Dict[str, str] = {
    "I_recovery": "信用扩张+库存去化，经济进入复苏通道，企业融资活跃且库存压力缓解，"
                  "适合积极配置成长型资产，缠论信号全开。",
    "II_overheat": "信用扩张+库存累积，经济过热信号显现，融资旺盛但库存开始积压，"
                   "维持中高仓位但需警惕转折，缠论信号全开。",
    "III_stagflation": "信用收缩+库存去化，经济滞胀特征，融资放缓但库存仍在去化，"
                       "降低仓位至防御水平，缠论信号全开但仓位受限。",
    "IV_recession": "信用收缩+库存累积，经济衰退确认，融资萎缩且库存积压，"
                    "严格控制仓位，关闭缠论信号以左侧交易为主。",
}


class MacroLayerConfig:
    """宏观周期定位层配置 (简化版，完整版在 models/fusion_config.py)

    封装所有用于四象限判定的阈值参数，支持自定义覆盖。

    Attributes
    ----------
    credit_expansion_threshold : float
        社融增速3月vs12月差值阈值，>此值为扩张
    m2_m1_spread_expansion_limit : float
        M2-M1剪刀差扩张上限 (%)
    m2_m1_spread_contraction_limit : float
        M2-M1剪刀差收缩下限 (%)
    pmi_destocking : float
        PMI产成品库存去库阈值
    pmi_accumulation : float
        PMI产成品库存累库阈值
    recession_exception_pe : float
        衰退期例外PE分位阈值
    """

    def __init__(self, **kwargs: Any) -> None:
        self.credit_expansion_threshold: float = kwargs.get(
            "credit_expansion_threshold", _DEFAULT_CREDIT_EXPANSION_THRESHOLD
        )
        self.m2_m1_spread_expansion_limit: float = kwargs.get(
            "m2_m1_spread_expansion_limit", _DEFAULT_M2_M1_SPREAD_EXPANSION_LIMIT
        )
        self.m2_m1_spread_contraction_limit: float = kwargs.get(
            "m2_m1_spread_contraction_limit", _DEFAULT_M2_M1_SPREAD_CONTRACTION_LIMIT
        )
        self.pmi_destocking: float = kwargs.get(
            "pmi_destocking", _DEFAULT_PMI_DESTOCKING
        )
        self.pmi_accumulation: float = kwargs.get(
            "pmi_accumulation", _DEFAULT_PMI_ACCUMULATION
        )
        self.recession_exception_pe: float = kwargs.get(
            "recession_exception_pe", _DEFAULT_RECESSION_EXCEPTION_PE
        )


class MacroLayer:
    """宏观周期定位层

    基于信用-库存双周期四象限模型，对宏观经济周期进行定位，
    输出战略仓位上限、缠论开关、丁昶风格等决策参数。

    Parameters
    ----------
    config : MacroLayerConfig, optional
        自定义配置对象，覆盖默认阈值
    fetcher : Any, optional
        外部数据获取器（如 MacroDataFetcher），为 None 时内部创建

    Examples
    --------
    >>> layer = MacroLayer()
    >>> result = layer.analyze()
    >>> print(result.quadrant_name, result.position_limit)
    复苏期 0.9
    """

    def __init__(
        self,
        config: Optional[MacroLayerConfig] = None,
        fetcher: Optional[Any] = None,
    ) -> None:
        self.config = config or MacroLayerConfig()
        self.fetcher = fetcher
        logger.info("MacroLayer: 宏观周期定位层初始化完成")

    # ────────────────────────────── 核心判定方法 ──────────────────────────────

    def calculate_credit_status(
        self,
        afre_yoy_3m: float,
        afre_yoy_12m: float,
        m2_m1_spread: float,
    ) -> Literal["expansion", "contraction"]:
        """计算信用周期状态

        判定规则:
            信用扩张 = 社融增速近3月均值 > 近12月均值 且 M2-M1剪刀差 < 5%
            信用收缩 = 社融增速近3月均值 < 近12月均值 或 M2-M1剪刀差 > 8%
            中间状态 → 默认收缩（保守处理）

        Parameters
        ----------
        afre_yoy_3m : float
            社融增速近3月均值 (%)
        afre_yoy_12m : float
            社融增速近12月均值 (%)
        m2_m1_spread : float
            M2-M1剪刀差 (%)

        Returns
        -------
        str
            "expansion" (扩张) 或 "contraction" (收缩)
        """
        afre_diff = afre_yoy_3m - afre_yoy_12m
        spread_limit_exp = self.config.m2_m1_spread_expansion_limit
        spread_limit_con = self.config.m2_m1_spread_contraction_limit

        # 扩张条件: 社融增速回升 且 剪刀差收窄
        is_expansion = (afre_diff > self.config.credit_expansion_threshold) and (
            m2_m1_spread < spread_limit_exp
        )

        # 收缩条件: 社融增速回落 或 剪刀差扩大
        is_contraction = (afre_diff <= self.config.credit_expansion_threshold) or (
            m2_m1_spread > spread_limit_con
        )

        if is_expansion:
            logger.debug(f"信用状态判定: 扩张 (afre_diff={afre_diff:+.2f}, spread={m2_m1_spread}%)")
            return "expansion"
        else:
            # 中间状态默认收缩（保守）
            logger.debug(f"信用状态判定: 收缩 (afre_diff={afre_diff:+.2f}, spread={m2_m1_spread}%)")
            return "contraction"

    def calculate_inventory_status(
        self,
        pmi_inventory: float,
        pmi_inventory_trend: List[float],
    ) -> Literal["destocking", "accumulation"]:
        """计算库存周期状态

        判定规则:
            库存去化 = PMI产成品库存 < 48 且 近3月呈下降趋势
            库存累积 = PMI产成品库存 > 50 或 近3月呈上升趋势
            中间状态 → 默认去化（保守偏积极）

        Parameters
        ----------
        pmi_inventory : float
            PMI产成品库存最新值
        pmi_inventory_trend : list[float]
            PMI产成品库存近3月序列（时间升序）

        Returns
        -------
        str
            "destocking" (去化) 或 "accumulation" (累积)
        """
        # 计算趋势: 最近一个月 vs 前一个月
        is_trend_down = False
        is_trend_up = False

        if len(pmi_inventory_trend) >= 2:
            # 近3月趋势判断：最后值 < 初始值 = 下降
            is_trend_down = pmi_inventory_trend[-1] < pmi_inventory_trend[0]
            is_trend_up = pmi_inventory_trend[-1] > pmi_inventory_trend[0]
        elif len(pmi_inventory_trend) == 1:
            # 单点数据无法判断趋势，用绝对水平
            is_trend_down = pmi_inventory < 50.0
            is_trend_up = pmi_inventory > 50.0

        # 去化条件: PMI < 48 且 趋势下降
        is_destocking = (pmi_inventory < self.config.pmi_destocking) and is_trend_down

        # 累积条件: PMI > 50 或 趋势上升
        is_accumulation = (pmi_inventory > self.config.pmi_accumulation) or is_trend_up

        if is_destocking:
            logger.debug(
                f"库存状态判定: 去化 (PMI={pmi_inventory}, trend={pmi_inventory_trend})"
            )
            return "destocking"
        elif is_accumulation:
            logger.debug(
                f"库存状态判定: 累积 (PMI={pmi_inventory}, trend={pmi_inventory_trend})"
            )
            return "accumulation"
        else:
            # 中间状态: 48-50之间且趋势不明显 → 默认去化（复苏倾向）
            logger.debug(
                f"库存状态判定: 中间状态 → 默认去化 (PMI={pmi_inventory}, trend={pmi_inventory_trend})"
            )
            return "destocking"

    def get_quadrant(
        self, credit: Literal["expansion", "contraction"],
        inventory: Literal["destocking", "accumulation"]
    ) -> str:
        """根据信用和库存状态判定四象限

        Parameters
        ----------
        credit : str
            信用周期状态: "expansion" / "contraction"
        inventory : str
            库存周期状态: "destocking" / "accumulation"

        Returns
        -------
        str
            象限编码: I_recovery / II_overheat / III_stagflation / IV_recession
        """
        if credit == "expansion" and inventory == "destocking":
            return "I_recovery"
        elif credit == "expansion" and inventory == "accumulation":
            return "II_overheat"
        elif credit == "contraction" and inventory == "destocking":
            return "III_stagflation"
        else:
            return "IV_recession"

    # ────────────────────────────── 象限参数查询 ──────────────────────────────

    def get_position_limit(self, quadrant: str) -> float:
        """获取指定象限的战略仓位上限

        Parameters
        ----------
        quadrant : str
            象限编码

        Returns
        -------
        float
            仓位上限 [0.2, 0.9]
        """
        return _QUADRANT_POSITION_LIMITS.get(quadrant, 0.50)

    def is_chanlun_enabled(self, quadrant: str) -> bool:
        """判断指定象限是否启用缠论信号

        衰退期关闭缠论，其他象限均启用。

        Parameters
        ----------
        quadrant : str
            象限编码

        Returns
        -------
        bool
            True = 缠论信号参与决策, False = 屏蔽缠论
        """
        return quadrant != "IV_recession"

    def _get_ding_style(self, quadrant: str) -> str:
        """获取指定象限的丁昶风格映射

        Parameters
        ----------
        quadrant : str
            象限编码

        Returns
        -------
        str
            growth / balanced / defensive / cash
        """
        return _QUADRANT_DING_STYLE.get(quadrant, "balanced")

    def _get_quadrant_name(self, quadrant: str) -> str:
        """获取象限中文名称

        Parameters
        ----------
        quadrant : str
            象限编码

        Returns
        -------
        str
            象限中文名称
        """
        return _QUADRANT_NAMES.get(quadrant, "未知")

    # ────────────────────────────── 衰退期例外处理 ──────────────────────────────

    def _apply_recession_exception(
        self, quadrant: str, position_limit: float, pe_percentile: float
    ) -> tuple[float, bool]:
        """应用衰退期例外规则

        衰退期(IV_recession)中，若沪深300 PE分位数 < 10%，
        仓位上限从 0.20 提升至 0.40（但缠论仍关闭）。

        Parameters
        ----------
        quadrant : str
            当前象限编码
        position_limit : float
            当前仓位上限
        pe_percentile : float
            沪深300 PE分位数 (0-100)

        Returns
        -------
        tuple[float, bool]
            (调整后仓位上限, 是否触发了例外)
        """
        if quadrant != "IV_recession":
            return position_limit, False

        pe_threshold = self.config.recession_exception_pe * 100  # 0.10 → 10%

        if pe_percentile < pe_threshold:
            new_limit = 0.40
            logger.info(
                f"衰退期例外触发: PE分位数={pe_percentile:.1f}% < {pe_threshold:.1f}%, "
                f"仓位上限从 {position_limit} 提升至 {new_limit}"
            )
            return new_limit, True

        return position_limit, False

    # ────────────────────────────── 数据获取 ──────────────────────────────

    def _fetch_macro_data(self) -> Dict[str, Any]:
        """获取宏观数据（内部自动创建 fetcher）

        若外部未传入 fetcher，内部延迟创建 MacroDataFetcher。
        任何异常都捕获并返回 fallback 值。

        Returns
        -------
        dict
            包含所有宏观指标的字典
        """
        try:
            if self.fetcher is None:
                from app.data.macro_fetcher import MacroDataFetcher
                self.fetcher = MacroDataFetcher()
            return self.fetcher.fetch_all()
        except Exception as e:
            logger.error(f"宏观数据获取异常: {e}，使用硬编码默认值")
            return {
                "afre_yoy_3m": 9.0,
                "afre_yoy_12m": 9.5,
                "m2_m1_spread": 6.0,
                "pmi_inventory": 48.0,
                "pmi_inventory_trend": [48.5, 48.2, 47.8],
                "pe_percentile": 50.0,
                "data_source": "emergency_fallback",
            }

    # ────────────────────────────── 主分析入口 ──────────────────────────────

    def analyze(self, macro_data: Optional[Dict[str, Any]] = None) -> MacroResult:
        """执行宏观周期分析

        完整的四象限分析流程:
        1. 获取宏观数据（或直接使用传入的数据）
        2. 判定信用周期状态
        3. 判定库存周期状态
        4. 确定四象限
        5. 查询象限参数（仓位上限、缠论开关等）
        6. 检查衰退期例外

        Parameters
        ----------
        macro_data : dict, optional
            外部传入的宏观数据，为 None 时内部自动获取

        Returns
        -------
        MacroResult
            宏观周期分析结果，永不抛异常
        """
        logger.info("MacroLayer: 开始宏观周期分析...")

        try:
            # 1. 获取数据
            if macro_data is None:
                data = self._fetch_macro_data()
            else:
                data = macro_data
                data.setdefault("data_source", "user_provided")

            # 2. 提取指标（带默认值保护）
            afre_yoy_3m = float(data.get("afre_yoy_3m", 9.0))
            afre_yoy_12m = float(data.get("afre_yoy_12m", 9.5))
            m2_m1_spread = float(data.get("m2_m1_spread", 6.0))
            pmi_inventory = float(data.get("pmi_inventory", 48.0))
            pmi_trend_raw = data.get("pmi_inventory_trend", [48.5, 48.2, 47.8])
            pmi_inventory_trend = [float(v) for v in pmi_trend_raw] if pmi_trend_raw else [48.0, 47.5, 47.0]
            pe_percentile = float(data.get("pe_percentile", 50.0))
            data_source = data.get("data_source", "unknown")

            logger.info(
                f"宏观数据: 社融3m={afre_yoy_3m}%, 社融12m={afre_yoy_12m}%, "
                f"M2-M1={m2_m1_spread}%, PMI库存={pmi_inventory}, "
                f"PE分位={pe_percentile}%, 来源={data_source}"
            )

            # 3. 判定信用周期
            credit = self.calculate_credit_status(afre_yoy_3m, afre_yoy_12m, m2_m1_spread)

            # 4. 判定库存周期
            inventory = self.calculate_inventory_status(pmi_inventory, pmi_inventory_trend)

            # 5. 确定象限
            quadrant = self.get_quadrant(credit, inventory)
            quadrant_name = self._get_quadrant_name(quadrant)

            logger.info(f"象限判定: {quadrant} ({quadrant_name}), 信用={credit}, 库存={inventory}")

            # 6. 查询象限参数
            position_limit = self.get_position_limit(quadrant)
            chan_enabled = self.is_chanlun_enabled(quadrant)
            ding_style = self._get_ding_style(quadrant)
            description = _QUADRANT_DESCRIPTIONS.get(quadrant, "")

            # 7. 衰退期例外检查
            position_limit, exception_applied = self._apply_recession_exception(
                quadrant, position_limit, pe_percentile
            )

            if exception_applied:
                description += " [衰退期例外已触发: PE极度低估，仓位上限提升]"

            # 8. 构建结果
            result = MacroResult(
                quadrant=quadrant,
                quadrant_name=quadrant_name,
                position_limit=position_limit,
                chan_enabled=chan_enabled,
                ding_style=ding_style,
                credit_status=credit,
                inventory_status=inventory,
                description=description,
                exception_applied=exception_applied,
            )

            logger.info(
                f"宏观分析完成: {quadrant_name}, 仓位上限={position_limit}, "
                f"缠论={'开' if chan_enabled else '关'}, 丁昶风格={ding_style}"
            )
            return result

        except Exception as e:
            # 绝对安全网: 任何异常都不抛到上层
            logger.error(f"宏观分析过程中发生异常: {e}，返回保守默认结果")
            return self._get_safe_default_result()

    def _get_safe_default_result(self) -> MacroResult:
        """获取安全的默认结果（应急用）

        当分析流程发生不可预期异常时返回保守配置。

        Returns
        -------
        MacroResult
            衰退期保守配置（最低仓位、关闭缠论）
        """
        return MacroResult(
            quadrant="IV_recession",
            quadrant_name="衰退期",
            position_limit=0.20,
            chan_enabled=False,
            ding_style="cash",
            credit_status="contraction",
            inventory_status="accumulation",
            description="分析过程异常，启用保守默认配置。建议等待数据恢复后再做决策。",
            exception_applied=False,
        )
