/**
 * ActuatorPanel.tsx — Visual feedback for physical IoT actuators.
 *
 * Surfaces real-time state of SmartBarriers, DigitalPricingBoards,
 * and CongestionLights as reported by the ActuatorBridge.
 *
 * Paper fidelity: closes the "invisible actuator layer" gap (Layer 6).
 */

import { useEffect, useState } from 'react'
import { useReveal } from '../../hooks/useScrollReveal'
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

const BASE_URL = import.meta.env.VITE_API_URL || '/api/v1'

function fetchActuatorStatus(): Promise<ActuatorApiResponse> {
  return fetchJson<ActuatorApiResponse>('/actuator/status', {}, 1)
}

function LightBulb({ color, flashing }: { color: string; flashing: boolean }) {
  const colors: Record<string, string> = {
    green: '#00c785',
    yellow: '#ffb347',
    red: '#ef4444',
  }
  return (
    <div className="flex items-center gap-1.5">
      <span
        className={`w-2.5 h-2.5 rounded-full ${flashing ? 'animate-pulse' : ''}`}
        style={{ backgroundColor: colors[color] || '#64748b' }}
      />
      <span className="text-[10px] font-mono text-[#64748b] uppercase">{color}</span>
    </div>
  )
}

export function ActuatorPanel() {
  const [data, setData] = useState<ActuatorApiResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const visible = useReveal(100)

  const load = () => {
    setLoading(true)
    setError(null)
    fetchActuatorStatus()
      .then(setData)
      .catch((e: Error) => setError(e.message || 'Failed to load actuator status'))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    load()
    const interval = setInterval(load, 15000)
    return () => clearInterval(interval)
  }, [])

  return (
    <section className="section bg-[#0e0e18]" id="actuator">
      <div className="section-inner">
        <div className={`text-center mb-12 transition-all duration-700 ${visible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'}`}>
          <p className="section-label" style={{ color: '#00d4ff' }}>ACTUATOR FEEDBACK</p>
          <h2 className="section-headline">Closing the loop.</h2>
          <p className="section-body mx-auto text-center">
            Real-time state of physical parking actuators — barriers, pricing boards, and congestion lights —
            updated directly by the RL agent without human intervention.
          </p>
        </div>

        {loading && !data && (
          <div className="flex justify-center py-12">
            <span className="w-5 h-5 rounded-full border border-[#00d4ff] border-t-transparent animate-spin" />
          </div>
        )}

        {error && (
          <div className="mb-6 mx-auto max-w-lg p-3 rounded-lg text-xs font-mono text-center"
            style={{
              background: 'rgba(245,158,11,0.08)',
              border: '1px solid rgba(245,158,11,0.2)',
              color: '#f59e0b',
            }}>
            {error}
            <button
              onClick={load}
              className="ml-2 underline hover:text-white transition-colors"
            >
              Retry
            </button>
          </div>
        )}

        {data && (
          <>
            {/* Summary stats */}
            <div className={`flex justify-center gap-8 mb-10 transition-all duration-500 delay-100 ${visible ? 'opacity-100' : 'opacity-0'}`}>
              <div className="text-center">
                <div className="text-2xl font-bold text-white font-mono">{data.summary.zones_registered}</div>
                <div className="text-[10px] font-mono text-[#64748b] mt-1">Zones Registered</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-white font-mono">{data.summary.total_commands}</div>
                <div className="text-[10px] font-mono text-[#64748b] mt-1">Total Commands</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-white font-mono">{data.zones.length}</div>
                <div className="text-[10px] font-mono text-[#64748b] mt-1">Active Zones</div>
              </div>
            </div>

            {/* Zone actuator cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {data.zones.map((zone, i) => (
                <div
                  key={zone.zone_id}
                  className={`bg-[#13131f] border border-[rgba(255,255,255,0.06)] rounded-xl p-5 transition-all duration-500 hover:border-[rgba(255,255,255,0.15)] ${
                    visible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4'
                  }`}
                  style={{ transitionDelay: `${i * 100}ms` }}
                >
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="text-sm font-medium text-white font-mono">{zone.zone_id}</h3>
                    <span className={`text-[9px] font-mono px-1.5 py-0.5 rounded ${
                      zone.barrier.open
                        ? 'bg-[rgba(0,199,133,0.1)] text-[#00c785]'
                        : 'bg-[rgba(239,68,68,0.1)] text-[#ef4444]'
                    }`}>
                      {zone.barrier.open ? 'Open' : 'Restricted'}
                    </span>
                  </div>

                  {/* Barrier status */}
                  <div className="flex items-center gap-3 mb-3 p-2 rounded-lg bg-[rgba(255,255,255,0.02)]">
                    <span className="text-lg">🚧</span>
                    <div className="flex-1 min-w-0">
                      <div className="text-[9px] font-mono text-[#64748b] uppercase tracking-wider">Barrier</div>
                      <div className="text-xs font-mono text-white truncate">{zone.barrier.barrier_id}</div>
                    </div>
                    <div className="text-right">
                      <div className={`text-[10px] font-mono ${zone.barrier.open ? 'text-[#00c785]' : 'text-[#ef4444]'}`}>
                        {zone.barrier.reservation_only ? 'Reservation Only' : zone.barrier.restricted ? 'Closed' : 'Open'}
                      </div>
                    </div>
                  </div>

                  {/* Pricing board */}
                  <div className="flex items-center gap-3 mb-3 p-2 rounded-lg bg-[rgba(255,255,255,0.02)]">
                    <span className="text-lg">💲</span>
                    <div className="flex-1 min-w-0">
                      <div className="text-[9px] font-mono text-[#64748b] uppercase tracking-wider">Pricing Board</div>
                      <div className="text-xs font-mono text-white truncate">{zone.pricing_board.board_id}</div>
                    </div>
                    <div className="text-right">
                      <div className="text-sm font-mono text-[#ffb347] font-bold">
                        ${zone.pricing_board.displayed_price.toFixed(2)}
                      </div>
                    </div>
                  </div>

                  {/* Congestion light */}
                  <div className="flex items-center gap-3 p-2 rounded-lg bg-[rgba(255,255,255,0.02)]">
                    <span className="text-lg">🚦</span>
                    <div className="flex-1 min-w-0">
                      <div className="text-[9px] font-mono text-[#64748b] uppercase tracking-wider">Congestion Light</div>
                      <div className="text-xs font-mono text-white truncate">{zone.congestion_light.light_id}</div>
                    </div>
                    <LightBulb color={zone.congestion_light.color} flashing={zone.congestion_light.flashing} />
                  </div>
                </div>
              ))}
            </div>

            {/* Command history */}
            {data.summary.last_commands.length > 0 && (
              <div className={`mt-8 transition-all duration-500 delay-300 ${visible ? 'opacity-100' : 'opacity-0'}`}>
                <h3 className="text-xs font-mono text-[#64748b] uppercase tracking-wider mb-3 text-center">Recent Commands</h3>
                <div className="flex flex-wrap justify-center gap-2">
                  {data.summary.last_commands.map((cmd, i) => (
                    <span
                      key={i}
                      className="px-2 py-1 rounded text-[9px] font-mono bg-[rgba(0,212,255,0.06)] border border-[rgba(0,212,255,0.12)] text-[#94a3b8]"
                    >
                      {cmd}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Empty state when no zones registered */}
            {data.zones.length === 0 && (
              <div className="text-center py-12">
                <div className="text-4xl mb-4 opacity-30">⚙️</div>
                <p className="text-sm text-[#64748b] font-mono">
                  No actuators registered yet. Start a parking session to activate them.
                </p>
              </div>
            )}
          </>
        )}
      </div>
    </section>
  )
}
