import { useState, useEffect, useRef } from 'react'
import { endSession, confirmPayment, fetchSessionReceipt, fetchActiveSession, type SessionReceipt } from '../../api/driverClient'

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
  return <span className="font-mono tracking-widest">{elapsed}</span>
}

function ActiveSessionView({ session, onEnded }: { session: { session_id: string; start_time?: string; slot?: number; entry_price?: number; lot_id?: string; status?: string; amount_charged?: number }; onEnded: () => void }) {
  const [ending, setEnding] = useState(false)
  const [ended, setEnded] = useState<any>(session.status === 'pending_settlement' ? session : null)
  const [paying, setPaying] = useState(false)
  const [receipt, setReceipt] = useState<SessionReceipt | null>(null)
  const paidRef = useRef(false)

  const handleEnd = async () => {
    setEnding(true)
    try {
      const result = await endSession(session.session_id)
      setEnded(result)
    } catch { setEnding(false) }
  }

  const handlePay = async () => {
    if (paidRef.current) return
    paidRef.current = true
    setPaying(true)
    try {
      await confirmPayment(session.session_id)
      const r = await fetchSessionReceipt(session.session_id)
      setReceipt(r)
    } catch {
      paidRef.current = false
      setPaying(false)
    }
  }

  if (receipt) {
    const mins = receipt.duration_minutes || 0
    const hrs = receipt.duration_hours || 0
    return (
      <div className="space-y-5 pt-4 text-center">
        <div className="w-14 h-14 rounded-full bg-[rgba(0,212,255,0.1)] flex items-center justify-center mx-auto">
          <span className="text-2xl text-[#00d4ff]">✓</span>
        </div>
        <h2 className="text-base font-semibold text-white">Parking Complete</h2>
        <div className="rounded-xl p-5 space-y-2 text-left"
          style={{
            background: 'linear-gradient(135deg, #0e0e24 0%, #12122a 50%, #0e0e24 100%)',
            boxShadow: '0 1px 0 rgba(255,255,255,0.04), 0 0 0 1px rgba(255,255,255,0.04)',
          }}>
          <div className="flex justify-between text-xs"><span className="text-[#475569]">Duration</span><span className="text-white/80">{mins} min</span></div>
          <div className="flex justify-between text-xs"><span className="text-[#475569]">Rate</span><span className="text-white/80">${receipt.entry_price.toFixed(2)}/hr</span></div>
          <div className="h-px bg-[rgba(255,255,255,0.04)]" />
          <div className="flex justify-between text-sm"><span className="text-[#475569]">Charged</span><span className="text-white font-semibold">${receipt.amount_charged.toFixed(2)}</span></div>
          {receipt.blockchain_ref && <p className="text-[9px] text-[#475569] font-mono truncate">tx: {receipt.blockchain_ref.slice(0, 16)}...</p>}
        </div>
        <button onClick={() => window.location.hash = '/driver/history'}
          className="w-full rounded-xl py-3 text-sm font-medium text-white"
          style={{ background: 'linear-gradient(135deg, #00d4ff, #0088cc)' }}>
          View History
        </button>
      </div>
    )
  }

  if (ended && !receipt) {
    const amount = ended.amount_charged || ended.total_cost || 0
    return (
      <div className="space-y-5 pt-4 text-center">
        <div className="w-14 h-14 rounded-full bg-[rgba(245,158,11,0.1)] flex items-center justify-center mx-auto">
          <span className="text-xl text-[#f59e0b]">$</span>
        </div>
        <h2 className="text-base font-semibold text-white">Session Ended</h2>
        <p className="text-xs text-[#475569]">Confirm payment to complete</p>
        <div className="rounded-xl p-5"
          style={{
            background: 'linear-gradient(135deg, #0e0e24 0%, #12122a 50%, #0e0e24 100%)',
            boxShadow: '0 1px 0 rgba(255,255,255,0.04), 0 0 0 1px rgba(255,255,255,0.04)',
          }}>
          <p className="text-3xl font-bold text-white font-mono">${amount.toFixed(2)}</p>
          <p className="text-[10px] text-[#475569] mt-1">Total due</p>
        </div>
        <button onClick={handlePay} disabled={paying}
          className="w-full rounded-xl py-3.5 text-sm font-semibold text-white transition-all disabled:opacity-50"
          style={{ background: 'linear-gradient(135deg, #00c785, #00a06b)' }}>
          {paying ? 'Processing...' : `Pay $${amount.toFixed(2)}`}
        </button>
        {ended.deposit_refund && ended.deposit_refund > 0 && (
          <p className="text-[10px] text-[#00c785]">Deposit refund: ${ended.deposit_refund.toFixed(2)}</p>
        )}
      </div>
    )
  }

  return (
    <div className="space-y-6 pt-4 text-center">
      <div className="w-16 h-16 rounded-full bg-[rgba(0,212,255,0.08)] flex items-center justify-center mx-auto animate-pulse">
        <span className="text-2xl">◷</span>
      </div>
      <div>
        <h2 className="text-base font-semibold text-white">Active Session</h2>
        {session.start_time && (
          <p className="text-3xl font-bold text-white mt-3">
            <Timer startTime={session.start_time} />
          </p>
        )}
        <div className="mt-3 space-y-1">
          {session.slot !== undefined && session.slot > 0 && (
            <p className="text-xs text-[#94a3b8]">Slot #{session.slot}</p>
          )}
          {session.entry_price !== undefined && session.entry_price > 0 && (
            <p className="text-xs text-[#00d4ff]">${session.entry_price.toFixed(2)}/hr</p>
          )}
        </div>
        <p className="text-[10px] text-[#475569] mt-1">Session ID: {session.session_id.slice(0, 8)}...</p>
      </div>
      <button onClick={handleEnd} disabled={ending}
        className="w-full rounded-xl py-3.5 text-sm font-semibold text-white transition-all disabled:opacity-50"
        style={{ background: 'linear-gradient(135deg, #ff4757, #d63031)' }}>
        {ending ? 'Ending...' : 'End Parking'}
      </button>
    </div>
  )
}

export function ActiveSessionPage() {
  const [session, setSession] = useState<{ session_id: string; start_time?: string; slot?: number; entry_price?: number; lot_id?: string; status?: string; amount_charged?: number } | null>(null)
  const [loading, setLoading] = useState(true)
  const [checked, setChecked] = useState(false)

  useEffect(() => {
    if (checked) return
    setChecked(true)
    const check = async () => {
      try {
        const s = await fetchActiveSession()
        if (s) setSession(s)
      } catch { /* silent */ }
      setLoading(false)
    }
    check()
  }, [checked])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-[#5a6a8a] animate-pulse text-sm">Checking active session...</div>
      </div>
    )
  }

  if (!session) {
    return (
      <div className="space-y-5 pt-4 text-center">
        <div className="w-14 h-14 rounded-full bg-[rgba(90,106,138,0.1)] flex items-center justify-center mx-auto">
          <span className="text-xl text-[#475569]">◷</span>
        </div>
        <h2 className="text-base font-semibold text-white">No Active Session</h2>
        <p className="text-xs text-[#475569]">Find a lot and start parking</p>
        <button onClick={() => window.location.hash = '/driver/find'}
          className="inline-block rounded-xl px-8 py-3 text-sm font-medium text-white"
          style={{ background: 'linear-gradient(135deg, #00d4ff, #0088cc)' }}>
          Find Parking
        </button>
      </div>
    )
  }

  return <ActiveSessionView session={session} onEnded={() => setSession(null)} />
}
