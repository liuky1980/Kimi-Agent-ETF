import { useState } from 'react';
import type { DingChangResult } from '@/data/mockData';
import { cn } from '@/lib/utils';
import ScoreRing from './ScoreRing';
import {
  RadarChart,
  Radar,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
  Tooltip,
} from 'recharts';
import {
  ChevronDown,
  ChevronUp,
  TrendingUp,
  Shield,
  DollarSign,
  Users,
  Globe,
  Award,
  AlertTriangle,
  Signal,
} from 'lucide-react';

interface DingChangPanelProps {
  data: DingChangResult;
}

const dimensionMeta = [
  {
    key: 'dividendQuality' as const,
    label: '股息质量',
    weight: 30,
    icon: DollarSign,
    color: '#10b981',
    subs: [
      { key: 'dividend_yield', label: '股息率', unit: '%' },
      { key: 'yield_5y_avg', label: '5年均值', unit: '%' },
      { key: 'payout_consistency', label: '分红连续性', unit: '' },
      { key: 'distribution_quality', label: '分红质量', unit: '' },
      { key: 'capital_return_efficiency', label: '资本回报效率', unit: '' },
    ],
  },
  {
    key: 'valuationSafety' as const,
    label: '估值安全',
    weight: 25,
    icon: Shield,
    color: '#3b82f6',
    subs: [
      { key: 'pe_ttm', label: 'PE-TTM', unit: 'x' },
      { key: 'pe_percentile', label: 'PE百分位', unit: '%' },
      { key: 'pb', label: 'PB', unit: 'x' },
      { key: 'pb_percentile', label: 'PB百分位', unit: '%' },
      { key: 'peg', label: 'PEG', unit: '' },
      { key: 'spread_risk_free', label: '无风险利差', unit: '%' },
      { key: 'nav_discount_premium', label: '折溢价', unit: '%' },
    ],
  },
  {
    key: 'profitability' as const,
    label: '盈利质地',
    weight: 20,
    icon: TrendingUp,
    color: '#f59e0b',
    subs: [
      { key: 'roe', label: 'ROE', unit: '%' },
      { key: 'roic', label: 'ROIC', unit: '%' },
      { key: 'earnings_stability', label: '盈利稳定性', unit: '' },
      { key: 'earnings_growth_3y', label: '3年盈利增长', unit: '%' },
      { key: 'revenue_growth_3y', label: '3年营收增长', unit: '%' },
      { key: 'cash_flow_quality', label: '现金流质量', unit: '' },
    ],
  },
  {
    key: 'capitalFlow' as const,
    label: '资金驱动',
    weight: 15,
    icon: Users,
    color: '#8b5cf6',
    subs: [
      { key: 'aum', label: '规模(AUM)', unit: '亿' },
      { key: 'aum_growth_3m', label: '3月规模增长', unit: '%' },
      { key: 'aum_growth_1y', label: '1年规模增长', unit: '%' },
      { key: 'volume_trend', label: '成交量趋势', unit: '' },
      { key: 'institutional_ratio', label: '机构持仓比例', unit: '%' },
      { key: 'institutional_change', label: '机构持仓变化', unit: '%' },
      { key: 'fund_flow_20d', label: '20日资金流向', unit: '亿' },
    ],
  },
  {
    key: 'macroFit' as const,
    label: '宏观适配',
    weight: 10,
    icon: Globe,
    color: '#06b6d4',
    subs: [
      { key: 'cycle_position', label: '周期定位', unit: '' },
      { key: 'cycle_fit_score', label: '周期匹配度', unit: '' },
      { key: 'rate_environment_fit', label: '利率环境适配', unit: '' },
      { key: 'policy_support', label: '政策支持', unit: '' },
      { key: 'global_comparison', label: '全球比较', unit: '' },
      { key: 'macro_risk_score', label: '宏观风险', unit: '' },
    ],
  },
];

export default function DingChangPanel({ data }: DingChangPanelProps) {
  const [expandedDim, setExpandedDim] = useState<string | null>(null);

  const radarData = dimensionMeta.map((d) => ({
    subject: d.label,
    score: data.dimensions[d.key].score,
    fullMark: 100,
  }));

  const signalColor = data.compositeSignal === '增持' ? 'text-emerald-400' : data.compositeSignal === '减持' ? 'text-rose-400' : 'text-amber-400';
  const signalBg = data.compositeSignal === '增持' ? 'bg-emerald-500/15' : data.compositeSignal === '减持' ? 'bg-rose-500/15' : 'bg-amber-500/15';

  return (
    <div className="space-y-5">
      {/* Score and Radar */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 flex flex-col items-center justify-center">
          <div className="text-sm text-slate-400 mb-3">丁昶分析框架综合评分</div>
          <ScoreRing score={data.compositeScore} />
          <div className="mt-3 flex items-center gap-2">
            <Award className="h-4 w-4 text-sky-400" />
            <span
              className={cn(
                'text-sm font-medium px-3 py-1 rounded-full',
                data.rating === '买入' && 'bg-emerald-500/15 text-emerald-400',
                data.rating === '持有' && 'bg-sky-500/15 text-sky-400',
                data.rating === '观察' && 'bg-amber-500/15 text-amber-400',
                data.rating === '回避' && 'bg-rose-500/15 text-rose-400'
              )}
            >
              {data.rating}
            </span>
          </div>
        </div>

        <div className="lg:col-span-2 rounded-xl border border-slate-800 bg-slate-900/60 p-5">
          <div className="text-sm font-semibold text-slate-200 mb-3">五维雷达图</div>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <RadarChart data={radarData}>
                <PolarGrid stroke="#334155" />
                <PolarAngleAxis
                  dataKey="subject"
                  stroke="#94a3b8"
                  fontSize={12}
                  tickLine={false}
                />
                <PolarRadiusAxis
                  stroke="#475569"
                  fontSize={10}
                  domain={[0, 100]}
                  tickCount={6}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#0f172a',
                    border: '1px solid #1e293b',
                    borderRadius: '8px',
                    fontSize: '12px',
                  }}
                  labelStyle={{ color: '#e2e8f0' }}
                  formatter={(value: number) => [`${value}分`, '得分']}
                />
                <Radar
                  name={`${data.etfCode}.${data.etfName}`}
                  dataKey="score"
                  stroke="#10b981"
                  fill="#10b981"
                  fillOpacity={0.2}
                  strokeWidth={2}
                />
              </RadarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Dimension Breakdown */}
      <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5">
        <div className="text-sm font-semibold text-slate-200 mb-4">维度拆解</div>
        <div className="space-y-2">
          {dimensionMeta.map((dim) => {
            const Icon = dim.icon;
            const dimData = data.dimensions[dim.key];
            const isExpanded = expandedDim === dim.key;
            return (
              <div
                key={dim.key}
                className="rounded-lg border border-slate-800/60 overflow-hidden"
              >
                <button
                  onClick={() => setExpandedDim(isExpanded ? null : dim.key)}
                  className="w-full flex items-center justify-between p-3 hover:bg-slate-800/40 transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <div
                      className="flex h-8 w-8 items-center justify-center rounded-lg"
                      style={{ backgroundColor: `${dim.color}20` }}
                    >
                      <Icon className="h-4 w-4" style={{ color: dim.color }} />
                    </div>
                    <div className="text-left">
                      <div className="text-sm font-medium text-slate-200">
                        {dim.label}
                        <span className="ml-2 text-xs text-slate-500">权重{dim.weight}%</span>
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-sm font-bold" style={{ color: dim.color }}>
                      {dimData.score}分
                    </span>
                    <div className="w-20 h-1.5 rounded-full bg-slate-700 hidden sm:block">
                      <div
                        className="h-full rounded-full transition-all duration-500"
                        style={{ width: `${dimData.score}%`, backgroundColor: dim.color }}
                      />
                    </div>
                    {isExpanded ? (
                      <ChevronUp className="h-4 w-4 text-slate-400" />
                    ) : (
                      <ChevronDown className="h-4 w-4 text-slate-400" />
                    )}
                  </div>
                </button>
                {isExpanded && (
                  <div className="border-t border-slate-800/60 p-3 grid grid-cols-2 sm:grid-cols-4 gap-3">
                    {dim.subs.map((sub) => {
                      const val = dimData[sub.key as keyof typeof dimData];
                      return (
                        <div key={sub.key} className="rounded-md bg-slate-800/40 p-2.5">
                          <div className="text-[11px] text-slate-400 mb-1">{sub.label}</div>
                          <div className="text-sm font-mono font-semibold text-slate-200">
                            {typeof val === 'number' ? val.toFixed(2) : val}
                            <span className="text-xs text-slate-500 ml-0.5">{sub.unit}</span>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Signal System */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5">
          <div className="flex items-center gap-2 mb-4">
            <Signal className="h-4 w-4 text-emerald-400" />
            <h3 className="text-sm font-semibold text-slate-200">综合信号</h3>
          </div>
          <div className="flex items-center justify-between mb-4">
            <div>
              <div className={cn('text-2xl font-bold', signalColor)}>
                {data.compositeSignal}
              </div>
              <div className="text-xs text-slate-500 mt-1">基于五维评分与趋势因子</div>
            </div>
            <div className={cn('rounded-full px-4 py-2', signalBg)}>
              <span className={cn('text-sm font-bold', signalColor)}>
                {data.compositeScore}分
              </span>
            </div>
          </div>
          <div className="space-y-2">
            <SignalFactor label="趋势因子" value={data.signalFactors.trend} />
            <SignalFactor label="保险行为" value={data.signalFactors.insurance} />
            <SignalFactor label="拥挤度" value={data.signalFactors.crowding} />
          </div>
        </div>

        {/* Risks */}
        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5">
          <div className="flex items-center gap-2 mb-4">
            <AlertTriangle className="h-4 w-4 text-amber-400" />
            <h3 className="text-sm font-semibold text-slate-200">风险提示</h3>
          </div>
          <div className="space-y-2">
            {data.risks.map((risk, idx) => (
              <div
                key={idx}
                className="flex items-start gap-2 rounded-lg bg-amber-500/10 border border-amber-500/20 p-3"
              >
                <AlertTriangle className="h-3.5 w-3.5 text-amber-400 mt-0.5 flex-shrink-0" />
                <span className="text-sm text-amber-300">{risk}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function SignalFactor({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex items-center gap-3">
      <span className="text-xs text-slate-400 w-16">{label}</span>
      <div className="flex-1 h-2 rounded-full bg-slate-700">
        <div
          className={cn(
            'h-full rounded-full transition-all duration-500',
            value >= 70 ? 'bg-emerald-500' : value >= 40 ? 'bg-amber-500' : 'bg-rose-500'
          )}
          style={{ width: `${value}%` }}
        />
      </div>
      <span
        className={cn(
          'text-xs font-mono w-8 text-right',
          value >= 70 ? 'text-emerald-400' : value >= 40 ? 'text-amber-400' : 'text-rose-400'
        )}
      >
        {value}
      </span>
    </div>
  );
}
