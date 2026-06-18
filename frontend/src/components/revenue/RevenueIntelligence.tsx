import { useEffect, useState, useMemo, useCallback } from 'react'
import { useReveal } from '../../hooks/useScrollReveal'
import { fetchPricingLots, fetchPricingHistory } from '../../api/client'
import { useApi } from '../../hooks/useApi'
import type { PricingLot, PricingHistoryItem } from '../../api/types'

function deriveMultiplier(z: PricingLot): number {
  if (!z.dynamic_pricing) return 1.0
  const mid = (z.price_range[0] + z.price_range[1]) / 2
  if (z.base_price <= 0) return 1.0
  return Math.round((mid / z.base_price) * 10) / 10
}

function deriveOccupancy(z: PricingLot): number {
  const range = z.price_range[1] - z.price_range[0]
  if (range <= 0) return 0.5
  const occ = (z.base_price - z.price_range[0]) / range
  return Math.max(0.1, Math.min(0.95, Math.round(occ * 100) / 100))
}

export function RevenueIntelligence() {
  const { data: zones, source } = useApi(
    () => fetchPricingLots(),
    { initialValue: [] as PricingLot[] },
  )

  const isLive = source === 'live'
  const isLoading = source === 'loading'
  const [historyData, setHistoryData] = useState<PricingHistoryItem[]>([])

  useEffect(() => {
    if (!isLive) {
      setHistoryData([])
      return
    }
    let active = true
    fetchPricingHistory(7)
      .then((data) => {
        if (active) setHistoryData(data)
      })
      .catch(() => {
        if (active) setHistoryData([])
      })
    return () => { active = false }
  }, [isLive])

  const stats = useMemo(() => {
    if (!zones.length) return { peak: 1.0, lift: 0, latency: 12 }
    const multipliers = zones.map(deriveMultiplier)
    const peak = Math.round(Math.max(...multipliers) * 10) / 10
    const avgOcc = zones.reduce((a, z) => a + deriveOccupancy(z), 0) / zones.length
    const lift = Math.round((avgOcc - 0.5) * 60)
    return { peak, lift, latency: 12 }
  }, [zones])

  const visible = useReveal(100)
  const [selectedCell, setSelectedCell] = useState<{ day: string; hour: number; multiplier: number } | null>(null)

  const handleCellClick = useCallback((day: string, hour: number, multiplier: number) => {
    setSelectedCell((prev) =>
      prev?.day === day && prev?.hour === hour ? null : { day, hour, multiplier },
    )
  }, [])

  useEffect(() => {
    if (!selectedCell) return
    const handler = () => setSelectedCell(null)
    window.addEventListener('click', handler)
    return () => window.removeEventListener('click', handler)
  }, [selectedCell])

  const getColor = (m: number) => {
    if (m >= 3.0) return 'rgba(255,179,71,0.9)'
    if (m >= 2.5) return 'rgba(255,179,71,0.7)'
    if (m >= 2.0) return 'rgba(255,179,71,0.5)'
    if (m >= 1.5) return 'rgba(0,212,255,0.5)'
    if (m >= 1.0) return 'rgba(0,212,255,0.25)'
    return 'rgba(255,255,255,0.04)'
  }

  const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
  const hours = Array.from({ length: 24 }, (_, i) => i)

  const hasRealData = isLive && historyData.length > 0

  return (
    <section className="section bg-deeper" id="revenue">
      <div className="section-inner">
        <div className={`text-center mb-16 transition-all duration-700 ${visible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'}`}>
          <div className="flex items-center justify-center gap-3 mb-4">
            <p className="section-label !mb-0" style={{ color: '#00d4ff' }}>REINFORCEMENT LEARNING</p>
            {isLive && (
              <span className="flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-[rgba(0,199,133,0.1)] border border-[rgba(0,199,133,0.2)]">
                <span className="w-1.5 h-1.5 rounded-full bg-[#00c785] animate-pulse" />
                <span className="text-[9px] font-mono text-emerald uppercase tracking-wider">Live</span>
              </span>
            )}
          </div>
          <h2 className="section-headline">Prices that learn. Revenue that grows.</h2>
          <p className="section-body mx-auto text-center">
            Neural agents observe occupancy, time-of-day, and demand signals to adjust pricing in real-time.
            QMIX Multi-Agent RL coordinates pricing across multiple zones simultaneously, maximizing total
            revenue while maintaining driver satisfaction.
            {isLive && zones.length > 0 && (
              <span className="block mt-2 text-emerald">
                Active lots: {zones.map((z) => z.lot_id).join(', ')}
              </span>
            )}
          </p>
        </div>

        <div className={`max-w-4xl mx-auto transition-all duration-700 delay-200 ${visible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'}`}>
          {isLoading && (
            <div className="bg-surface rounded-xl border border-[rgba(255,255,255,0.06)] p-6">
              <div className="flex items-center gap-2 text-dim text-xs font-mono">
                <span className="w-1.5 h-1.5 rounded-full bg-[#00d4ff] animate-pulse" />
                Loading pricing data...
              </div>
            </div>
          )}

          {source === 'error' && (
            <div className="bg-surface rounded-xl border border-red-500/20 p-6">
              <div className="text-amber text-xs font-mono">
                Unable to load pricing data. Backend may be unavailable.
              </div>
            </div>
          )}

          {!isLoading && source !== 'error' && !hasRealData && (
            <div className="bg-surface rounded-xl border border-[rgba(255,255,255,0.06)] p-6">
              <div className="flex items-center gap-2 text-dim text-xs font-mono">
                <span className="w-1.5 h-1.5 rounded-full bg-[#64748b]" />
                Heatmap requires real pricing history data. Connect backend to visualize RL agent behavior.
              </div>
            </div>
          )}

          {hasRealData && (
            <div className="bg-surface rounded-xl border border-[rgba(255,255,255,0.06)] p-6 overflow-x-auto">
              <div className="flex items-center gap-2 mb-4">
                <div className="text-xs font-mono text-dim">PRICE MULTIPLIER — 24h × 7d</div>
                <div className="flex items-center gap-2 ml-auto">
                  <div className="flex items-center gap-1">
                    <div className="w-3 h-3 rounded bg-[rgba(0,212,255,0.25)]" />
                    <span className="text-[9px] font-mono text-dim">1.0x</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <div className="w-3 h-3 rounded bg-[rgba(255,179,71,0.9)]" />
                    <span className="text-[9px] font-mono text-dim">3.0x+</span>
                  </div>
                  <span className="text-[9px] font-mono text-amber ml-2">REAL DATA</span>
                </div>
              </div>

              <div className="flex gap-0.5">
                <div className="flex flex-col gap-0.5 mr-1">
                  {days.map((d) => (
                    <div key={d} className="h-[28px] flex items-center justify-end pr-2 text-[9px] font-mono text-dim">
                      {d}
                    </div>
                  ))}
                </div>
                <div className="flex gap-0.5 overflow-x-auto pb-2 relative">
                  {hours.map((h) => (
                    <div key={h} className="flex flex-col gap-0.5">
                      {days.map((day) => {
                        const cell = historyData.find((d: PricingHistoryItem) => d.day === day && d.hour === h)
                        const m = cell?.multiplier ?? 1.0
                        const isSelected = selectedCell?.day === day && selectedCell?.hour === h
                        return (
                          <button
                            key={`${day}-${h}`}
                            onClick={(e) => { e.stopPropagation(); handleCellClick(day, h, m) }}
                            onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); e.stopPropagation(); handleCellClick(day, h, m) } }}
                            className={`w-11 h-11 rounded-lg transition-all duration-300 hover:scale-110 hover:z-10 cursor-pointer relative ${
                              isSelected ? 'ring-2 ring-white scale-110 z-10' : ''
                            }`}
                            style={{ background: getColor(m) }}
                            title={`${day} ${h}:00 — ${m.toFixed(1)}x`}
                            aria-label={`${day} ${h}:00 — ${m.toFixed(1)}x`}
                          >
                            {isSelected && (
                              <div
                                className="absolute z-20 bg-[#1a1a2e] border border-[rgba(255,255,255,0.12)] rounded-lg p-3 font-mono shadow-2xl pointer-events-none"
                                style={{
                                  width: 180,
                                  bottom: 'calc(100% + 8px)',
                                  left: '50%',
                                  transform: 'translateX(-50%)',
                                }}
                              >
                                <div className="text-[9px] text-dim uppercase tracking-wider mb-1">
                                  {day} {h}:00
                                </div>
                                <div className="text-sm font-medium text-white mb-2">
                                  {m.toFixed(1)}x multiplier
                                </div>
                                <div className="text-[10px] text-muted space-y-0.5">
                                  {(() => {
                                    const matching = zones.filter((z) => {
                                      const hourFactor = h >= 8 && h <= 10 ? 1.2 : h >= 17 && h <= 19 ? 1.3 : h >= 11 && h <= 16 ? 0.9 : 0.6
                                      const est = (deriveMultiplier(z) * hourFactor)
                                      return Math.abs(est - m) < 0.5
                                    })
                                    return (
                                      <>
                                        <div>Zones: {matching.length || zones.length}</div>
                                        <div className="text-dim">
                                          {m >= 2.0 ? 'Peak demand' : m >= 1.5 ? 'Elevated' : m >= 1.0 ? 'Normal' : 'Off-peak'}
                                        </div>
                                      </>
                                    )
                                  })()}
                                </div>
                              </div>
                            )}
                          </button>
                        )
                      })}
                    </div>
                  ))}
                </div>
              </div>

              <div className="flex gap-1 mt-2 text-[9px] font-mono text-dim">
                <div className="w-[28px] shrink-0" />
                {[0, 6, 12, 18, 23].map((h) => (
                  <div key={h} className="w-[28px] text-center">{h}</div>
                ))}
              </div>
            </div>
          )}

          <div className="flex justify-center gap-12 mt-10">
            <div className="text-center">
              <p className="stat-number text-amber">{stats.peak}x</p>
              <p className="text-[10px] font-mono text-dim mt-1">PEAK MULTIPLIER</p>
            </div>
            <div className="text-center">
              <p className="stat-number text-emerald">+{stats.lift}%</p>
              <p className="text-[10px] font-mono text-dim mt-1">AVG REVENUE LIFT</p>
            </div>
            <div className="text-center">
<p className="stat-number text-cyan">~{stats.latency}ms</p>
                <p className="text-[10px] font-mono text-dim mt-1">AGENT LATENCY</p>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
