export interface ChanlunResult {
  etfCode: string;
  etfName: string;
  trendPosition: '上升趋势' | '下跌趋势' | '中枢震荡' | '趋势转折中';
  trendConfidence: number;
  currentPrice: number;
  changePercent: number;
  // 结构分析
  topFractal: boolean;
  bottomFractal: boolean;
  biCount: number;
  biDirection: '向上' | '向下';
  centerRange: [number, number]; // [ZD, ZG]
  segmentDirection: '向上' | '向下';
  // 背驰
  divergenceType: '趋势背驰' | '盘整背驰' | '笔背驰' | '无背驰';
  divergenceStrength: number;
  macdAreaCurrent: number;
  macdAreaPrevious: number;
  // 买卖点
  buySellPoints: Array<{
    type: '一买' | '二买' | '三买' | '一卖' | '二卖' | '三卖';
    price: number;
    confidence: number;
    description: string;
  }>;
  // 多周期共振
  dailyResonance: number;
  min30Resonance: number;
  min5Resonance: number;
  compositeResonance: number;
  recommendation: string;
  // MACD history for charts
  macdHistory: Array<{ date: string; macd: number; signal: number; histogram: number }>;
  priceHistory: Array<{ date: string; price: number }>;
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

export const chanlunMockData: Record<string, ChanlunResult> = {
  '510300': {
    etfCode: '510300',
    etfName: '沪深300ETF',
    trendPosition: '上升趋势',
    trendConfidence: 78,
    currentPrice: 3.924,
    changePercent: 1.23,
    topFractal: false,
    bottomFractal: true,
    biCount: 5,
    biDirection: '向上',
    centerRange: [3.78, 3.89],
    segmentDirection: '向上',
    divergenceType: '无背驰',
    divergenceStrength: 0,
    macdAreaCurrent: 12.5,
    macdAreaPrevious: 11.8,
    buySellPoints: [
      { type: '二买', price: 3.82, confidence: 82, description: '回踩中枢上轨获得支撑' },
      { type: '三买', price: 3.90, confidence: 75, description: '突破中枢后回调不破ZG' },
    ],
    dailyResonance: 85,
    min30Resonance: 72,
    min5Resonance: 60,
    compositeResonance: 72,
    recommendation: '多头格局，回调至中枢上轨附近可关注',
    macdHistory: [
      { date: '1月', macd: 8.2, signal: 6.1, histogram: 2.1 },
      { date: '2月', macd: 10.5, signal: 7.8, histogram: 2.7 },
      { date: '3月', macd: 12.5, signal: 9.5, histogram: 3.0 },
      { date: '4月', macd: 11.8, signal: 10.2, histogram: 1.6 },
      { date: '5月', macd: 12.5, signal: 10.8, histogram: 1.7 },
    ],
    priceHistory: [
      { date: '1月', price: 3.65 },
      { date: '2月', price: 3.72 },
      { date: '3月', price: 3.85 },
      { date: '4月', price: 3.80 },
      { date: '5月', price: 3.92 },
    ],
  },
  '512890': {
    etfCode: '512890',
    etfName: '红利低波ETF',
    trendPosition: '中枢震荡',
    trendConfidence: 65,
    currentPrice: 1.256,
    changePercent: 0.45,
    topFractal: false,
    bottomFractal: false,
    biCount: 7,
    biDirection: '向下',
    centerRange: [1.23, 1.27],
    segmentDirection: '向上',
    divergenceType: '盘整背驰',
    divergenceStrength: 42,
    macdAreaCurrent: 5.2,
    macdAreaPrevious: 7.8,
    buySellPoints: [
      { type: '一买', price: 1.235, confidence: 68, description: '盘整背驰，价格创新低MACD不创新低' },
    ],
    dailyResonance: 55,
    min30Resonance: 60,
    min5Resonance: 45,
    compositeResonance: 53,
    recommendation: '中枢震荡中，等待方向选择',
    macdHistory: [
      { date: '1月', macd: 6.5, signal: 5.2, histogram: 1.3 },
      { date: '2月', macd: 7.8, signal: 6.0, histogram: 1.8 },
      { date: '3月', macd: 6.2, signal: 6.2, histogram: 0.0 },
      { date: '4月', macd: 5.2, signal: 6.0, histogram: -0.8 },
      { date: '5月', macd: 4.8, signal: 5.6, histogram: -0.8 },
    ],
    priceHistory: [
      { date: '1月', price: 1.24 },
      { date: '2月', price: 1.27 },
      { date: '3月', price: 1.25 },
      { date: '4月', price: 1.22 },
      { date: '5月', price: 1.26 },
    ],
  },
  '515290': {
    etfCode: '515290',
    etfName: '银行ETF',
    trendPosition: '上升趋势',
    trendConfidence: 85,
    currentPrice: 1.452,
    changePercent: 2.11,
    topFractal: false,
    bottomFractal: false,
    biCount: 4,
    biDirection: '向上',
    centerRange: [1.38, 1.41],
    segmentDirection: '向上',
    divergenceType: '无背驰',
    divergenceStrength: 0,
    macdAreaCurrent: 18.6,
    macdAreaPrevious: 16.2,
    buySellPoints: [
      { type: '三买', price: 1.42, confidence: 88, description: '离开中枢后强势整理' },
      { type: '二买', price: 1.39, confidence: 80, description: '中枢中轨获得支撑' },
    ],
    dailyResonance: 90,
    min30Resonance: 82,
    min5Resonance: 70,
    compositeResonance: 81,
    recommendation: '强势上涨段，持有为主',
    macdHistory: [
      { date: '1月', macd: 10.2, signal: 8.5, histogram: 1.7 },
      { date: '2月', macd: 13.5, signal: 10.0, histogram: 3.5 },
      { date: '3月', macd: 16.2, signal: 12.4, histogram: 3.8 },
      { date: '4月', macd: 15.8, signal: 13.8, histogram: 2.0 },
      { date: '5月', macd: 18.6, signal: 15.0, histogram: 3.6 },
    ],
    priceHistory: [
      { date: '1月', price: 1.32 },
      { date: '2月', price: 1.36 },
      { date: '3月', price: 1.40 },
      { date: '4月', price: 1.38 },
      { date: '5月', price: 1.45 },
    ],
  },
  '588000': {
    etfCode: '588000',
    etfName: '科创50ETF',
    trendPosition: '下跌趋势',
    trendConfidence: 72,
    currentPrice: 1.085,
    changePercent: -1.45,
    topFractal: true,
    bottomFractal: false,
    biCount: 6,
    biDirection: '向下',
    centerRange: [1.12, 1.16],
    segmentDirection: '向下',
    divergenceType: '趋势背驰',
    divergenceStrength: 65,
    macdAreaCurrent: -8.5,
    macdAreaPrevious: -14.2,
    buySellPoints: [
      { type: '一买', price: 1.08, confidence: 72, description: '趋势背驰，下跌动能减弱' },
      { type: '二卖', price: 1.14, confidence: 68, description: '中枢下轨附近压力' },
    ],
    dailyResonance: 35,
    min30Resonance: 42,
    min5Resonance: 55,
    compositeResonance: 44,
    recommendation: '下跌趋势末端，背驰信号出现，关注企稳机会',
    macdHistory: [
      { date: '1月', macd: -5.2, signal: -3.1, histogram: -2.1 },
      { date: '2月', macd: -8.5, signal: -5.2, histogram: -3.3 },
      { date: '3月', macd: -12.1, signal: -7.8, histogram: -4.3 },
      { date: '4月', macd: -14.2, signal: -10.2, histogram: -4.0 },
      { date: '5月', macd: -8.5, signal: -9.8, histogram: 1.3 },
    ],
    priceHistory: [
      { date: '1月', price: 1.25 },
      { date: '2月', price: 1.18 },
      { date: '3月', price: 1.12 },
      { date: '4月', price: 1.08 },
      { date: '5月', price: 1.09 },
    ],
  },
  '159915': {
    etfCode: '159915',
    etfName: '创业板ETF',
    trendPosition: '趋势转折中',
    trendConfidence: 55,
    currentPrice: 2.156,
    changePercent: -0.32,
    topFractal: false,
    bottomFractal: true,
    biCount: 3,
    biDirection: '向上',
    centerRange: [2.08, 2.18],
    segmentDirection: '向下',
    divergenceType: '笔背驰',
    divergenceStrength: 38,
    macdAreaCurrent: 3.2,
    macdAreaPrevious: -2.5,
    buySellPoints: [
      { type: '一买', price: 2.10, confidence: 62, description: '底分型确立，笔背驰' },
      { type: '二买', price: 2.12, confidence: 58, description: '回踩不创新低' },
    ],
    dailyResonance: 50,
    min30Resonance: 55,
    min5Resonance: 65,
    compositeResonance: 57,
    recommendation: '底部构建中，谨慎观察',
    macdHistory: [
      { date: '1月', macd: -4.2, signal: -2.5, histogram: -1.7 },
      { date: '2月', macd: -6.5, signal: -4.2, histogram: -2.3 },
      { date: '3月', macd: -2.5, signal: -3.8, histogram: 1.3 },
      { date: '4月', macd: 0.8, signal: -2.0, histogram: 2.8 },
      { date: '5月', macd: 3.2, signal: -0.2, histogram: 3.4 },
    ],
    priceHistory: [
      { date: '1月', price: 2.35 },
      { date: '2月', price: 2.22 },
      { date: '3月', price: 2.15 },
      { date: '4月', price: 2.08 },
      { date: '5月', price: 2.16 },
    ],
  },
};

export const dingchangMockData: Record<string, DingChangResult> = {
  '510300': {
    etfCode: '510300',
    etfName: '沪深300ETF',
    compositeScore: 76,
    rating: '持有',
    dimensions: {
      dividendQuality: { score: 78, yield: 2.85, growth: 12.5, stability: 85, continuity: 92 },
      valuationSafety: { score: 72, pb: 1.45, pbPercentile: 35, pe: 14.2, peg: 1.15, spread: 8.5 },
      profitability: { score: 82, roe: 11.2, roic: 9.8, volatility: 18.5, cashCoverage: 105 },
      capitalFlow: { score: 68, insuranceChange: 2.8, etfFlow: 12.5, researchFreq: 85, northbound: 5.2 },
      macroFit: { score: 80, cycleMatch: 75, rateEnv: 82, policy: 88, globalVal: 75 },
    },
    compositeSignal: '维持',
    signalFactors: { trend: 72, insurance: 68, crowding: 45 },
    risks: ['短期涨幅较大，注意回调风险', '外资流向存在不确定性'],
  },
  '512890': {
    etfCode: '512890',
    etfName: '红利低波ETF',
    compositeScore: 88,
    rating: '买入',
    dimensions: {
      dividendQuality: { score: 95, yield: 4.85, growth: 8.2, stability: 92, continuity: 98 },
      valuationSafety: { score: 90, pb: 0.85, pbPercentile: 22, pe: 8.5, peg: 0.95, spread: 15.2 },
      profitability: { score: 75, roe: 10.5, roic: 8.2, volatility: 12.8, cashCoverage: 95 },
      capitalFlow: { score: 85, insuranceChange: 5.2, etfFlow: 18.6, researchFreq: 72, northbound: 3.8 },
      macroFit: { score: 95, cycleMatch: 88, rateEnv: 98, policy: 95, globalVal: 92 },
    },
    compositeSignal: '增持',
    signalFactors: { trend: 85, insurance: 92, crowding: 35 },
    risks: ['低估值修复节奏可能较慢', '利率环境变化可能影响吸引力'],
  },
  '515290': {
    etfCode: '515290',
    etfName: '银行ETF',
    compositeScore: 82,
    rating: '买入',
    dimensions: {
      dividendQuality: { score: 90, yield: 4.52, growth: 6.5, stability: 95, continuity: 96 },
      valuationSafety: { score: 88, pb: 0.68, pbPercentile: 18, pe: 6.2, peg: 0.75, spread: 18.5 },
      profitability: { score: 78, roe: 11.8, roic: 7.5, volatility: 15.2, cashCoverage: 88 },
      capitalFlow: { score: 75, insuranceChange: 3.5, etfFlow: 22.8, researchFreq: 65, northbound: 2.5 },
      macroFit: { score: 80, cycleMatch: 72, rateEnv: 85, policy: 82, globalVal: 78 },
    },
    compositeSignal: '增持',
    signalFactors: { trend: 88, insurance: 75, crowding: 55 },
    risks: ['净息差持续承压', '房地产相关资产质量风险'],
  },
  '588000': {
    etfCode: '588000',
    etfName: '科创50ETF',
    compositeScore: 45,
    rating: '观察',
    dimensions: {
      dividendQuality: { score: 25, yield: 0.52, growth: -15.2, stability: 15, continuity: 10 },
      valuationSafety: { score: 55, pb: 3.85, pbPercentile: 28, pe: 52.5, peg: 1.85, spread: -5.2 },
      profitability: { score: 35, roe: 6.2, roic: 4.5, volatility: 32.5, cashCoverage: 65 },
      capitalFlow: { score: 52, insuranceChange: -1.5, etfFlow: -8.2, researchFreq: 92, northbound: -3.5 },
      macroFit: { score: 58, cycleMatch: 62, rateEnv: 55, policy: 75, globalVal: 48 },
    },
    compositeSignal: '减持',
    signalFactors: { trend: 35, insurance: 28, crowding: 68 },
    risks: ['估值水平仍然偏高', '盈利波动较大', '外资持续流出', '技术迭代风险'],
  },
  '159915': {
    etfCode: '159915',
    etfName: '创业板ETF',
    compositeScore: 52,
    rating: '观察',
    dimensions: {
      dividendQuality: { score: 35, yield: 0.85, growth: -5.2, stability: 25, continuity: 20 },
      valuationSafety: { score: 58, pb: 3.62, pbPercentile: 32, pe: 35.8, peg: 1.55, spread: 2.5 },
      profitability: { score: 48, roe: 9.5, roic: 7.2, volatility: 28.5, cashCoverage: 72 },
      capitalFlow: { score: 55, insuranceChange: 0.8, etfFlow: -2.5, researchFreq: 88, northbound: -1.2 },
      macroFit: { score: 65, cycleMatch: 68, rateEnv: 62, policy: 70, globalVal: 58 },
    },
    compositeSignal: '维持',
    signalFactors: { trend: 45, insurance: 42, crowding: 58 },
    risks: ['估值修复尚需时间', '流动性改善不明显'],
  },
};

export const popularETFs = [
  { code: '510300', name: '沪深300ETF' },
  { code: '512890', name: '红利低波ETF' },
  { code: '515290', name: '银行ETF' },
  { code: '588000', name: '科创50ETF' },
  { code: '159915', name: '创业板ETF' },
];

export const recentAnalyses = [
  { code: '510300', name: '沪深300ETF', date: '2026-04-23', type: '缠论分析' },
  { code: '512890', name: '红利低波ETF', date: '2026-04-22', type: '丁昶评估' },
  { code: '588000', name: '科创50ETF', date: '2026-04-21', type: '综合报告' },
  { code: '515290', name: '银行ETF', date: '2026-04-20', type: '缠论分析' },
  { code: '159915', name: '创业板ETF', date: '2026-04-19', type: '综合报告' },
];
