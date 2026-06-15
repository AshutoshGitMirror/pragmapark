import { useState, useEffect, useRef, useCallback } from 'react'
import { useWarmupContext } from '../components/layout/WarmupContext'

export type DataSource = 'loading' | 'live' | 'error'

interface UseApiState<T> {
  data: T
  source: DataSource
  error: string | null
}

interface UseApiOptions {
  immediate?: boolean
  pollInterval?: number
}

export function useApi<T>(
  fetcher: () => Promise<T>,
  options?: UseApiOptions & { initialValue: T },
): { data: T; source: DataSource; error: string | null; refetch: () => void }
export function useApi<T>(
  fetcher: () => Promise<T>,
  options?: UseApiOptions,
): { data: T | null; source: DataSource; error: string | null; refetch: () => void }
export function useApi<T>(
  fetcher: () => Promise<T>,
  options: UseApiOptions & { initialValue?: T } = {},
) {
  const { immediate = true, pollInterval = 0, initialValue } = options
  const { backendReady } = useWarmupContext()
  const [state, setState] = useState<UseApiState<T | null>>({
    data: initialValue ?? null,
    source: 'loading',
    error: null,
  })
  const hasFetchedLive = useRef(false)
  const mounted = useRef(true)
  const fetcherRef = useRef(fetcher)
  fetcherRef.current = fetcher

  const tryFetch = useCallback(async () => {
    if (!mounted.current) return

    setState((s) => ({ ...s, source: 'loading', error: null }))

    try {
      const data = await fetcherRef.current()
      if (mounted.current) {
        hasFetchedLive.current = true
        setState({ data, source: 'live', error: null })
      }
    } catch (err) {
      if (mounted.current) {
        const message = err instanceof Error ? err.message : 'Fetch failed'
        setState({ data: null, source: 'error', error: message })
      }
    }
  }, [])

  useEffect(() => {
    mounted.current = true
    if (immediate) tryFetch()
    let pollTimer: ReturnType<typeof setInterval>
    if (pollInterval > 0) {
      pollTimer = setInterval(tryFetch, pollInterval)
    }
    return () => {
      mounted.current = false
      clearInterval(pollTimer)
    }
  }, [tryFetch, immediate, pollInterval])

  useEffect(() => {
    if (backendReady && !hasFetchedLive.current) {
      tryFetch()
    }
  }, [backendReady, tryFetch])

  return { ...state, refetch: tryFetch }
}
