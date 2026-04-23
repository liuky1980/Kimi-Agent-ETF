"""
丁昶投资框架分析模块
====================
提供完整的五维评分体系功能，包括：
- 股息质量评分 (dividend) - 30%
- 估值安全评分 (valuation) - 25%
- 盈利质地评分 (profitability) - 20%
- 资金驱动评分 (capital_flow) - 15%
- 宏观适配评分 (macro) - 10%
- 综合评分引擎 (engine)
"""

from app.dingchang.engine import DingChangEngine
from app.dingchang.dividend import DividendQuality
from app.dingchang.valuation import ValuationSafety
from app.dingchang.profitability import ProfitabilityQuality
from app.dingchang.capital_flow import CapitalFlow
from app.dingchang.macro import MacroAdaptation

__all__ = [
    "DingChangEngine",
    "DividendQuality",
    "ValuationSafety",
    "ProfitabilityQuality",
    "CapitalFlow",
    "MacroAdaptation",
]
