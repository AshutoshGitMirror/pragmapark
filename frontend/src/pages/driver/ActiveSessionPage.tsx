import { useState, useEffect, useRef } from 'react'
import { endSession, confirmPayment, fetchSessionReceipt, fetchActiveSession, type SessionReceipt, type SessionEndResponse } from '../../api/driverClient'

const CYAN = '#00d4ff'
const CYAN_DIM = 'rgba(0,212,255,0.10)'
const GOLD = '#f0c040'
const ROSE = '#f04060'

function Timer({ startTime }: { startTime: string }) {
  const [elapsed, setElapsed] = useState('')
  useEffect(() => {
    const start = new Date(startTime).getTime()
    const tick = () => {
      const diff = Date.now() - start
      const m = Math.floor(diff / 60000)
      const s = Math.floor((diff % 60000) / 1000)
      setElapsed(`${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`)
    }
    tick()
    const id = setInterval(tick, 1000)
    return () => clearInterval(id)
  }, [startTime])
  return <span className="font-mono tracking-widest tabular-nums">{elapsed}</span>
}

function ActiveSessionView({ session }: { session: { session_id: string; start_time?: string; slot?: number; entry_price?: number; lot_id?: string; status?: string; amount_charged?: number }; onEnded?: () => void }) {
  const [ending, setEnding] = useState(false)
  const [ended, setEnded] = useState<SessionEndResponse | null>(
    session.status === 'pending_settlement'
      ? ({ amount_charged: session.amount_charged ?? 0, session_id: session.session_id, status: session.status } as SessionEndResponse)
      : null,
  )
  const [paying, setPaying] = useState(false)
  const [receipt, setReceipt] = useState<SessionReceipt | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const paidRef = useRef(false)

  const handleEnd = async () => {
    setEnding(true)
    setActionError(null)
    try {
      const result = await endSession(session.session_id)
      setEnded(result)
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Failed to end session')
      setEnding(false)
    }
  }

  const handlePay = async () => {
    if (paidRef.current) return
    paidRef.current = true
    setPaying(true)
    setActionError(null)
    try {
      await confirmPayment(session.session_id)
      const r = await fetchSessionReceipt(session.session_id)
      setReceipt(r)
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Payment failed')
      paidRef.current = false
      setPaying(false)
    }
  }

  if (receipt) {
    const mins = receipt.duration_minutes || 0
    return (
      <div className="space-y-6 pt-4 text-center">
        <div className="w-16 h-16 rounded-full flex items-center justify-center mx-auto"
          style={{ background: `${CYAN_DIM}` }}>
          <svg className="w-7 h-7" viewBox="0 0 24 24" fill="none" stroke={CYAN} strokeWidth={1.8}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        </div>

        <div>
          <h2 className="text-lg font-heading font-semibold text-white">Parking Complete</h2>
          <p className="font-mono text-[10px] text-[#9a97b0] mt-0.5">Transaction settled</p>
        </div>

        {actionError && (
          <div className="rounded-lg p-3 text-xs text-left" style={{ background: 'rgba(240,64,96,0.12)', border: '1px solid rgba(240,64,96,0.25)', color: '#f06070' }}>
            <span className="font-mono">{actionError}</span>
          </div>
        )}

        <div className="rounded-xl p-5 space-y-3 text-left"
          style={{
            background: 'linear-gradient(135deg, #0e0e24 0%, #12122a 50%, #0e0e24 100%)',
            boxShadow: '0 1px 0 rgba(255,255,255,0.04), 0 0 0 1px rgba(255,255,255,0.04)',
          }}>
          <div className="flex justify-between text-xs">
            <span className="text-[#9a97b0] font-mono">Duration</span>
            <span className="text-white/80 font-mono">{mins} min</span>
          </div>
          <div className="flex justify-between text-xs">
            <span className="text-[#9a97b0] font-mono">Rate</span>
            <span className="font-mono" style={{ color: CYAN }}>${receipt.entry_price.toFixed(2)}/hr</span>
          </div>
          <div className="h-px" style={{ background: 'rgba(255,255,255,0.04)' }} />
          <div className="flex justify-between text-sm">
            <span className="text-[#9a97b0]">Charged</span>
            <span className="text-white font-semibold font-mono">${receipt.amount_charged.toFixed(2)}</span>
          </div>
          {receipt.blockchain_ref && (
            <p className="text-[9px] text-[#5a6a8a] font-mono truncate">tx: {receipt.blockchain_ref.slice(0, 24)}...</p>
          )}
        </div>

        <button onClick={() => window.location.hash = '/driver/history'}
          className="cta-btn w-full justify-center text-xs"
          style={{ background: CYAN, color: '#04040a', padding: '13px 32px', boxShadow: `0 0 24px ${CYAN_DIM}` }}>
          View History
        </button>
      </div>
    )
  }

  if (ended && !receipt) {
    const amount = ended.amount_charged || ended.total_cost || 0
    return (
      <div className="space-y-6 pt-4 text-center">
        <div className="w-16 h-16 rounded-full flex items-center justify-center mx-auto"
          style={{ background: 'rgba(240,192,64,0.10)' }}>
          <span className="font-display text-xl" style={{ color: GOLD }}>$</span>
        </div>

        <div>
          <h2 className="text-lg font-heading font-semibold text-white">Session Ended</h2>
          <p className="font-mono text-[10px] text-[#9a97b0] mt-0.5">Confirm payment to complete</p>
        </div>

        <div className="rounded-xl p-5"
          style={{
            background: 'linear-gradient(135deg, #0e0e24 0%, #12122a 50%, #0e0e24 100%)',
            boxShadow: '0 1px 0 rgba(255,255,255,0.04), 0 0 0 1px rgba(255,255,255,0.04)',
            border: `1px solid rgba(240,192,64,0.1)`,
          }}>
          <p className="font-display text-3xl font-bold" style={{ color: GOLD }}>${amount.toFixed(2)}</p>
          <p className="text-[9px] font-mono text-[#9a97b0] mt-1 uppercase tracking-wider">Total due</p>
        </div>

        <button onClick={handlePay} disabled={paying}
          className="cta-btn w-full justify-center text-xs"
          style={{
            background: `linear-gradient(135deg, #00c785, #00a06b)`,
            color: '#04040a',
            padding: '13px 32px',
            boxShadow: '0 0 24px rgba(0,199,133,0.15)',
          }}>
          {paying ? 'Processing...' : `Pay $${amount.toFixed(2)}`}
        </button>

        {ended.deposit_refund && ended.deposit_refund > 0 && (
          <div className="flex items-center justify-center gap-1.5 text-[10px]"
            style={{ color: '#00c785' }}>
            <svg className="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v12m6-6H6" />
            </svg>
            Deposit refund: ${ended.deposit_refund.toFixed(2)}
          </div>
        )}

        {actionError && (
          <div className="rounded-lg p-3 text-xs text-left" style={{ background: 'rgba(240,64,96,0.12)', border: '1px solid rgba(240,64,96,0.25)', color: '#f06070' }}>
            <span className="font-mono">{actionError}</span>
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="space-y-6 pt-4 text-center">
      {/* Active pulse ring */}
      <div className="relative inline-flex mx-auto">
        <div className="absolute inset-0 rounded-full animate-ping opacity-20"
          style={{ background: CYAN }} />
        <div className="relative w-20 h-20 rounded-full flex items-center justify-center"
          style={{ background: CYAN_DIM }}>
          <svg className="w-8 h-8" viewBox="0 0 24 24" fill="none" stroke={CYAN} strokeWidth={1.8}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        </div>
      </div>

      <div>
        <h2 className="text-lg font-heading font-semibold text-white">Active Session</h2>
        {session.start_time && (
          <p className="font-display text-4xl font-bold mt-4 mb-3" style={{ color: CYAN }}>
            <Timer startTime={session.start_time} />
          </p>
        )}
        <div className="flex items-center justify-center gap-4 text-xs">
          {session.slot !== undefined && session.slot > 0 && (
            <span className="font-mono text-[#9a97b0]">Slot #{session.slot}</span>
          )}
          {session.entry_price !== undefined && session.entry_price > 0 && (
            <span className="font-mono" style={{ color: CYAN }}>${session.entry_price.toFixed(2)}/hr</span>
          )}
        </div>
        <p className="text-[9px] font-mono text-[#5a6a8a] mt-2">ID: {session.session_id.slice(0, 10)}...</p>
      </div>

      {actionError && (
        <div className="rounded-lg p-3 text-xs text-left" style={{ background: 'rgba(240,64,96,0.12)', border: '1px solid rgba(240,64,96,0.25)', color: '#f06070' }}>
          <span className="font-mono">{actionError}</span>
        </div>
      )}

      <button onClick={handleEnd} disabled={ending}
        className="cta-btn w-full justify-center text-xs"
        style={{
          background: `linear-gradient(135deg, ${ROSE}, #d03050)`,
          color: '#fff',
          padding: '13px 32px',
          boxShadow: `0 0 24px rgba(240,64,96,0.15)`,
        }}>
        {ending ? 'Ending...' : 'End Parking'}
      </button>
    </div>
  )
}

export function ActiveSessionPage() {
  const [session, setSession] = useState<{ session_id: string; start_time?: string; slot?: number; entry_price?: number; lot_id?: string; status?: string; amount_charged?: number } | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [checked, setChecked] = useState(false)

  useEffect(() => {
    if (checked) return
    setChecked(true)
    const check = async () => {
      try {
        const s = await fetchActiveSession()
        if (s) setSession(s)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to check active session')
      }
      setLoading(false)
    }
    check()
  }, [checked])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-[#5a6a8a] animate-pulse font-mono text-[11px]">Checking active session...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-64 flex-col gap-3">
        <div className="text-[#f59e0b] text-sm font-mono">{error}</div>
        <button onClick={() => { setChecked(false); setLoading(true); setError(null) }}
          className="text-[10px] font-mono px-3 py-1.5 rounded-lg transition-all"
          style={{
            background: 'rgba(245,158,11,0.08)',
            color: '#f59e0b',
            border: '1px solid rgba(245,158,11,0.2)',
          }}>
          Retry
        </button>
      </div>
    )
  }

  if (!session) {
    return (
      <div className="space-y-5 pt-4 text-center">
        <div className="w-16 h-16 rounded-full flex items-center justify-center mx-auto"
          style={{ background: 'rgba(90,106,138,0.08)' }}>
          <svg className="w-7 h-7" viewBox="0 0 24 24" fill="none" stroke="#5a6a8a" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        </div>
        <div>
          <h2 className="text-lg font-heading font-semibold text-white">No Active Session</h2>
          <p className="font-mono text-[11px] text-[#9a97b0] mt-0.5">Find a lot and start parking</p>
        </div>
        <button onClick={() => window.location.hash = '/driver/find'}
          className="cta-btn inline-flex text-xs"
          style={{ background: CYAN, color: '#04040a', padding: '12px 32px', boxShadow: `0 0 24px ${CYAN_DIM}` }}>
          Find Parking
        </button>
      </div>
    )
  }

  return <ActiveSessionView session={session} onEnded={() => setSession(null)} />
}
