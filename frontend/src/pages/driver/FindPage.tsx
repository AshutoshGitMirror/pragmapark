import { useState, useEffect } from 'react'
import { fetchDriverLots, fetchLotDetail, startSession, type DriverLot, type DriverLotDetail } from '../../api/driverClient'

function SlotPicker({ lot, onBack, onStart }: { lot: DriverLotDetail; onBack: () => void; onStart: (slot: number) => void }) {
  const [selected, setSelected] = useState<number | null>(null)
  const [starting, setStarting] = useState(false)

  const regularSlots = lot.available_regular
  const handicapSlots = lot.available_handicap
  const evSlots = lot.available_ev
  const totalAvail = lot.available_spots

  const handleStart = async () => {
    if (selected === null) return
    setStarting(true)
    try {
      await onStart(selected)
    } catch { setStarting(false) }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <button onClick={onBack} className="text-[#475569] hover:text-white transition-colors text-lg">←</button>
        <div>
          <h2 className="text-base font-semibold text-white">{lot.name}</h2>
          <p className="text-[10px] text-[#475569]">{lot.address}</p>
        </div>
      </div>

      <div className="flex items-center gap-4 text-[10px] text-[#475569] pb-3" style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
        <span>{totalAvail} spots · ${lot.current_price.toFixed(2)}/hr</span>
        <span className={`px-1.5 py-0.5 rounded ${
          lot.predicted_occupancy > 0.7 ? 'bg-[rgba(245,158,11,0.15)] text-[#f59e0b]' :
          lot.predicted_occupancy > 0.4 ? 'bg-[rgba(0,212,255,0.1)] text-[#00d4ff]' :
          'bg-[rgba(90,106,138,0.15)] text-[#5a6a8a]'
        }`}>
          {Math.round(lot.predicted_occupancy * 100)}% full
        </span>
      </div>

      <div className="flex gap-2 text-[10px]">
        <span className="text-[#5a6a8a]">{regularSlots} regular</span>
        {handicapSlots > 0 && <span className="text-[#f59e0b]">{handicapSlots} ♿</span>}
        {evSlots > 0 && <span className="text-[#00c785]">{evSlots} ⚡</span>}
      </div>

      <p className="text-xs text-[#475569]">Tap a slot number to park:</p>

      <div className="grid grid-cols-4 gap-2">
        {Array.from({ length: Math.min(Math.max(totalAvail, 8), 16) }, (_, i) => i + 1).map((num) => {
          const isSelected = selected === num
          return (
            <button key={num} onClick={() => setSelected(num)}
              className="rounded-xl py-4 text-center transition-all duration-150"
              style={{
                background: isSelected
                  ? 'linear-gradient(135deg, #00d4ff, #0088cc)'
                  : 'linear-gradient(135deg, #0e0e24 0%, #12122a 50%, #0e0e24 100%)',
                boxShadow: isSelected
                  ? '0 0 16px rgba(0,212,255,0.3)'
                  : '0 1px 0 rgba(255,255,255,0.04), 0 0 0 1px rgba(255,255,255,0.04)',
              }}>
              <span className={`text-lg font-bold ${isSelected ? 'text-white' : 'text-white/80'}`}>{num}</span>
            </button>
          )
        })}
      </div>

      <button onClick={handleStart} disabled={selected === null || starting}
        className="w-full rounded-xl py-3.5 text-sm font-semibold text-white transition-all duration-200 disabled:opacity-40"
        style={{ background: 'linear-gradient(135deg, #00d4ff, #0088cc)' }}>
        {starting ? 'Starting...' : selected ? `Park in Slot ${selected}` : 'Select a Slot'}
      </button>
    </div>
  )
}

export function FindPage() {
  const [lots, setLots] = useState<DriverLot[]>([])
  const [selectedLot, setSelectedLot] = useState<DriverLotDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadLots = async () => {
    setError(null)
    try {
      const data = await fetchDriverLots()
      const sorted = (data || []).slice().sort((a, b) => a.dynamic_price - b.dynamic_price)
      setLots(sorted)
    } catch {
      setError('Could not load nearby lots. The backend may be warming up.')
    }
    setLoading(false)
  }

  useEffect(() => { loadLots() }, [])

  const handleSelectLot = async (lotId: string) => {
    setError(null)
    try {
      const detail = await fetchLotDetail(lotId)
      setSelectedLot(detail)
    } catch {
      setError('Could not load lot details. Please try again.')
    }
  }

  const handleStartSession = async (slot: number) => {
    if (!selectedLot) return
    setError(null)
    try {
      await startSession(selectedLot.lot_id, slot)
      window.location.hash = '/driver/active'
    } catch {
      setError('Failed to start session. Please try again.')
    }
  }

  if (selectedLot) {
    return (
      <div className="pt-2">
        <SlotPicker lot={selectedLot} onBack={() => setSelectedLot(null)} onStart={handleStartSession} />
      </div>
    )
  }

  return (
    <div className="space-y-4 pt-2">
      <div>
        <h1 className="text-lg font-semibold text-white">Find Parking</h1>
        <p className="text-xs text-[#475569] mt-0.5">Cheapest lots first</p>
      </div>

      {error && (
        <div className="p-3 rounded-lg text-xs font-mono text-center"
          style={{
            background: 'rgba(245,158,11,0.08)',
            border: '1px solid rgba(245,158,11,0.2)',
            color: '#f59e0b',
          }}>
          {error}
          <button onClick={loadLots} className="ml-2 underline hover:no-underline">Retry</button>
        </div>
      )}

      {loading ? (
        <div className="text-[#5a6a8a] text-sm animate-pulse text-center py-12">Finding nearby lots...</div>
      ) : lots.length === 0 && !error ? (
        <div className="rounded-xl p-10 text-center"
          style={{
            background: 'linear-gradient(135deg, #0e0e24 0%, #12122a 50%, #0e0e24 100%)',
            boxShadow: '0 1px 0 rgba(255,255,255,0.04), 0 0 0 1px rgba(255,255,255,0.04)',
          }}>
          <p className="text-sm text-[#475569]">No lots available nearby</p>
        </div>
      ) : (
        <div className="space-y-2">
          {lots.map((lot) => (
            <button key={lot.lot_id} onClick={() => handleSelectLot(lot.lot_id)}
              className="w-full text-left rounded-xl p-4 transition-all duration-150 hover:scale-[1.01]"
              style={{
                background: 'linear-gradient(135deg, #0e0e24 0%, #12122a 50%, #0e0e24 100%)',
                boxShadow: '0 1px 0 rgba(255,255,255,0.04), 0 0 0 1px rgba(255,255,255,0.04)',
              }}>
              <div className="flex items-start justify-between mb-1.5">
                <div>
                  <p className="text-sm font-medium text-white/90">{lot.name}</p>
                  <p className="text-[10px] text-[#475569] mt-0.5">{lot.city} · {lot.available_spots} spots</p>
                </div>
                <div className="text-right">
                  <p className="text-sm font-mono font-semibold text-[#00d4ff]">${lot.dynamic_price.toFixed(2)}</p>
                  <p className="text-[9px] text-[#475569]">/hr</p>
                </div>
              </div>
              <div className="h-1 rounded-full bg-[rgba(255,255,255,0.04)] w-full overflow-hidden">
                <div className="h-full rounded-full transition-all duration-500"
                  style={{
                    width: `${Math.round(lot.predicted_occupancy * 100)}%`,
                    background: lot.predicted_occupancy > 0.7 ? '#f59e0b' : '#00d4ff',
                  }} />
              </div>
              <div className="flex justify-between mt-1.5 text-[9px] text-[#475569]">
                <span>{lot.total_slots} slots</span>
                <span>{Math.round(lot.predicted_occupancy * 100)}% occupied</span>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
