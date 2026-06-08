import { useState, useEffect } from 'react'
import { fetchDriverLots, fetchLotDetail, startSession, prebookSlot, type DriverLot, type DriverLotDetail, type PrebookSlotResponse } from '../../api/driverClient'
import { getErrorMessage } from '../../utils/format'

const CYAN = '#00d4ff'
const CYAN_DIM = 'rgba(0,212,255,0.10)'
const GOLD = '#f0c040'

/* ─── Slot Picker (detail view) ─── */

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
    try { await onStart(selected) } catch { setStarting(false) }
  }

  return (
    <div className="space-y-5">
      {/* Back + header */}
      <div className="flex items-center gap-3">
        <button onClick={onBack}
          className="w-8 h-8 rounded-lg flex items-center justify-center transition-colors"
          style={{ background: CYAN_DIM, color: CYAN }}>
          <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 19.5L3 12m0 0l7.5-7.5M3 12h18" />
          </svg>
        </button>
        <div>
          <h2 className="font-heading text-base font-semibold text-white">{lot.name}</h2>
          <p className="text-[10px] font-mono text-[#5a6a8a]">{lot.address}</p>
        </div>
      </div>

      {/* Meta bar */}
      <div className="flex items-center gap-3 text-[10px] font-mono pb-3" style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
        <span className="text-[#5a6a8a]">
          <span className="font-display text-xs font-bold text-white">{totalAvail}</span> spots · ${lot.current_price.toFixed(2)}/hr
        </span>
        <span className="px-2 py-0.5 rounded text-[9px] font-semibold uppercase tracking-wider"
          style={{
            background: lot.predicted_occupancy > 0.7 ? 'rgba(245,158,11,0.12)' : 'rgba(0,212,255,0.1)',
            color: lot.predicted_occupancy > 0.7 ? '#f59e0b' : CYAN,
          }}>
          {Math.round(lot.predicted_occupancy * 100)}% full
        </span>
      </div>

      {/* Slot type counts */}
      <div className="flex gap-3 text-[10px] font-mono">
        <span className="text-[#5a6a8a]">{regularSlots} regular</span>
        {handicapSlots > 0 && <span style={{ color: '#f59e0b' }}>{handicapSlots} ♿</span>}
        {evSlots > 0 && <span style={{ color: '#00c785' }}>{evSlots} ⚡</span>}
      </div>

      <p className="text-xs font-mono text-[#5a6a8a]">Select a slot to park:</p>

      {/* Slot grid */}
      <div className="grid grid-cols-4 gap-2.5">
        {Array.from({ length: Math.min(Math.max(totalAvail, 8), 20) }, (_, i) => i + 1).map((num) => {
          const isSelected = selected === num
          return (
            <button key={num} onClick={() => setSelected(num)}
              className="rounded-xl py-4 text-center transition-all duration-150 active:scale-95"
              style={{
                background: isSelected
                  ? `linear-gradient(135deg, ${CYAN}, #0088cc)`
                  : 'linear-gradient(135deg, #0e0e24 0%, #12122a 50%, #0e0e24 100%)',
                boxShadow: isSelected
                  ? `0 0 20px ${CYAN_DIM}`
                  : '0 1px 0 rgba(255,255,255,0.04), 0 0 0 1px rgba(255,255,255,0.04)',
              }}>
              <span className="font-display text-lg font-bold" style={{ color: isSelected ? '#fff' : 'rgba(255,255,255,0.8)' }}>
                {num}
              </span>
            </button>
          )
        })}
      </div>

      <button onClick={handleStart} disabled={selected === null || starting}
        className="cta-btn w-full justify-center text-xs"
        style={{
          background: CYAN,
          color: '#04040a',
          padding: '14px 32px',
          boxShadow: `0 0 24px ${CYAN_DIM}`,
        }}>
        {starting ? 'Starting...' : selected ? `Park in Slot ${selected}` : 'Select a Slot'}
      </button>
    </div>
  )
}

/* ─── Reserve Modal ─── */

function ReserveModal({
  lot, onClose, onSuccess,
}: {
  lot: DriverLot
  onClose: () => void
  onSuccess: (prebookResponse: PrebookSlotResponse) => void
}) {
  const [lotDetail, setLotDetail] = useState<DriverLotDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [selectedSlot, setSelectedSlot] = useState<number | null>(null)

  const getNextTime = (minutes: number) => new Date(Date.now() + minutes * 60 * 1000)
  const toLocalDateTimeString = (date: Date) => {
    const pad = (num: number) => String(num).padStart(2, '0')
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`
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
      } catch { setError('Failed to fetch lot slots details.') }
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
    } catch (err: unknown) {
      setError(getErrorMessage(err, 'Prebooking failed. Check your balance.'))
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
          <h3 className="font-heading text-base font-semibold text-white">Reserve a Slot</h3>
          <button type="button" onClick={onClose}
            className="w-7 h-7 rounded-lg flex items-center justify-center transition-colors"
            style={{ color: '#5a6a8a' }}>
            <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div className="text-xs">
          <p className="font-medium text-white/95">{lot.name}</p>
          <p className="text-[#5a6a8a] font-mono text-[10px] mt-0.5">{lot.address}</p>
        </div>

        {loading ? (
          <div className="text-center py-6 text-sm font-mono text-[#5a6a8a] animate-pulse">Loading lot details...</div>
        ) : error && !lotDetail ? (
          <div className="text-center py-4 text-xs font-mono rounded-lg" style={{ background: 'rgba(245,158,11,0.08)', color: '#f59e0b' }}>
            {error}
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1.5">
              <label className="text-[9px] font-mono font-semibold uppercase tracking-wider" style={{ color: '#5a6a8a' }}>Select Slot</label>
              <select value={selectedSlot || ''} onChange={(e) => setSelectedSlot(Number(e.target.value))}
                className="w-full rounded-lg p-2.5 text-xs text-white font-mono"
                style={{
                  background: '#070714',
                  border: '1px solid rgba(255,255,255,0.06)',
                }}>
                {Array.from({ length: Math.min(Math.max(lotDetail?.available_spots || 8, 8), 16) }, (_, i) => i + 1).map((num) => (
                  <option key={num} value={num}>Slot #{num}</option>
                ))}
              </select>
            </div>

            <div className="space-y-1.5">
              <label className="text-[9px] font-mono font-semibold uppercase tracking-wider" style={{ color: '#5a6a8a' }}>Arrival Time</label>
              <input type="datetime-local" value={targetTime} min={minTimeString} max={maxTimeString}
                onChange={(e) => setTargetTime(e.target.value)} required
                className="w-full rounded-lg p-2.5 text-xs text-white font-mono"
                style={{
                  background: '#070714',
                  border: '1px solid rgba(255,255,255,0.06)',
                }} />
              <p className="text-[8px] font-mono text-[#5a6a8a]">Must be within the next 6 hours</p>
            </div>

            {/* Cost breakdown */}
            <div className="rounded-xl p-3.5 space-y-2" style={{
              background: 'rgba(0,0,0,0.2)',
              border: '1px solid rgba(255,255,255,0.04)',
            }}>
              <p className="text-[9px] font-mono font-semibold uppercase tracking-wider mb-1" style={{ color: '#5a6a8a' }}>Estimated Cost</p>
              <div className="flex justify-between text-xs font-mono">
                <span style={{ color: '#5a6a8a' }}>Booking Fee (non-refundable)</span>
                <span className="text-white/80">${bookingFee.toFixed(2)}</span>
              </div>
              <div className="flex justify-between text-xs font-mono">
                <span style={{ color: '#5a6a8a' }}>Refundable Deposit</span>
                <span className="text-white/80">${deposit.toFixed(2)}</span>
              </div>
              <div className="h-px" style={{ background: 'rgba(255,255,255,0.04)' }} />
              <div className="flex justify-between text-sm font-semibold">
                <span className="text-white/90">Total Due Now</span>
                <span className="font-display" style={{ color: CYAN }}>${total.toFixed(2)}</span>
              </div>
            </div>

            {error && (
              <div className="text-[10px] text-center font-mono py-2 rounded-lg" style={{
                background: 'rgba(255,71,87,0.06)',
                border: '1px solid rgba(255,71,87,0.15)',
                color: '#ff4757',
              }}>{error}</div>
            )}

            <div className="flex gap-3 pt-1">
              <button type="button" onClick={onClose}
                className="flex-1 py-2.5 rounded-lg text-xs font-mono font-semibold transition-all"
                style={{
                  color: '#5a6a8a',
                  border: '1px solid rgba(255,255,255,0.06)',
                }}>
                Cancel
              </button>
              <button type="submit" disabled={submitting || !selectedSlot}
                className="flex-1 py-2.5 rounded-lg text-xs font-semibold text-white transition-all disabled:opacity-40"
                style={{
                  background: `linear-gradient(135deg, ${CYAN}, #0088cc)`,
                  boxShadow: `0 0 16px ${CYAN_DIM}`,
                }}>
                {submitting ? 'Booking...' : 'Confirm Reserve'}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  )
}

/* ─── Reserve Success Modal ─── */

function ReserveSuccessModal({ prebook, onClose }: { prebook: PrebookSlotResponse; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
      <div className="w-full max-w-sm rounded-2xl p-6 space-y-5 text-center"
        style={{
          background: 'linear-gradient(135deg, #0d0d21 0%, #151532 50%, #0d0d21 100%)',
          border: '1px solid rgba(255,255,255,0.08)',
          boxShadow: '0 20px 40px rgba(0,0,0,0.5)',
        }}>
        <div className="w-14 h-14 rounded-full flex items-center justify-center mx-auto"
          style={{ background: 'rgba(0,199,133,0.10)' }}>
          <svg className="w-7 h-7" viewBox="0 0 24 24" fill="none" stroke="#00c785" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
          </svg>
        </div>
        <div>
          <h3 className="font-heading text-base font-semibold text-white">Reservation Confirmed</h3>
          <p className="font-mono text-[10px] text-[#5a6a8a] mt-0.5">Slot successfully reserved</p>
        </div>

        <div className="rounded-xl p-4 text-left space-y-2 text-xs" style={{
          background: 'rgba(0,0,0,0.2)',
          border: '1px solid rgba(255,255,255,0.04)',
        }}>
          <div className="flex justify-between">
            <span className="text-[#5a6a8a]">Slot</span>
            <span style={{ color: CYAN }} className="font-bold">#{prebook.assigned_slot_index ?? prebook.slot_index} ({prebook.slot_label ?? '-'})</span>
          </div>
          <div className="flex justify-between">
            <span className="text-[#5a6a8a]">Rate</span>
            <span className="text-white/90 font-mono">${(prebook.price_at_booking ?? 0).toFixed(2)}/hr</span>
          </div>
          <div className="flex justify-between">
            <span className="text-[#5a6a8a]">Probability</span>
            <span className="text-[#00c785] font-semibold">{Math.round((prebook.probability ?? 0) * 100)}%</span>
          </div>
          <div className="h-px" style={{ background: 'rgba(255,255,255,0.04)' }} />
          <p className="text-[9px] text-center font-mono text-[#5a6a8a]">
            Grace period: {prebook.expires_at ? new Date(prebook.expires_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : 'N/A'}
          </p>
        </div>

        <button type="button" onClick={onClose}
          className="cta-btn w-full justify-center text-xs"
          style={{
            background: `linear-gradient(135deg, ${CYAN}, #0088cc)`,
            color: '#04040a',
            padding: '13px 32px',
            boxShadow: `0 0 24px ${CYAN_DIM}`,
          }}>
          Go to My Bookings
        </button>
      </div>
    </div>
  )
}

/* ─── Filter Pills ─── */

function FilterPill({ label, active, color, count, onClick }: {
  label: string; active: boolean; color: string; count?: number; onClick: () => void
}) {
  return (
    <button onClick={onClick}
      className="relative flex items-center gap-2 px-4 py-2 rounded-xl text-left transition-all duration-200"
      style={{
        background: active
          ? `linear-gradient(135deg, ${color}10 0%, rgba(10,10,24,0.8) 100%)`
          : 'linear-gradient(135deg, #0a0a18 0%, #0e0e20 100%)',
        boxShadow: active
          ? `0 0 0 1px ${color}30, 0 1px 0 rgba(255,255,255,0.04)`
          : '0 0 0 1px rgba(255,255,255,0.04)',
      }}>
      <span className="text-[11px] font-mono uppercase tracking-wider" style={{ color: active ? color : '#5a6a8a' }}>
        {label}
      </span>
      {count !== undefined && (
        <span className="font-display text-sm font-bold" style={{ color: active ? '#fff' : '#5a6a8a' }}>
          {count}
        </span>
      )}
    </button>
  )
}

/* ─── Main FindPage ─── */

export function FindPage() {
  const [lots, setLots] = useState<DriverLot[]>([])
  const [selectedLot, setSelectedLot] = useState<DriverLotDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [reserveLot, setReserveLot] = useState<DriverLot | null>(null)
  const [successPrebook, setSuccessPrebook] = useState<PrebookSlotResponse | null>(null)

  const [slotType, setSlotType] = useState<string>('')
  const [maxPrice, setMaxPrice] = useState<number>(150)

  const loadLots = async () => {
    setLoading(true)
    setError(null)
    try {
      const params: { max_price?: number; slot_type?: string } = {}
      if (slotType) params.slot_type = slotType
      if (maxPrice < 150) params.max_price = maxPrice
      const data = await fetchDriverLots(params)
      const sorted = (data || []).slice().sort((a, b) => a.dynamic_price - b.dynamic_price)
      setLots(sorted)
    } catch { setError('Could not load nearby lots. The backend may be warming up.') }
    setLoading(false)
  }

  useEffect(() => { loadLots() }, [slotType, maxPrice])

  const handleSelectLot = async (lotId: string) => {
    setError(null)
    try {
      const detail = await fetchLotDetail(lotId)
      setSelectedLot(detail)
    } catch { setError('Could not load lot details. Please try again.') }
  }

  const handleStartSession = async (slot: number) => {
    if (!selectedLot) return
    setError(null)
    try {
      await startSession(selectedLot.lot_id, slot)
      window.location.hash = '/driver/active'
    } catch { setError('Failed to start session. Please try again.') }
  }

  if (selectedLot) {
    return (
      <div className="pt-2">
        <SlotPicker lot={selectedLot} onBack={() => setSelectedLot(null)} onStart={handleStartSession} />
      </div>
    )
  }

  const hasActiveFilters = slotType !== '' || maxPrice !== 150

  return (
    <div className="space-y-5 pt-2">
      {/* Header */}
      <div>
        <p className="text-[9px] font-mono tracking-[3px] uppercase mb-1" style={{ color: '#9a97b0' }}>
          Near You
        </p>
        <h1 className="text-lg font-heading font-semibold text-white">Find Parking</h1>
      </div>

      {/* Filter pills row */}
      <div className="flex flex-wrap gap-2">
        <FilterPill
          label="All"
          active={!hasActiveFilters}
          color={CYAN}
          count={lots.length}
          onClick={() => { setSlotType(''); setMaxPrice(150) }}
        />
        <FilterPill
          label="Regular"
          active={slotType === 'regular'}
          color={CYAN}
          onClick={() => setSlotType(slotType === 'regular' ? '' : 'regular')}
        />
        <FilterPill
          label="♿ Handicap"
          active={slotType === 'handicap'}
          color={GOLD}
          onClick={() => setSlotType(slotType === 'handicap' ? '' : 'handicap')}
        />
        <FilterPill
          label="⚡ EV"
          active={slotType === 'ev'}
          color="#00c785"
          onClick={() => setSlotType(slotType === 'ev' ? '' : 'ev')}
        />
      </div>

      {/* Price range */}
      <div className="flex items-center gap-4 rounded-xl p-3"
        style={{
          background: 'linear-gradient(135deg, #0e0e24 0%, #12122a 50%, #0e0e24 100%)',
          boxShadow: '0 1px 0 rgba(255,255,255,0.04), 0 0 0 1px rgba(255,255,255,0.04)',
        }}>
        <div className="flex-1">
          <div className="flex justify-between items-center mb-1">
            <span className="text-[9px] font-mono uppercase tracking-wider" style={{ color: '#5a6a8a' }}>Max Price</span>
            <span className="font-display text-sm font-bold" style={{ color: CYAN }}>
              {maxPrice === 150 ? 'Any' : `$${maxPrice}`}
            </span>
          </div>
          <input type="range" min="5" max="150" step="5" value={maxPrice}
            onChange={(e) => setMaxPrice(Number(e.target.value))}
            className="w-full h-1 rounded-lg appearance-none cursor-pointer"
            style={{ background: 'rgba(255,255,255,0.06)', accentColor: CYAN }} />
        </div>
        {hasActiveFilters && (
          <button onClick={() => { setSlotType(''); setMaxPrice(150) }}
            className="text-[9px] font-mono font-semibold uppercase tracking-wider px-2.5 py-1.5 rounded-lg transition-all shrink-0"
            style={{ color: '#ff4757', border: '1px solid rgba(255,71,87,0.15)' }}>
            Reset
          </button>
        )}
      </div>

      {/* Error */}
      {error && (
        <div className="rounded-xl py-3 px-4 text-xs font-mono text-center flex items-center justify-center gap-2"
          style={{ background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.2)', color: '#f59e0b' }}>
          <span>⚠</span> {error}
          <button onClick={loadLots} className="underline hover:no-underline">Retry</button>
        </div>
      )}

      {/* Loading */}
      {loading ? (
        <div className="text-[#5a6a8a] font-mono text-[11px] animate-pulse text-center py-16">Finding nearby lots...</div>
      ) : lots.length === 0 && !error ? (
        <div className="rounded-xl p-12 text-center" style={{
          background: 'linear-gradient(135deg, #0e0e24 0%, #12122a 50%, #0e0e24 100%)',
          boxShadow: '0 1px 0 rgba(255,255,255,0.04), 0 0 0 1px rgba(255,255,255,0.04)',
        }}>
          <svg className="w-8 h-8 mx-auto mb-3" viewBox="0 0 24 24" fill="none" stroke="#5a6a8a" strokeWidth={1.2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M15 10.5a3 3 0 11-6 0 3 3 0 016 0z" />
            <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 10.5c0 7.142-7.5 11.25-7.5 11.25S4.5 17.642 4.5 10.5a7.5 7.5 0 1115 0z" />
          </svg>
          <p className="text-sm text-[#5a6a8a] font-mono">No lots available nearby</p>
        </div>
      ) : (
        <div className="space-y-3">
          {lots.map((lot) => (
            <div key={lot.lot_id}
              className="rounded-xl p-4 transition-all duration-200"
              style={{
                background: 'linear-gradient(135deg, #0e0e24 0%, #12122a 50%, #0e0e24 100%)',
                boxShadow: '0 1px 0 rgba(255,255,255,0.04), 0 0 0 1px rgba(255,255,255,0.04)',
              }}>
              {/* Clickable main area */}
              <div onClick={() => handleSelectLot(lot.lot_id)} className="cursor-pointer">
                <div className="flex items-start justify-between mb-2">
                  <div className="flex items-center gap-2.5">
                    <div className="w-2 h-2 rounded-full shrink-0" style={{
                      background: lot.predicted_occupancy > 0.7 ? '#f59e0b' : CYAN,
                      boxShadow: `0 0 6px ${lot.predicted_occupancy > 0.7 ? 'rgba(245,158,11,0.4)' : `${CYAN_DIM}`}`,
                    }} />
                    <div>
                      <p className="text-sm font-medium text-white/90">{lot.name}</p>
                      <p className="text-[9px] font-mono text-[#5a6a8a] mt-0.5">{lot.city} · {lot.available_spots} spots</p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="font-display text-lg font-bold" style={{ color: CYAN }}>${lot.dynamic_price.toFixed(2)}</p>
                    <p className="text-[9px] font-mono text-[#5a6a8a] leading-none">/hr</p>
                  </div>
                </div>

                {/* Occupancy bar */}
                <div className="h-1 rounded-full w-full overflow-hidden" style={{ background: 'rgba(255,255,255,0.04)' }}>
                  <div className="h-full rounded-full transition-all duration-500"
                    style={{
                      width: `${Math.round(lot.predicted_occupancy * 100)}%`,
                      background: lot.predicted_occupancy > 0.7 ? '#f59e0b' : CYAN,
                    }} />
                </div>
                <div className="flex justify-between mt-1.5 text-[9px] font-mono text-[#5a6a8a]">
                  <span>{lot.total_slots} slots</span>
                  <span>{Math.round(lot.predicted_occupancy * 100)}% occupied</span>
                </div>
              </div>

              {/* Action buttons */}
              <div className="flex gap-2 mt-3 pt-3" style={{ borderTop: '1px solid rgba(255,255,255,0.04)' }}>
                <button onClick={() => handleSelectLot(lot.lot_id)}
                  className="flex-1 py-1.5 rounded-lg text-[10px] font-mono font-semibold transition-all"
                  style={{ color: '#9a97b0', border: '1px solid rgba(255,255,255,0.06)' }}>
                  Park Here
                </button>
                <button onClick={() => setReserveLot(lot)}
                  className="flex-1 py-1.5 rounded-lg text-[10px] font-mono font-semibold text-white transition-all"
                  style={{
                    background: `linear-gradient(135deg, ${CYAN}, #0088cc)`,
                    boxShadow: `0 0 12px ${CYAN_DIM}`,
                  }}>
                  Reserve
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Modals */}
      {reserveLot && (
        <ReserveModal lot={reserveLot} onClose={() => setReserveLot(null)} onSuccess={(res) => {
          setReserveLot(null)
          setSuccessPrebook(res)
        }} />
      )}
      {successPrebook && (
        <ReserveSuccessModal prebook={successPrebook} onClose={() => {
          setSuccessPrebook(null)
          window.location.hash = '/driver/bookings'
        }} />
      )}
    </div>
  )
}
