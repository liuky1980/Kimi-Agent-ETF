// ETF数据缓存服务
// 用于存储搜索结果，为各分析框架提供统一数据入口

export interface CacheItem {
  code: string;
  name: string;
  source: string;       // 数据源: akshare | tushare | mock
  updateTime: string;   // 更新时间
  data?: {
    chanlun?: unknown;  // 李彪分析框架数据
    dingchang?: unknown; // 丁昶分析框架数据
    basic?: unknown;    // 基本信息
  };
  status: 'loading' | 'ready' | 'error';
  errorMessage?: string;
}

class DataCache {
  private pool: Map<string, CacheItem> = new Map();
  private listeners: Set<(pool: CacheItem[]) => void> = new Set();

  // 添加或更新缓存项
  add(item: Omit<CacheItem, 'status'> & { status?: CacheItem['status'] }): CacheItem {
    const fullItem: CacheItem = {
      ...item,
      status: item.status || 'ready',
    };
    this.pool.set(item.code, fullItem);
    this.notify();
    return fullItem;
  }

  // 获取单个缓存项
  get(code: string): CacheItem | undefined {
    return this.pool.get(code);
  }

  // 获取全部缓存项（按添加顺序）
  getAll(): CacheItem[] {
    return Array.from(this.pool.values());
  }

  // 获取最新的缓存项code
  getLatestCode(): string | undefined {
    const all = this.getAll();
    return all.length > 0 ? all[all.length - 1].code : undefined;
  }

  // 更新数据状态
  updateStatus(code: string, status: CacheItem['status'], errorMessage?: string): void {
    const item = this.pool.get(code);
    if (item) {
      item.status = status;
      if (errorMessage) item.errorMessage = errorMessage;
      this.pool.set(code, item);
      this.notify();
    }
  }

  // 更新分析数据
  updateData(code: string, key: 'chanlun' | 'dingchang' | 'basic', data: unknown): void {
    const item = this.pool.get(code);
    if (item) {
      if (!item.data) item.data = {};
      item.data[key] = data;
      this.pool.set(code, item);
      this.notify();
    }
  }

  // 检查数据是否存在
  has(code: string): boolean {
    return this.pool.has(code);
  }

  // 检查特定分析数据是否存在
  hasData(code: string, key: 'chanlun' | 'dingchang' | 'basic'): boolean {
    const item = this.pool.get(code);
    return !!item?.data?.[key];
  }

  // 清空缓存
  clear(): void {
    this.pool.clear();
    this.notify();
  }

  // 订阅缓存变化（用于React组件响应式更新）
  subscribe(listener: (pool: CacheItem[]) => void): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  private notify(): void {
    const all = this.getAll();
    this.listeners.forEach(fn => fn(all));
  }
}

export const dataCache = new DataCache();
