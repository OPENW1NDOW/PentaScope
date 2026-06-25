'use client'

import { create } from 'zustand'
import type { AnalysisResponse } from '@/types'

interface AnalysisState {
  lastResponse: AnalysisResponse | null
  lastTraceId: string | null
  isAnalyzing: boolean
  startAnalysis: (traceId: string) => void
  setResponse: (response: AnalysisResponse) => void
  reset: () => void
}

export const useAnalysis = create<AnalysisState>((set) => ({
  lastResponse: null,
  lastTraceId: null,
  isAnalyzing: false,

  startAnalysis: (traceId: string) =>
    set({ lastTraceId: traceId, isAnalyzing: true, lastResponse: null }),

  setResponse: (response: AnalysisResponse) =>
    set({ lastResponse: response, isAnalyzing: false }),

  reset: () =>
    set({ lastResponse: null, lastTraceId: null, isAnalyzing: false }),
}))
