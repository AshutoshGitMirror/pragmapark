import { useState, useEffect } from 'react'
import { fetchMicroSlots, fetchLots, type MicroSlot, type Lot } from '../../api/adminClient'

const stateColors: Record<string, string> = {
  available: '#00d4ff',
  occupied: '#f59e0b',
  reserved: '#00c785',
  prebooked: '#a855f7',
  maintenance: '#ff4757',
}

export function MicroSlotsPage() {
  const [lots, setLots] = useState<Lot[]>([])
  const [selectedLot, setSelectedLot] = useState('')
  const [slots, setSlots] = useState<MicroSlot[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let mounted = true
    fetchLots().then((data) => {
      if (mounted) {
        setLots(data)
        if (data.length > 0) setSelectedLot(data[0].lot_id)
      }
    })
    return () => { mounted = false }
  }, [])

  useEffect(() => {
    if (!selectedLot) return
    let mounted = true
    setLoading(true)
    fetchMicroSlots(selectedLot).then((data) => {
      if (mounted) { setSlots(data); setLoading(false) }
    }).catch(() => { if (mounted) setLoading(false) })
    return () => { mounted = false }
  }, [selectedLot])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-[#5a6a8a] animate-pulse text-sm">Loading slots...</div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-white">Micro Slots</h1>
        <p className="text-xs text-[#5a6a8a] mt-1">Individual slot status and control</p>
      </div>

      <div className="flex items-center gap-3">
        <select
          value={selectedLot}
          onChange={(e) => setSelectedLot(e.target.value)}
          className="bg-[#0e0e24] border border-[rgba(255,255,255,0.08)] rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none focus:border-[rgba(0,212,255,0.3)]"
        >
          {lots.map((lot) => (
            <option key={lot.lot_id} value={lot.lot_id}>{lot.name}</option>
          ))}
        </select>
        <span className="text-xs text-[#475569]">{slots.length} slots</span>
      </div>

      <div className="flex gap-4 text-xs">
        {Object.entries(stateColors).map(([state, color]) => (
          <div key={state} className="flex items-center gap-1.5">
            <div className="w-2.5 h-2.5 rounded-sm" style={{ backgroundColor: color }} />
            <span className="text-[#5a6a8a] capitalize">{state}</span>
          </div>
        ))}
      </div>

      <div className="rounded-xl p-6"
        style={{
          background: 'linear-gradient(135deg, #0e0e24 0%, #12122a 50%, #0e0e24 100%)',
          boxShadow: '0 1px 0 rgba(255,255,255,0.04), 0 0 0 1px rgba(255,255,255,0.04)',
        }}>
        <div className="grid grid-cols-5 sm:grid-cols-8 md:grid-cols-10 gap-2">
          {slots.map((slot) => (
            <div
              key={slot.id}
              className="aspect-square rounded-lg flex items-center justify-center text-[10px] font-mono font-medium transition-all duration-200 hover:scale-110 cursor-default"
              style={{
                backgroundColor: `${stateColors[slot.state || 'available']}15`,
                color: stateColors[slot.state || 'available'],
                border: `1px solid ${stateColors[slot.state || 'available']}30`,
                boxShadow: slot.state === 'available' ? '0 0 8px rgba(0,212,255,0.08)' : 'none',
              }}
              title={`${slot.row_label}${slot.position} — ${slot.state || 'available'} (${((slot.probability || 0) * 100).toFixed(0)}%)`}
            >
              {slot.row_label}{slot.position}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
