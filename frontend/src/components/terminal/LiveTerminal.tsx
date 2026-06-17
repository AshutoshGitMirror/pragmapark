import { useEffect, useState, useRef, useMemo, useCallback } from 'react'
import { useReveal } from '../../hooks/useScrollReveal'
import { motion } from 'framer-motion'

type LogLevel = 'info' | 'warn' | 'error'

interface LogEntry {
  id: number
  timestamp: string
  level: LogLevel
  message: string
}

interface HealthResponse {
  status?: string
  models?: { rf?: boolean; xgb?: boolean; meta?: boolean }
  blockchain?: { chain_length?: number; valid?: boolean }
  lot_count?: number
}

interface LotResponse {
  lot_id?: string
  name?: string
  current_occupancy?: number
  current_price?: number
  total_slots?: number
}

const BASE = import.meta.env.VITE_API_BASE || ''

let _nextId = 1
function nextId() { return _nextId++ }

function buildLog(level: LogLevel, message: string): LogEntry {
  return { id: nextId(), timestamp: new Date().toISOString(), level, message }
}

export function LiveTerminal() {
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [connected, setConnected] = useState(false)
  const visible = useReveal(100)
  const [paused, setPaused] = useState(false)
  const [filter, setFilter] = useState<LogLevel | 'all'>('all')
  const terminalRef = useRef<HTMLDivElement>(null)
  const refreshRef = useRef<ReturnType<typeof setInterval>>()

  const addLogs = useCallback((entries: LogEntry[]) => {
    setLogs((prev) => [...prev, ...entries].slice(-200))
  }, [])

  const fetchData = useCallback(async () => {
    const results = await Promise.allSettled([
      fetch(`${BASE}/api/v1/health`).then((r) => r.ok ? r.json() : Promise.reject(r.status)),
      fetch(`${BASE}/api/v1/lots`).then((r) => r.ok ? r.json() : Promise.reject(r.status)),
    ])

    const batch: LogEntry[] = []

    // Health
    if (results[0].status === 'fulfilled') {
      const h = results[0].value as HealthResponse
      const parts: string[] = []
      if (h.status) parts.push(`status=${h.status}`)
      if (h.models) {
        const m = h.models
        parts.push(`rf=${m.rf ? 'loaded' : 'unavailable'}, xgb=${m.xgb ? 'loaded' : 'unavailable'}`)
      }
      if (h.blockchain) {
        const b = h.blockchain
        parts.push(`chain=${b.chain_length ?? '?'}, valid=${b.valid ? 'yes' : 'no'}`)
      }
      if (h.lot_count !== undefined) parts.push(`lots=${h.lot_count}`)
      if (parts.length) batch.push(buildLog('info', `System: healthy, ${parts.join(', ')}`))
    } else {
      batch.push(buildLog('warn', 'Health check: unreachable'))
    }

    // Lots
    if (results[1].status === 'fulfilled') {
      const lots = results[1].value as LotResponse[]
      if (Array.isArray(lots) && lots.length > 0) {
        lots.slice(0, 10).forEach((lot) => {
          const occ = lot.current_occupancy != null ? lot.current_occupancy.toFixed(1) : '?'
          const price = lot.current_price != null ? `$${lot.current_price.toFixed(2)}/hr` : '?'
          const name = lot.name || lot.lot_id || 'Unknown'
          batch.push(buildLog('info', `Lot ${name}: ${occ}% occupied, ${price}`))
        })
        if (lots.length > 10) {
          batch.push(buildLog('info', `… and ${lots.length - 10} more lots`))
        }
      } else {
        batch.push(buildLog('info', 'Lots: no data yet'))
      }
    } else {
      batch.push(buildLog('warn', 'Lots API: unreachable'))
    }

    setConnected(true)

    if (batch.length) addLogs(batch)
  }, [addLogs])

  // Initial fetch
  useEffect(() => {
    fetchData()
  }, [fetchData])

  // Auto-refresh every 30s
  useEffect(() => {
    if (!paused) {
      refreshRef.current = setInterval(fetchData, 30000)
    }
    return () => { if (refreshRef.current) clearInterval(refreshRef.current) }
  }, [paused, fetchData])

  // Auto-scroll
  useEffect(() => {
    if (terminalRef.current) {
      terminalRef.current.scrollTop = terminalRef.current.scrollHeight
    }
  }, [logs])

  const filteredLogs = useMemo(
    () => filter === 'all' ? logs : logs.filter((l) => l.level === filter),
    [logs, filter],
  )

  const clearLogs = useCallback(() => setLogs([]), [])

  const logColors: Record<LogLevel, string> = { info: '#94a3b8', warn: '#ffb347', error: '#ef4444' }
  const logCounts = useMemo(() => ({
    all: logs.length,
    info: logs.filter((l) => l.level === 'info').length,
    warn: logs.filter((l) => l.level === 'warn').length,
    error: logs.filter((l) => l.level === 'error').length,
  }), [logs])

  const filters: { key: LogLevel | 'all'; label: string }[] = [
    { key: 'all', label: 'All' },
    { key: 'info', label: 'Info' },
    { key: 'warn', label: 'Warn' },
    { key: 'error', label: 'Error' },
  ]

  return (
    <section className="section bg-[#0a0a0f]" id="terminal">
      <div className="section-inner">
        <div className={`mb-6 flex items-center justify-between transition-all duration-700 ${visible ? 'opacity-100' : 'opacity-0'}`}>
          <div>
            <p className="section-label" style={{ color: '#00d4ff' }}>SYSTEM TERMINAL</p>
            <h2 className="section-headline">System Terminal</h2>
          </div>
          <motion.button
            onClick={() => setPaused(!paused)}
            whileHover={{ scale: 1.03 }}
            whileTap={{ scale: 0.97 }}
            className="text-[10px] font-mono text-[#64748b] px-3 py-1.5 rounded border border-[rgba(255,255,255,0.1)] hover:border-[#00d4ff] hover:text-[#00d4ff] transition-all"
          >
            {paused ? '▶ Resume' : '❚❚ Pause'}
          </motion.button>
        </div>

        {/* ── Filter bar ── */}
        <div className={`flex items-center justify-between mb-3 transition-all duration-500 delay-100 ${visible ? 'opacity-100' : 'opacity-0'}`}>
          <div className="flex items-center gap-1.5">
            {filters.map((f) => (
              <motion.button
                key={f.key}
                onClick={() => setFilter(f.key)}
                whileHover={{ scale: 1.03 }}
                whileTap={{ scale: 0.97 }}
                className={`px-2.5 py-1 rounded text-[10px] font-mono transition-all ${
                  filter === f.key
                    ? 'bg-white/10 text-white border border-white/20'
                    : 'text-[#64748b] hover:text-[#94a3b8] border border-transparent'
                }`}
              >
                {f.label}
                <span className="ml-1 opacity-60">({logCounts[f.key]})</span>
              </motion.button>
            ))}
          </div>
          <motion.button
            onClick={clearLogs}
            whileHover={{ scale: 1.03 }}
            whileTap={{ scale: 0.97 }}
            className="text-[10px] font-mono text-[#64748b] px-2.5 py-1 rounded hover:text-[#ef4444] hover:bg-[rgba(239,68,68,0.06)] transition-all"
          >
            ✕ Clear
          </motion.button>
        </div>

        <div
          ref={terminalRef}
          className={`bg-black rounded-xl border border-[rgba(255,255,255,0.06)] p-4 h-[400px] overflow-y-auto transition-all duration-700 delay-200 ${
            visible ? 'opacity-100' : 'opacity-0'
          }`}
          style={{ scrollbarWidth: 'thin', scrollbarColor: 'rgba(255,255,255,0.1) transparent' }}
        >
          {filteredLogs.length === 0 ? (
            <div className="h-full flex items-center justify-center text-xs font-mono text-[#475569]">
              {!connected
                ? 'Terminal connected — awaiting system events'
                : logs.length === 0
                  ? 'Terminal cleared. New events will appear.'
                  : 'No events match this level.'}
            </div>
          ) : (
            filteredLogs.map((log) => (
              <div key={log.id} className="flex gap-3 text-xs font-mono leading-relaxed hover:bg-[rgba(255,255,255,0.02)] px-1 rounded transition-colors">
                <span className="text-[#64748b] shrink-0 w-16">{log.timestamp.slice(11, 19)}</span>
                <span
                  className="shrink-0 w-10 text-[9px] uppercase tracking-wider"
                  style={{ color: logColors[log.level] || '#94a3b8' }}
                >
                  {log.level}
                </span>
                <span style={{ color: logColors[log.level] || '#94a3b8' }}>
                  {log.message}
                </span>
              </div>
            ))
          )}
        </div>

        <div className="flex items-center gap-4 mt-3 text-[10px] font-mono text-[#64748b]">
          <span className="flex items-center gap-1">
            <span className={`w-1.5 h-1.5 rounded-full ${connected ? 'bg-[#22c55e]' : 'bg-[#64748b]'} animate-pulse`} />
            {connected ? 'Live' : 'Connecting'}
          </span>
          <span>{logCounts.error} errors</span>
          <span>{filteredLogs.length} of {logs.length} events</span>
        </div>
      </div>
    </section>
  )
}
