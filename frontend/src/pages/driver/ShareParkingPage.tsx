import { useState, useEffect, useCallback } from 'react'
import { fetchAvailableShares, bookShare, fetchMyShareBookings, cancelShareBooking, ShareListingItem, ShareBookingResponse } from '../../api/driverClient'

const STALL_THRESHOLD = 15000

export function ShareParkingPage() {
  const [tab, setTab] = useState<'browse' | 'bookings'>('browse')
  const [listings, setListings] = useState<ShareListingItem[]>([])
  const [bookings, setBookings] = useState<ShareBookingResponse[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [stallMsg, setStallMsg] = useState('')

  // book modal
  const [selectedListing, setSelectedListing] = useState<ShareListingItem | null>(null)
  const [startTime, setStartTime] = useState('')
  const [endTime, setEndTime] = useState('')
  const [vehicleId, setVehicleId] = useState('')
  const [bookingLoading, setBookingLoading] = useState(false)
  const [bookingError, setBookingError] = useState('')
  const [bookingSuccess, setBookingSuccess] = useState(false)

  // cancel
  const [confirmCancel, setConfirmCancel] = useState<number | null>(null)
  const [cancelLoading, setCancelLoading] = useState(false)

  const loadData = useCallback(async () => {
    setLoading(true)
    setError('')
    const timer = setTimeout(() => setStallMsg('Taking longer than expected…'), STALL_THRESHOLD)
    try {
      if (tab === 'browse') {
        setListings(await fetchAvailableShares())
      } else {
        setBookings(await fetchMyShareBookings())
      }
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || 'Failed to load data')
    } finally {
      clearTimeout(timer)
      setStallMsg('')
      setLoading(false)
    }
  }, [tab])

  useEffect(() => { loadData() }, [loadData])

  const handleBook = async () => {
    if (!selectedListing || !startTime || !endTime || !vehicleId) return
    setBookingLoading(true)
    setBookingError('')
    setBookingSuccess(false)
    const timer = setTimeout(() => setStallMsg('Taking longer than expected…'), STALL_THRESHOLD)
    try {
      await bookShare(selectedListing.id, startTime, endTime)
      setBookingSuccess(true)
      setSelectedListing(null)
      setStartTime(''); setEndTime(''); setVehicleId('')
      loadData()
    } catch (err: any) {
      setBookingError(err?.response?.data?.detail || err?.message || 'Booking failed')
    } finally {
      clearTimeout(timer)
      setStallMsg('')
      setBookingLoading(false)
    }
  }

  const handleCancel = async (bookingId: number) => {
    setCancelLoading(true)
    const timer = setTimeout(() => setStallMsg('Taking longer than expected…'), STALL_THRESHOLD)
    try {
      await cancelShareBooking(bookingId)
      setConfirmCancel(null)
      loadData()
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || 'Cancel failed')
    } finally {
      clearTimeout(timer)
      setStallMsg('')
      setCancelLoading(false)
    }
  }

  const totalCost = selectedListing && startTime && endTime
    ? ((new Date(endTime).getTime() - new Date(startTime).getTime()) / 3600000) * selectedListing.price_per_hour
    : 0

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-white font-heading">Share Parking</h1>
      </div>

      <div className="flex gap-4 border-b border-white/[0.04] pb-3">
        <button onClick={() => setTab('browse')}
          className={`text-sm font-medium transition-colors ${tab === 'browse' ? 'text-cyan' : 'text-dim hover:text-white'}`}>
          Browse Listings
        </button>
        <button onClick={() => setTab('bookings')}
          className={`text-sm font-medium transition-colors ${tab === 'bookings' ? 'text-cyan' : 'text-dim hover:text-white'}`}>
          My Bookings
        </button>
      </div>

      {stallMsg && (
        <div className="text-xs text-amber/80 bg-amber/[0.05] border border-amber/10 rounded-lg px-4 py-2">{stallMsg}</div>
      )}

      {error && (
        <div className="text-xs text-red/80 bg-red/[0.05] border border-red/10 rounded-lg px-4 py-2 flex items-center justify-between">
          <span>{error}</span>
          <button onClick={loadData} className="ml-3 text-cyan hover:text-white transition-colors">Retry</button>
        </div>
      )}

      {loading ? (
        <div className="flex items-center gap-2 text-xs text-dim">
          <div className="w-3 h-3 border border-cyan border-t-transparent rounded-full animate-spin" />
          Loading…
        </div>
      ) : tab === 'browse' ? (
        listings.length === 0 ? (
          <p className="text-xs text-dim">No share listings available right now.</p>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2">
            {listings.map((l) => (
              <div key={l.id} className="rounded-xl p-4"
                style={{ border: '1px solid rgba(255,255,255,0.06)', background: 'rgba(255,255,255,0.02)' }}>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-semibold text-white">{l.lot_name}</span>
                  <span className="text-[10px] font-mono text-cyan">${l.price_per_hour}/hr</span>
                </div>
                <p className="text-[10px] text-dim mb-1">Slot {l.slot_index} · {l.resident_name}</p>
                <p className="text-[10px] text-dim mb-3">
                   {l.available_from ? new Date(l.available_from).toLocaleDateString() : 'Now'} – {l.available_until ? new Date(l.available_until).toLocaleDateString() : 'Open'}
                </p>
                <button onClick={() => setSelectedListing(l)}
                  className="w-full text-xs bg-cyan/10 text-cyan border border-cyan/20 rounded-lg py-1.5 font-medium hover:bg-cyan/20 transition-colors">
                  Book Now
                </button>
              </div>
            ))}
          </div>
        )
      ) : (
        bookings.length === 0 ? (
          <p className="text-xs text-dim">You have no share bookings yet.</p>
        ) : (
          <div className="space-y-2">
            {bookings.map((b) => (
              <div key={b.id} className="rounded-xl p-4 flex items-center justify-between"
                style={{ border: '1px solid rgba(255,255,255,0.06)', background: 'rgba(255,255,255,0.02)' }}>
                <div>
                  <p className="text-xs font-semibold text-white">{b.lot_name} · Slot {b.slot_index}</p>
                  <p className="text-[10px] text-dim mt-0.5">
                    {new Date(b.start_time).toLocaleString()} – {new Date(b.end_time).toLocaleString()}
                  </p>
                  <p className="text-[10px] font-mono mt-1">
                    <span className="text-cyan">${b.total_cost.toFixed(2)}</span>
                    <span className="text-dim mx-1">·</span>
                    <span className={b.status === 'active' ? 'text-green' : b.status === 'cancelled' ? 'text-red' : 'text-dim'}>
                      {b.status}
                    </span>
                    {b.vehicle_id && <><span className="text-dim mx-1">·</span>{b.vehicle_id}</>}
                  </p>
                </div>
                {b.status === 'active' && (
                  confirmCancel === b.id ? (
                    <div className="flex items-center gap-2">
                      <span className="text-[9px] text-dim">Cancel?</span>
                      <button onClick={() => handleCancel(b.id)} disabled={cancelLoading}
                        className="text-[10px] text-white bg-red/80 px-2 py-1 rounded font-semibold disabled:opacity-50">
                        Yes
                      </button>
                      <button onClick={() => setConfirmCancel(null)}
                        className="text-[10px] text-dim hover:text-white px-2 py-1 rounded">
                        No
                      </button>
                    </div>
                  ) : (
                    <button onClick={() => setConfirmCancel(b.id)}
                      className="text-[10px] text-dim hover:text-red transition-colors">
                      Cancel
                    </button>
                  )
                )}
              </div>
            ))}
          </div>
        )
      )}

      {/* Book Modal */}
      {selectedListing && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4"
          onClick={() => { if (!bookingLoading) setSelectedListing(null) }}>
          <div onClick={(e) => e.stopPropagation()}
            className="w-full max-w-md rounded-2xl p-6 space-y-4"
            style={{ background: '#0c0c20', border: '1px solid rgba(255,255,255,0.08)' }}>
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold text-white">Book Slot</h2>
              <button onClick={() => { if (!bookingLoading) setSelectedListing(null) }}
                className="text-dim hover:text-white text-lg leading-none">&times;</button>
            </div>
            <p className="text-[10px] text-dim">{selectedListing.lot_name} · Slot {selectedListing.slot_index} · ${selectedListing.price_per_hour}/hr</p>
            {bookingSuccess && (
              <div className="text-xs text-green bg-green/[0.05] border border-green/20 rounded-lg px-3 py-2">
                Booking confirmed!
              </div>
            )}
            {bookingError && (
              <div className="text-xs text-red bg-red/[0.05] border border-red/20 rounded-lg px-3 py-2">{bookingError}</div>
            )}
            <div className="space-y-3">
              <div>
                <label className="text-[10px] font-mono text-dim block mb-1">Start Time</label>
                <input type="datetime-local" value={startTime} onChange={(e) => setStartTime(e.target.value)}
                  className="w-full bg-white/[0.04] border border-white/[0.08] rounded-lg px-3 py-2 text-xs text-white" />
              </div>
              <div>
                <label className="text-[10px] font-mono text-dim block mb-1">End Time</label>
                <input type="datetime-local" value={endTime} onChange={(e) => setEndTime(e.target.value)}
                  className="w-full bg-white/[0.04] border border-white/[0.08] rounded-lg px-3 py-2 text-xs text-white" />
              </div>
              <div>
                <label className="text-[10px] font-mono text-dim block mb-1">Vehicle ID</label>
                <input type="text" value={vehicleId} onChange={(e) => setVehicleId(e.target.value)} placeholder="e.g. MH-01-AB-1234"
                  className="w-full bg-white/[0.04] border border-white/[0.08] rounded-lg px-3 py-2 text-xs text-white placeholder:text-dim" />
              </div>
              {totalCost > 0 && (
                <div className="flex items-center justify-between text-xs">
                  <span className="text-dim">Estimated Total</span>
                  <span className="text-cyan font-semibold">${totalCost.toFixed(2)}</span>
                </div>
              )}
              <button onClick={handleBook} disabled={bookingLoading || !startTime || !endTime || !vehicleId}
                className="w-full text-xs bg-cyan text-black font-semibold rounded-lg py-2.5 hover:bg-cyan/90 transition-colors disabled:opacity-40">
                {bookingLoading ? 'Processing…' : 'Confirm Booking'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
