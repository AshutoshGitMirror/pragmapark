/**
 * MicroSlotGrid.tsx — Live micro-slot visualization.
 *
 * BEFORE (broken):
 *   - fetchLots().catch(() => {}) — silently failed
 *   - Generated 100 random slots on every mount (different each reload)
 *   - On API success, rebuilt slot array with wrong proportions (free/occupied/reserved)
 *   - No indication if data was live
 *
 * AFTER (fixed):
 *   - useApiWithFallback with fallbackMicroSlots (consistent 40-slot grid)
 *   - On live data, fetches real /micro/lots/A1/slots
 *   - Slot states reflect actual API responses
 *   - LIVE badge when connected
 */

import { useEffect, useState, useMemo } from 'react'
import { fetchMicroSlots } from '../../api/client'
import { fallbackMicroSlots } from '../../api/fallbackData'
import { useApiWithFallback } from '../../hooks/useApi'
import type { MicroSlot } from '../../api/types'

const statusConfig: Record<string, { bg: string; border: string; label: string }> = {
  available: { bg: 'rgba(0,199,133,0.08)', border: '#00c785', label: 'FREE' },
  occupied: { bg: 'rgba(255,179,71,0.08)', border: '#ffb347', label: 'OCC' },
  reserved: { bg: 'rgba(0,212,255,0.08)', border: '#00d4ff', label: 'RSV' },
  maintenance: { bg: 'rgba(148,163,184,0.06)', border: '#475569', label: 'MNT' },
  free: { bg: 'rgba(0,199,133,0.08)', border: '#00c785', label: 'FREE' },
}

export function MicroSlotGrid() {
  const { data: slots, source } = useApiWithFallback(
    () => fetchMicroSlots('A1'),
    fallbackMicroSlots,
  )

  const isLive = source === 'live'

  const [visible, setVisible] = useState(false)
  useEffect(() => {
    const t = setTimeout(() => setVisible(true), 100)
    return () => clearTimeout(t)
  }, [])

  const counts = useMemo(() => {
    const c: Record<string, number> = { free: 0, occupied: 0, reserved: 0, maintenance: 0, available: 0 }
    slots.forEach((s) => {
      const key = s.state || 'free'
      c[key] = (c[key] || 0) + 1
    })
    // Treat 'available' as 'free' for display
    c.free += c.available
    return c
  }, [slots])

  const avgProbability = useMemo(() => {
    if (!slots.length) return 0
    return Math.round(slots.reduce((a, s) => a + (s.probability || 0), 0) / slots.length * 100)
  }, [slots])

  const availableNow = counts.free || counts.available || 0
  const totalSlots = slots.length

  return (
    <section className="section bg-[#0a0a0f]" id="slots">
      <div className="section-inner">
        <div className="grid grid-cols-1 lg:grid-cols-[35%_65%] gap-12 items-start">
          {/* Left column */}
          <div className={`transition-all duration-700 ${visible ? 'opacity-100 translate-x-0' : 'opacity-0 -translate-x-8'}`}>
            <div className="flex items-center gap-3 mb-4">
              <p className="section-label !mb-0" style={{ color: '#00c785' }}>MICRO-SLOT GRID</p>
              {isLive && (
                <span className="flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-[rgba(0,199,133,0.1)] border border-[rgba(0,199,133,0.2)]">
                  <span className="w-1.5 h-1.5 rounded-full bg-[#00c785] animate-pulse" />
                  <span className="text-[9px] font-mono text-[#00c785] uppercase tracking-wider">Live</span>
                </span>
              )}
            </div>
            <h2 className="section-headline">Every spot. Live. Vision Zero.</h2>
            <p className="section-body mb-8">
              Individual slot management with real-time probability scoring.
              Each spot carries its own state machine, price modifier, and availability prediction.
              Handicap, EV charging, covered, and premium slots each carry their own pricing logic.
              {!isLive && (
                <span className="block mt-2 text-[#64748b]">Showing simulation data — connect to backend for live slot states.</span>
              )}
            </p>

            <div className="grid grid-cols-2 gap-4 mb-6">
              <div className="bg-[#13131f] rounded-lg p-4 border border-[rgba(255,255,255,0.04)]">
                <p className="stat-number text-[#00c785]">{availableNow}</p>
                <p className="text-[10px] font-mono text-[#64748b]">Available Now</p>
              </div>
              <div className="bg-[#13131f] rounded-lg p-4 border border-[rgba(255,255,255,0.04)]">
                <p className="stat-number text-[#ffb347]">{counts.occupied}</p>
                <p className="text-[10px] font-mono text-[#64748b]">Occupied</p>
              </div>
              <div className="bg-[#13131f] rounded-lg p-4 border border-[rgba(255,255,255,0.04)]">
                <p className="stat-number text-[#00d4ff]">{counts.reserved}</p>
                <p className="text-[10px] font-mono text-[#64748b]">Reserved</p>
              </div>
              <div className="bg-[#13131f] rounded-lg p-4 border border-[rgba(255,255,255,0.04)]">
                <p className="stat-number text-[#94a3b8]">{avgProbability}%</p>
                <p className="text-[10px] font-mono text-[#64748b]">Avg Confidence</p>
              </div>
            </div>

            <div className="flex items-center gap-4 text-[10px] font-mono text-[#64748b]">
              {Object.entries(statusConfig).filter(([k]) => k !== 'available').map(([key, cfg]) => (
                <div key={key} className="flex items-center gap-1.5">
                  <div className="w-2 h-2 rounded-full" style={{ background: cfg.border }} />
                  {cfg.label}
                </div>
              ))}
            </div>
          </div>

          {/* Right column — Slot grid */}
          <div className={`transition-all duration-700 delay-200 ${visible ? 'opacity-100 translate-x-0' : 'opacity-0 translate-x-8'}`}>
            <div className="bg-[#13131f] rounded-xl border border-[rgba(255,255,255,0.06)] p-4">
              <div className="flex flex-wrap gap-1.5">
                {slots.slice(0, 200).map((slot) => {
                  const cfg = statusConfig[slot.state || 'free'] || statusConfig.free
                  return (
                    <div
                      key={slot.id}
                      className="w-[24px] h-[24px] rounded-sm border cursor-crosshair transition-all duration-300 hover:scale-125"
                      style={{
                        background: cfg.bg,
                        borderColor: cfg.border,
                        opacity: slot.state === 'available' || slot.state === 'free' ? 0.7 : 1,
                        boxShadow: (slot.state === 'available' || slot.state === 'free')
                          ? 'inset 0 0 6px rgba(0,199,133,0.1)'
                          : 'none',
                      }}
                      title={`${slot.row_label}${slot.position} (${slot.slot_type}): ${cfg.label} — ${Math.round((slot.probability || 0) * 100)}%`}
                    />
                  )
                })}
              </div>
            </div>
            <p className="text-[10px] font-mono text-[#64748b] mt-3 text-right">
              Showing {Math.min(totalSlots, 200)} of {totalSlots} slots
              {isLive && ' — live from A1'}
            </p>
          </div>
        </div>
      </div>
    </section>
  )
}
