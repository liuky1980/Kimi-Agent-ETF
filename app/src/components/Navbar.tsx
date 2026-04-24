import { cn } from '@/lib/utils';
import { TrendingUp, LineChart, BarChart3, FileText, Home } from 'lucide-react';

export type Tab = 'home' | 'overview' | 'chanlun' | 'dingchang';

interface NavbarProps {
  activeTab: Tab;
  onTabChange: (tab: Tab) => void;
}

const navItems: Array<{ key: Tab; label: string; icon: typeof Home }> = [
  { key: 'home', label: '首页', icon: Home },
  { key: 'overview', label: '多框架综合', icon: FileText },
  { key: 'chanlun', label: '李彪分析框架', icon: LineChart },
  { key: 'dingchang', label: '丁昶分析框架', icon: BarChart3 },
];

export default function Navbar({ activeTab, onTabChange }: NavbarProps) {
  return (
    <nav className="fixed top-0 left-0 right-0 z-50 border-b border-slate-800 bg-slate-950/90 backdrop-blur-md">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="flex h-16 items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-500/20">
              <TrendingUp className="h-5 w-5 text-emerald-400" />
            </div>
            <span className="text-lg font-bold text-slate-100 tracking-tight">
              ETF多框架分析系统
            </span>
          </div>

          <div className="flex items-center gap-1 rounded-lg bg-slate-900/60 p-1">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = activeTab === item.key;
              return (
                <button
                  key={item.key}
                  onClick={() => onTabChange(item.key)}
                  className={cn(
                    'flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-all duration-200',
                    isActive
                      ? 'bg-emerald-500/15 text-emerald-400 shadow-sm'
                      : 'text-slate-400 hover:bg-slate-800/60 hover:text-slate-200'
                  )}
                >
                  <Icon className="h-4 w-4" />
                  <span className="hidden sm:inline">{item.label}</span>
                </button>
              );
            })}
          </div>
        </div>
      </div>
    </nav>
  );
}
