import type { AnalysisRequest, AnalysisResponse, PickScenarioResponse, TracesResponse } from '@/types'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1'

export const api = {
  analyze: (input: AnalysisRequest): Promise<Response> =>
    fetch(`${API_BASE}/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(input),
    }),

  pickScenario: (userText: string): Promise<Response> =>
    fetch(`${API_BASE}/pick-scenario`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_text: userText }),
    }),

  getTrace: (traceId: string): Promise<Response> =>
    fetch(`${API_BASE}/trace/${traceId}`),

  getTraces: (page = 1, pageSize = 20): Promise<Response> =>
    fetch(`${API_BASE}/traces?page=${page}&page_size=${pageSize}`),

  exportUrl: (traceId: string, format: 'md' | 'html'): string =>
    `${API_BASE}/trace/${traceId}/export?format=${format}`,

  sseUrl: (traceId: string): string =>
    `${API_BASE}/analyze/${traceId}/stream`,
}

export type { AnalysisResponse, PickScenarioResponse, TracesResponse }
