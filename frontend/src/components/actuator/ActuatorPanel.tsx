/**
 * ActuatorPanel.tsx — Interactive actuator control panel.
 *
 * Real-time state of SmartBarriers, DigitalPricingBoards, and CongestionLights
 * with interactive override controls and terminal log.
 * Layer 6: Actuator.
 */

import { useEffect, useState, useCallback } from 'react'
import { fetchJson } from '../../api/client'

interface BarrierStatus {
  barrier_id: string
  zone_id: string
  open: boolean
  restricted: boolean
  reservation_only: boolean
}

interface PricingBoardStatus {
  board_id: string
  zone_id: string
  displayed_price: number
}

interface CongestionLightStatus {
  light_id: string
  color: string
  flashing: boolean
}

interface ZoneActuatorStatus {
  zone_id: string
  barrier: BarrierStatus
  pricing_board: PricingBoardStatus
  congestion_light: CongestionLightStatus
}

interface ActuatorSummary {
  zones_registered: number
  total_commands: number
  last_commands: string[]
}

interface ActuatorApiResponse {
  summary: ActuatorSummary
  zones: ZoneActuatorStatus[]
}

const ROSE = '#f04060'
const ROSE_DIM = 'rgba(240,64,96,0.12)'
const ROSE_GLOW = 'rgba(240,64,96,0.3)'

function fetchActuatorStatus(): Promise<ActuatorApiResponse> {
  return fetchJson<ActuatorApiResponse>('/actuator/status', {}, 1)
}

function LightBulb({ color, flashing }: { color: string; flashing: boolean }) {
  const colors: Record<string, string> = {
    green: '#60d4a0',
    yellow: '#f0c040',
    red: '#f04060',
  }
  return (
    <div className="flex items-center gap-1.5">
      <span
        className={`w-2.5 h-2.5 rounded-full ${flashing ? 'animate-pulse' : ''}`}
        style={{
          backgroundColor: colors[color] || '#5a6a8a',
          boxShadow: flashing ? `0 0 6px ${colors[color] || '#5a6a8a'}66` : 'none',
        }}
      />
      <span className="text-[9px] font-mono uppercase tracking-wider" style={{ color: colors[color] || '#5a6a8a' }}>
        {color}
      </span>
    </div>
  )
}

/* ── Terminal log line ── */
function TerminalLog({ lines }: { lines: string[] }) {
  const [autoScroll, setAutoScroll] = useState(true)
  useEffect(() => {
    // Scroll to bottom when new lines arrive
    const el = document.getElementById('actuator-terminal')
    if (el && autoScroll) el.scrollTop = el.scrollHeight
  })

  if (lines.length === 0) return null

  return (
    <div className="mt-5">
      <div className="flex items-center justify-between mb-2">
        <span className="text-[9px] font-mono text-[#5a6a8a] uppercase tracking-wider">Terminal Log</span>
        <button
          onClick={() => setAutoScroll(!autoScroll)}
          className="text-[8px] font-mono px-1.5 py-0.5 rounded transition-colors"
          style={{
            color: autoScroll ? '#60d4a0' : '#5a6a8a',
            background: autoScroll ? 'rgba(96,212,160,0.08)' : 'transparent',
          }}
        >
          {autoScroll ? 'AUTO ▼' : 'PAUSE'}
        </button>
      </div>
      <div
        id="actuator-terminal"
        className="h-24 overflow-y-auto rounded-lg p-3 font-mono text-[9px] leading-relaxed"
        style={{
          background: '#04040a',
          border: '1px solid rgba(255,255,255,0.04)',
          scrollbarWidth: 'thin',
          scrollbarColor: 'rgba(240,64,96,0.2) transparent',
        }}
      >
        {lines.map((cmd, i) => (
          <div key={i} className="flex gap-2">
            <span style={{ color: ROSE }}>&gt;</span>
            <span className="text-[#94a3b8]">{cmd}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

export function ActuatorPanel() {
  const [data, setData] = useState<ActuatorApiResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [terminalLines, setTerminalLines] = useState<string[]>([])
  const [overriding, setOverriding] = useState<string | null>(null)

  const load = useCallback(() => {
    setLoading(true)
    setError(null)
    fetchActuatorStatus()
      .then(setData)
      .catch((e: Error) => setError(e.message || 'Failed to load actuator status'))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    load()
    const interval = setInterval(load, 15000)
    return () => clearInterval(interval)
  }, [load])

  // Seed initial terminal lines from last_commands
  useEffect(() => {
    if (data?.summary?.last_commands) {
      setTerminalLines(() => {
        const merged = [...data.summary.last_commands]
        // Keep unique, newest first
        return merged.slice(0, 20)
      })
    }
  }, [data?.summary?.last_commands])

  const executeOverride = async (zoneId: string, action: string) => {
    setOverriding(`${zoneId}:${action}`)
    setTerminalLines((prev) => [`EXEC ${action} on ${zoneId}...`, ...prev].slice(0, 30))
    try {
      // Fire-and-forget: try to post, but don't block UI
      await fetchJson('/actuator/command', {
        method: 'POST',
        body: JSON.stringify({ zone_id: zoneId, command: action, source: 'admin_panel' }),
      })
      setTerminalLines((prev) => [`OK ${action} on ${zoneId}`, ...prev].slice(0, 30))
      // Reload to reflect changes
      load()
    } catch {
      setTerminalLines((prev) => [`FAIL ${action} on ${zoneId}`, ...prev].slice(0, 30))
    } finally {
      setOverriding(null)
    }
  }

  return (
    <div className="space-y-6">
      {/* ── Header ── */}
      <div>
        <p className="text-[10px] font-mono text-[#9a97b0] tracking-[3px] uppercase mb-2">05 / Actuate</p>
        <h1 className="section-headline">Actuator Control</h1>
        <p className="section-body mt-1">Real-time state and manual override for smart parking actuators</p>
      </div>

      {/* ── Error state ── */}
      {error && (
        <div className="rounded-lg p-3 text-xs font-mono flex items-center gap-2"
          style={{
            background: ROSE_DIM,
            border: `1px solid rgba(240,64,96,0.2)`,
            color: ROSE,
          }}>
          <span>⚠</span>
          <span className="flex-1">{error}</span>
          <button onClick={load} className="underline hover:text-white transition-colors">Retry</button>
        </div>
      )}

      {loading && !data && (
        <div className="flex justify-center py-12">
          <div className="flex items-center gap-2 text-[#5a6a8a] text-xs font-mono">
            <span className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ background: ROSE }} />
            Loading actuator state...
          </div>
        </div>
      )}

      {data && (
        <>
          {/* ── Summary stats ── */}
          <div className="flex gap-6">
            {[
              { label: 'Zones Registered', value: data.summary.zones_registered, color: ROSE },
              { label: 'Total Commands', value: data.summary.total_commands, color: '#40d4f0' },
              { label: 'Active Zones', value: data.zones.length, color: '#60d4a0' },
            ].map((s) => (
              <div key={s.label} className="flex-1 rounded-xl p-4"
                style={{
                  background: 'linear-gradient(135deg, #0e0e24 0%, #12122a 50%, #0e0e24 100%)',
                  boxShadow: '0 1px 0 rgba(255,255,255,0.04), 0 0 0 1px rgba(255,255,255,0.04)',
                }}>
                <p className="text-[9px] font-mono text-[#9a97b0] uppercase tracking-wider mb-1">{s.label}</p>
                <p className="display-number" style={{ color: s.color, fontSize: '24px' }}>{s.value}</p>
              </div>
            ))}
          </div>

          {/* ── Zone cards ── */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {data.zones.map((zone) => (
              <div
                key={zone.zone_id}
                className="rounded-xl p-5 transition-all duration-300 hover:scale-[1.01]"
                style={{
                  background: 'linear-gradient(135deg, #0e0e24 0%, #12122a 50%, #0e0e24 100%)',
                  boxShadow: '0 1px 0 rgba(255,255,255,0.04), 0 0 0 1px rgba(255,255,255,0.04)',
                }}>
                {/* Zone header */}
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-2">
                    <div className="w-2 h-2 rounded-full" style={{
                      background: zone.barrier.open ? '#60d4a0' : ROSE,
                      boxShadow: zone.barrier.open ? '0 0 4px rgba(96,212,160,0.4)' : `0 0 4px ${ROSE_GLOW}`,
                    }} />
                    <h3 className="font-heading text-sm font-semibold text-white">{zone.zone_id}</h3>
                  </div>
                  <span className="text-[9px] font-mono px-2 py-0.5 rounded tracking-wider uppercase"
                    style={{
                      background: zone.barrier.open ? 'rgba(96,212,160,0.1)' : `${ROSE_DIM}`,
                      color: zone.barrier.open ? '#60d4a0' : ROSE,
                      border: `1px solid ${zone.barrier.open ? 'rgba(96,212,160,0.2)' : `${ROSE}30`}`,
                    }}>
                    {zone.barrier.open ? 'Open' : 'Restricted'}
                  </span>
                </div>

                {/* Barrier */}
                <div className="flex items-center gap-3 mb-2.5 p-2.5 rounded-lg"
                  style={{ background: 'rgba(255,255,255,0.02)' }}>
                  <div className="w-6 h-6 rounded flex items-center justify-center text-xs"
                    style={{ background: zone.barrier.open ? 'rgba(96,212,160,0.1)' : `${ROSE_DIM}` }}>
                    <span style={{ color: zone.barrier.open ? '#60d4a0' : ROSE }}>{zone.barrier.open ? '◈' : '⊘'}</span>
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-[8px] font-mono text-[#5a6a8a] uppercase tracking-wider">Barrier</div>
                    <div className="text-[10px] font-mono text-white/80 truncate">{zone.barrier.barrier_id}</div>
                  </div>
                  <div className="text-right">
                    <div className="text-[9px] font-mono" style={{ color: zone.barrier.open ? '#60d4a0' : ROSE }}>
                      {zone.barrier.reservation_only ? 'Res. Only' : zone.barrier.restricted ? 'Closed' : 'Open'}
                    </div>
                  </div>
                </div>

                {/* Pricing Board */}
                <div className="flex items-center gap-3 mb-2.5 p-2.5 rounded-lg"
                  style={{ background: 'rgba(255,255,255,0.02)' }}>
                  <div className="w-6 h-6 rounded flex items-center justify-center text-xs"
                    style={{ background: 'rgba(240,192,64,0.1)' }}>
                    <span style={{ color: '#f0c040' }}>¤</span>
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-[8px] font-mono text-[#5a6a8a] uppercase tracking-wider">Pricing Board</div>
                    <div className="text-[10px] font-mono text-white/80 truncate">{zone.pricing_board.board_id}</div>
                  </div>
                  <div className="text-right">
                    <div className="font-mono font-bold" style={{ color: '#f0c040', fontSize: '13px' }}>
                      ${zone.pricing_board.displayed_price.toFixed(2)}
                    </div>
                  </div>
                </div>

                {/* Congestion Light */}
                <div className="flex items-center gap-3 mb-3 p-2.5 rounded-lg"
                  style={{ background: 'rgba(255,255,255,0.02)' }}>
                  <div className="w-6 h-6 rounded flex items-center justify-center text-xs">
                    <span style={{ color: zone.congestion_light.color === 'red' ? ROSE : zone.congestion_light.color === 'yellow' ? '#f0c040' : '#60d4a0' }}>⬟</span>
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-[8px] font-mono text-[#5a6a8a] uppercase tracking-wider">Congestion Light</div>
                    <div className="text-[10px] font-mono text-white/80 truncate">{zone.congestion_light.light_id}</div>
                  </div>
                  <LightBulb color={zone.congestion_light.color} flashing={zone.congestion_light.flashing} />
                </div>

                {/* Interactive Override Buttons */}
                <div className="flex gap-2 mt-3 pt-3 border-t border-[rgba(255,255,255,0.04)]">
                  <button
                    onClick={() => executeOverride(zone.zone_id, 'toggle_barrier')}
                    disabled={overriding === `${zone.zone_id}:toggle_barrier`}
                    className="flex-1 py-1.5 rounded text-[9px] font-mono font-semibold tracking-wider uppercase transition-all active:scale-95 disabled:opacity-40"
                    style={{
                      background: zone.barrier.open ? `${ROSE_DIM}` : 'rgba(96,212,160,0.1)',
                      color: zone.barrier.open ? ROSE : '#60d4a0',
                      border: `1px solid ${zone.barrier.open ? `${ROSE}30` : 'rgba(96,212,160,0.2)'}`,
                    }}
                  >
                    {overriding === `${zone.zone_id}:toggle_barrier` ? '...' : zone.barrier.open ? 'Close' : 'Open'}
                  </button>
                  <button
                    onClick={() => executeOverride(zone.zone_id, 'toggle_light')}
                    disabled={overriding === `${zone.zone_id}:toggle_light`}
                    className="flex-1 py-1.5 rounded text-[9px] font-mono font-semibold tracking-wider uppercase transition-all active:scale-95 disabled:opacity-40"
                    style={{
                      background: 'rgba(255,255,255,0.04)',
                      color: '#5a6a8a',
                      border: '1px solid rgba(255,255,255,0.06)',
                    }}
                  >
                    {overriding === `${zone.zone_id}:toggle_light` ? '...' : 'Toggle Light'}
                  </button>
                </div>
              </div>
            ))}
          </div>

          {/* ── Terminal Log ── */}
          <TerminalLog lines={terminalLines} />

          {/* ── Empty state ── */}
          {data.zones.length === 0 && (
            <div className="text-center py-12 rounded-xl"
              style={{
                background: 'linear-gradient(135deg, #0e0e24 0%, #12122a 50%, #0e0e24 100%)',
                boxShadow: '0 1px 0 rgba(255,255,255,0.04), 0 0 0 1px rgba(255,255,255,0.04)',
              }}>
              <div className="text-2xl mb-3 opacity-20" style={{ color: ROSE }}>◈</div>
              <p className="text-sm text-[#5a6a8a] font-mono">
                No actuators registered yet. Start a parking session to activate them.
              </p>
            </div>
          )}
        </>
      )}
    </div>
  )
}
