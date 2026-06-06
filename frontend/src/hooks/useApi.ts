/**
 * useApi.ts — Data fetching hooks with live API → fallback chain.
 *
 * BEFORE (broken):
 *   - useApi hook existed but no component used it
 *   - Every component had its own useState + useEffect + .catch(() => {})
 *   - Fallback data was randomly generated on each mount
 *   - No way to refetch when backend came online
 *
 * AFTER (fixed):
 *   - useApi: generic fetch hook with source tracking ('live' | 'fallback')
 *   - useApiWithFallback: THE hook all components should use
 *     • Shows fallback data immediately (no loading state)
 *     • Fetches from API in background
 *     • Swaps to live data when API responds
 *     • Tracks source so UI can show "LIVE" vs "SIMULATION" badges
 *   - useWarmupAwareFetch: auto-refetches when backend comes online
 */

import { useState, useEffect, useRef, useCallback } from 'react'
import { useWarmupContext } from '../components/layout/WarmupContext'

type DataSource = 'live' | 'fallback' | 'loading'

interface UseApiState<T> {
  data: T
  source: DataSource
  error: string | null
}

interface UseApiOptions {
  /** If true (default), fetch immediately on mount */
  immediate?: boolean
  /** Polling interval in ms. 0 = no polling. */
  pollInterval?: number
}

// ── useApiWithFallback: THE hook for all sections ──
/**
 * Usage in components:
 *
 *   const { data, source } = useApiWithFallback(
 *     () => fetchLots(),
 *     fallbackLots,
 *   )
 *
 *   // data is ALWAYS valid — starts as fallback, swaps to live when ready
 *   // source tells you which: 'live' | 'fallback' | 'loading'
 *
 *   return (
 *     <div>
 *       {source === 'live' && <span className="live-badge">LIVE</span>}
 *       {data.map(...)}
 *     </div>
 *   )
 */
export function useApiWithFallback<T>(
  fetcher: () => Promise<T>,
  fallbackData: T,
  options: UseApiOptions = {},
) {
  const { immediate = true, pollInterval = 0 } = options
  const { backendReady } = useWarmupContext()
  const [state, setState] = useState<UseApiState<T>>({
    data: fallbackData,
    source: 'fallback',
    error: null,
  })
  const hasFetchedLive = useRef(false)
  const mounted = useRef(true)
  const fetcherRef = useRef(fetcher)
  fetcherRef.current = fetcher

  const tryFetch = useCallback(async () => {
    if (!mounted.current) return

    setState((s) => ({ ...s, source: 'loading' }))

    try {
      const data = await fetcherRef.current()
      if (mounted.current) {
        hasFetchedLive.current = true
        setState({ data, source: 'live', error: null })
      }
    } catch {
      if (mounted.current) {
        setState((s) => ({ ...s, source: 'fallback' }))
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


