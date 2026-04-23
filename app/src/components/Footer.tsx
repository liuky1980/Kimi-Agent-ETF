import { TrendingUp, Github, Mail } from 'lucide-react';

export default function Footer() {
  return (
    <footer className="border-t border-slate-800 bg-slate-950 py-6 mt-auto">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <div className="flex h-7 w-7 items-center justify-center rounded-md bg-emerald-500/20">
              <TrendingUp className="h-4 w-4 text-emerald-400" />
            </div>
            <span className="text-sm font-medium text-slate-300">
              ETF双框架智能分析系统
            </span>
          </div>

          <div className="flex items-center gap-6">
            <span className="text-xs text-slate-500">缠论技术分析 + 丁昶评估框架</span>
            <div className="flex items-center gap-3">
              <button className="text-slate-500 hover:text-slate-300 transition-colors">
                <Github className="h-4 w-4" />
              </button>
              <button className="text-slate-500 hover:text-slate-300 transition-colors">
                <Mail className="h-4 w-4" />
              </button>
            </div>
          </div>

          <div className="text-xs text-slate-600">
            数据仅供分析参考，不构成投资建议
          </div>
        </div>
      </div>
    </footer>
  );
}
