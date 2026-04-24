import { useState, useEffect, useMemo, useCallback } from 'react';
import { api } from '@/services/api';
import { cn } from '@/lib/utils';
import type { Tab } from '@/components/Navbar';
import {
  Search,
  ListFilter,
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
  ArrowRight,
  TrendingUp,
  TrendingDown,
  Minus,
  Loader2,
  AlertCircle,
  Table2,
} from 'lucide-react';

interface ETFItem {
  code: string;
  name: string;
  price: number;
  change_pct: number;
  volume: number;
  category: string;
}

interface ETFListProps {
  onNavigate: (tab: Tab, etfCode?: string) => void;
}

const PAGE_SIZE = 50;

export default function ETFList({ onNavigate }: ETFListProps) {
  const [allETFs, setAllETFs] = useState<ETFItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [searchText, setSearchText] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string>('全部');
  const [currentPage, setCurrentPage] = useState(1);

  // 加载全量ETF列表
  useEffect(() => {
    let cancelled = false;
    setIsLoading(true);
    setError(null);

    api.getETFList(5000)
      .then((resp) => {
        if (cancelled) return;
        if (resp.etfs && resp.etfs.length > 0) {
          setAllETFs(resp.etfs);
        } else {
          setAllETFs([]);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : '加载失败');
        }
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });

    return () => { cancelled = true; };
  }, []);

  // 提取所有分类
  const categories = useMemo(() => {
    const set = new Set<string>();
    allETFs.forEach((etf) => {
      if (etf.category) set.add(etf.category);
    });
    return ['全部', ...Array.from(set).sort()];
  }, [allETFs]);

  // 筛选+分页
  const filteredETFs = useMemo(() => {
    let result = allETFs;

    // 分类筛选
    if (selectedCategory !== '全部') {
      result = result.filter((etf) => etf.category === selectedCategory);
    }

    // 搜索筛选（代码或名称）
    const keyword = searchText.trim().toLowerCase();
    if (keyword) {
      result = result.filter(
        (etf) =>
          etf.code.toLowerCase().includes(keyword) ||
          etf.name.toLowerCase().includes(keyword)
      );
    }

    return result;
  }, [allETFs, selectedCategory, searchText]);

  const totalPages = Math.max(1, Math.ceil(filteredETFs.length / PAGE_SIZE));
  const safePage = Math.min(currentPage, totalPages);
  const pageETFs = filteredETFs.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE);

  // 搜索或筛选变化时重置到第一页
  useEffect(() => {
    setCurrentPage(1);
  }, [searchText, selectedCategory]);

  const handleETFClick = useCallback((code: string) => {
    onNavigate('overview', code);
  }, [onNavigate]);

  return (
    <div className="space-y-6">
      {/* 页面标题 */}
      <section className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-500/15">
            <Table2 className="h-5 w-5 text-emerald-400" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-slate-100 tracking-tight">
              全市场ETF列表
            </h1>
            <p className="text-xs text-slate-500">
              共 {filteredETFs.length} 只ETF（全市场 {allETFs.length} 只）
            </p>
          </div>
        </div>
      </section>

      {/* 搜索与筛选 */}
      <section className="flex flex-col lg:flex-row gap-4">
        {/* 搜索框 */}
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-500" />
          <input
            type="text"
            placeholder="搜索ETF代码或名称..."
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            className="w-full rounded-lg border border-slate-700 bg-slate-800/80 py-2.5 pl-10 pr-4 text-sm text-slate-200 placeholder:text-slate-500 focus:border-emerald-500/50 focus:outline-none focus:ring-1 focus:ring-emerald-500/30 transition-colors"
          />
        </div>

        {/* 分类筛选 */}
        <div className="flex items-center gap-2 overflow-x-auto pb-1 lg:pb-0">
          <ListFilter className="h-4 w-4 text-slate-500 shrink-0" />
          {categories.map((cat) => (
            <button
              key={cat}
              onClick={() => setSelectedCategory(cat)}
              className={cn(
                'shrink-0 rounded-md px-3 py-1.5 text-xs font-medium transition-all',
                selectedCategory === cat
                  ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30'
                  : 'bg-slate-800/60 text-slate-400 border border-slate-700/50 hover:bg-slate-800 hover:text-slate-200'
              )}
            >
              {cat}
            </button>
          ))}
        </div>
      </section>

      {/* 加载状态 */}
      {isLoading && (
        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-12 text-center">
          <Loader2 className="h-8 w-8 text-emerald-400 mx-auto mb-3 animate-spin" />
          <p className="text-sm text-slate-400">正在加载全市场ETF数据...</p>
        </div>
      )}

      {/* 错误状态 */}
      {error && !isLoading && (
        <div className="rounded-xl border border-rose-800/50 bg-rose-900/10 p-8 text-center">
          <AlertCircle className="h-8 w-8 text-rose-400 mx-auto mb-3" />
          <p className="text-sm text-rose-300 mb-1">加载失败</p>
          <p className="text-xs text-rose-400/70">{error}</p>
        </div>
      )}

      {/* ETF列表表格 */}
      {!isLoading && !error && (
        <>
          <div className="rounded-xl border border-slate-800 bg-slate-900/60 overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-800 bg-slate-900/80">
                    <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 w-28">ETF代码</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-slate-500">名称</th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-slate-500 w-24">最新价</th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-slate-500 w-24">涨跌幅</th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-slate-500 w-28">成交量</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 w-32">类型</th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-slate-500 w-20">操作</th>
                  </tr>
                </thead>
                <tbody>
                  {pageETFs.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="px-4 py-12 text-center text-slate-500">
                        <Search className="h-8 w-8 text-slate-600 mx-auto mb-3" />
                        <p className="text-sm">未找到匹配的ETF</p>
                        <p className="text-xs text-slate-600 mt-1">请尝试其他关键词或筛选条件</p>
                      </td>
                    </tr>
                  ) : (
                    pageETFs.map((etf) => (
                      <tr
                        key={etf.code}
                        className="border-b border-slate-800/50 last:border-0 hover:bg-slate-800/40 transition-colors cursor-pointer"
                        onClick={() => handleETFClick(etf.code)}
                      >
                        <td className="px-4 py-3">
                          <span className="font-mono text-xs font-bold text-amber-400">{etf.code}</span>
                        </td>
                        <td className="px-4 py-3 text-slate-200">{etf.name}</td>
                        <td className="px-4 py-3 text-right font-mono text-slate-300">
                          {etf.price > 0 ? etf.price.toFixed(3) : '--'}
                        </td>
                        <td className="px-4 py-3 text-right">
                          <span
                            className={cn(
                              'inline-flex items-center gap-0.5 text-xs font-medium',
                              etf.change_pct > 0 && 'text-red-400',
                              etf.change_pct < 0 && 'text-green-400',
                              etf.change_pct === 0 && 'text-slate-400'
                            )}
                          >
                            {etf.change_pct > 0 ? (
                              <TrendingUp className="h-3 w-3" />
                            ) : etf.change_pct < 0 ? (
                              <TrendingDown className="h-3 w-3" />
                            ) : (
                              <Minus className="h-3 w-3" />
                            )}
                            {etf.change_pct > 0 ? '+' : ''}
                            {etf.change_pct.toFixed(2)}%
                          </span>
                        </td>
                        <td className="px-4 py-3 text-right text-xs text-slate-400 font-mono">
                          {etf.volume > 0 ? formatVolume(etf.volume) : '--'}
                        </td>
                        <td className="px-4 py-3">
                          <span className="rounded-full bg-slate-800 px-2 py-0.5 text-[11px] text-slate-400 border border-slate-700/50">
                            {etf.category || '--'}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-right">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleETFClick(etf.code);
                            }}
                            className="inline-flex items-center gap-1 text-xs text-emerald-400 hover:text-emerald-300 transition-colors"
                          >
                            分析
                            <ArrowRight className="h-3 w-3" />
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* 分页控制 */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between rounded-xl border border-slate-800 bg-slate-900/60 px-4 py-3">
              <div className="text-xs text-slate-500">
                第 {safePage} / {totalPages} 页，共 {filteredETFs.length} 条
              </div>
              <div className="flex items-center gap-1">
                <button
                  onClick={() => setCurrentPage(1)}
                  disabled={safePage <= 1}
                  className="p-1.5 rounded-md text-slate-400 hover:bg-slate-800 hover:text-slate-200 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                >
                  <ChevronsLeft className="h-4 w-4" />
                </button>
                <button
                  onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                  disabled={safePage <= 1}
                  className="p-1.5 rounded-md text-slate-400 hover:bg-slate-800 hover:text-slate-200 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                >
                  <ChevronLeft className="h-4 w-4" />
                </button>

                {/* 页码按钮（简化：只显示邻近页） */}
                <div className="flex items-center gap-1 mx-2">
                  {Array.from({ length: totalPages }, (_, i) => i + 1)
                    .filter((p) => {
                      // 只显示当前页附近的页码
                      const dist = Math.abs(p - safePage);
                      return dist <= 2 || p === 1 || p === totalPages;
                    })
                    .reduce<(number | string)[]>((acc, p, idx, arr) => {
                      if (idx > 0 && typeof arr[idx - 1] === 'number' && p - (arr[idx - 1] as number) > 1) {
                        acc.push('...');
                      }
                      acc.push(p);
                      return acc;
                    }, [])
                    .map((item, idx) =>
                      item === '...' ? (
                        <span key={`ellipsis-${idx}`} className="px-2 text-xs text-slate-600">
                          ...
                        </span>
                      ) : (
                        <button
                          key={item}
                          onClick={() => setCurrentPage(item as number)}
                          className={cn(
                            'min-w-[28px] h-7 rounded-md text-xs font-medium transition-colors',
                            safePage === item
                              ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30'
                              : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'
                          )}
                        >
                          {item}
                        </button>
                      )
                    )}
                </div>

                <button
                  onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                  disabled={safePage >= totalPages}
                  className="p-1.5 rounded-md text-slate-400 hover:bg-slate-800 hover:text-slate-200 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                >
                  <ChevronRight className="h-4 w-4" />
                </button>
                <button
                  onClick={() => setCurrentPage(totalPages)}
                  disabled={safePage >= totalPages}
                  className="p-1.5 rounded-md text-slate-400 hover:bg-slate-800 hover:text-slate-200 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                >
                  <ChevronsRight className="h-4 w-4" />
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

/** 格式化成交量 */ function formatVolume(vol: number): string {
  if (vol >= 1e8) return (vol / 1e8).toFixed(1) + '亿';
  if (vol >= 1e4) return (vol / 1e4).toFixed(1) + '万';
  return vol.toFixed(0);
}
