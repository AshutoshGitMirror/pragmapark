import { useState, useEffect } from 'react'
import { fetchLots, fetchMicroSlots, type Lot, type MicroSlot } from '../../api/adminClient'

export function MicroSlotsPage() {
  const [lots, setLots] = useState<Lot[]>([])
  const [selectedLot, setSelectedLot] = useState<string>('')
  const [slots, setSlots] = useState<MicroSlot[]>([])
  const [loading, setLoading] = useState(true)
  const [slotsLoading, setSlotsLoading] = useState(false)

  useEffect(() => {
    fetchLots().then((data) => {
      setLots(data)
      if (data.length > 0) setSelectedLot(data[0].lot_id)
    }).catch(() => {}).finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    if (!selectedLot) return
    setSlotsLoading(true)
    fetchMicroSlots(selectedLot).then(setSlots).catch(() => {}).finally(() => setSlotsLoading(false))
  }, [selectedLot])

  if (loading) return <div className="flex items-center justify-center h-64"><div className="text-dim animate-pulse">Loading...</div></div>

  return (
    <div className="space-y-5">
      <h1 className="text-xl font-light text-white">Micro Slots</h1>

      <div className="flex items-center gap-3">
        <select
          value={selectedLot}
          onChange={(e) => setSelectedLot(e.target.value)}
          className="bg-[#0a0a0f] border border-white/10 rounded-lg px-3 py-2 text-xs text-muted focus:outline-none focus:border-cyan-500/50"
        >
          {lots.map((lot) => (
            <option key={lot.lot_id} value={lot.lot_id}>{lot.name} ({lot.lot_id})</option>
          ))}
        </select>
        <span className="text-[10px] text-dim">{slots.length} slots</span>
      </div>

      {slotsLoading ? (
        <div className="text-dim text-sm animate-pulse">Loading slots...</div>
      ) : (
        <div className="grid grid-cols-6 sm:grid-cols-8 md:grid-cols-10 lg:grid-cols-12 gap-1.5">
          {slots.map((slot) => (
            <div
              key={slot.id}
              className={`aspect-square rounded-lg border flex items-center justify-center text-[10px] font-mono transition-colors ${
                slot.state === 'occupied'
                  ? 'bg-red-500/10 border-red-500/30 text-red-400'
                  : slot.probability && slot.probability > 0.7
                  ? 'bg-amber-500/10 border-amber-500/30 text-amber-400'
                  : 'bg-emerald-500/5 border-emerald-500/20 text-emerald-400'
              }`}
              title={`${slot.row_label}-${slot.position} | ${slot.slot_type} | score: ${slot.base_modifier_score.toFixed(2)}`}
            >
              {slot.row_label}{slot.position}
            </div>
          ))}
        </div>
      )}

      <div className="flex items-center gap-4 text-[10px] text-dim">
        <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded bg-emerald-500/30" /> Available</span>
        <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded bg-amber-500/30" /> High Prob.</span>
        <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded bg-red-500/30" /> Occupied</span>
      </div>
    </div>
  )
}
