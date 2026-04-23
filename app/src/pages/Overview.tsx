import { useState, useMemo, useEffect } from 'react';
import { chanlunMockData, dingchangMockData, popularETFs } from '@/data/mockData';
import { dataCache } from '@/services/dataCache';
import { cn } from '@/lib/utils';
import {
  FileText,
  Search,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  CheckCircle2,
  ArrowRight,
  Shield,
  Target,
  Zap,
  BarChart3,
  LineChart,
  Award,
} from 'lucide-react';
import {
  RadarChart,
  Radar,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
  Tooltip,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Cell,
} from 'recharts';
import ScoreRing from '@/components/ScoreRing';

interface OverviewProps {
  initialCode?: string;
}

export default function Overview({ initialCode }: OverviewProps) {
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

  // 优先从缓存读取，fallback到mock数据
  const clData = useMemo(() => {
    const cached = dataCache.get(selectedCode);
    if (cached?.data?.chanlun) {
      return cached.data.chanlun as typeof chanlunMockData[keyof typeof chanlunMockData];
    }
    return chanlunMockData[selectedCode];
  }, [selectedCode]);

  const dcData = useMemo(() => {
    const cached = dataCache.get(selectedCode);
    if (cached?.data?.dingchang) {
      return cached.data.dingchang as typeof dingchangMockData[keyof typeof dingchangMockData];
    }
    return dingchangMockData[selectedCode];
  }, [selectedCode]);

  const isMockFallback = useMemo(() => {
    const cached = dataCache.get(selectedCode);
    return !cached?.data?.chanlun || !cached?.data?.dingchang;
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
      if (chanlunMockData[code] && dingchangMockData[code]) {
        setSelectedCode(code);
      }
    }
  };

  const hasData = clData && dcData;

  // Radar data for overview
  const radarData = hasData
    ? [
        { subject: '股息质量', score: dcData.dimensions.dividendQuality.score },
        { subject: '估值安全', score: dcData.dimensions.valuationSafety.score },
        { subject: '盈利质地', score: dcData.dimensions.profitability.score },
        { subject: '资金驱动', score: dcData.dimensions.capitalFlow.score },
        { subject: '宏观适配', score: dcData.dimensions.macroFit.score },
      ]
    : [];

  // Determine overall recommendation
  const getOverallRec = () => {
    if (!clData || !dcData) return null;
    const clBullish = clData.trendPosition === '上升趋势' || clData.trendPosition === '趋势转折中';
    const clBearish = clData.trendPosition === '下跌趋势';
    const dcGood = dcData.compositeScore >= 70;
    const dcBad = dcData.compositeScore < 50;

    if (clBullish && dcGood) return { text: '积极关注', color: 'emerald', detail: '李彪分析框架趋势向好 + 丁昶评分优秀，建议重点关注' };
    if (clBearish && dcBad) return { text: '谨慎回避', color: 'rose', detail: '李彪分析框架趋势向下 + 丁昶评分偏低，建议暂时回避' };
    if (clBullish && !dcGood) return { text: '结构机会', color: 'sky', detail: '李彪分析框架出现结构机会，但基本面评分一般，控制仓位参与' };
    if (clBearish && dcGood) return { text: '价值关注', color: 'amber', detail: '基本面优秀但趋势偏弱，可纳入观察列表等待企稳' };
    return { text: '中性观察', color: 'slate', detail: '多空因素交织，建议继续观察等待明确信号' };
  };

  const overallRec = getOverallRec();

  // Mini bar chart for dimensions
  const dimBarData = hasData
    ? [
        { name: '股息', score: dcData.dimensions.dividendQuality.score, weight: 30 },
        { name: '估值', score: dcData.dimensions.valuationSafety.score, weight: 25 },
        { name: '盈利', score: dcData.dimensions.profitability.score, weight: 20 },
        { name: '资金', score: dcData.dimensions.capitalFlow.score, weight: 15 },
        { name: '宏观', score: dcData.dimensions.macroFit.score, weight: 10 },
      ]
    : [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-amber-500/15">
            <FileText className="h-5 w-5 text-amber-400" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-slate-100">多框架综合</h1>
            <p className="text-xs text-slate-500">多框架融合研判 · 李彪 + 丁昶</p>
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
              className="w-32 rounded-lg border border-slate-700 bg-slate-800/80 py-1.5 pl-8 pr-3 text-sm text-slate-200 placeholder:text-slate-500 focus:border-amber-500/50 focus:outline-none focus:ring-1 focus:ring-amber-500/30"
            />
          </div>
          <button
            onClick={handleSearch}
            className="rounded-lg bg-amber-500/15 border border-amber-500/30 px-3 py-1.5 text-xs font-medium text-amber-400 hover:bg-amber-500/25 transition-colors"
          >
            查询
          </button>
        </div>
      </div>

      {/* ETF Selector */}
      <div className="flex flex-wrap gap-2">
        {popularETFs.map((etf) => {
          const isActive = selectedCode === etf.code;
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
                  ? 'border-amber-500/40 bg-amber-500/10 text-amber-400'
                  : 'border-slate-800 bg-slate-900/60 text-slate-400 hover:border-slate-700 hover:text-slate-300'
              )}
            >
              <span className="font-mono text-xs">{etf.code}</span>
              <span className="text-xs">{etf.name}</span>
            </button>
          );
        })}
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

      {hasData && overallRec && (
        <div className="space-y-5">
          {/* Executive Summary */}
          <div className={cn(
            'rounded-xl border p-6',
            overallRec.color === 'emerald' && 'border-emerald-500/30 bg-emerald-500/5',
            overallRec.color === 'rose' && 'border-rose-500/30 bg-rose-500/5',
            overallRec.color === 'sky' && 'border-sky-500/30 bg-sky-500/5',
            overallRec.color === 'amber' && 'border-amber-500/30 bg-amber-500/5',
            overallRec.color === 'slate' && 'border-slate-500/30 bg-slate-500/5',
          )}>
            <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4">
              <ScoreRing score={dcData.compositeScore} size={100} strokeWidth={8} />
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-2">
                  <h2 className="text-lg font-bold text-slate-100">
                    {clData.etfCode}.{clData.etfName}
                  </h2>
                  <span className={cn(
                    'rounded-full px-3 py-1 text-xs font-bold',
                    overallRec.color === 'emerald' && 'bg-emerald-500/20 text-emerald-400',
                    overallRec.color === 'rose' && 'bg-rose-500/20 text-rose-400',
                    overallRec.color === 'sky' && 'bg-sky-500/20 text-sky-400',
                    overallRec.color === 'amber' && 'bg-amber-500/20 text-amber-400',
                    overallRec.color === 'slate' && 'bg-slate-500/20 text-slate-400',
                  )}>
                    {overallRec.text}
                  </span>
                </div>
                <p className="text-sm text-slate-300 mb-3">{overallRec.detail}</p>
                <div className="flex flex-wrap gap-4 text-xs">
                  <div className="flex items-center gap-1.5">
                    <LineChart className="h-3.5 w-3.5 text-emerald-400" />
                    <span className="text-slate-400">李彪:</span>
                    <span className={cn(
                      'font-medium',
                      clData.trendPosition === '上升趋势' ? 'text-emerald-400' :
                      clData.trendPosition === '下跌趋势' ? 'text-rose-400' :
                      'text-amber-400'
                    )}>
                      {clData.trendPosition}
                    </span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <BarChart3 className="h-3.5 w-3.5 text-sky-400" />
                    <span className="text-slate-400">丁昶:</span>
                    <span className="font-medium text-slate-200">{dcData.compositeScore}分 · {dcData.rating}</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <Target className="h-3.5 w-3.5 text-amber-400" />
                    <span className="text-slate-400">信号:</span>
                    <span className="font-medium text-slate-200">{dcData.compositeSignal}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
            {/* Chanlun Summary */}
            <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5">
              <div className="flex items-center gap-2 mb-4">
                <LineChart className="h-4 w-4 text-emerald-400" />
                <h3 className="text-sm font-semibold text-slate-200">李彪分析框架研判</h3>
              </div>

              <div className="space-y-3">
                <SummaryRow
                  label="趋势位置"
                  value={clData.trendPosition}
                  icon={clData.trendPosition === '上升趋势' ? TrendingUp : clData.trendPosition === '下跌趋势' ? TrendingDown : AlertTriangle}
                  color={clData.trendPosition === '上升趋势' ? 'emerald' : clData.trendPosition === '下跌趋势' ? 'rose' : 'amber'}
                />
                <SummaryRow
                  label="分型状态"
                  value={clData.bottomFractal ? '底分型形成' : clData.topFractal ? '顶分型形成' : '无明确分型'}
                  icon={CheckCircle2}
                  color={clData.bottomFractal ? 'emerald' : clData.topFractal ? 'rose' : 'slate'}
                />
                <SummaryRow
                  label="背驰信号"
                  value={clData.divergenceType}
                  icon={Zap}
                  color={clData.divergenceType !== '无背驰' ? 'amber' : 'slate'}
                />
                <SummaryRow
                  label="买卖点"
                  value={clData.buySellPoints.map((p) => p.type).join('、') || '暂无'}
                  icon={Target}
                  color={clData.buySellPoints.length > 0 ? 'emerald' : 'slate'}
                />
                <SummaryRow
                  label="多周期共振"
                  value={`${clData.compositeResonance}%`}
                  icon={BarChart3}
                  color={clData.compositeResonance >= 70 ? 'emerald' : clData.compositeResonance >= 50 ? 'amber' : 'rose'}
                />
              </div>

              <div className="mt-4 rounded-lg bg-slate-800/60 p-3">
                <div className="text-xs text-slate-400 mb-1">李彪分析框架结论</div>
                <p className="text-sm text-slate-300">{clData.recommendation}</p>
              </div>
            </div>

            {/* DingChang Summary */}
            <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5">
              <div className="flex items-center gap-2 mb-4">
                <BarChart3 className="h-4 w-4 text-sky-400" />
                <h3 className="text-sm font-semibold text-slate-200">丁昶分析框架五维评估</h3>
              </div>

              {/* Mini dimension bars */}
              <div className="h-40 mb-4">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={dimBarData} barSize={20}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                    <XAxis dataKey="name" stroke="#94a3b8" fontSize={11} />
                    <YAxis domain={[0, 100]} stroke="#94a3b8" fontSize={11} />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: '#0f172a',
                        border: '1px solid #1e293b',
                        borderRadius: '8px',
                        fontSize: '12px',
                      }}
                    />
                    <Bar dataKey="score" radius={[4, 4, 0, 0]}>
                      {dimBarData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.score >= 70 ? '#10b981' : entry.score >= 50 ? '#3b82f6' : '#f59e0b'} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>

              <div className="space-y-2">
                <DimensionScoreRow label="股息质量" score={dcData.dimensions.dividendQuality.score} weight={30} />
                <DimensionScoreRow label="估值安全" score={dcData.dimensions.valuationSafety.score} weight={25} />
                <DimensionScoreRow label="盈利质地" score={dcData.dimensions.profitability.score} weight={20} />
                <DimensionScoreRow label="资金驱动" score={dcData.dimensions.capitalFlow.score} weight={15} />
                <DimensionScoreRow label="宏观适配" score={dcData.dimensions.macroFit.score} weight={10} />
              </div>

              <div className="mt-4 flex items-center justify-between rounded-lg bg-slate-800/60 p-3">
                <div className="text-xs text-slate-400">综合信号</div>
                <span className={cn(
                  'text-sm font-bold',
                  dcData.compositeSignal === '增持' ? 'text-emerald-400' :
                  dcData.compositeSignal === '减持' ? 'text-rose-400' :
                  'text-amber-400'
                )}>
                  {dcData.compositeSignal}
                </span>
              </div>
            </div>
          </div>

          {/* Action Recommendation */}
          <div className={cn(
            'rounded-xl border p-5',
            overallRec.color === 'emerald' && 'border-emerald-500/30 bg-emerald-500/5',
            overallRec.color === 'rose' && 'border-rose-500/30 bg-rose-500/5',
            overallRec.color === 'sky' && 'border-sky-500/30 bg-sky-500/5',
            overallRec.color === 'amber' && 'border-amber-500/30 bg-amber-500/5',
            overallRec.color === 'slate' && 'border-slate-500/30 bg-slate-500/5',
          )}>
            <div className="flex items-center gap-2 mb-3">
              <Award className={cn('h-4 w-4', `text-${overallRec.color}-400`)} />
              <h3 className="text-sm font-semibold text-slate-200">操作建议</h3>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <ActionCard
                title="李彪策略"
                content={clData.recommendation}
                icon={LineChart}
                color="emerald"
              />
              <ActionCard
                title="丁昶策略"
                content={`综合评分${dcData.compositeScore}分，评级"${dcData.rating}"，建议${dcData.compositeSignal}。${dcData.risks.length > 0 ? '注意' + dcData.risks[0] : ''}`}
                icon={BarChart3}
                color="sky"
              />
              <ActionCard
                title="融合决策"
                content={overallRec.detail}
                icon={Shield}
                color={overallRec.color === 'slate' ? 'amber' : overallRec.color}
              />
            </div>
          </div>

          {/* Risk Warnings */}
          <div className="rounded-xl border border-rose-900/40 bg-rose-950/10 p-5">
            <div className="flex items-center gap-2 mb-3">
              <AlertTriangle className="h-4 w-4 text-rose-400" />
              <h3 className="text-sm font-semibold text-rose-300">风险提示</h3>
            </div>
            <div className="space-y-2">
              {dcData.risks.map((risk, idx) => (
                <div key={idx} className="flex items-start gap-2">
                  <ArrowRight className="h-3 w-3 text-rose-500 mt-1 flex-shrink-0" />
                  <span className="text-sm text-rose-200/70">{risk}</span>
                </div>
              ))}
              <div className="flex items-start gap-2">
                <ArrowRight className="h-3 w-3 text-rose-500 mt-1 flex-shrink-0" />
                <span className="text-sm text-rose-200/70">
                  李彪分析框架当前为{clData.trendPosition}，{clData.divergenceType !== '无背驰' ? '出现' + clData.divergenceType + '信号需警惕' : '暂无背驰信号但需持续跟踪'}
                </span>
              </div>
            </div>
          </div>

          {/* Radar Chart */}
          <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5">
            <div className="text-sm font-semibold text-slate-200 mb-3">五维能力雷达</div>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <RadarChart data={radarData}>
                  <PolarGrid stroke="#334155" />
                  <PolarAngleAxis dataKey="subject" stroke="#94a3b8" fontSize={12} />
                  <PolarRadiusAxis stroke="#475569" fontSize={10} domain={[0, 100]} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#0f172a',
                      border: '1px solid #1e293b',
                      borderRadius: '8px',
                      fontSize: '12px',
                    }}
                    formatter={(value: number) => [`${value}分`, '']}
                  />
                  <Radar
                    name={dcData.etfName}
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
      )}

      {!hasData && (
        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-12 text-center">
          <FileText className="h-8 w-8 text-slate-600 mx-auto mb-3" />
          <p className="text-sm text-slate-500">请输入有效的ETF代码生成多框架综合报告</p>
          <p className="text-xs text-slate-600 mt-1">支持的代码: 510300, 512890, 515290, 588000, 159915</p>
        </div>
      )}
    </div>
  );
}

function SummaryRow({
  label,
  value,
  icon: Icon,
  color,
}: {
  label: string;
  value: string;
  icon: typeof CheckCircle2;
  color: string;
}) {
  const colorMap: Record<string, string> = {
    emerald: 'text-emerald-400',
    rose: 'text-rose-400',
    amber: 'text-amber-400',
    sky: 'text-sky-400',
    slate: 'text-slate-400',
  };

  return (
    <div className="flex items-center justify-between rounded-lg bg-slate-800/40 p-2.5">
      <div className="flex items-center gap-2">
        <Icon className={cn('h-3.5 w-3.5', colorMap[color] || 'text-slate-400')} />
        <span className="text-xs text-slate-400">{label}</span>
      </div>
      <span className={cn('text-xs font-medium', colorMap[color] || 'text-slate-300')}>{value}</span>
    </div>
  );
}

function DimensionScoreRow({ label, score, weight }: { label: string; score: number; weight: number }) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-slate-400 w-16">{label}</span>
      <span className="text-[10px] text-slate-600 w-8">{weight}%</span>
      <div className="flex-1 h-1.5 rounded-full bg-slate-700">
        <div
          className={cn(
            'h-full rounded-full transition-all duration-500',
            score >= 80 ? 'bg-emerald-500' : score >= 60 ? 'bg-sky-500' : score >= 40 ? 'bg-amber-500' : 'bg-rose-500'
          )}
          style={{ width: `${score}%` }}
        />
      </div>
      <span className={cn(
        'text-xs font-mono w-10 text-right',
        score >= 80 ? 'text-emerald-400' : score >= 60 ? 'text-sky-400' : score >= 40 ? 'text-amber-400' : 'text-rose-400'
      )}>
        {score}
      </span>
    </div>
  );
}

function ActionCard({
  title,
  content,
  icon: Icon,
  color,
}: {
  title: string;
  content: string;
  icon: typeof LineChart;
  color: string;
}) {
  const colorMap: Record<string, { border: string; bg: string; text: string }> = {
    emerald: { border: 'border-emerald-500/20', bg: 'bg-emerald-500/10', text: 'text-emerald-400' },
    rose: { border: 'border-rose-500/20', bg: 'bg-rose-500/10', text: 'text-rose-400' },
    amber: { border: 'border-amber-500/20', bg: 'bg-amber-500/10', text: 'text-amber-400' },
    sky: { border: 'border-sky-500/20', bg: 'bg-sky-500/10', text: 'text-sky-400' },
    slate: { border: 'border-slate-500/20', bg: 'bg-slate-500/10', text: 'text-slate-400' },
  };
  const colors = colorMap[color] || colorMap.slate;

  return (
    <div className={cn('rounded-lg border p-3', colors.border, colors.bg)}>
      <div className="flex items-center gap-1.5 mb-2">
        <Icon className={cn('h-3.5 w-3.5', colors.text)} />
        <span className={cn('text-xs font-semibold', colors.text)}>{title}</span>
      </div>
      <p className="text-xs text-slate-300 leading-relaxed">{content}</p>
    </div>
  );
}
