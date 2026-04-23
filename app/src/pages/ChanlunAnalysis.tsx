import { useState, useMemo, useEffect, useCallback } from 'react';
import { api } from '@/services/api';
import { dataCache } from '@/services/dataCache';
import type { ChanlunResult } from '@/data/mockData';
import ChanlunPanel from '@/components/ChanlunPanel';
import {
  Search,
  LineChart,
  TrendingUp,
  TrendingDown,
  Minus,
  AlertTriangle,
  Loader2,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';

interface ChanlunAnalysisProps {
  initialCode?: string;
}

// 后端数据可能为snake_case，映射到前端camelCase
function normalizeChanlun(raw: Record<string, unknown>): ChanlunResult | null {
  if (!raw) return null;
  const get = (k: string) => (raw[k] !== undefined ? raw[k] : raw[k.replace(/[A-Z]/g, m => '_' + m.toLowerCase())]);

  const result: ChanlunResult = {
    etfCode: (get('etfCode') as string) || '',
    etfName: '', // 去除中文名称显示
    trendPosition: (get('trendPosition') as ChanlunResult['trendPosition']) || '中枢震荡',
    trendConfidence: Number(get('trendConfidence')) || 0,
    currentPrice: Number(get('currentPrice')) || 0,
    changePercent: Number(get('changePercent')) || 0,
    topFractal: Boolean(get('topFractal')),
    bottomFractal: Boolean(get('bottomFractal')),
    biCount: Number(get('biCount')) || 0,
    biDirection: (get('biDirection') as ChanlunResult['biDirection']) || '向上',
    centerRange: (get('centerRange') as [number, number]) || [0, 0],
    segmentDirection: (get('segmentDirection') as ChanlunResult['segmentDirection']) || '向上',
    divergenceType: (get('divergenceType') as ChanlunResult['divergenceType']) || '无背驰',
    divergenceStrength: Number(get('divergenceStrength')) || 0,
    macdAreaCurrent: Number(get('macdAreaCurrent')) || 0,
    macdAreaPrevious: Number(get('macdAreaPrevious')) || 0,
    buySellPoints: (get('buySellPoints') as ChanlunResult['buySellPoints']) || [],
    dailyResonance: Number(get('dailyResonance')) || 0,
    min30Resonance: Number(get('min30Resonance')) || 0,
    min5Resonance: Number(get('min5Resonance')) || 0,
    compositeResonance: Number(get('compositeResonance')) || 0,
    recommendation: (get('recommendation') as string) || '',
    macdHistory: (get('macdHistory') as ChanlunResult['macdHistory']) || [],
    priceHistory: (get('priceHistory') as ChanlunResult['priceHistory']) || [],
  };
  return result;
}

export default function ChanlunAnalysis({ initialCode }: ChanlunAnalysisProps) {
  const [searchCode, setSearchCode] = useState(initialCode || '');
  const [selectedCode, setSelectedCode] = useState(initialCode || '');
  const [cacheWarning, setCacheWarning] = useState<string>('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string>('');
  const [dataSource, setDataSource] = useState<string>('');
  const [analysisTime, setAnalysisTime] = useState<string>('');
  const [etfSelectorCodes, setEtfSelectorCodes] = useState<string[]>([]);
  const [allTrends, setAllTrends] = useState<Array<{ code: string; trendPosition: string }>>([]);

  // 从缓存获取已分析过的ETF代码列表
  useEffect(() => {
    const all = dataCache.getAll();
    const codes = all.map(item => item.code);
    setEtfSelectorCodes(codes);

    // 收集所有缓存中的趋势数据用于按钮图标显示
    const trends: Array<{ code: string; trendPosition: string }> = [];
    for (const item of all) {
      if (item.data?.chanlun) {
        const cl = normalizeChanlun(item.data.chanlun as Record<string, unknown>);
        if (cl) {
          trends.push({ code: item.code, trendPosition: cl.trendPosition });
        }
      }
    }
    setAllTrends(trends);
  }, []);

  // 监听缓存变化
  useEffect(() => {
    const unsubscribe = dataCache.subscribe((pool) => {
      const codes = pool.map(item => item.code);
      setEtfSelectorCodes(codes);
      const trends: Array<{ code: string; trendPosition: string }> = [];
      for (const item of pool) {
        if (item.data?.chanlun) {
          const cl = normalizeChanlun(item.data.chanlun as Record<string, unknown>);
          if (cl) {
            trends.push({ code: item.code, trendPosition: cl.trendPosition });
          }
        }
      }
      setAllTrends(trends);
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
      let clRaw = cached?.data?.chanlun as Record<string, unknown> | undefined;

      // 如果缓存中没有，调用API
      if (!clRaw) {
        const result = await api.getChanlunAnalysis(code);
        clRaw = result;
        setDataSource((result.data_source as string) || '');
        setAnalysisTime((result.analysis_time as string) || '');

        // 存入缓存
        if (clRaw) dataCache.updateData(code, 'chanlun', clRaw);

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
  const data = useMemo<ChanlunResult | null>(() => {
    const cached = dataCache.get(selectedCode);
    if (cached?.data?.chanlun) {
      return normalizeChanlun(cached.data.chanlun as Record<string, unknown>);
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

  const chartData = useMemo(() => {
    if (!data) return [];
    return data.macdHistory.map((item, idx) => ({
      ...item,
      price: data.priceHistory[idx]?.price || 0,
    }));
  }, [data]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-emerald-500/15">
            <LineChart className="h-5 w-5 text-emerald-400" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-slate-100">李彪分析框架</h1>
            <p className="text-xs text-slate-500">Libiao Analysis Framework - 趋势 · 结构 · 买卖点</p>
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
              className="w-32 rounded-lg border border-slate-700 bg-slate-800/80 py-1.5 pl-8 pr-3 text-sm text-slate-200 placeholder:text-slate-500 focus:border-emerald-500/50 focus:outline-none focus:ring-1 focus:ring-emerald-500/30"
            />
          </div>
          <button
            onClick={handleSearch}
            className="rounded-lg bg-emerald-500/15 border border-emerald-500/30 px-3 py-1.5 text-xs font-medium text-emerald-400 hover:bg-emerald-500/25 transition-colors"
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
            const trendEntry = allTrends.find(t => t.code === code);
            const trendUp = trendEntry?.trendPosition === '上升趋势';
            const trendDown = trendEntry?.trendPosition === '下跌趋势';
            const trendConsolidation = trendEntry?.trendPosition === '中枢震荡';
            const trendTransition = trendEntry?.trendPosition === '趋势转折中';
            return (
              <button
                key={code}
                onClick={() => handleSelectCode(code)}
                className={cn(
                  'flex items-center gap-1.5 rounded-lg border px-3 py-2 text-sm transition-all',
                  isActive
                    ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-400'
                    : 'border-slate-800 bg-slate-900/60 text-slate-400 hover:border-slate-700 hover:text-slate-300'
                )}
              >
                {/* 只显示代码 */}
                <span className="font-mono text-xs">{code}</span>
                {trendUp && <TrendingUp className="h-3 w-3 text-emerald-400" />}
                {trendDown && <TrendingDown className="h-3 w-3 text-rose-400" />}
                {trendConsolidation && <Minus className="h-3 w-3 text-amber-400" />}
                {trendTransition && <AlertTriangle className="h-3 w-3 text-amber-400" />}
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
          <p className="text-sm text-slate-500">正在获取李彪分析数据...</p>
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

      {/* Price & MACD Chart */}
      {data && !isLoading && (
        <div className="grid grid-cols-1 gap-5">
          <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5">
            <div className="flex items-center justify-between mb-4">
              <div>
                {/* 只显示代码 */}
                <div className="text-sm font-semibold text-slate-200 font-mono">
                  {data.etfCode}
                </div>
                <div className="text-xs text-slate-500 mt-0.5">MACD指标与价格走势</div>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-xl font-bold text-slate-100">{data.currentPrice.toFixed(3)}</span>
                <span
                  className={cn(
                    'text-sm font-medium',
                    data.changePercent >= 0 ? 'text-emerald-400' : 'text-rose-400'
                  )}
                >
                  {data.changePercent >= 0 ? '+' : ''}{data.changePercent}%
                </span>
              </div>
            </div>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                  <XAxis dataKey="date" stroke="#64748b" fontSize={11} />
                  <YAxis yAxisId="left" stroke="#64748b" fontSize={11} />
                  <YAxis yAxisId="right" orientation="right" stroke="#64748b" fontSize={11} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#0f172a',
                      border: '1px solid #1e293b',
                      borderRadius: '8px',
                      fontSize: '12px',
                    }}
                    labelStyle={{ color: '#e2e8f0' }}
                  />
                  <Legend wrapperStyle={{ fontSize: '12px' }} />
                  <Area
                    yAxisId="left"
                    type="monotone"
                    dataKey="histogram"
                    name="MACD柱状"
                    stroke="#10b981"
                    fill="#10b981"
                    fillOpacity={0.15}
                    strokeWidth={1.5}
                  />
                  <Area
                    yAxisId="right"
                    type="monotone"
                    dataKey="price"
                    name="价格"
                    stroke="#3b82f6"
                    fill="#3b82f6"
                    fillOpacity={0.1}
                    strokeWidth={1.5}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>

          <ChanlunPanel data={data} />
        </div>
      )}

      {!data && !isLoading && (
        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-12 text-center">
          <Search className="h-8 w-8 text-slate-600 mx-auto mb-3" />
          <p className="text-sm text-slate-500">请输入ETF代码进行分析</p>
          <p className="text-xs text-slate-600 mt-1">支持的代码示例: 510300, 512890, 515290, 588000, 159915</p>
        </div>
      )}
    </div>
  );
}
