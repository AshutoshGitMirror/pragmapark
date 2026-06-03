/**
 * WarmupContext — Shared backend state for the entire app.
 *
 * Problem: Every component was fetching independently, catching errors silently,
 * and falling back to hardcoded data. There was no shared signal for "backend is ready."
 *
 * Solution: A React Context that:
 * 1. Tracks backend status (idle / warming / ready / failed)
 * 2. Provides a global "backendReady" boolean
 * 3. Lets components register for auto-refetch when backend comes online
 * 4. Renders the WarmupOverlay as a visual layer WITHOUT blocking content
 */

import { createContext, useContext, useState, useCallback, useRef, useEffect, type ReactNode } from 'react'
import { fetchHealth, login, setJwt } from '../api/client'

export type BackendStatus = 'idle' | 'connecting' | 'warming' | 'ready' | 'failed'

interface WarmupContextValue {
  status: BackendStatus
  message: string
  elapsed: number
  backendReady: boolean      // true when status === 'ready'
  backendFailed: boolean     // true when status === 'failed'
  // Call this when a component successfully fetches live data
  // (hooks call this internally — components don't need to)
  markLive: () => void
}

const WarmupContext = createContext<WarmupContextValue>({
  status: 'idle',
  message: 'Initializing...',
  elapsed: 0,
  backendReady: false,
  backendFailed: false,
  markLive: () => {},
})

export function useWarmupContext() {
  return useContext(WarmupContext)
}

// ── Constants ──
const HEALTH_POLL_INTERVAL_MS = 8000   // Poll every 8s (was 20s — too slow for UX)
const HEALTH_MAX_ATTEMPTS = 75          // 75 × 8s = 10 min max (Render cold-start)
const AUTH_TIMEOUT_MS = 10000

interface Props {
  children: ReactNode
}

export function WarmupProvider({ children }: Props) {
  const [status, setStatus] = useState<BackendStatus>('idle')
  const [message, setMessage] = useState('Initializing...')
  const [elapsed, setElapsed] = useState(0)
  const startTimeRef = useRef(Date.now())
  const cancelledRef = useRef(false)

  // ── Elapsed timer ──
  useEffect(() => {
    const interval = setInterval(() => {
      if (!cancelledRef.current) {
        setElapsed(Date.now() - startTimeRef.current)
      }
    }, 1000)
    return () => clearInterval(interval)
  }, [])

  // ── Main warmup sequence ──
  useEffect(() => {
    let attempt = 0
    let pollTimer: ReturnType<typeof setTimeout>

    async function tryConnect() {
      while (attempt < HEALTH_MAX_ATTEMPTS && !cancelledRef.current) {
        attempt++
        setStatus('connecting')
        setMessage(`Connecting to Pragma system... (attempt ${attempt}/${HEALTH_MAX_ATTEMPTS})`)

        try {
          const health = await fetchHealth()
          // Backend responded — check if it's actually healthy
          if (health.status === 'healthy' || health.dependencies?.database) {
            // ── Step 2: Authenticate ──
            setStatus('warming')
            setMessage('Authenticating...')
            try {
              const token = await login()
              setJwt(token)
            } catch {
              // Auth failed but health passed — backend is warming, not ready
              setMessage('Backend warming — retrying auth...')
              await sleep(HEALTH_POLL_INTERVAL_MS)
              continue
            }

            if (!cancelledRef.current) {
              setStatus('ready')
              setMessage('System ready')
            }
            return // Success! Exit the loop.
          }
        } catch {
          // Expected: 503 during cold-start, network error, etc.
          setMessage(
            attempt < 3
              ? 'Backend is cold-starting on Render (up to 10 min)...'
              : `Still waiting... Render free tier cold-start can take several minutes. (${Math.round(elapsed / 1000)}s elapsed)`
          )
        }

        // Wait before next attempt
        await sleep(HEALTH_POLL_INTERVAL_MS)
      }

      // Exhausted all attempts
      if (!cancelledRef.current) {
        setStatus('failed')
        setMessage('Could not connect to backend — using simulation data')
      }
    }

    tryConnect()

    return () => {
      cancelledRef.current = true
      clearTimeout(pollTimer)
    }
  }, [])

  const backendReady = status === 'ready'
  const backendFailed = status === 'failed'

  const markLive = useCallback(() => {
    if (status !== 'ready') {
      setStatus('ready')
      setMessage('System ready (detected via live fetch)')
    }
  }, [status])

  return (
    <WarmupContext.Provider
      value={{
        status,
        message,
        elapsed,
        backendReady,
        backendFailed,
        markLive,
      }}
    >
      {children}
    </WarmupContext.Provider>
  )
}

function sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms))
}
