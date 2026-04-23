import { useState, useMemo, useEffect } from 'react';
import { dingchangMockData, popularETFs } from '@/data/mockData';
import { dataCache } from '@/services/dataCache';
import DingChangPanel from '@/components/DingChangPanel';
import {
  Search,
  BarChart3,
  Award,
  TrendingUp,
  TrendingDown,
  Minus,
  AlertTriangle,
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

export default function DingChangAnalysis({ initialCode }: DingChangAnalysisProps) {
  const [searchCode, setSearchCode] = useState(initialCode || '');
  const [selectedCode, setSelectedCode] = useState(initialCode || '510300');
  const [cacheWarning, setCacheWarning] = useState<string>('');

  useEffect(() => {
    if (initialCode) {
      setSearchCode(initialCode);
      setSelectedCode(initialCode);
      checkCache(initialCode);
    }
  }, [initialCode]);

  const data = useMemo(() => {
    // 优先从缓存读取，fallback到mock数据
    const cached = dataCache.get(selectedCode);
    if (cached?.data?.dingchang) {
      return cached.data.dingchang as typeof dingchangMockData[keyof typeof dingchangMockData];
    }
    return dingchangMockData[selectedCode] || dingchangMockData['510300'];
  }, [selectedCode]);

  const isMockFallback = useMemo(() => {
    const cached = dataCache.get(selectedCode);
    return !cached?.data?.dingchang;
  }, [selectedCode]);

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
      if (!dataCache.has(code)) {
        setCacheWarning('该标的暂无缓存数据，请先在首页搜索');
      } else {
        setCacheWarning('');
      }
      if (dingchangMockData[code]) {
        setSelectedCode(code);
      }
    }
  };

  const comparisonData = useMemo(() => {
    return popularETFs.map((etf) => {
      const d = dingchangMockData[etf.code];
      return {
        name: etf.name,
        code: etf.code,
        score: d?.compositeScore || 0,
        rating: d?.rating || '观察',
      };
    }).sort((a, b) => b.score - a.score);
  }, []);

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

      {/* Cache Warning */}
      {cacheWarning && (
        <div className="rounded-lg border border-amber-500/20 bg-amber-500/10 px-4 py-2.5 flex items-center gap-2">
          <AlertTriangle className="h-4 w-4 text-amber-400 flex-shrink-0" />
          <span className="text-xs text-amber-300">{cacheWarning}</span>
        </div>
      )}

      {/* Data Source Badge */}
      {isMockFallback && (
        <div className="rounded-lg border border-slate-700/50 bg-slate-800/40 px-3 py-1.5 flex items-center gap-2 w-fit">
          <span className="text-[11px] text-slate-400">当前展示: </span>
          <span className="rounded bg-slate-700 px-2 py-0.5 text-[11px] text-slate-300">模拟数据</span>
        </div>
      )}

      {/* ETF Selector */}
      <div className="flex flex-wrap gap-2">
        {popularETFs.map((etf) => {
          const isActive = selectedCode === etf.code;
          const dcData = dingchangMockData[etf.code];
          const ratingBuy = dcData?.rating === '买入';
          const ratingAvoid = dcData?.rating === '回避';
          return (
            <button
              key={etf.code}
              onClick={() => {
                setSelectedCode(etf.code);
                checkCache(etf.code);
              }}
              className={cn(
                'flex items-center gap-1.5 rounded-lg border px-3 py-2 text-sm transition-all',
                isActive
                  ? 'border-sky-500/40 bg-sky-500/10 text-sky-400'
                  : 'border-slate-800 bg-slate-900/60 text-slate-400 hover:border-slate-700 hover:text-slate-300'
              )}
            >
              <span className="font-mono text-xs">{etf.code}.{etf.name}</span>
              {ratingBuy && <TrendingUp className="h-3 w-3 text-emerald-400" />}
              {ratingAvoid && <TrendingDown className="h-3 w-3 text-rose-400" />}
              {!ratingBuy && !ratingAvoid && <Minus className="h-3 w-3 text-amber-400" />}
            </button>
          );
        })}
      </div>

      {data && (
        <div className="space-y-5">
          {/* ETF Comparison Chart */}
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
                  <YAxis dataKey="name" type="category" stroke="#94a3b8" fontSize={11} width={80} />
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

          <DingChangPanel data={data} />
        </div>
      )}

      {!data && (
        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-12 text-center">
          <Search className="h-8 w-8 text-slate-600 mx-auto mb-3" />
          <p className="text-sm text-slate-500">请输入有效的ETF代码进行评估</p>
          <p className="text-xs text-slate-600 mt-1">支持的代码: 510300, 512890, 515290, 588000, 159915</p>
        </div>
      )}
    </div>
  );
}
