'use client'

import useSWR from 'swr'
import { api } from '@/lib/api'
import type { TracesResponse } from '@/types'

export interface TraceFilters {
  scenario?: string
  status?: string
}

export function useTraces(page = 1, pageSize = 20, filters?: TraceFilters) {
  const { data, error, isLoading, mutate } = useSWR<TracesResponse>(
    ['traces', page, pageSize, filters?.scenario ?? '', filters?.status ?? ''],
    () => api.getTraces(page, pageSize, filters),
    {
      refreshInterval: 30000,
      revalidateOnFocus: true,
    }
  )

  return {
    traces: data?.traces ?? [],
    total: data?.total ?? 0,
    isLoading,
    error,
    mutate,
  }
}
