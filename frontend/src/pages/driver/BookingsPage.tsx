import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { fetchPrebooks, confirmPrebook, cancelPrebook, type PrebookItem } from '../../api/driverClient'
import { getErrorMessage } from '../../utils/format'

const SAGE = '#60d4a0'
const SAGE_DIM = 'rgba(96,212,160,0.10)'

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
  const onExpireRef = useRef(onExpire)
  onExpireRef.current = onExpire

  useEffect(() => {
    if (!expiresAt) { setTimeLeft('—'); return }
    const target = new Date(expiresAt).getTime()
    let expired = false
    const tick = () => {
      const diff = target - Date.now()
      if (diff <= 0) {
        if (!expired) { expired = true; onExpireRef.current() }
        setTimeLeft('Expired')
        return
      }
      const totalM = Math.floor(diff / 60000)
      const s = Math.floor((diff % 60000) / 1000)
      const h = Math.floor(totalM / 60)
      const m = totalM % 60
      const d = Math.floor(h / 24)
      const displayH = h % 24
      if (d > 0) setTimeLeft(`${d}d ${displayH}h ${m}m`)
      else if (h > 0) setTimeLeft(`${h}h ${m}m`)
      else setTimeLeft(`${m}m ${s}s`)
    }
    tick()
    const id = setInterval(tick, 1000)
    return () => clearInterval(id)
  }, [expiresAt])

  return (
    <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg"
      style={{
        background: SAGE_DIM,
        border: `1px solid ${SAGE}25`,
      }}>
      <span className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ background: SAGE }} />
      <span className="font-display text-xs font-bold" style={{ color: SAGE }}>{timeLeft}</span>
    </div>
  )
}

export function BookingsPage() {
  const [bookings, setBookings] = useState<PrebookItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [confirmingId, setConfirmingId] = useState<string | null>(null)
  const [cancellingId, setCancellingId] = useState<string | null>(null)
  const [expiredIds, setExpiredIds] = useState<Set<string>>(new Set())
  const [dismissedIds, setDismissedIds] = useState<Set<string>>(new Set())
  const navigate = useNavigate()

  const loadBookings = async (isRetry = false) => {
    setLoading(true)
    setError(null)
    try {
      const data = await fetchPrebooks()
      setBookings(data || [])
      setLoading(false)
    } catch {
      setLoading(false)
      if (!isRetry) {
        setTimeout(() => { loadBookings(true) }, 4000)
        setError('Loading bookings failed. Retrying...')
      } else {
        setError('Failed to fetch bookings list.')
      }
    }
  }

  useEffect(() => { loadBookings() }, [])

  const handleConfirm = async (prebookId: string) => {
    setConfirmingId(prebookId)
    setError(null)
    try {
      await confirmPrebook(prebookId)
      navigate('/driver/active')
    } catch (err: unknown) {
      setError(getErrorMessage(err, 'Failed to confirm arrival.'))
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
    } catch (err: unknown) {
      setError(getErrorMessage(err, 'Failed to cancel booking.'))
    }
    setCancellingId(null)
  }

  const handleDismiss = (prebookId: string) => {
    setDismissedIds(prev => new Set(prev).add(prebookId))
  }

  const isPastExpiry = (expiresAt: string | null | undefined) => {
    if (!expiresAt) return true
    return new Date(expiresAt).getTime() <= Date.now()
  }

  const formatDate = (dateStr: string) => {
    try {
      const d = new Date(dateStr)
      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', month: 'short', day: 'numeric' })
    } catch { return dateStr }
  }

  return (
    <div className="space-y-5 pt-2">
      {/* Header */}
      <div>
        <p className="text-[9px] font-mono tracking-[3px] uppercase mb-1" style={{ color: '#9a97b0' }}>
          Reservations
        </p>
        <h1 className="text-lg font-heading font-semibold text-white">My Bookings</h1>
      </div>

      {error && (
        <div className="rounded-xl py-3 px-4 text-xs font-mono text-center flex items-center justify-center gap-2"
          style={{
            background: 'rgba(245,158,11,0.08)',
            border: '1px solid rgba(245,158,11,0.2)',
            color: '#f59e0b',
          }}>
          <span>⚠</span> {error}
          <button onClick={() => loadBookings()} className="underline hover:no-underline">Retry</button>
        </div>
      )}

      {loading ? (
        <div className="text-subtle font-mono text-[11px] animate-pulse text-center py-16">Loading bookings...</div>
      ) : (() => {
        const filtered = bookings.filter(item => !dismissedIds.has(item.prebook_id))
        if (filtered.length === 0) {
          return (
            <div className="card-dark rounded-xl p-12 text-center" >
              <svg className="w-8 h-8 mx-auto mb-3" viewBox="0 0 24 24" fill="none" stroke="#5a6a8a" strokeWidth={1.2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 6.75h12M8.25 12h12m-12 5.25h12M3.75 6.75h.007v.008H3.75V6.75zm.375 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zM3.75 12h.007v.008H3.75V12zm.375 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm-.375 5.25h.007v.008H3.75v-.008zm.375 0a.375.375 0 11-.75 0 .375.375 0 01.75 0z" />
              </svg>
              <p className="text-sm text-subtle font-mono">No bookings scheduled</p>
            </div>
          )
        }
        return (
        <div className="space-y-3">
          {filtered.map((item) => {
            const status = getStatusDetails(item.status)
            const timerExpired = expiredIds.has(item.prebook_id)
            const expired = timerExpired || isPastExpiry(item.expires_at)
            const isActive = item.status === 'active' && !expired
            const isTerminal = ['cancelled','refunded','no_show','expired'].includes(item.status) || expired
            const hasDepositRefund = item.deposit_refunded

            return (
              <div key={item.prebook_id}
                className={`rounded-xl p-4 space-y-3 transition-all duration-200 ${expired ? 'opacity-70' : ''}`}
                >
                {/* Header */}
                <div className="flex justify-between items-start">
                  <div className="flex items-center gap-2.5">
                    <div className="w-2 h-2 rounded-full shrink-0"
                      style={{ background: status.text, boxShadow: `0 0 6px ${status.text}66` }} />
                    <div>
                      <h3 className="text-sm font-medium text-white/90">{item.lot_name}</h3>
                      <p className="text-[9px] font-mono text-subtle mt-0.5">ID: {item.prebook_id.slice(0, 10)}...</p>
                    </div>
                  </div>
                  <span className="text-[9px] font-mono font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full"
                    style={{ background: status.bg, color: status.text }}>
                    {status.label}
                  </span>
                </div>

                {/* Details grid */}
                <div className="grid grid-cols-2 gap-3 text-xs" style={{ borderTop: '1px solid rgba(255,255,255,0.04)', paddingTop: '12px' }}>
                  <div>
                    <p className="text-subtle text-[9px] font-mono uppercase tracking-wider">Arrival</p>
                    <p className="text-white/95 mt-0.5">{formatDate(item.target_time)}</p>
                  </div>
                  <div>
                    <p className="text-subtle text-[9px] font-mono uppercase tracking-wider">Slot</p>
                    <p className="font-bold mt-0.5" style={{ color: SAGE }}>#{item.slot_index} ({item.slot_label})</p>
                  </div>
                  <div>
                    <p className="text-subtle text-[9px] font-mono uppercase tracking-wider">Rate</p>
                    <p className="text-white/80 font-mono mt-0.5">
                      {item.price_at_booking !== null ? `$${item.price_at_booking.toFixed(2)}/hr` : '—'}
                    </p>
                  </div>
                  <div>
                    <p className="text-subtle text-[9px] font-mono uppercase tracking-wider">Deducted</p>
                    <p className="text-white/80 font-mono mt-0.5">
                      {item.booking_fee !== null && item.deposit !== null
                        ? `$${(item.booking_fee + item.deposit).toFixed(2)}`
                        : '—'}
                    </p>
                  </div>
                </div>

                {/* Active booking controls */}
                {isActive && (
                  <div className="flex items-center justify-between gap-3 pt-2"
                    style={{ borderTop: '1px solid rgba(255,255,255,0.04)' }}>
                    <CountdownTimer expiresAt={item.expires_at} onExpire={() => { setExpiredIds(prev => new Set(prev).add(item.prebook_id)); loadBookings() }} />
                    <div className="flex gap-2">
                      <button onClick={() => handleCancel(item.prebook_id)}
                        disabled={cancellingId !== null || confirmingId !== null}
                        className="px-3 py-2 rounded-lg text-[12px] font-mono font-semibold transition-all disabled:opacity-40"
                        style={{
                          color: '#ff4757',
                          border: '1px solid rgba(255,71,87,0.2)',
                        }}>
                        {cancellingId === item.prebook_id ? '⟳' : 'Cancel'}
                      </button>
                      <button onClick={() => handleConfirm(item.prebook_id)}
                        disabled={confirmingId !== null || cancellingId !== null}
                        className="px-3 py-2 rounded-lg text-[12px] font-mono font-semibold text-white transition-all disabled:opacity-40"
                        style={{
                          background: `linear-gradient(135deg, ${SAGE}, #40b880)`,
                          boxShadow: `0 0 16px ${SAGE_DIM}`,
                        }}>
                        {confirmingId === item.prebook_id ? '⟳' : 'Arrive'}
                      </button>
                    </div>
                  </div>
                )}

                {/* Dismiss button for expired / terminal bookings */}
                {!isActive && isTerminal && (
                  <div className="flex justify-end pt-2"
                    style={{ borderTop: '1px solid rgba(255,255,255,0.04)' }}>
                    <button onClick={() => handleDismiss(item.prebook_id)}
                      className="px-3 py-1.5 rounded-lg text-[11px] font-mono transition-all"
                      style={{
                        color: '#94a3b8',
                        border: '1px solid rgba(148,163,184,0.2)',
                      }}>
                      ✕ Dismiss
                    </button>
                  </div>
                )}

                {/* Deposit refund notice */}
                {hasDepositRefund && (
                  <div className="flex items-center gap-2 text-[10px] px-3 py-2 rounded-lg"
                    style={{
                      background: 'rgba(0,199,133,0.06)',
                      border: '1px solid rgba(0,199,133,0.15)',
                      color: '#00c785',
                    }}>
                    <svg className="w-3 h-3 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v12m-3-2.818l.879.659c1.171.879 3.07.879 4.242 0 1.172-.879 1.172-2.303 0-3.182C13.536 12.219 12.768 12 12 12c-.725 0-1.45-.22-2.003-.659-1.106-.879-1.106-2.303 0-3.182s2.9-.879 4.006 0l.415.33M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    <span className="flex-1">Deposit Refunded</span>
                    <span className="font-mono font-bold">+${(item.deposit || 0).toFixed(2)}</span>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )
      })()}
    </div>
  )
}
