import { useMemo, useEffect } from 'react'
import { fetchSlotsByLot } from '../../api/client'
import type { SlotGridData, Lot, MicroSlot, WeekDay } from '../../api/types'

interface MicroSlotsViewProps { lots: Lot[]; slotGrid: SlotGridData | null; onSlotGrid: (d: SlotGridData | null) => void }

const DAYS: WeekDay[] = ['monday','tuesday','wednesday','thursday','friday','saturday','sunday']

function weekDayAbr(d: WeekDay) { return d.slice(0, 3) }

export default function MicroSlotsView({ lots, slotGrid, onSlotGrid }: MicroSlotsViewProps) {
  const selectedLotId = slotGrid?.lot_id

  const handleLotSelect = async (lotId: string) => {
    if (!lotId) { onSlotGrid(null); return }
    try {
      const slots = await fetchSlotsByLot(lotId)
      onSlotGrid({ lot_id: lotId, slots })
    } catch { onSlotGrid({ lot_id: lotId, slots: [] }) }
  }

  const grouped = useMemo(() => {
    if (!slotGrid?.slots) return {}
    const map: Record<string, Record<WeekDay, MicroSlot[]>> = {}
    slotGrid.slots.forEach((s) => {
      const type = s.slot_type || 'general'
      const day = s.day_of_week as WeekDay
      if (!map[type]) map[type] = {} as any
      if (!map[type][day]) map[type][day] = []
      map[type][day].push(s)
    })
    return map
  }, [slotGrid])

  const totalUsed = useMemo(() => (slotGrid?.slots || []).filter((s) => s.is_reserved).length, [slotGrid])
  const totalSlots = slotGrid?.slots?.length || 0
  const occRate = totalSlots > 0 ? totalUsed / totalSlots : 0

  return (
    <div>
      <div className="flex gap-2.5 items-center mb-6 flex-wrap">
        <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl" style={{
          background: 'rgba(255,255,255,0.06)', backdropFilter: 'blur(12px)',
          border: '1px solid rgba(255,255,255,0.06)',
        }}>
          <i className="fas fa-warehouse text-[13px]" style={{ color: '#e2b84d' }} />
          <select value={selectedLotId || ''} onChange={(e) => handleLotSelect(e.target.value)}
            className="bg-transparent border-none text-[13px] outline-none cursor-pointer min-w-[180px]" style={{ color: '#f0eef8' }}>
            <option value="" style={{ background: '#1a1a28' }}>Select a lot...</option>
            {lots.map((l) => <option key={l.lot_id || l.id} value={l.lot_id || l.id} style={{ background: '#1a1a28' }}>{l.name}</option>)}
          </select>
        </div>
        {slotGrid && (
          <div className="flex gap-3 text-xs" style={{ color: '#a49fc4' }}>
            <span><span className="font-semibold" style={{ color: '#34d399' }}>{totalSlots - totalUsed}</span> free</span>
            <span><span className="font-semibold" style={{ color: '#f87171' }}>{totalUsed}</span> reserved</span>
            <span className="px-2 py-0.5 rounded-full text-[10px]" style={{ background: 'rgba(226,184,77,0.15)', color: '#e2b84d' }}>
              {(occRate * 100).toFixed(0)}% occupied
            </span>
          </div>
        )}
      </div>

      {!slotGrid && (
        <div className="text-center py-20 text-sm" style={{ color: '#64748b' }}>
          <i className="fas fa-calendar-alt text-3xl block mb-3 opacity-50" />
          Select a parking lot to view its micro-slot grid
        </div>
      )}

      {slotGrid && Object.keys(grouped).length === 0 && (
        <div className="text-center py-20 text-sm" style={{ color: '#64748b' }}>
          <i className="fas fa-info-circle text-2xl block mb-3" />
          No slot data available for this lot
        </div>
      )}

      {slotGrid && Object.entries(grouped).map(([type, days]) => (
        <div key={type} className="mb-6">
          <h3 className="text-[11px] mb-3 uppercase tracking-[0.8px]" style={{ color: 'rgba(240,238,248,0.55)' }}>
            <i className="fas fa-tag mr-1" /> {type}
          </h3>
          <div className="grid gap-3" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(380px, 1fr))' }}>
            {DAYS.map((day) => {
              const slots = days[day] || []
              if (slots.length === 0) return null
              const used = slots.filter((s) => s.is_reserved).length
              return (
                <div key={day} className="p-[18px] rounded-2xl" style={{
                  background: 'rgba(255,255,255,0.06)', backdropFilter: 'blur(16px)',
                  border: '1px solid rgba(255,255,255,0.06)',
                }}>
                  <div className="flex items-center justify-between mb-3">
                    <span className="text-sm font-semibold capitalize">{weekDayAbr(day)}</span>
                    <span className="text-[11px] px-2 py-0.5 rounded-full" style={{ background: used > 0 ? 'rgba(248,113,113,0.15)' : 'rgba(52,211,153,0.15)', color: used > 0 ? '#f87171' : '#34d399' }}>
                      {slots.length - used} free / {slots.length}
                    </span>
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {slots.map((slot, i) => (
                      <div key={i} className="w-5 h-5 rounded text-[8px] flex items-center justify-center font-semibold cursor-default transition-all"
                        style={{
                          background: slot.is_reserved ? 'rgba(248,113,113,0.2)' : 'rgba(52,211,153,0.12)',
                          color: slot.is_reserved ? '#f87171' : '#34d399',
                          border: `1px solid ${slot.is_reserved ? 'rgba(248,113,113,0.2)' : 'rgba(52,211,153,0.15)'}`,
                        }}
                        title={`${slot.is_reserved ? 'Reserved' : 'Free'} — ${slot.start_time || '00:00'}–${slot.end_time || '23:59'}`}
                      >
                        {i + 1}
                      </div>
                    ))}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      ))}
    </div>
  )
}
