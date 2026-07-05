import type {
  AnalysisRequest,
  AnalysisResponse,
  PickScenarioResponse,
  TracesResponse,
  TraceResponse,
} from '@/types'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1'

/** API 错误：携带 HTTP 状态码与后端 detail 消息 */
export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

/** 统一请求入口：res.ok 判断 + FastAPI detail 解析 + JSON 反序列化 */
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, init)
  if (!res.ok) {
    const body = await res.json().catch(() => null)
    const detail =
      body && typeof body.detail === 'string' ? body.detail : `HTTP ${res.status}`
    throw new ApiError(res.status, detail)
  }
  return res.json() as Promise<T>
}

function postJson<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

export const api = {
  analyze: (input: AnalysisRequest): Promise<AnalysisResponse> =>
    postJson('/analyze', input),

  pickScenario: (userText: string): Promise<PickScenarioResponse> =>
    postJson('/pick-scenario', { user_text: userText }),

  getTrace: (traceId: string): Promise<TraceResponse> =>
    request(`/trace/${traceId}`),

  getTraces: (
    page = 1,
    pageSize = 20,
    filters?: { scenario?: string; status?: string },
  ): Promise<TracesResponse> => {
    const params = new URLSearchParams({
      page: String(page),
      page_size: String(pageSize),
    })
    if (filters?.scenario) params.set('scenario', filters.scenario)
    if (filters?.status) params.set('status', filters.status)
    return request(`/traces?${params.toString()}`)
  },

  exportUrl: (traceId: string, format: 'md' | 'html'): string =>
    `${API_BASE}/trace/${traceId}/export?format=${format}`,

  sseUrl: (traceId: string): string =>
    `${API_BASE}/analyze/${traceId}/stream`,
}

export type { AnalysisResponse, PickScenarioResponse, TracesResponse, TraceResponse }
