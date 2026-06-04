/**
 * WarmupOverlay — Visual overlay that shows during backend warm-up.
 *
 * BEFORE (broken): Fake 6-second setTimeout, auto-dismissed without checking backend.
 * AFTER: Reads from WarmupContext, shows real status, dismisses when backendReady
 *        OR when user clicks "Continue with Simulation Data."
 *
 * Key change: This is a VISUAL overlay only. It sits on top of already-rendered
 * content. It does NOT block React from mounting sections.
 */

import { useState, useEffect, useRef } from 'react'
import { useWarmupContext } from './WarmupContext'
import { cn } from '../../utils/cn'
import { formatLatency } from '../../utils/format'

export function WarmupOverlay() {
  const { status, message, elapsed, backendReady, backendFailed } = useWarmupContext()
  const [dismissed, setDismissed] = useState(false)
  const readyTimer = useRef<ReturnType<typeof setTimeout>>()

  // Issue 76: Show ready step briefly before dismissing
  useEffect(() => {
    if (backendReady && !dismissed) {
      readyTimer.current = setTimeout(() => setDismissed(true), 1500)
    }
    return () => { if (readyTimer.current) clearTimeout(readyTimer.current) }
  }, [backendReady, dismissed])

  // Also dismiss immediately on skip click via the context change
  useEffect(() => {
    const handler = () => setDismissed(true)
    window.addEventListener('pragma:warmup-dismiss', handler)
    return () => window.removeEventListener('pragma:warmup-dismiss', handler)
  }, [])

  if (dismissed) return null

  const steps = [
    { key: 'connecting', label: 'Connecting to Pragma...' },
    { key: 'warming', label: 'Authenticating...' },
    { key: 'ready', label: 'System ready' },
  ]

  const currentStepIndex =
    status === 'connecting' ? 0 :
    status === 'warming' ? 1 :
    backendReady ? 2 : 0

  return (
    <div className="fixed inset-0 z-[9999] flex flex-col items-center justify-center bg-[#0a0a0f]/95 backdrop-blur-sm">
      {/* Animated spinner */}
      <div className="relative mb-12">
        <div className="w-24 h-24 rounded-full border border-[rgba(0,212,255,0.2)] flex items-center justify-center">
          <div
            className="w-16 h-16 rounded-full border-2 border-[#00d4ff] animate-spin"
            style={{ borderTopColor: 'transparent' }}
          />
        </div>
        <div className="absolute inset-0 w-24 h-24 rounded-full animate-ping bg-[rgba(0,212,255,0.05)]" />
      </div>

      {/* Title */}
      <h1
        className="text-5xl font-[300] tracking-[-0.03em] text-white mb-4"
        style={{ fontFamily: "'Geist Sans', system-ui, sans-serif" }}
      >
        PRAGMA
      </h1>

      {/* Status message */}
      <p className="text-[#94a3b8] text-base mb-2 max-w-md text-center px-6">
        {message}
      </p>

      {/* Elapsed time */}
      <p className="text-[10px] font-mono text-[rgba(255,255,255,0.2)] mb-8">
        {formatLatency(elapsed)} elapsed
      </p>

      {/* Progress steps */}
      <div className="flex flex-col gap-3 w-72 mb-8">
        {steps.map((s, i) => (
          <div key={s.key} className="flex items-center gap-3">
            <div
              className={cn(
                'w-2 h-2 rounded-full shrink-0 transition-colors duration-500',
                backendFailed
                  ? 'bg-[#ffb347]'
                  : i === currentStepIndex
                  ? 'bg-[#00d4ff] animate-pulse'
                  : i < currentStepIndex
                  ? 'bg-[#00c785]'
                  : 'bg-[rgba(255,255,255,0.1)]'
              )}
            />
            <span
              className={cn(
                'text-xs font-mono transition-colors duration-500',
                i === currentStepIndex ? 'text-[#94a3b8]' : 'text-[#64748b]'
              )}
            >
              {s.label}
            </span>
          </div>
        ))}
      </div>

      {/* ── NEW: "Skip" button ──
          The old overlay blocked everything for 6s then auto-dismissed.
          Now the user can dismiss it immediately and use fallback data.
          The sections are ALREADY rendered underneath. */}
      {elapsed > 3000 && (
        <button
          onClick={() => {
            setDismissed(true)
            window.dispatchEvent(new CustomEvent('pragma:warmup-dismiss'))
          }}
          className="text-xs font-mono text-[#64748b] px-4 py-2 rounded border border-[rgba(255,255,255,0.1)] hover:border-[#00d4ff] hover:text-[#00d4ff] transition-all"
        >
          Continue with Simulation Data
        </button>
      )}

      {/* Render free-tier hint after 15s */}
      {elapsed > 15000 && (
        <p className="mt-4 text-[10px] font-mono text-[rgba(255,255,255,0.15)] max-w-sm text-center px-6">
          Render free tier spins down after inactivity. Cold-start can take 2–10 minutes. 
          The demo works fully with simulation data — no backend required.
        </p>
      )}
    </div>
  )
}
