'use client'

import useSWR from 'swr'
import { api } from '@/lib/api'
import type { TracesResponse } from '@/types'

const fetcher = (url: string) => fetch(url).then(r => r.json())

export function useTraces(page = 1, pageSize = 20) {
  const { data, error, isLoading, mutate } = useSWR<TracesResponse>(
    `/api/v1/traces?page=${page}&page_size=${pageSize}`,
    fetcher,
    {
      refreshInterval: 30000, // 每 30s 自动刷新
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
