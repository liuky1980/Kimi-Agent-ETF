import { useState, useCallback, useEffect } from 'react';
import { popularETFs, recentAnalyses } from '@/data/mockData';
import { dataCache, type CacheItem } from '@/services/dataCache';
import type { Tab } from '@/components/Navbar';
import { cn } from '@/lib/utils';
import {
  Search,
  TrendingUp,
  LineChart,
  BarChart3,
  FileText,
  Clock,
  ArrowRight,
  Zap,
  Shield,
  Layers,
} from 'lucide-react';

interface HomeProps {
  onNavigate: (tab: Tab, etfCode?: string) => void;
}

export default function Home({ onNavigate }: HomeProps) {
  const [searchCode, setSearchCode] = useState('');
  const [searchPool, setSearchPool] = useState<CacheItem[]>([]);

  useEffect(() => {
    const unsubscribe = dataCache.subscribe((pool) => {
      setSearchPool(pool);
    });
    setSearchPool(dataCache.getAll()); // 初始同步
    return unsubscribe;
  }, []);

  const addToPool = useCallback((item: Omit<CacheItem, 'status'> & { status?: CacheItem['status'] }) => {
    dataCache.add(item);
  }, []);

  const handleSearch = () => {
    const code = searchCode.trim();
    if (code) {
      const etf = popularETFs.find(e => e.code === code);
      const name = etf?.name || code;

      addToPool({
        code,
        name,
        source: 'akshare',
        updateTime: new Date().toLocaleString()
      });

      onNavigate('overview', code);
    }
  };

  return (
    <div className="space-y-8">
      {/* Hero Section */}
      <section className="relative overflow-hidden rounded-2xl border border-slate-800 bg-slate-900/80 p-8 sm:p-12">
        <div className="absolute inset-0 bg-emerald-500/5" />
        <div className="relative">
          <div className="flex items-center gap-3 mb-4">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-500/20">
              <Zap className="h-6 w-6 text-emerald-400" />
            </div>
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-sky-500/20">
              <Shield className="h-6 w-6 text-sky-400" />
            </div>
          </div>
          <h1 className="text-3xl sm:text-4xl font-bold text-slate-100 mb-3 tracking-tight">
            ETF多框架分析系统
          </h1>
          <p className="text-base text-slate-400 max-w-2xl mb-6 leading-relaxed">
            融合李彪分析框架与丁昶分析框架，提供多维度的ETF投资分析工具。
            从趋势结构到价值评分，辅助投资决策。
          </p>

          {/* Search Bar */}
          <div className="flex flex-col sm:flex-row gap-3 max-w-lg">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-500" />
              <input
                type="text"
                placeholder="输入ETF代码 (如: 510300)"
                value={searchCode}
                onChange={(e) => setSearchCode(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                className="w-full rounded-lg border border-slate-700 bg-slate-800/80 py-2.5 pl-10 pr-4 text-sm text-slate-200 placeholder:text-slate-500 focus:border-emerald-500/50 focus:outline-none focus:ring-1 focus:ring-emerald-500/30 transition-colors"
              />
            </div>
            <button
              onClick={handleSearch}
              className="flex items-center justify-center gap-2 rounded-lg bg-emerald-500/15 border border-emerald-500/30 px-5 py-2.5 text-sm font-medium text-emerald-400 hover:bg-emerald-500/25 transition-colors"
            >
              <TrendingUp className="h-4 w-4" />
              开始分析
            </button>
          </div>
        </div>
      </section>

      {/* Search Pool */}
      <section>
        <h2 className="text-lg font-semibold text-slate-200 mb-4 flex items-center gap-2">
          <Layers className="h-5 w-5 text-amber-400" />
          标的池
        </h2>
        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5">
          {searchPool.length === 0 ? (
            <div className="text-center py-8">
              <Search className="h-8 w-8 text-slate-600 mx-auto mb-3" />
              <p className="text-sm text-slate-500">搜索ETF代码，结果将实时更新至此</p>
            </div>
          ) : (
            <div className="space-y-2">
              {searchPool.map((item) => (
                <button
                  key={item.code}
                  onClick={() => onNavigate('overview', item.code)}
                  className={cn(
                    'w-full flex items-center justify-between rounded-lg border px-4 py-3 text-sm transition-all',
                    'border-slate-800 bg-slate-800/40 text-slate-300 hover:border-amber-500/30 hover:bg-slate-800/60'
                  )}
                >
                  <div className="flex items-center gap-3">
                    <span className="font-mono text-xs font-bold text-amber-400">{item.code}</span>
                    <span className="text-sm text-slate-200">{item.name}</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="rounded-full bg-slate-700 px-2 py-0.5 text-[11px] text-slate-400">
                      {item.source}
                    </span>
                    <span className="text-[11px] text-slate-500">{item.updateTime}</span>
                    <ArrowRight className="h-3.5 w-3.5 text-slate-500" />
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      </section>

      {/* Quick Access ETFs */}
      <section>
        <h2 className="text-lg font-semibold text-slate-200 mb-4 flex items-center gap-2">
          <LineChart className="h-5 w-5 text-emerald-400" />
          热门ETF快速入口
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {popularETFs.map((etf) => (
            <button
              key={etf.code}
              onClick={() => onNavigate('overview', etf.code)}
              className="group flex items-center justify-between rounded-xl border border-slate-800 bg-slate-900/60 p-4 hover:border-emerald-500/30 hover:bg-slate-800/60 transition-all"
            >
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-slate-800 group-hover:bg-emerald-500/15 transition-colors">
                  <span className="text-xs font-mono font-bold text-slate-300 group-hover:text-emerald-400">
                    {etf.code.slice(0, 3)}
                  </span>
                </div>
                <div className="text-left">
                  <div className="text-sm font-medium text-slate-200">{etf.name}</div>
                  <div className="text-xs text-slate-500 font-mono">{etf.code}</div>
                </div>
              </div>
              <ArrowRight className="h-4 w-4 text-slate-600 group-hover:text-emerald-400 transition-colors" />
            </button>
          ))}
        </div>
      </section>

      {/* Framework Cards */}
      <section>
        <h2 className="text-lg font-semibold text-slate-200 mb-4 flex items-center gap-2">
          <BarChart3 className="h-5 w-5 text-sky-400" />
          多框架分析体系
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-6">
            <div className="flex items-center gap-3 mb-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-emerald-500/15">
                <LineChart className="h-5 w-5 text-emerald-400" />
              </div>
              <div>
                <h3 className="text-base font-semibold text-slate-200">李彪分析框架</h3>
                <p className="text-xs text-slate-500">Libiao Analysis Framework</p>
              </div>
            </div>
            <p className="text-sm text-slate-400 leading-relaxed mb-3">
              基于李彪分析框架，通过分型、笔、中枢、线段的层次结构识别，
              判断趋势位置，检测背驰信号，定位三类买卖点。
            </p>
            <div className="flex flex-wrap gap-2">
              {['趋势判断', '背驰检测', '买卖点识别', '多周期共振'].map((tag) => (
                <span
                  key={tag}
                  className="rounded-full bg-slate-800 px-2.5 py-1 text-[11px] text-slate-400 border border-slate-700/50"
                >
                  {tag}
                </span>
              ))}
            </div>
          </div>

          <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-6">
            <div className="flex items-center gap-3 mb-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-sky-500/15">
                <BarChart3 className="h-5 w-5 text-sky-400" />
              </div>
              <div>
                <h3 className="text-base font-semibold text-slate-200">丁昶分析框架</h3>
                <p className="text-xs text-slate-500">Ding Chang Analysis Framework</p>
              </div>
            </div>
            <p className="text-sm text-slate-400 leading-relaxed mb-3">
              五维评分模型：股息质量(30%)、估值安全(25%)、盈利质地(20%)、
              资金驱动(15%)、宏观适配(10%)，综合评定投资价值。
            </p>
            <div className="flex flex-wrap gap-2">
              {['股息质量', '估值安全', '盈利质地', '资金驱动', '宏观适配'].map((tag) => (
                <span
                  key={tag}
                  className="rounded-full bg-slate-800 px-2.5 py-1 text-[11px] text-slate-400 border border-slate-700/50"
                >
                  {tag}
                </span>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* Recent Analyses */}
      <section>
        <h2 className="text-lg font-semibold text-slate-200 mb-4 flex items-center gap-2">
          <Clock className="h-5 w-5 text-amber-400" />
          最近分析记录
        </h2>
        <div className="rounded-xl border border-slate-800 bg-slate-900/60 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-800">
                  <th className="px-4 py-3 text-left text-xs font-medium text-slate-500">ETF名称</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-slate-500">代码</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-slate-500">分析类型</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-slate-500">日期</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-slate-500">操作</th>
                </tr>
              </thead>
              <tbody>
                {recentAnalyses.map((item, idx) => (
                  <tr
                    key={idx}
                    className="border-b border-slate-800/50 last:border-0 hover:bg-slate-800/40 transition-colors"
                  >
                    <td className="px-4 py-3 text-slate-200">{item.name}</td>
                    <td className="px-4 py-3 font-mono text-slate-400">{item.code}</td>
                    <td className="px-4 py-3">
                      <span
                        className={cn(
                          'inline-flex rounded-full px-2 py-0.5 text-[11px] font-medium',
                          item.type === '李彪分析框架' && 'bg-emerald-500/10 text-emerald-400',
                          item.type === '丁昶分析框架' && 'bg-sky-500/10 text-sky-400',
                          item.type === '多框架综合' && 'bg-amber-500/10 text-amber-400'
                        )}
                      >
                        {item.type}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-slate-500">{item.date}</td>
                    <td className="px-4 py-3 text-right">
                      <button
                        onClick={() => onNavigate('overview', item.code)}
                        className="text-xs text-emerald-400 hover:text-emerald-300 transition-colors flex items-center gap-1 ml-auto"
                      >
                        <FileText className="h-3 w-3" />
                        查看报告
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>
    </div>
  );
}
