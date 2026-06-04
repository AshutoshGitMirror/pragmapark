import { useEffect, useState, useRef, useMemo } from 'react'
import { useReveal } from '../../hooks/useScrollReveal'
import { motion } from 'framer-motion'


const fallbackLogs = [
  { timestamp: '2025-01-15T00:56:05Z', level: 'info', message: 'Block mined #142 — 30 TX, 6.2s, diff=0.0012' },
  { timestamp: '2025-01-15T00:59:05Z', level: 'info', message: 'MARL policy update: zone=7, epoch=142, reward=0.873, entropy=0.12' },
  { timestamp: '2025-01-15T01:02:05Z', level: 'warn', message: 'Session timeout: lot=B2, slot=#231, duration=2400s > max=1800s' },
  { timestamp: '2025-01-15T01:05:05Z', level: 'info', message: 'Prediction pipeline: rf=0.921, xgb=0.908, ensemble=0.917' },
  { timestamp: '2025-01-15T01:08:05Z', level: 'info', message: 'Price update: zone=4, base=1.0, multiplier=2.3, demand=HIGH' },
  { timestamp: '2025-01-15T01:11:05Z', level: 'error', message: 'OCR timeout: node=cam-12, image=6.2MB, no plate found' },
  { timestamp: '2025-01-15T01:14:05Z', level: 'info', message: 'Overflow reroute: lot=C → lot=A, 8 vehicles diverted' },
  { timestamp: '2025-01-15T01:17:05Z', level: 'info', message: 'Blockchain sync: height=142, peer=ipfs-3, latency=140ms' },
  { timestamp: '2025-01-15T01:20:05Z', level: 'warn', message: 'Sensor anomaly: lot=D2, bias=+0.12σ beyond 3σ threshold' },
  { timestamp: '2025-01-15T01:23:05Z', level: 'info', message: 'Digital twin: scenario=heavy-rain, impact=-14% occupancy' },
]

type LogLevel = 'info' | 'warn' | 'error'

export function LiveTerminal() {
  const [logs, setLogs] = useState(fallbackLogs)
  const visible = useReveal(100)
  const [paused, setPaused] = useState(false)
  const [filter, setFilter] = useState<LogLevel | 'all'>('all')
  const terminalRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    let interval: ReturnType<typeof setInterval>
    const agents = ['cam-4', 'price-agent-2', 'sensor-d3', 'blockchain-v', 'ocr-pipe']
    const actions = [
      'policy update: reward=0.921',
      'heartbeat: ok, latency=42ms',
      'frame processed: 1200x800, 4 vehicles',
      'pricing recomputed: zone-3, multiplier=1.8',
      'block propagated: #143 to 6 peers',
    ]
    const levels = ['info', 'info', 'info', 'info', 'warn', 'info', 'info'] as const

    if (!paused) {
      interval = setInterval(() => {
        const ts = new Date().toISOString().slice(11, 19) + 'Z'
        const agent = agents[Math.floor(Math.random() * agents.length)]
        const action = actions[Math.floor(Math.random() * actions.length)]
        const level = levels[Math.floor(Math.random() * levels.length)]
        setLogs((prev) => [...prev.slice(-49), { timestamp: ts, level, message: `[${agent}] ${action}` }])
      }, 2000)
    }

    return () => clearInterval(interval)
  }, [paused])

  useEffect(() => {
    if (terminalRef.current) {
      terminalRef.current.scrollTop = terminalRef.current.scrollHeight
    }
  }, [logs])

  const filteredLogs = useMemo(
    () => filter === 'all' ? logs : logs.filter((l) => l.level === filter),
    [logs, filter],
  )

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
            <h2 className="section-headline">Simulated system log. No filter.</h2>
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
            onClick={() => setLogs([])}
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
              {logs.length === 0 ? 'Terminal cleared. New events will appear.' : 'No events match this level.'}
            </div>
          ) : (
            filteredLogs.map((log, i) => (
              <div key={i} className="flex gap-3 text-xs font-mono leading-relaxed hover:bg-[rgba(255,255,255,0.02)] px-1 rounded transition-colors">
                <span className="text-[#64748b] shrink-0 w-16">{log.timestamp.slice(11, 19)}</span>
                <span
                  className="shrink-0 w-10 text-[9px] uppercase tracking-wider"
                  style={{ color: logColors[log.level as LogLevel] || '#94a3b8' }}
                >
                  {log.level}
                </span>
                <span style={{ color: logColors[log.level as LogLevel] || '#94a3b8' }}>
                  {log.message}
                </span>
              </div>
            ))
          )}
        </div>

        <div className="flex items-center gap-4 mt-3 text-[10px] font-mono text-[#64748b]">
          <span className="flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-[#ffb347] animate-pulse" />
            Simulating
          </span>
          <span>{logCounts.error} errors</span>
          <span>{filteredLogs.length} of {logs.length} events</span>
        </div>
      </div>
    </section>
  )
}
