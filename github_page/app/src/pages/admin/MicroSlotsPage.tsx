import { useState, useEffect } from 'react'
import { fetchMicroSlots, type MicroSlot } from '../../api/adminClient'

export function MicroSlotsPage() {
  const [slots, setSlots] = useState<MicroSlot[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedLot, setSelectedLot] = useState('A1')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let mounted = true
    const load = async () => {
      try {
        const data = await fetchMicroSlots(selectedLot)
        if (mounted) setSlots(data)
      } catch (err: any) {
        if (mounted) setError(err.message)
      } finally {
        if (mounted) setLoading(false)
      }
    }
    load()
    const interval = setInterval(load, 15000)
    return () => { mounted = false; clearInterval(interval) }
  }, [selectedLot])

  const getSlotStyle = (slot: MicroSlot) => {
    if (slot.state === 'occupied') return 'bg-red-500/10 border-red-500/25 text-red-400'
    if (slot.probability !== undefined && slot.probability > 0.7) return 'bg-[rgba(245,158,11,0.08)] border-[rgba(245,158,11,0.25)] text-[#f59e0b]'
    return 'bg-[rgba(0,199,133,0.05)] border-[rgba(0,199,133,0.15)] text-[#00c785]'
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-[#64748b] animate-pulse text-sm">Loading slots...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-red-400 text-sm">{error}</div>
      </div>
    )
  }

  return (
    <div className="space-y-5">
      <h1 className="text-lg font-semibold text-white">Micro Slots</h1>

      <div className="flex items-center gap-3">
        <select
          value={selectedLot}
          onChange={(e) => setSelectedLot(e.target.value)}
          className="bg-[#0a0a0f] border border-[rgba(255,255,255,0.08)] rounded-lg px-3 py-1.5 text-xs text-[#64748b] focus:outline-none focus:border-[rgba(0,212,255,0.4)]"
        >
          {['A1', 'A2', 'B1', 'B2', 'BR1', 'BR2', 'DB1'].map((lot) => (
            <option key={lot} value={lot}>Lot {lot}</option>
          ))}
        </select>
        <span className="text-[11px] text-[#475569]">{slots.length} slots</span>
      </div>

      <div className="flex items-center gap-4 text-[10px] text-[#475569]">
        <div className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded bg-[rgba(0,199,133,0.3)]" />
          Available
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded bg-[rgba(245,158,11,0.3)]" />
          High Demand
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded bg-red-500/30" />
          Occupied
        </div>
      </div>

      <div className="grid grid-cols-6 sm:grid-cols-8 md:grid-cols-10 lg:grid-cols-12 gap-1.5">
        {slots.map((slot) => (
          <div
            key={slot.id}
            className={`aspect-square rounded-lg border flex items-center justify-center text-[10px] font-mono transition-colors ${getSlotStyle(slot)}`}
            title={`${slot.row_label}${slot.position} — ${slot.state || 'available'}${slot.probability !== undefined ? ` (${(slot.probability * 100).toFixed(0)}%)` : ''}`}
          >
            {slot.position}
          </div>
        ))}
      </div>
    </div>
  )
}
