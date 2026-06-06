import { useState, useEffect } from 'react'
import { fetchPrebooks, confirmPrebook, cancelPrebook, type PrebookItem } from '../../api/driverClient'

function getStatusDetails(status: string) {
  switch (status) {
    case 'active':
      return { label: 'Active', bg: 'rgba(0, 212, 255, 0.1)', text: '#00d4ff' }
    case 'confirmed':
      return { label: 'Confirmed', bg: 'rgba(0, 199, 133, 0.1)', text: '#00c785' }
    case 'cancelled':
      return { label: 'Cancelled', bg: 'rgba(255, 71, 87, 0.1)', text: '#ff4757' }
    case 'refunded':
      return { label: 'Refunded', bg: 'rgba(245, 158, 11, 0.1)', text: '#f59e0b' }
    case 'no_show':
      return { label: 'No Show', bg: 'rgba(239, 68, 68, 0.1)', text: '#ef4444' }
    case 'expired':
    default:
      return { label: 'Expired', bg: 'rgba(148, 163, 184, 0.1)', text: '#94a3b8' }
  }
}

function CountdownTimer({ expiresAt, onExpire }: { expiresAt: string; onExpire: () => void }) {
  const [timeLeft, setTimeLeft] = useState('')

  useEffect(() => {
    const target = new Date(expiresAt).getTime()
    const tick = () => {
      const diff = target - Date.now()
      if (diff <= 0) {
        setTimeLeft('Expired')
        onExpire()
        return
      }
      const m = Math.floor(diff / 60000)
      const s = Math.floor((diff % 60000) / 1000)
      setTimeLeft(`${m}m ${s}s`)
    }
    tick()
    const id = setInterval(tick, 1000)
    return () => clearInterval(id)
  }, [expiresAt, onExpire])

  return (
    <div className="flex items-center gap-1.5 bg-[rgba(0,212,255,0.08)] px-2.5 py-1 rounded-lg border border-[rgba(0,212,255,0.15)]">
      <span className="text-[10px] text-[#00d4ff]/80 font-medium">Expires in</span>
      <span className="text-xs font-mono font-bold text-[#00d4ff]">{timeLeft}</span>
    </div>
  )
}

export function BookingsPage() {
  const [bookings, setBookings] = useState<PrebookItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [confirmingId, setConfirmingId] = useState<string | null>(null)
  const [cancellingId, setCancellingId] = useState<string | null>(null)

  const loadBookings = async () => {
    setError(null)
    try {
      const data = await fetchPrebooks()
      setBookings(data || [])
    } catch {
      setError('Failed to fetch bookings list.')
    }
    setLoading(false)
  }

  useEffect(() => {
    loadBookings()
  }, [])

  const handleConfirm = async (prebookId: string) => {
    setConfirmingId(prebookId)
    setError(null)
    try {
      await confirmPrebook(prebookId)
      window.location.hash = '/driver/active'
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to confirm arrival. Please try again.')
      setConfirmingId(null)
      loadBookings()
    }
  }

  const handleCancel = async (prebookId: string) => {
    setCancellingId(prebookId)
    setError(null)
    try {
      await cancelPrebook(prebookId)
      await loadBookings()
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to cancel booking. Please try again.')
    }
    setCancellingId(null)
  }

  const formatDate = (dateStr: string) => {
    try {
      const d = new Date(dateStr)
      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', month: 'short', day: 'numeric' })
    } catch {
      return dateStr
    }
  }

  return (
    <div className="space-y-4 pt-2">
      <div>
        <h1 className="text-lg font-semibold text-white">My Bookings</h1>
        <p className="text-xs text-[#475569] mt-0.5">Prebooked parking spots and active reservations</p>
      </div>

      {error && (
        <div className="p-3 rounded-lg text-xs font-mono text-center"
          style={{
            background: 'rgba(245,158,11,0.08)',
            border: '1px solid rgba(245,158,11,0.2)',
            color: '#f59e0b',
          }}>
          {error}
          <button onClick={loadBookings} className="ml-2 underline hover:no-underline">Retry</button>
        </div>
      )}

      {loading ? (
        <div className="text-[#5a6a8a] text-sm animate-pulse text-center py-12">Loading bookings...</div>
      ) : bookings.length === 0 ? (
        <div className="rounded-xl p-10 text-center"
          style={{
            background: 'linear-gradient(135deg, #0e0e24 0%, #12122a 50%, #0e0e24 100%)',
            boxShadow: '0 1px 0 rgba(255,255,255,0.04), 0 0 0 1px rgba(255,255,255,0.04)',
          }}>
          <p className="text-sm text-[#475569]">No bookings scheduled</p>
        </div>
      ) : (
        <div className="space-y-3">
          {bookings.map((item) => {
            const status = getStatusDetails(item.status)
            const isActive = item.status === 'active'
            const hasDepositRefund = item.deposit_refunded

            return (
              <div key={item.prebook_id} className="rounded-xl p-4 space-y-4"
                style={{
                  background: 'linear-gradient(135deg, #0e0e24 0%, #12122a 50%, #0e0e24 100%)',
                  boxShadow: '0 1px 0 rgba(255,255,255,0.04), 0 0 0 1px rgba(255,255,255,0.04)',
                }}>
                <div className="flex justify-between items-start">
                  <div>
                    <h3 className="text-sm font-semibold text-white">{item.lot_name}</h3>
                    <p className="text-[10px] text-[#475569] mt-0.5">ID: {item.prebook_id.slice(0, 8)}...</p>
                  </div>
                  <span className="text-[10px] font-medium px-2 py-0.5 rounded-full"
                    style={{ background: status.bg, color: status.text }}>
                    {status.label}
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-3 text-xs" style={{ borderTop: '1px solid rgba(255,255,255,0.04)', paddingTop: '12px' }}>
                  <div>
                    <p className="text-[#475569] text-[10px]">Target Arrival</p>
                    <p className="text-white/95 font-medium mt-0.5">{formatDate(item.target_time)}</p>
                  </div>
                  <div>
                    <p className="text-[#475569] text-[10px]">Assigned Slot</p>
                    <p className="text-[#00d4ff] font-bold mt-0.5">Slot #{item.slot_index} ({item.slot_label})</p>
                  </div>
                </div>

                <div className="grid grid-cols-3 gap-2 text-xs">
                  <div>
                    <p className="text-[#475569] text-[10px]">Rate</p>
                    <p className="text-white/80 font-medium font-mono mt-0.5">
                      {item.price_at_booking !== null ? `$${item.price_at_booking.toFixed(2)}/hr` : '—'}
                    </p>
                  </div>
                  <div>
                    <p className="text-[#475569] text-[10px]">Deducted</p>
                    <p className="text-white/80 font-medium font-mono mt-0.5">
                      {item.booking_fee !== null && item.deposit !== null ? (
                        `$${(item.booking_fee + item.deposit).toFixed(2)}`
                      ) : '—'}
                    </p>
                  </div>
                  <div>
                    <p className="text-[#475569] text-[10px]">Probability</p>
                    <p className="text-white/80 font-medium font-mono mt-0.5">
                      {item.probability_given !== null ? `${Math.round(item.probability_given * 100)}%` : '—'}
                    </p>
                  </div>
                </div>

                {isActive && (
                  <div className="flex items-center justify-between gap-3 pt-1 border-t border-[rgba(255,255,255,0.04)]">
                    <CountdownTimer expiresAt={item.expires_at} onExpire={loadBookings} />
                    <div className="flex gap-2">
                      <button onClick={() => handleCancel(item.prebook_id)} disabled={cancellingId !== null || confirmingId !== null}
                        className="px-3 py-1.5 rounded-lg text-xs font-semibold text-[#ff4757] border border-[rgba(255,71,87,0.2)] hover:bg-[rgba(255,71,87,0.05)] transition-colors disabled:opacity-40">
                        {cancellingId === item.prebook_id ? 'Cancelling...' : 'Cancel'}
                      </button>
                      <button onClick={() => handleConfirm(item.prebook_id)} disabled={confirmingId !== null || cancellingId !== null}
                        className="px-3 py-1.5 rounded-lg text-xs font-semibold text-white transition-all disabled:opacity-40"
                        style={{ background: 'linear-gradient(135deg, #00d4ff, #0088cc)' }}>
                        {confirmingId === item.prebook_id ? 'Confirming...' : 'Confirm Arrival'}
                      </button>
                    </div>
                  </div>
                )}

                {hasDepositRefund && (
                  <div className="flex justify-between items-center text-[10px] text-[#00c785] bg-[rgba(0,199,133,0.06)] px-2.5 py-1.5 rounded-lg border border-[rgba(0,199,133,0.15)]">
                    <span>Deposit Refunded</span>
                    <span className="font-mono font-bold">+${((item.deposit || 0) * 0.9).toFixed(2)}</span>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
