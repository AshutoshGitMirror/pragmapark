import { useState, useEffect } from 'react'
import { fetchDriverLots, fetchLotDetail, startSession, prebookSlot, type DriverLot, type DriverLotDetail } from '../../api/driverClient'

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
  const [reserveLot, setReserveLot] = useState<DriverLot | null>(null)
  const [successPrebook, setSuccessPrebook] = useState<any>(null)

  const [slotType, setSlotType] = useState<string>('')
  const [maxPrice, setMaxPrice] = useState<number>(150)

  const loadLots = async () => {
    setLoading(true)
    setError(null)
    try {
      const params: any = {}
      if (slotType) params.slot_type = slotType
      if (maxPrice < 150) params.max_price = maxPrice
      const data = await fetchDriverLots(params)
      const sorted = (data || []).slice().sort((a, b) => a.dynamic_price - b.dynamic_price)
      setLots(sorted)
    } catch {
      setError('Could not load nearby lots. The backend may be warming up.')
    }
    setLoading(false)
  }

  useEffect(() => {
    loadLots()
  }, [slotType, maxPrice])

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
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-white/[0.04]">
        <div>
          <h1 className="text-lg font-semibold text-white">Find Parking</h1>
          <p className="text-xs text-[#475569] mt-0.5">Cheapest lots first</p>
        </div>
        
        {/* Filters Panel */}
        <div className="flex flex-wrap items-center gap-4 bg-[#09091b] p-3 rounded-xl border border-white/[0.04] shadow-inner">
          {/* Slot Type Dropdown */}
          <div className="flex flex-col gap-1">
            <span className="text-[9px] uppercase tracking-wider font-bold text-[#5a6a8a]">Slot Type</span>
            <select
              value={slotType}
              onChange={(e) => setSlotType(e.target.value)}
              className="bg-[#070714] border border-white/10 rounded-lg px-2.5 py-1.5 text-xs text-white focus:outline-none focus:border-[#00d4ff] cursor-pointer"
            >
              <option value="">All Spots</option>
              <option value="regular">Regular</option>
              <option value="handicap">Handicap ♿</option>
              <option value="ev">EV Charging ⚡</option>
            </select>
          </div>

          {/* Max Price Range Slider */}
          <div className="flex flex-col gap-1 min-w-[120px]">
            <div className="flex justify-between items-center text-[9px] uppercase tracking-wider font-bold text-[#5a6a8a] gap-2">
              <span>Max Price</span>
              <span className="text-[#00d4ff] font-mono text-xs font-semibold">
                {maxPrice === 150 ? 'Any' : `$${maxPrice}`}
              </span>
            </div>
            <input
              type="range"
              min="5"
              max="150"
              step="5"
              value={maxPrice}
              onChange={(e) => setMaxPrice(Number(e.target.value))}
              className="w-full accent-[#00d4ff] h-1 bg-white/10 rounded-lg appearance-none cursor-pointer"
            />
          </div>

          {/* Reset button */}
          {(slotType !== '' || maxPrice !== 150) && (
            <button
              onClick={() => { setSlotType(''); setMaxPrice(150); }}
              className="self-end px-2.5 py-1.5 rounded-lg text-[10px] uppercase font-bold tracking-wider text-[#ff4757]/80 hover:text-[#ff4757] hover:bg-[#ff4757]/5 border border-[#ff4757]/10 transition-all cursor-pointer mt-auto"
            >
              Reset
            </button>
          )}
        </div>
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
        <div className="space-y-3">
          {lots.map((lot) => (
            <div key={lot.lot_id}
              className="w-full text-left rounded-xl p-4 transition-all duration-150"
              style={{
                background: 'linear-gradient(135deg, #0e0e24 0%, #12122a 50%, #0e0e24 100%)',
                boxShadow: '0 1px 0 rgba(255,255,255,0.04), 0 0 0 1px rgba(255,255,255,0.04)',
              }}>
              <div onClick={() => handleSelectLot(lot.lot_id)} className="cursor-pointer hover:opacity-95">
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
              </div>

              <div className="flex gap-2 mt-3 pt-3 border-t border-white/[0.04]">
                <button onClick={() => handleSelectLot(lot.lot_id)}
                  className="flex-1 py-1.5 rounded-lg text-xs font-semibold text-white/80 hover:text-white hover:bg-white/[0.04] border border-white/10 transition-colors">
                  Park Here
                </button>
                <button onClick={() => setReserveLot(lot)}
                  className="flex-1 py-1.5 rounded-lg text-xs font-semibold text-white transition-all hover:opacity-90"
                  style={{ background: 'linear-gradient(135deg, #00d4ff, #0088cc)' }}>
                  Reserve
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {reserveLot && (
        <ReserveModal
          lot={reserveLot}
          onClose={() => setReserveLot(null)}
          onSuccess={(res) => {
            setReserveLot(null)
            setSuccessPrebook(res)
          }}
        />
      )}

      {successPrebook && (
        <ReserveSuccessModal
          prebook={successPrebook}
          onClose={() => {
            setSuccessPrebook(null)
            window.location.hash = '/driver/bookings'
          }}
        />
      )}
    </div>
  )
}

function ReserveModal({
  lot,
  onClose,
  onSuccess,
}: {
  lot: DriverLot
  onClose: () => void
  onSuccess: (prebookResponse: any) => void
}) {
  const [lotDetail, setLotDetail] = useState<DriverLotDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [selectedSlot, setSelectedSlot] = useState<number | null>(null)

  const getNextTime = (minutes: number) => new Date(Date.now() + minutes * 60 * 1000)
  const toLocalDateTimeString = (date: Date) => {
    const pad = (num: number) => String(num).padStart(2, '0')
    return date.getFullYear() +
      '-' + pad(date.getMonth() + 1) +
      '-' + pad(date.getDate()) +
      'T' + pad(date.getHours()) +
      ':' + pad(date.getMinutes())
  }

  const [targetTime, setTargetTime] = useState(toLocalDateTimeString(getNextTime(30)))
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const loadDetail = async () => {
      try {
        const detail = await fetchLotDetail(lot.lot_id)
        setLotDetail(detail)
        setSelectedSlot(1)
      } catch {
        setError('Failed to fetch lot slots details.')
      }
      setLoading(false)
    }
    loadDetail()
  }, [lot.lot_id])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!selectedSlot) return
    setSubmitting(true)
    setError(null)
    try {
      const isoTargetTime = new Date(targetTime).toISOString()
      const res = await prebookSlot(lot.lot_id, selectedSlot, isoTargetTime)
      onSuccess(res)
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Prebooking failed. Please check your balance.')
      setSubmitting(false)
    }
  }

  const basePrice = lot.base_price || 2.5
  const deposit = basePrice * 1.0
  const bookingFee = 2.0
  const total = deposit + bookingFee

  const minTimeString = toLocalDateTimeString(getNextTime(5))
  const maxTimeString = toLocalDateTimeString(getNextTime(6 * 60))

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
      <div className="w-full max-w-sm rounded-2xl p-6 space-y-4 text-left"
        style={{
          background: 'linear-gradient(135deg, #0d0d21 0%, #151532 50%, #0d0d21 100%)',
          border: '1px solid rgba(255,255,255,0.08)',
          boxShadow: '0 20px 40px rgba(0,0,0,0.5)',
        }}>
        <div className="flex justify-between items-center">
          <h3 className="text-base font-semibold text-white">Reserve a Slot</h3>
          <button type="button" onClick={onClose} className="text-[#475569] hover:text-white transition-colors">✕</button>
        </div>

        <div className="text-xs text-[#5a6a8a]">
          <p className="font-semibold text-white/95">{lot.name}</p>
          <p className="mt-0.5">{lot.address}</p>
        </div>

        {loading ? (
          <div className="text-center py-6 text-sm text-[#5a6a8a] animate-pulse">Loading lot details...</div>
        ) : error && !lotDetail ? (
          <div className="text-center py-4 text-xs font-mono text-[#f59e0b] bg-[rgba(245,158,11,0.08)] rounded-lg p-2">
            {error}
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1.5">
              <label className="text-[10px] text-[#5a6a8a] uppercase font-bold tracking-wider">Select Slot</label>
              <select value={selectedSlot || ''} onChange={(e) => setSelectedSlot(Number(e.target.value))}
                className="w-full bg-[#070714] border border-white/10 rounded-lg p-2.5 text-xs text-white focus:outline-none focus:border-[#00d4ff]">
                {Array.from({ length: Math.min(Math.max(lotDetail?.available_spots || 8, 8), 16) }, (_, i) => i + 1).map((num) => (
                  <option key={num} value={num}>Slot #{num}</option>
                ))}
              </select>
            </div>

            <div className="space-y-1.5">
              <label className="text-[10px] text-[#5a6a8a] uppercase font-bold tracking-wider">Arrival Time</label>
              <input type="datetime-local" value={targetTime} min={minTimeString} max={maxTimeString}
                onChange={(e) => setTargetTime(e.target.value)} required
                className="w-full bg-[#070714] border border-white/10 rounded-lg p-2.5 text-xs text-white focus:outline-none focus:border-[#00d4ff] font-mono" />
              <p className="text-[9px] text-[#475569]">Must be within the next 6 hours</p>
            </div>

            <div className="bg-[#070714] rounded-xl p-3.5 space-y-2 border border-white/[0.02]">
              <p className="text-[10px] text-[#5a6a8a] uppercase font-bold tracking-wider mb-1">Estimated Cost Breakdown</p>
              <div className="flex justify-between text-xs">
                <span className="text-[#475569]">Booking Fee (Non-refundable)</span>
                <span className="text-white/80 font-mono">${bookingFee.toFixed(2)}</span>
              </div>
              <div className="flex justify-between text-xs">
                <span className="text-[#475569]">Refundable Deposit</span>
                <span className="text-white/80 font-mono">${deposit.toFixed(2)}</span>
              </div>
              <div className="h-px bg-white/[0.04] my-1" />
              <div className="flex justify-between text-xs font-semibold">
                <span className="text-white/90">Total Due Now</span>
                <span className="text-[#00d4ff] font-mono">${total.toFixed(2)}</span>
              </div>
            </div>

            {error && (
              <div className="text-[10px] text-center font-mono text-[#ff4757] bg-[rgba(255,71,87,0.06)] rounded-lg p-2 border border-[rgba(255,71,87,0.15)]">
                {error}
              </div>
            )}

            <div className="flex gap-3 pt-2">
              <button type="button" onClick={onClose}
                className="flex-1 py-2.5 rounded-lg text-xs font-semibold text-white/70 hover:text-white hover:bg-white/5 border border-white/10 transition-colors">
                Cancel
              </button>
              <button type="submit" disabled={submitting || !selectedSlot}
                className="flex-1 py-2.5 rounded-lg text-xs font-semibold text-white transition-all disabled:opacity-40"
                style={{ background: 'linear-gradient(135deg, #00d4ff, #0088cc)' }}>
                {submitting ? 'Booking...' : 'Confirm Reserve'}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  )
}

function ReserveSuccessModal({
  prebook,
  onClose,
}: {
  prebook: any
  onClose: () => void
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
      <div className="w-full max-w-sm rounded-2xl p-6 space-y-5 text-center"
        style={{
          background: 'linear-gradient(135deg, #0d0d21 0%, #151532 50%, #0d0d21 100%)',
          border: '1px solid rgba(255,255,255,0.08)',
          boxShadow: '0 20px 40px rgba(0,0,0,0.5)',
        }}>
        <div className="w-12 h-12 rounded-full bg-[rgba(0,199,133,0.1)] flex items-center justify-center mx-auto">
          <span className="text-xl text-[#00c785]">✓</span>
        </div>
        <div className="space-y-1">
          <h3 className="text-base font-semibold text-white">Reservation Confirmed</h3>
          <p className="text-xs text-[#5a6a8a]">Your slot has been successfully reserved</p>
        </div>

        <div className="bg-[#070714] rounded-xl p-4 text-left space-y-2 text-xs">
          <div className="flex justify-between"><span className="text-[#475569]">Slot Assigned</span><span className="text-[#00d4ff] font-bold">Slot #{prebook.assigned_slot_index} ({prebook.slot_label})</span></div>
          <div className="flex justify-between"><span className="text-[#475569]">Rate</span><span className="text-white/90 font-mono">${prebook.price_at_booking.toFixed(2)}/hr</span></div>
          <div className="flex justify-between"><span className="text-[#475569]">Success Probability</span><span className="text-[#00c785] font-semibold">{Math.round(prebook.probability * 100)}%</span></div>
          <div className="h-px bg-white/[0.04]" />
          <p className="text-[10px] text-[#475569] text-center">Arrival grace period expires at {new Date(prebook.expires_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</p>
        </div>

        <button type="button" onClick={onClose}
          className="w-full py-3 rounded-xl text-xs font-semibold text-white transition-all"
          style={{ background: 'linear-gradient(135deg, #00c785, #00a06b)' }}>
          Go to My Bookings
        </button>
      </div>
    </div>
  )
}
