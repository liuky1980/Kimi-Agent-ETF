"""
丁昶投资框架 Pydantic 模型
=========================
定义丁昶五维评分体系的请求/响应数据结构，
包括股息质量、估值安全、盈利质地、资金驱动、宏观适配五个维度。
"""

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


# ────────────────────────────── 单维度评分模型 ──────────────────────────────

class DividendScore(BaseModel):
    """股息质量评分（权重30%）"""
    score: float = Field(..., ge=0.0, le=100.0, description="维度得分 0~100")
    dividend_yield: float = Field(0.0, description="股息率 (%)")
    yield_5y_avg: float = Field(0.0, description="5年平均股息率 (%)")
    payout_consistency: float = Field(0.0, ge=0.0, le=1.0, description="分红持续性评分")
    distribution_quality: float = Field(0.0, ge=0.0, le=1.0, description="分红质量评分")
    capital_return_efficiency: float = Field(0.0, ge=0.0, le=1.0, description="资本回报效率 (非分红型ETF替代指标)")
    sub_scores: Dict[str, float] = Field(default_factory=dict, description="子项得分明细")
    description: str = Field("", description="维度评价说明")


class ValuationScore(BaseModel):
    """估值安全评分（权重25%）"""
    score: float = Field(..., ge=0.0, le=100.0, description="维度得分 0~100")
    pe_ttm: float = Field(0.0, description="当前PE-TTM")
    pe_percentile: float = Field(0.0, ge=0.0, le=100.0, description="PE历史百分位")
    pb: float = Field(0.0, description="当前PB")
    pb_percentile: float = Field(0.0, ge=0.0, le=100.0, description="PB历史百分位")
    peg: float = Field(0.0, description="PEG比率")
    spread_risk_free: float = Field(0.0, description="股息率-无风险利率利差")
    nav_discount_premium: float = Field(0.0, description="净值折溢价率 (%)")
    valuation_method: str = Field("", description="适用的估值方法")
    sub_scores: Dict[str, float] = Field(default_factory=dict, description="子项得分明细")
    description: str = Field("", description="维度评价说明")


class ProfitabilityScore(BaseModel):
    """盈利质地评分（权重20%）"""
    score: float = Field(..., ge=0.0, le=100.0, description="维度得分 0~100")
    roe: float = Field(0.0, description="净资产收益率 ROE (%)")
    roic: float = Field(0.0, description="投入资本回报率 ROIC (%)")
    earnings_stability: float = Field(0.0, ge=0.0, le=1.0, description="盈利稳定性评分")
    earnings_growth_3y: float = Field(0.0, description="近3年盈利复合增长率 (%)")
    revenue_growth_3y: float = Field(0.0, description="近3年营收复合增长率 (%)")
    cash_flow_quality: float = Field(0.0, ge=0.0, le=1.0, description="现金流质量评分")
    sub_scores: Dict[str, float] = Field(default_factory=dict, description="子项得分明细")
    description: str = Field("", description="维度评价说明")


class CapitalFlowScore(BaseModel):
    """资金驱动评分（权重15%）"""
    score: float = Field(..., ge=0.0, le=100.0, description="维度得分 0~100")
    aum: float = Field(0.0, description="最新资产管理规模 (亿元)")
    aum_growth_3m: float = Field(0.0, description="近3月AUM增长率 (%)")
    aum_growth_1y: float = Field(0.0, description="近1年AUM增长率 (%)")
    volume_trend: float = Field(0.0, ge=-1.0, le=1.0, description="成交量趋势得分")
    institutional_ratio: float = Field(0.0, ge=0.0, le=1.0, description="机构持仓占比")
    institutional_change: float = Field(0.0, description="机构持仓变化 (%)")
    fund_flow_20d: float = Field(0.0, description="近20日资金流向")
    sub_scores: Dict[str, float] = Field(default_factory=dict, description="子项得分明细")
    description: str = Field("", description="维度评价说明")


class MacroScore(BaseModel):
    """宏观适配评分（权重10%）"""
    score: float = Field(..., ge=0.0, le=100.0, description="维度得分 0~100")
    cycle_position: str = Field("", description="周期定位")
    cycle_fit_score: float = Field(0.0, ge=0.0, le=1.0, description="周期适配得分")
    rate_environment_fit: float = Field(0.0, ge=0.0, le=1.0, description="利率环境适配度")
    policy_support: float = Field(0.0, ge=0.0, le=1.0, description="政策支持度")
    global_comparison: float = Field(0.0, ge=0.0, le=1.0, description="全球估值比较优势")
    macro_risk_score: float = Field(0.0, ge=0.0, le=1.0, description="宏观风险评分")
    sub_scores: Dict[str, float] = Field(default_factory=dict, description="子项得分明细")
    description: str = Field("", description="维度评价说明")


# ────────────────────────────── 综合结果模型 ──────────────────────────────

class DingChangDimensions(BaseModel):
    """五维评分明细"""
    dividend: DividendScore = Field(..., description="股息质量 (30%)")
    valuation: ValuationScore = Field(..., description="估值安全 (25%)")
    profitability: ProfitabilityScore = Field(..., description="盈利质地 (20%)")
    capital_flow: CapitalFlowScore = Field(..., description="资金驱动 (15%)")
    macro: MacroScore = Field(..., description="宏观适配 (10%)")


class DingChangResult(BaseModel):
    """丁昶五维评分完整结果"""
    # 基础信息
    etf_code: str = Field(..., description="ETF代码")
    etf_name: str = Field("", description="ETF名称")
    analysis_time: datetime = Field(default_factory=datetime.now, description="分析时间")

    # 综合评分
    composite_score: float = Field(..., ge=0.0, le=100.0, description="综合评分 0~100")
    rating: str = Field(..., description="评级: 买入/持有/观察/回避")

    # 五维明细
    dimensions: DingChangDimensions = Field(..., description="五维评分明细")

    # 权重配置（记录实际使用的权重）
    weights: Dict[str, float] = Field(default_factory=lambda: {
        "dividend": 0.30,
        "valuation": 0.25,
        "profitability": 0.20,
        "capital_flow": 0.15,
        "macro": 0.10,
    }, description="各维度权重")

    # 综合信号
    composite_signal: str = Field("", description="综合信号方向: bullish/bearish/neutral")
    signal_strength: float = Field(0.0, ge=0.0, le=1.0, description="信号强度")
    signal_factors: Dict[str, str] = Field(default_factory=dict, description="信号因子说明")

    # 风险提示
    risks: List[str] = Field(default_factory=list, description="风险因素列表")
    opportunities: List[str] = Field(default_factory=list, description="机会因素列表")

    # 建议
    recommendation: str = Field("", description="丁昶框架综合建议")
    summary: str = Field("", description="分析摘要")

    # 对比基准
    benchmark_comparison: Optional[str] = Field(None, description="相对基准表现")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


# ────────────────────────────── API 请求/响应模型 ──────────────────────────────

class ETFAnalysisRequest(BaseModel):
    """ETF分析请求"""
    etf_code: str = Field(..., min_length=1, description="ETF代码，如 '510300'")
    timeframe: str = Field("daily", description="主分析周期")
    include_minute: bool = Field(True, description="是否包含分钟级分析")
    analysis_depth: str = Field("full", description="分析深度: full-完整, basic-基础")

    class Config:
        json_schema_extra = {
            "example": {
                "etf_code": "510300",
                "timeframe": "daily",
                "include_minute": True,
                "analysis_depth": "full"
            }
        }


class ETFAnalysisResponse(BaseModel):
    """ETF双框架分析响应"""
    success: bool = Field(True, description="分析是否成功")
    message: str = Field("", description="状态消息")

    # 双框架结果
    chanlun: Optional[Dict] = Field(None, description="缠论分析结果")
    dingchang: Optional[Dict] = Field(None, description="丁昶五维评分结果")

    # 综合分析
    summary: str = Field("", description="双框架综合摘要")
    action: str = Field("", description="综合行动建议: 强烈关注/关注/观望/回避")
    dual_signal: str = Field("", description="双框架信号对齐: aligned/mixed/conflicting")
    confidence: float = Field(0.0, ge=0.0, le=1.0, description="综合置信度")

    # 元数据
    processing_time_ms: int = Field(0, description="处理耗时(ms)")
    data_source: str = Field("akshare", description="数据来源")
    analysis_time: datetime = Field(default_factory=datetime.now, description="分析完成时间")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ETFSimpleInfo(BaseModel):
    """ETF基本信息"""
    code: str = Field(..., description="ETF代码")
    name: str = Field("", description="ETF名称")
    price: float = Field(0.0, description="最新价格")
    change_pct: float = Field(0.0, description="涨跌幅(%)")
    volume: float = Field(0.0, description="成交量")
    category: str = Field("", description="ETF类别")


class ETFListResponse(BaseModel):
    """ETF列表响应"""
    count: int = Field(0, description="总数")
    etfs: List[ETFSimpleInfo] = Field(default_factory=list, description="ETF列表")
    update_time: datetime = Field(default_factory=datetime.now, description="更新时间")
