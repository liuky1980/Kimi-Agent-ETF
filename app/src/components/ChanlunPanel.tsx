import type { ChanlunResult } from '@/data/mockData';
import { cn } from '@/lib/utils';
import {
  TrendingUp,
  TrendingDown,
  Minus,
  AlertTriangle,
  CheckCircle2,
  ArrowUp,
  ArrowDown,
  Activity,
  BarChart3,
  Zap,
  Target,
} from 'lucide-react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
  AreaChart,
  Area,
  Line,
  ComposedChart,
  Legend,
} from 'recharts';

interface ChanlunPanelProps {
  data: ChanlunResult;
}

function TrendBadge({ position, confidence }: { position: string; confidence: number }) {
  const isUp = position === '上升趋势';
  const isDown = position === '下跌趋势';
  const isTransition = position === '趋势转折中';

  return (
    <div
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-sm font-medium',
        isUp && 'bg-red-500/15 text-red-400',
        isDown && 'bg-green-500/15 text-green-400',
        isTransition && 'bg-amber-500/15 text-amber-400',
        !isUp && !isDown && !isTransition && 'bg-slate-500/15 text-slate-400'
      )}
    >
      {isUp && <TrendingUp className="h-4 w-4" />}
      {isDown && <TrendingDown className="h-4 w-4" />}
      {isTransition && <AlertTriangle className="h-4 w-4" />}
      {!isUp && !isDown && !isTransition && <Minus className="h-4 w-4" />}
      {position} (置信度{(confidence * 100).toFixed(0)}%)
    </div>
  );
}

export default function ChanlunPanel({ data }: ChanlunPanelProps) {
  const buyPoints = data.buySellPoints.filter((p) => p.type.includes('买'));
  const sellPoints = data.buySellPoints.filter((p) => p.type.includes('卖'));

  const divergenceData = [
    { name: '前段MACD面积', value: Math.abs(data.macdAreaPrevious) },
    { name: '当前MACD面积', value: Math.abs(data.macdAreaCurrent) },
  ];

  const resonanceData = [
    { name: '周线', value: data.weeklyResonance },
    { name: '日线', value: data.dailyResonance },
    { name: '小时线', value: data.hourlyResonance },
  ];

  return (
    <div className="space-y-5">
      {/* Trend Verdict Banner */}
      <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div>
            <div className="text-sm text-slate-400 mb-2">趋势判定</div>
            <TrendBadge position={data.trendPosition} confidence={data.trendConfidence} />
          </div>
          <div className="text-right">
            <div className="text-2xl font-bold text-slate-100">
              {data.currentPrice.toFixed(3)}
              <span
                className={cn(
                  'ml-2 text-sm font-medium',
                  data.changePercent >= 0 ? 'text-red-400' : 'text-green-400'
                )}
              >
                {data.changePercent >= 0 ? '+' : ''}
                {data.changePercent}%
              </span>
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* Structure Analysis */}
        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5">
          <div className="flex items-center gap-2 mb-4">
            <Activity className="h-4 w-4 text-emerald-400" />
            <h3 className="text-sm font-semibold text-slate-200">结构分析</h3>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <StructureCard
              label="顶分型"
              value={data.topFractal ? '形成' : '未形成'}
              active={data.topFractal}
              type="danger"
            />
            <StructureCard
              label="底分型"
              value={data.bottomFractal ? '形成' : '未形成'}
              active={data.bottomFractal}
              type="success"
            />
            <div className="rounded-lg bg-slate-800/60 p-3">
              <div className="text-xs text-slate-400 mb-1">笔数量 / 方向</div>
              <div className="flex items-center gap-1.5 text-sm font-medium text-slate-200">
                <span>{data.biCount}笔</span>
                {data.biDirection === '向上' ? (
                  <ArrowUp className="h-3.5 w-3.5 text-red-400" />
                ) : (
                  <ArrowDown className="h-3.5 w-3.5 text-green-400" />
                )}
                <span className={data.biDirection === '向上' ? 'text-red-400' : 'text-green-400'}>
                  {data.biDirection}
                </span>
              </div>
            </div>
            <div className="rounded-lg bg-slate-800/60 p-3">
              <div className="text-xs text-slate-400 mb-1">线段方向</div>
              <div className="flex items-center gap-1.5 text-sm font-medium text-slate-200">
                {data.segmentDirection === '向上' ? (
                  <ArrowUp className="h-3.5 w-3.5 text-red-400" />
                ) : (
                  <ArrowDown className="h-3.5 w-3.5 text-green-400" />
                )}
                <span className={data.segmentDirection === '向上' ? 'text-red-400' : 'text-green-400'}>
                  {data.segmentDirection}
                </span>
              </div>
            </div>
          </div>
          <div className="mt-3 rounded-lg bg-slate-800/60 p-3">
            <div className="text-xs text-slate-400 mb-1.5">中枢区间 [ZD - ZG]</div>
            <div className="flex items-center gap-2">
              <span className="text-sm font-mono font-medium text-amber-400">{data.centerRange[0].toFixed(3)}</span>
              <span className="text-slate-500">-</span>
              <span className="text-sm font-mono font-medium text-amber-400">{data.centerRange[1].toFixed(3)}</span>
              <span className="ml-2 text-xs text-slate-500">
                宽度 {((data.centerRange[1] - data.centerRange[0]) / data.centerRange[0] * 100).toFixed(1)}%
              </span>
            </div>
            <div className="mt-2 h-2 rounded-full bg-slate-700 overflow-hidden">
              <div
                className="h-full rounded-full bg-amber-500/60"
                style={{ width: '100%' }}
              />
            </div>
            <div className="flex justify-between mt-1 text-[10px] text-slate-500 font-mono">
              <span>ZD</span>
              <span>中枢</span>
              <span>ZG</span>
            </div>
          </div>
        </div>

        {/* Divergence Detection */}
        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5">
          <div className="flex items-center gap-2 mb-4">
            <BarChart3 className="h-4 w-4 text-amber-400" />
            <h3 className="text-sm font-semibold text-slate-200">背驰检测</h3>
          </div>
          <div className="mb-3">
            <div
              className={cn(
                'inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium',
                data.divergenceType === '无背驰'
                  ? 'bg-slate-500/15 text-slate-400'
                  : 'bg-amber-500/15 text-amber-400'
              )}
            >
              {data.divergenceType}
              {data.divergenceStrength > 0 && ` (强度 ${data.divergenceStrength})`}
            </div>
          </div>
          <div className="h-40">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={divergenceData} barSize={40}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis dataKey="name" stroke="#94a3b8" fontSize={12} />
                <YAxis stroke="#94a3b8" fontSize={12} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#0f172a',
                    border: '1px solid #1e293b',
                    borderRadius: '8px',
                    fontSize: '12px',
                  }}
                  labelStyle={{ color: '#e2e8f0' }}
                />
                <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                  {divergenceData.map((_, index) => (
                    <Cell
                      key={`cell-${index}`}
                      fill={index === 0 ? '#f59e0b' : '#10b981'}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
          {data.divergenceType !== '无背驰' && (
            <div className="mt-2 text-xs text-amber-400 bg-amber-500/10 rounded-lg p-2">
              MACD面积出现衰减，{data.macdAreaCurrent < data.macdAreaPrevious ? '当前段面积小于前段' : '注意观察后续走势'}
            </div>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* Buy/Sell Points */}
        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5">
          <div className="flex items-center gap-2 mb-4">
            <Target className="h-4 w-4 text-rose-400" />
            <h3 className="text-sm font-semibold text-slate-200">买卖点信号</h3>
          </div>
          {buyPoints.length > 0 && (
            <div className="mb-3">
              <div className="text-xs text-red-400 mb-2 font-medium">买入信号</div>
              <div className="space-y-2">
                {buyPoints.map((point, idx) => (
                  <PointCard key={idx} point={point} type="buy" />
                ))}
              </div>
            </div>
          )}
          {sellPoints.length > 0 && (
            <div>
              <div className="text-xs text-green-400 mb-2 font-medium">卖出信号</div>
              <div className="space-y-2">
                {sellPoints.map((point, idx) => (
                  <PointCard key={idx} point={point} type="sell" />
                ))}
              </div>
            </div>
          )}
          {data.buySellPoints.length === 0 && (
            <div className="text-sm text-slate-500 text-center py-4">暂无明确买卖点信号</div>
          )}
        </div>

        {/* Multi-timeframe Resonance */}
        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5">
          <div className="flex items-center gap-2 mb-4">
            <Zap className="h-4 w-4 text-sky-400" />
            <h3 className="text-sm font-semibold text-slate-200">多周期共振</h3>
          </div>
          <div className="h-40">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={resonanceData} barSize={40}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis dataKey="name" stroke="#94a3b8" fontSize={12} />
                <YAxis domain={[0, 100]} stroke="#94a3b8" fontSize={12} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#0f172a',
                    border: '1px solid #1e293b',
                    borderRadius: '8px',
                    fontSize: '12px',
                  }}
                  labelStyle={{ color: '#e2e8f0' }}
                />
                <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                  {resonanceData.map((entry, index) => (
                    <Cell
                      key={`cell-${index}`}
                      fill={entry.value >= 70 ? '#10b981' : entry.value >= 50 ? '#f59e0b' : '#ef4444'}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="mt-3 flex items-center justify-between rounded-lg bg-slate-800/60 p-3">
            <span className="text-xs text-slate-400">综合共振度</span>
            <span
              className={cn(
                'text-sm font-bold',
                data.compositeResonance >= 70
                  ? 'text-emerald-400'
                  : data.compositeResonance >= 50
                    ? 'text-amber-400'
                    : 'text-rose-400'
              )}
            >
              {data.compositeResonance}%
            </span>
          </div>
        </div>
      </div>

      {/* Price & MACD Charts */}
      <div className="grid grid-cols-1 gap-5">
        {/* Price History Chart */}
        {data.priceHistory && data.priceHistory.length > 0 && (
          <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5">
            <div className="flex items-center gap-2 mb-4">
              <TrendingUp className="h-4 w-4 text-sky-400" />
              <h3 className="text-sm font-semibold text-slate-200">价格走势</h3>
            </div>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={data.priceHistory} margin={{ top: 5, right: 5, left: 0, bottom: 5 }}>
                  <defs>
                    <linearGradient id="priceGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#0ea5e9" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#0ea5e9" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                  <XAxis
                    dataKey="date"
                    stroke="#94a3b8"
                    fontSize={11}
                    tickFormatter={(v: string) => v.slice(5, 10)}
                    minTickGap={30}
                  />
                  <YAxis stroke="#94a3b8" fontSize={11} domain={['auto', 'auto']} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#0f172a',
                      border: '1px solid #1e293b',
                      borderRadius: '8px',
                      fontSize: '12px',
                    }}
                    labelStyle={{ color: '#e2e8f0' }}
                    formatter={(value: number, name: string) => {
                      if (name === 'close') return [value.toFixed(3), '收盘价'];
                      return [value, name];
                    }}
                  />
                  <Area
                    type="monotone"
                    dataKey="close"
                    stroke="#0ea5e9"
                    strokeWidth={1.5}
                    fill="url(#priceGradient)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}

        {/* MACD Indicator Chart */}
        {data.macdHistory && data.macdHistory.length > 0 && (
          <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5">
            <div className="flex items-center gap-2 mb-4">
              <Activity className="h-4 w-4 text-amber-400" />
              <h3 className="text-sm font-semibold text-slate-200">MACD 指标</h3>
            </div>
            <div className="h-56">
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={data.macdHistory} margin={{ top: 5, right: 5, left: 0, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                  <XAxis
                    dataKey="date"
                    stroke="#94a3b8"
                    fontSize={11}
                    tickFormatter={(v: string) => v.slice(5, 10)}
                    minTickGap={30}
                  />
                  <YAxis stroke="#94a3b8" fontSize={11} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#0f172a',
                      border: '1px solid #1e293b',
                      borderRadius: '8px',
                      fontSize: '12px',
                    }}
                    labelStyle={{ color: '#e2e8f0' }}
                  />
                  <Legend
                    wrapperStyle={{ fontSize: '11px', color: '#94a3b8' }}
                  />
                  <Bar dataKey="histogram" name="MACD柱状" barSize={2} fill="#64748b" />
                  <Line
                    type="monotone"
                    dataKey="macd"
                    name="DIF"
                    stroke="#f59e0b"
                    strokeWidth={1.5}
                    dot={false}
                  />
                  <Line
                    type="monotone"
                    dataKey="signal"
                    name="DEA"
                    stroke="#10b981"
                    strokeWidth={1.5}
                    dot={false}
                  />
                  {/* 零轴参考线 */}
                  <Line
                    type="monotone"
                    dataKey={() => 0}
                    name=""
                    stroke="#475569"
                    strokeDasharray="3 3"
                    strokeWidth={1}
                    dot={false}
                    legendType="none"
                  />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}
      </div>

      {/* Recommendation */}
      <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5">
        <div className="flex items-center gap-2 mb-2">
          <CheckCircle2 className="h-4 w-4 text-sky-400" />
          <h3 className="text-sm font-semibold text-slate-200">李彪分析框架结论</h3>
        </div>
        <p className="text-sm text-slate-300 leading-relaxed">{data.recommendation}</p>
      </div>
    </div>
  );
}

function StructureCard({
  label,
  value,
  active,
  type,
}: {
  label: string;
  value: string;
  active: boolean;
  type: 'success' | 'danger';
}) {
  return (
    <div className="rounded-lg bg-slate-800/60 p-3">
      <div className="text-xs text-slate-400 mb-1">{label}</div>
      <div
        className={cn(
          'text-sm font-medium',
          active
            ?              type === 'success'
              ? 'text-red-400'
              : 'text-green-400'
            : 'text-slate-500'
        )}
      >
        {active && (
          <CheckCircle2
            className={cn('inline h-3.5 w-3.5 mr-1', type === 'success' ? 'text-red-400' : 'text-green-400')}
          />
        )}
        {value}
      </div>
    </div>
  );
}

function PointCard({
  point,
  type,
}: {
  point: { type: string; price: number; confidence: number; description: string };
  type: 'buy' | 'sell';
}) {
  return (
    <div
      className={cn(
        'flex items-center justify-between rounded-lg p-3',
        type === 'buy' ? 'bg-red-500/10 border border-red-500/20' : 'bg-green-500/10 border border-green-500/20'
      )}
    >
      <div>
        <div className="flex items-center gap-2">
          <span
            className={cn(
              'text-sm font-bold',
              type === 'buy' ? 'text-red-400' : 'text-green-400'
            )}
          >
            {point.type}
          </span>
          <span className="text-xs text-slate-400">{point.price.toFixed(3)}</span>
        </div>
        <div className="text-xs text-slate-500 mt-0.5">{point.description}</div>
      </div>
      <div className="text-right">
        <div
          className={cn(
            'text-xs font-medium px-2 py-0.5 rounded-full',
            point.confidence >= 0.8
              ? 'bg-emerald-500/20 text-emerald-400'
              : point.confidence >= 0.6
                ? 'bg-amber-500/20 text-amber-400'
                : 'bg-slate-500/20 text-slate-400'
          )}
        >
          {(point.confidence * 100).toFixed(0)}%
        </div>
      </div>
    </div>
  );
}
