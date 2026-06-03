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

// ── useApi: low-level fetch with state ──
export function useApi<T>(
  fetcher: () => Promise<T>,
  options: UseApiOptions = {},
) {
  const { immediate = true, pollInterval = 0 } = options
  const [state, setState] = useState<{
    data: T | null
    source: DataSource
    error: string | null
  }>({
    data: null,
    source: 'loading',
    error: null,
  })
  const mounted = useRef(true)

  const execute = useCallback(async () => {
    if (!mounted.current) return
    setState((s) => ({ ...s, source: 'loading' }))

    try {
      const data = await fetcher()
      if (mounted.current) {
        setState({ data, source: 'live', error: null })
      }
    } catch (err: any) {
      if (mounted.current) {
        setState((s) => ({ ...s, source: s.data ? 'fallback' : 'fallback', error: err.message }))
      }
    }
  }, [fetcher])

  useEffect(() => {
    mounted.current = true
    if (immediate) execute()

    // Polling
    let pollTimer: ReturnType<typeof setInterval>
    if (pollInterval > 0) {
      pollTimer = setInterval(execute, pollInterval)
    }

    return () => {
      mounted.current = false
      clearInterval(pollTimer)
    }
  }, [execute, immediate, pollInterval])

  return { ...state, refetch: execute }
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
  const { backendReady } = useWarmupContext()
  const [state, setState] = useState<UseApiState<T>>({
    data: fallbackData,
    source: 'fallback',
    error: null,
  })
  const hasFetchedLive = useRef(false)
  const mounted = useRef(true)

  const tryFetch = useCallback(async () => {
    if (!mounted.current) return

    setState((s) => ({ ...s, source: 'loading' }))

    try {
      const data = await fetcher()
      if (mounted.current) {
        hasFetchedLive.current = true
        setState({ data, source: 'live', error: null })
      }
    } catch (err: any) {
      // Keep fallback data, just mark the error
      if (mounted.current) {
        setState((s) => ({ ...s, source: 'fallback', error: err.message }))
      }
    }
  }, [fetcher])

  // Initial fetch attempt
  useEffect(() => {
    mounted.current = true
    // Always try to fetch — if it works, great. If not, we already have fallback.
    tryFetch()
    return () => { mounted.current = false }
  }, [tryFetch])

  // ── CRITICAL FIX: Auto-refetch when backend comes online ──
  // When the warmup sequence succeeds, backendReady flips to true.
  // At that moment, ALL components should refetch for live data.
  useEffect(() => {
    if (backendReady && !hasFetchedLive.current) {
      tryFetch()
    }
  }, [backendReady, tryFetch])

  return state
}

// ── usePoll: polling for live-updating data ──
export function usePoll<T>(
  fetcher: () => Promise<T>,
  fallbackData: T,
  intervalMs: number,
) {
  const state = useApiWithFallback(fetcher, fallbackData, {
    pollInterval: intervalMs,
  })
  return state
}
