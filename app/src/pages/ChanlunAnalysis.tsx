import { useState, useMemo } from 'react';
import { chanlunMockData, popularETFs } from '@/data/mockData';
import ChanlunPanel from '@/components/ChanlunPanel';
import {
  Search,
  LineChart,
  TrendingUp,
  TrendingDown,
  Minus,
  AlertTriangle,
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

export default function ChanlunAnalysis({ initialCode }: ChanlunAnalysisProps) {
  const [searchCode, setSearchCode] = useState(initialCode || '');
  const [selectedCode, setSelectedCode] = useState(initialCode || '510300');

  const data = useMemo(() => {
    return chanlunMockData[selectedCode] || chanlunMockData['510300'];
  }, [selectedCode]);

  const handleSearch = () => {
    const code = searchCode.trim();
    if (code && chanlunMockData[code]) {
      setSelectedCode(code);
    }
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
            <h1 className="text-xl font-bold text-slate-100">缠论技术分析</h1>
            <p className="text-xs text-slate-500">Chanlun Technical Analysis - 趋势 · 结构 · 买卖点</p>
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
      <div className="flex flex-wrap gap-2">
        {popularETFs.map((etf) => {
          const isActive = selectedCode === etf.code;
          const clData = chanlunMockData[etf.code];
          const trendUp = clData?.trendPosition === '上升趋势';
          const trendDown = clData?.trendPosition === '下跌趋势';
          return (
            <button
              key={etf.code}
              onClick={() => setSelectedCode(etf.code)}
              className={cn(
                'flex items-center gap-1.5 rounded-lg border px-3 py-2 text-sm transition-all',
                isActive
                  ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-400'
                  : 'border-slate-800 bg-slate-900/60 text-slate-400 hover:border-slate-700 hover:text-slate-300'
              )}
            >
              <span className="font-mono text-xs">{etf.code}</span>
              <span className="text-xs">{etf.name}</span>
              {trendUp && <TrendingUp className="h-3 w-3 text-emerald-400" />}
              {trendDown && <TrendingDown className="h-3 w-3 text-rose-400" />}
              {!trendUp && !trendDown && clData?.trendPosition === '中枢震荡' && (
                <Minus className="h-3 w-3 text-amber-400" />
              )}
              {!trendUp && !trendDown && clData?.trendPosition === '趋势转折中' && (
                <AlertTriangle className="h-3 w-3 text-amber-400" />
              )}
            </button>
          );
        })}
      </div>

      {/* Price & MACD Chart */}
      {data && (
        <div className="grid grid-cols-1 gap-5">
          <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5">
            <div className="flex items-center justify-between mb-4">
              <div>
                <div className="text-sm font-semibold text-slate-200">
                  {data.etfName} ({data.etfCode})
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

      {!data && (
        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-12 text-center">
          <Search className="h-8 w-8 text-slate-600 mx-auto mb-3" />
          <p className="text-sm text-slate-500">请输入有效的ETF代码进行分析</p>
          <p className="text-xs text-slate-600 mt-1">支持的代码: 510300, 512890, 515290, 588000, 159915</p>
        </div>
      )}
    </div>
  );
}
