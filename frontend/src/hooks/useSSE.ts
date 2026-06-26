'use client'

import { useEffect, useState, useCallback, useRef } from 'react'
import { api } from '@/lib/api'

export interface SSEEvent {
  event: string
  data: Record<string, unknown>
}

export interface UseSSEReturn {
  status: 'connecting' | 'connected' | 'disconnected' | 'error'
  currentNode: string | null
  completedNodes: string[]
  logs: SSEEvent[]
  error: string | null
}

export function useSSE(traceId: string | null): UseSSEReturn {
  const [status, setStatus] = useState<UseSSEReturn['status']>('disconnected')
  const [currentNode, setCurrentNode] = useState<string | null>(null)
  const [completedNodes, setCompletedNodes] = useState<string[]>([])
  const [logs, setLogs] = useState<SSEEvent[]>([])
  const [error, setError] = useState<string | null>(null)
  const eventSourceRef = useRef<EventSource | null>(null)
  const reconnectTimerRef = useRef<NodeJS.Timeout | null>(null)
  const reconnectCountRef = useRef(0)
  const connectRef = useRef<() => void>(() => undefined)

  const cleanup = useCallback(() => {
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current)
      reconnectTimerRef.current = null
    }
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
      eventSourceRef.current = null
    }
  }, [])

  const connect = useCallback(() => {
    if (!traceId) return

    cleanup()
    setStatus('connecting')

    const url = api.sseUrl(traceId)
    const es = new EventSource(url)
    eventSourceRef.current = es

    es.onopen = () => {
      setStatus('connected')
      setError(null)
      reconnectCountRef.current = 0
    }

    const handleEvent = (eventName: string) => {
      return (e: MessageEvent) => {
        try {
          const data = JSON.parse(e.data)
          const event: SSEEvent = { event: eventName, data }
          setLogs(prev => [...prev, event])

          switch (eventName) {
            case 'node_start':
              setCurrentNode(data.node as string)
              break
            case 'node_complete':
              setCompletedNodes(prev => [...prev, data.node as string])
              setCurrentNode(null)
              break
            case 'node_error':
              setError(data.error as string || `Node ${data.node} failed`)
              setCurrentNode(null)
              break
            case 'analysis_complete':
              setStatus('disconnected')
              es.close()
              break
            case 'analysis_failed':
              setError(data.error as string || 'Analysis failed')
              setStatus('disconnected')
              es.close()
              break
          }
        } catch {
          // malformed event data, ignore
        }
      }
    }

    const eventTypes = ['node_start', 'node_complete', 'node_error', 'analysis_complete', 'analysis_failed']
    for (const eventType of eventTypes) {
      es.addEventListener(eventType, handleEvent(eventType))
    }

    es.onerror = () => {
      es.close()
      setStatus('error')

      // Auto-reconnect with exponential backoff
      const maxReconnects = 5
      if (reconnectCountRef.current < maxReconnects) {
        const delay = Math.min(1000 * Math.pow(2, reconnectCountRef.current), 30000)
        reconnectCountRef.current++
        reconnectTimerRef.current = setTimeout(() => {
          connectRef.current()
        }, delay)
      } else {
        setError('Connection lost. Please refresh the page.')
      }
    }
  }, [traceId, cleanup])

  useEffect(() => {
    connectRef.current = connect
  }, [connect])

  useEffect(() => {
    void Promise.resolve().then(connect)
    return cleanup
  }, [connect, cleanup])

  return { status, currentNode, completedNodes, logs, error }
}
