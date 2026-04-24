// ETF分析系统 API 服务
// 调用后端接口获取真实数据

const API_BASE = import.meta.env.VITE_API_BASE || '/etf/api/v1';

interface ETFAnalysisResponse {
  success: boolean;
  message: string;
  chanlun: Record<string, unknown>;
  dingchang: Record<string, unknown>;
  summary: string;
  action: string;
  dual_signal: string;
  confidence: number;
  processing_time_ms: number;
  data_source: string;
  analysis_time: string;
}

interface ETFListResponse {
  count: number;
  etfs: Array<{
    code: string;
    name: string;
    price: number;
    change_pct: number;
    volume: number;
    category: string;
  }>;
  data_source?: string;
  update_time?: string;
}

interface ETFSimpleInfo {
  code: string;
  name: string;
  price: number;
  change_pct: number;
  volume: number;
  category: string;
}

class ETFApiService {
  private baseUrl: string;

  constructor(baseUrl: string = API_BASE) {
    this.baseUrl = baseUrl;
  }

  private async request<T>(path: string, options?: RequestInit): Promise<T> {
    const resp = await fetch(`${this.baseUrl}${path}`, {
      headers: { 'Content-Type': 'application/json' },
      ...options,
    });
    if (!resp.ok) {
      const err = await resp.text();
      throw new Error(`API ${path} 失败: ${resp.status} ${err}`);
    }
    return resp.json() as T;
  }

  /** 获取ETF列表 */
  async getETFList(limit: number = 1000): Promise<ETFListResponse> {
    return this.request<ETFListResponse>(`/etf/list?limit=${limit}`);
  }

  /** 获取ETF基本信息 */
  async getETFBasic(code: string): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>(`/etf/${code}/basic`);
  }

  /** 执行多框架综合分析 */
  async analyzeETF(code: string, includeMinute: boolean = true): Promise<ETFAnalysisResponse> {
    return this.request<ETFAnalysisResponse>('/analyze', {
      method: 'POST',
      body: JSON.stringify({
        etf_code: code,
        timeframe: 'daily',
        include_minute: includeMinute,
        analysis_depth: 'full',
      }),
    });
  }

  /** 获取李彪分析框架分析 */
  async getChanlunAnalysis(code: string): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>(`/etf/${code}/chanlun`);
  }

  /** 获取丁昶分析框架分析 */
  async getDingChangAnalysis(code: string): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>(`/etf/${code}/dingchang`);
  }

  /** 获取多周期数据 */
  async getMultiTimeframe(code: string): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>(`/etf/${code}/multi-timeframe`);
  }

  /** 健康检查 */
  async healthCheck(): Promise<{ status: string }> {
    return this.request<{ status: string }>('/health');
  }
}

export const api = new ETFApiService();
export type { ETFAnalysisResponse, ETFListResponse, ETFSimpleInfo };
