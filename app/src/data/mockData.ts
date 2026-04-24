export interface ChanlunResult {
  etfCode: string;
  etfName: string;
  trendPosition: '上升趋势' | '下跌趋势' | '中枢震荡' | '趋势转折中';
  trendConfidence: number;
  currentPrice: number;
  changePercent: number;
  topFractal: boolean;
  bottomFractal: boolean;
  biCount: number;
  biDirection: '向上' | '向下';
  centerRange: [number, number]; // [ZD, ZG]
  segmentDirection: '向上' | '向下';
  divergenceType: '趋势背驰' | '盘整背驰' | '笔背驰' | '无背驰';
  divergenceStrength: number;
  macdAreaCurrent: number;
  macdAreaPrevious: number;
  buySellPoints: Array<{
    type: '一买' | '二买' | '三买' | '一卖' | '二卖' | '三卖';
    price: number;
    confidence: number;
    description: string;
  }>;
  dailyResonance: number;
  fivedayResonance: number;
  hourlyResonance: number;
  compositeResonance: number;
  recommendation: string;
  macdHistory: Array<{ date: string; macd: number; signal: number; histogram: number }>;
  priceHistory: Array<{ date: string; close: number; open?: number; high?: number; low?: number; volume?: number }>;
}

export interface DingChangResult {
  etfCode: string;
  etfName: string;
  compositeScore: number;
  rating: '买入' | '持有' | '观察' | '回避';
  dimensions: {
    dividendQuality: { score: number; yield: number; growth: number; stability: number; continuity: number };
    valuationSafety: { score: number; pb: number; pbPercentile: number; pe: number; peg: number; spread: number };
    profitability: { score: number; roe: number; roic: number; volatility: number; cashCoverage: number };
    capitalFlow: { score: number; insuranceChange: number; etfFlow: number; researchFreq: number; northbound: number };
    macroFit: { score: number; cycleMatch: number; rateEnv: number; policy: number; globalVal: number };
  };
  compositeSignal: '增持' | '维持' | '减持';
  signalFactors: { trend: number; insurance: number; crowding: number };
  risks: string[];
}

// 空的初始数组，数据将从API动态获取
export const popularETFs: { code: string; name: string }[] = [];
export const recentAnalyses: { code: string; name: string; date: string; type: string }[] = [];
