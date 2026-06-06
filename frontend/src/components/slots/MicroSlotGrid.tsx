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

import { useEffect, useState, useMemo, useRef, useCallback } from 'react'
import { useReveal } from '../../hooks/useScrollReveal'
import { fetchMicroSlots } from '../../api/client'
import { fallbackMicroSlots } from '../../api/fallbackData'
import { useApiWithFallback } from '../../hooks/useApi'
import type { MicroSlot } from '../../api/types'

const statusConfig: Record<string, { bg: string; border: string; label: string }> = {
  available: { bg: 'rgba(0,199,133,0.08)', border: '#00c785', label: 'FREE' },
  occupied: { bg: 'rgba(255,179,71,0.08)', border: '#ffb347', label: 'OCC' },
  reserved: { bg: 'rgba(0,212,255,0.08)', border: '#00d4ff', label: 'RSV' },
  prebooked: { bg: 'rgba(168,85,247,0.08)', border: '#a855f7', label: 'PRB' },
  maintenance: { bg: 'rgba(148,163,184,0.06)', border: '#475569', label: 'MNT' },
  free: { bg: 'rgba(0,199,133,0.08)', border: '#00c785', label: 'FREE' },
}

export function MicroSlotGrid() {
  const { data: slots, source } = useApiWithFallback(
    () => fetchMicroSlots('A1'),
    fallbackMicroSlots,
  )

  const isLive = source === 'live'

  const visible = useReveal(100)
  const [selectedSlot, setSelectedSlot] = useState<MicroSlot | null>(null)
  const gridRef = useRef<HTMLDivElement>(null)
  const [columns, setColumns] = useState(10)

  useEffect(() => {
    const el = gridRef.current
    if (!el) return
    const calc = () => {
      const colCount = Math.floor(el.clientWidth / 30)
      setColumns(Math.max(1, colCount))
    }
    calc()
    const ro = new ResizeObserver(calc)
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  const handleGridKeyDown = useCallback((e: React.KeyboardEvent, idx: number) => {
    const buttons = gridRef.current?.querySelectorAll<HTMLButtonElement>('button')
    if (!buttons || !buttons[idx]) return

    if (e.key === 'Enter' || e.key === ' ') return // handled per-button

    let targetIdx = idx
    switch (e.key) {
      case 'ArrowRight':
        e.preventDefault()
        targetIdx = Math.min(idx + 1, buttons.length - 1)
        break
      case 'ArrowLeft':
        e.preventDefault()
        targetIdx = Math.max(idx - 1, 0)
        break
      case 'ArrowDown':
        e.preventDefault()
        targetIdx = Math.min(idx + columns, buttons.length - 1)
        break
      case 'ArrowUp':
        e.preventDefault()
        targetIdx = Math.max(idx - columns, 0)
        break
      default:
        return
    }
    buttons[targetIdx].focus()
  }, [columns])

  useEffect(() => {
    if (!selectedSlot) return
    const handler = () => setSelectedSlot(null)
    window.addEventListener('click', handler)
    return () => window.removeEventListener('click', handler)
  }, [selectedSlot])

  const counts = useMemo(() => {
    const c: Record<string, number> = { free: 0, occupied: 0, reserved: 0, prebooked: 0, maintenance: 0, available: 0 }
    slots.forEach((s) => {
      const key = s.state || 'free'
      c[key] = (c[key] || 0) + 1
    })
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
            <h2 className="section-headline">Every spot.{isLive ? ' Live.' : ' Simulated.'} Vision Zero.</h2>
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
              <div ref={gridRef} className="flex flex-wrap gap-1.5" role="grid" aria-label="Parking slot grid">
                {slots.slice(0, 200).map((slot, idx) => {
                  const cfg = statusConfig[slot.state || 'free'] || statusConfig.free
                  const isSelected = selectedSlot?.id === slot.id
                  return (
                    <button
                      key={slot.id}
                      onClick={(e) => { e.stopPropagation(); setSelectedSlot(isSelected ? null : slot) }}
                      onKeyDown={(e) => {
                        handleGridKeyDown(e, idx)
                        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); e.stopPropagation(); setSelectedSlot(isSelected ? null : slot) }
                      }}
                      className={`w-[24px] h-[24px] rounded-sm border cursor-pointer transition-all duration-300 hover:scale-125 relative ${
                        isSelected ? 'ring-2 ring-white scale-125 z-10' : ''
                      }`}
                      aria-label={`Slot ${slot.row_label}${slot.position} — ${slot.state || 'free'}`}
                      style={{
                        background: cfg.bg,
                        borderColor: cfg.border,
                        opacity: slot.state === 'available' || slot.state === 'free' ? 0.7 : 1,
                        boxShadow: (slot.state === 'available' || slot.state === 'free')
                          ? 'inset 0 0 6px rgba(0,199,133,0.1)'
                          : 'none',
                      }}
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
                          <div className="text-[9px] text-[#64748b] uppercase tracking-wider mb-1">
                            Slot {slot.row_label}{slot.position}
                          </div>
                          <div className="text-sm font-medium text-white mb-2">
                            {cfg.label}
                          </div>
                          <div className="text-[10px] text-[#94a3b8] space-y-0.5">
                            <div className="flex justify-between">
                              <span className="text-[#64748b]">Type:</span>
                              <span className="capitalize">{slot.slot_type}</span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-[#64748b]">Confidence:</span>
                              <span>{Math.round((slot.probability || 0) * 100)}%</span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-[#64748b]">Score:</span>
                              <span>{((slot.base_modifier_score || 0) * 100).toFixed(0)}</span>
                            </div>
                          </div>
                        </div>
                      )}
                    </button>
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
