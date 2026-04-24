import { useState, useMemo, useEffect, useCallback } from 'react';
import { api } from '@/services/api';
import { dataCache } from '@/services/dataCache';
import type { DingChangResult } from '@/data/mockData';
import DingChangPanel from '@/components/DingChangPanel';
import {
  Search,
  BarChart3,
  Award,
  TrendingUp,
  TrendingDown,
  Minus,
  AlertTriangle,
  Loader2,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';

interface DingChangAnalysisProps {
  initialCode?: string;
}

// 后端数据可能为snake_case，映射到前端camelCase
function normalizeDingChang(raw: Record<string, unknown>): DingChangResult | null {
  if (!raw) return null;
  const get = (k: string) => (raw[k] !== undefined ? raw[k] : raw[k.replace(/[A-Z]/g, m => '_' + m.toLowerCase())]);

  const dimsRaw = get('dimensions') as Record<string, unknown> || {};

  // 维度键名映射：前端 camelCase → 后端实际字段名
  const dimKeyMap: Record<string, string> = {
    dividendQuality: 'dividend',
    valuationSafety: 'valuation',
    profitability: 'profitability',
    capitalFlow: 'capital_flow',
    macroFit: 'macro',
  };

  const getDim = (k: string) => {
    const mappedKey = dimKeyMap[k] || k;
    return (dimsRaw[mappedKey] || dimsRaw[mappedKey.replace(/[A-Z]/g, m => '_' + m.toLowerCase())]) as Record<string, number> | undefined;
  };

  const getSubDim = (dimKey: string, subKey: string): number => {
    const dim = getDim(dimKey);
    if (!dim) return 0;
    return Number(dim[subKey] !== undefined ? dim[subKey] : dim[subKey.replace(/[A-Z]/g, m => '_' + m.toLowerCase())]) || 0;
  };

  const result: DingChangResult = {
    etfCode: (get('etfCode') as string) || '',
    etfName: '', // 去除中文名称显示
    compositeScore: Number(get('compositeScore')) || 0,
    rating: (get('rating') as DingChangResult['rating']) || '观察',
    dimensions: {
      dividendQuality: {
        score: getSubDim('dividendQuality', 'score'),
        yield: getSubDim('dividendQuality', 'yield'),
        growth: getSubDim('dividendQuality', 'growth'),
        stability: getSubDim('dividendQuality', 'stability'),
        continuity: getSubDim('dividendQuality', 'continuity'),
      },
      valuationSafety: {
        score: getSubDim('valuationSafety', 'score'),
        pb: getSubDim('valuationSafety', 'pb'),
        pbPercentile: getSubDim('valuationSafety', 'pbPercentile'),
        pe: getSubDim('valuationSafety', 'pe'),
        peg: getSubDim('valuationSafety', 'peg'),
        spread: getSubDim('valuationSafety', 'spread'),
      },
      profitability: {
        score: getSubDim('profitability', 'score'),
        roe: getSubDim('profitability', 'roe'),
        roic: getSubDim('profitability', 'roic'),
        volatility: getSubDim('profitability', 'volatility'),
        cashCoverage: getSubDim('profitability', 'cashCoverage'),
      },
      capitalFlow: {
        score: getSubDim('capitalFlow', 'score'),
        insuranceChange: getSubDim('capitalFlow', 'insuranceChange'),
        etfFlow: getSubDim('capitalFlow', 'etfFlow'),
        researchFreq: getSubDim('capitalFlow', 'researchFreq'),
        northbound: getSubDim('capitalFlow', 'northbound'),
      },
      macroFit: {
        score: getSubDim('macroFit', 'score'),
        cycleMatch: getSubDim('macroFit', 'cycleMatch'),
        rateEnv: getSubDim('macroFit', 'rateEnv'),
        policy: getSubDim('macroFit', 'policy'),
        globalVal: getSubDim('macroFit', 'globalVal'),
      },
    },
    compositeSignal: (get('compositeSignal') as DingChangResult['compositeSignal']) || '维持',
    signalFactors: (get('signalFactors') as DingChangResult['signalFactors']) || { trend: 0, insurance: 0, crowding: 0 },
    risks: (get('risks') as string[]) || [],
  };
  return result;
}

export default function DingChangAnalysis({ initialCode }: DingChangAnalysisProps) {
  const [searchCode, setSearchCode] = useState(initialCode || '');
  const [selectedCode, setSelectedCode] = useState(initialCode || '');
  const [cacheWarning, setCacheWarning] = useState<string>('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string>('');
  const [dataSource, setDataSource] = useState<string>('');
  const [analysisTime, setAnalysisTime] = useState<string>('');
  const [etfSelectorCodes, setEtfSelectorCodes] = useState<string[]>([]);
  const [allScores, setAllScores] = useState<Array<{ code: string; score: number; rating: string }>>([]);

  // 从缓存获取已分析过的ETF代码列表
  useEffect(() => {
    const all = dataCache.getAll();
    const codes = all.map(item => item.code);
    setEtfSelectorCodes(codes);

    // 收集所有缓存中的评分数据用于对比
    const scores: Array<{ code: string; score: number; rating: string }> = [];
    for (const item of all) {
      if (item.data?.dingchang) {
        const dc = normalizeDingChang(item.data.dingchang as Record<string, unknown>);
        if (dc) {
          scores.push({ code: item.code, score: dc.compositeScore, rating: dc.rating });
        }
      }
    }
    setAllScores(scores);
  }, []);

  // 监听缓存变化
  useEffect(() => {
    const unsubscribe = dataCache.subscribe((pool) => {
      const codes = pool.map(item => item.code);
      setEtfSelectorCodes(codes);
      const scores: Array<{ code: string; score: number; rating: string }> = [];
      for (const item of pool) {
        if (item.data?.dingchang) {
          const dc = normalizeDingChang(item.data.dingchang as Record<string, unknown>);
          if (dc) {
            scores.push({ code: item.code, score: dc.compositeScore, rating: dc.rating });
          }
        }
      }
      setAllScores(scores);
    });
    return unsubscribe;
  }, []);

  useEffect(() => {
    if (initialCode) {
      setSearchCode(initialCode);
      setSelectedCode(initialCode);
      fetchData(initialCode);
    }
  }, [initialCode]);

  const fetchData = useCallback(async (code: string) => {
    if (!code) return;
    setIsLoading(true);
    setError('');
    setCacheWarning('');

    try {
      // 先检查缓存
      const cached = dataCache.get(code);
      let dcRaw = cached?.data?.dingchang as Record<string, unknown> | undefined;

      // 如果缓存中没有，调用API
      if (!dcRaw) {
        const result = await api.getDingChangAnalysis(code);
        dcRaw = result;
        setDataSource((result.data_source as string) || '');
        setAnalysisTime((result.analysis_time as string) || '');

        // 存入缓存
        if (dcRaw) dataCache.updateData(code, 'dingchang', dcRaw);

        const existing = dataCache.get(code);
        if (existing) {
          dataCache.updateStatus(code, 'ready');
        } else {
          dataCache.add({
            code,
            name: code,
            source: (result.data_source as string) || 'api',
            updateTime: (result.analysis_time as string) || new Date().toLocaleString(),
            status: 'ready',
          });
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '获取数据失败');
      if (!dataCache.has(code)) {
        setCacheWarning('该标的暂无数据，请先在首页搜索分析');
      }
    } finally {
      setIsLoading(false);
    }
  }, []);

  // 从缓存获取归一化后的数据
  const data = useMemo<DingChangResult | null>(() => {
    const cached = dataCache.get(selectedCode);
    if (cached?.data?.dingchang) {
      return normalizeDingChang(cached.data.dingchang as Record<string, unknown>);
    }
    return null;
  }, [selectedCode, isLoading]);

  const checkCache = (code: string) => {
    if (!dataCache.has(code)) {
      setCacheWarning('该标的暂无缓存数据，请先在首页搜索');
    } else {
      setCacheWarning('');
    }
  };

  const handleSearch = () => {
    const code = searchCode.trim();
    if (code) {
      setSelectedCode(code);
      setCacheWarning('');
      fetchData(code);
    }
  };

  const handleSelectCode = (code: string) => {
    setSelectedCode(code);
    setSearchCode(code);
    checkCache(code);
    fetchData(code);
  };

  const comparisonData = useMemo(() => {
    return allScores.sort((a, b) => b.score - a.score);
  }, [allScores]);

  const getBarColor = (score: number) => {
    if (score >= 80) return '#10b981';
    if (score >= 60) return '#3b82f6';
    if (score >= 40) return '#f59e0b';
    return '#ef4444';
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-sky-500/15">
            <BarChart3 className="h-5 w-5 text-sky-400" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-slate-100">丁昶分析框架</h1>
            <p className="text-xs text-slate-500">Ding Chang Analysis Framework - 五维评分 · 价值投资</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-slate-500" />
            <input
              type="text"
              placeholder="ETF代码"
              value={searchCode}
              onChange={(e) => setSearchCode(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              className="w-32 rounded-lg border border-slate-700 bg-slate-800/80 py-1.5 pl-8 pr-3 text-sm text-slate-200 placeholder:text-slate-500 focus:border-sky-500/50 focus:outline-none focus:ring-1 focus:ring-sky-500/30"
            />
          </div>
          <button
            onClick={handleSearch}
            className="rounded-lg bg-sky-500/15 border border-sky-500/30 px-3 py-1.5 text-xs font-medium text-sky-400 hover:bg-sky-500/25 transition-colors"
          >
            查询
          </button>
        </div>
      </div>

      {/* ETF Selector */}
      {etfSelectorCodes.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {etfSelectorCodes.map((code) => {
            const isActive = selectedCode === code;
            const scoreEntry = allScores.find(s => s.code === code);
            const ratingBuy = scoreEntry?.rating === '买入';
            const ratingAvoid = scoreEntry?.rating === '回避';
            return (
              <button
                key={code}
                onClick={() => handleSelectCode(code)}
                className={cn(
                  'flex items-center gap-1.5 rounded-lg border px-3 py-2 text-sm transition-all',
                  isActive
                    ? 'border-sky-500/40 bg-sky-500/10 text-sky-400'
                    : 'border-slate-800 bg-slate-900/60 text-slate-400 hover:border-slate-700 hover:text-slate-300'
                )}
              >
                {/* 只显示代码 */}
                <span className="font-mono text-xs">{code}</span>
                {ratingBuy && <TrendingUp className="h-3 w-3 text-emerald-400" />}
                {ratingAvoid && <TrendingDown className="h-3 w-3 text-rose-400" />}
                {!ratingBuy && !ratingAvoid && scoreEntry && <Minus className="h-3 w-3 text-amber-400" />}
              </button>
            );
          })}
        </div>
      )}

      {/* Cache Warning */}
      {cacheWarning && (
        <div className="rounded-lg border border-amber-500/20 bg-amber-500/10 px-4 py-2.5 flex items-center gap-2">
          <AlertTriangle className="h-4 w-4 text-amber-400 flex-shrink-0" />
          <span className="text-xs text-amber-300">{cacheWarning}</span>
        </div>
      )}

      {/* Error */}
      {error && !isLoading && (
        <div className="rounded-lg border border-rose-500/20 bg-rose-500/10 px-4 py-2.5 flex items-center gap-2">
          <AlertTriangle className="h-4 w-4 text-rose-400 flex-shrink-0" />
          <span className="text-xs text-rose-300">{error}</span>
        </div>
      )}

      {/* Loading */}
      {isLoading && (
        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-12 text-center">
          <Loader2 className="h-8 w-8 text-slate-600 mx-auto mb-3 animate-spin" />
          <p className="text-sm text-slate-500">正在获取丁昶分析数据...</p>
        </div>
      )}

      {/* Data Source & Time */}
      {dataSource && (
        <div className="rounded-lg border border-slate-700/50 bg-slate-800/40 px-3 py-1.5 flex items-center gap-2 w-fit">
          <span className="text-[11px] text-slate-400">数据源: </span>
          <span className="rounded bg-slate-700 px-2 py-0.5 text-[11px] text-slate-300">{dataSource}</span>
          {analysisTime && <span className="text-[11px] text-slate-500 ml-2">{analysisTime}</span>}
        </div>
      )}

      {data && !isLoading && (
        <div className="space-y-5">
          {/* ETF Comparison Chart */}
          {comparisonData.length > 0 && (
            <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5">
              <div className="flex items-center gap-2 mb-4">
                <Award className="h-4 w-4 text-amber-400" />
                <h3 className="text-sm font-semibold text-slate-200">ETF评分对比</h3>
              </div>
              <div className="h-56">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={comparisonData} layout="vertical" barSize={24}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                    <XAxis type="number" domain={[0, 100]} stroke="#64748b" fontSize={11} />
                    <YAxis dataKey="code" type="category" stroke="#94a3b8" fontSize={10} width={70} />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: '#0f172a',
                        border: '1px solid #1e293b',
                        borderRadius: '8px',
                        fontSize: '12px',
                      }}
                      labelStyle={{ color: '#e2e8f0' }}
                      formatter={(value: number) => [`${value}分`, '综合评分']}
                    />
                    <Bar dataKey="score" radius={[0, 4, 4, 0]}>
                      {comparisonData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={getBarColor(entry.score)} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

          <DingChangPanel data={data} />
        </div>
      )}

      {!data && !isLoading && (
        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-12 text-center">
          <Search className="h-8 w-8 text-slate-600 mx-auto mb-3" />
          <p className="text-sm text-slate-500">请输入ETF代码进行评估</p>
          <p className="text-xs text-slate-600 mt-1">支持的代码示例: 510300, 512890, 515290, 588000, 159915</p>
        </div>
      )}
    </div>
  );
}
