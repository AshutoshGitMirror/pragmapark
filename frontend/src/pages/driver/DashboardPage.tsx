import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { driverApi, fetchActiveSession, fetchSessionHistory, topupWallet, type SessionHistoryItem } from '../../api/driverClient'
import { useAuth } from '../../context/AuthContext'
import { getErrorMessage } from '../../utils/format'

type ActiveInfo = { session_id: string; start_time?: string; slot?: number; entry_price?: number; lot_id?: string; status?: string; amount_charged?: number } | null

/* ── Micro narrative feed for driver ── */
function DriverNarrativeFeed({ active, balance, recent }: { active: ActiveInfo; balance: number | null; recent: SessionHistoryItem[] }) {
  const [current, setCurrent] = useState(0)

  const narrativeLines: { icon: string; color: string; text: string }[] = []

  if (active) {
    if (active.status === 'pending_settlement') {
      narrativeLines.push({
        icon: '△',
        color: '#f59e0b',
        text: `Payment due: ₹${(active.amount_charged ?? 0).toFixed(2)} outstanding. Settle to avoid penalties.`,
      })
    } else {
      narrativeLines.push({
        icon: '●',
        color: '#00d4ff',
        text: `Session active at ${active.lot_id || 'parking lot'}${active.slot ? ` · Slot #${active.slot}` : ''}. ₹${active.entry_price?.toFixed(2) ?? '?'}/hr.`,
      })
    }
  } else {
    narrativeLines.push({
      icon: '○',
      color: '#475569',
      text: 'No active session. Find a spot to start parking.',
    })
  }

  if (balance !== null) {
    narrativeLines.push({
      icon: '¤',
      color: '#f0c040',
      text: `Wallet: ₹${balance.toFixed(2)}. ${balance < 5 ? 'Low balance — consider topping up.' : balance < 10 ? 'Adequate for short parking sessions.' : 'Sufficient funds for parking.'}`,
    })
  }

  if (recent.length > 0) {
    const last = recent[0]
    narrativeLines.push({
      icon: '✓',
      color: '#00c785',
      text: `Last session: ${last.lot_name || last.lot_id} — ₹${(last.amount_charged ?? 0).toFixed(2)} for ${last.duration_minutes || 0} min.`,
    })
  }

  narrativeLines.push({
    icon: '◈',
    color: '#a060f0',
    text: 'System AI optimizing pricing across all lots in real-time.',
  })

  // Auto-rotate
  useEffect(() => {
    const t = setInterval(() => {
      setCurrent((prev) => (prev + 1) % narrativeLines.length)
    }, 4000)
    return () => clearInterval(t)
  }, [narrativeLines.length])

  if (narrativeLines.length === 0) return null

  const line = narrativeLines[current]

  return (
    <div className="group relative overflow-hidden rounded-xl p-3 transition-all"
      style={{
        background: 'linear-gradient(135deg, #0a0a18 0%, #0e0e24 100%)',
        border: '1px solid rgba(255,255,255,0.04)',
      }}>
      <div className="flex items-start gap-2.5">
        <span className="text-xs mt-0.5 shrink-0" style={{ color: line.color }}>{line.icon}</span>
        <p className="text-[11px] font-mono text-muted leading-relaxed">
          {line.text}
        </p>
      </div>
      {/* Dot indicators */}
      <div className="flex gap-1 justify-center mt-2">
        {narrativeLines.map((_, i) => (
          <span
            key={i}
            className="w-1 h-1 rounded-full transition-all duration-300"
            style={{
              backgroundColor: i === current ? line.color : 'rgba(255,255,255,0.08)',
              transform: i === current ? 'scale(1.3)' : 'scale(1)',
            }}
          />
        ))}
      </div>
    </div>
  )
}

export function DashboardPage() {
  const [balance, setBalance] = useState<number | null>(null)
  const [active, setActive] = useState<ActiveInfo>(null)
  const [recent, setRecent] = useState<SessionHistoryItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  
  const [showTopUp, setShowTopUp] = useState(false)
  const [topUpAmount, setTopUpAmount] = useState<string>('')
  const [topUpError, setTopUpError] = useState<string | null>(null)
  const [topUpLoading, setTopUpLoading] = useState(false)
  const [topUpSlow, setTopUpSlow] = useState(false)

  useEffect(() => {
    if (!topUpLoading) { setTopUpSlow(false); return }
    const t = setTimeout(() => setTopUpSlow(true), 15000)
    return () => clearTimeout(t)
  }, [topUpLoading])

  const navigate = useNavigate()
  const { user } = useAuth()

  const load = async (isRetry = false) => {
    setLoading(true)
    setError(null)
    try {
      const [balRes, act, hist] = await Promise.all([
        driverApi.get('/wallet'),
        fetchActiveSession(),
        fetchSessionHistory(0, 3),
      ])
      if (balRes?.data?.balance !== undefined) setBalance(balRes.data.balance)
      setActive(act)
      setRecent(hist.sessions || [])
      setLoading(false)
    } catch (err) {
      setLoading(false)
      if (!isRetry) {
        setTimeout(() => { load(true) }, 4000)
        setError('Loading dashboard failed. Retrying...')
      } else {
        setError(err instanceof Error ? err.message : 'Failed to load driver dashboard')
      }
    }
  }

  useEffect(() => {
    load()
  }, [])

  useEffect(() => {
    if (!showTopUp) return
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') { setShowTopUp(false); setTopUpAmount(''); setTopUpError(null) }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [showTopUp])

  const handleTopUp = async () => {
    const amt = parseFloat(topUpAmount)
    if (isNaN(amt) || amt <= 0) {
      setTopUpError('Please enter a valid amount greater than 0')
      return
    }
    setTopUpLoading(true)
    setTopUpError(null)
    try {
      const res = await topupWallet(amt)
      setBalance(res.balance)
      setShowTopUp(false)
      setTopUpAmount('')
    } catch (err: unknown) {
      setTopUpError(getErrorMessage(err, 'Top-up failed. Please try again.'))
    } finally {
      setTopUpLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-subtle animate-pulse text-sm">Loading...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-64 flex-col gap-3">
        <div className="text-amber text-sm font-mono">{error}</div>
        <button onClick={() => load()}
          className="text-[12px] font-mono px-3 py-2 rounded-lg transition-all"
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

  return (
    <div className="space-y-5">
      {/* ── Greeting ── */}
      <div>
        <h2 className="section-headline">
          Hello, {user?.full_name || 'Driver'}
        </h2>
        <p className="section-body mt-0.5">Your parking overview</p>
      </div>

      {/* ── Narrative feed ── */}
      <DriverNarrativeFeed active={active} balance={balance} recent={recent} />

      {/* ── Wallet Card with Fraunces display number ── */}
      <div
        className="card-dark w-full rounded-xl p-4 transition-all relative overflow-hidden group"
        >
        {/* Accent bar */}
        <div className="absolute top-0 left-0 w-full h-px opacity-0 group-hover:opacity-100 transition-opacity"
          style={{ background: 'linear-gradient(to right, transparent, #f0c040, transparent)' }}
        />
        <div className="flex justify-between items-center">
          <div>
            <p className="text-[10px] text-dim font-mono uppercase tracking-wider">Wallet Balance</p>
            <p className="display-number mt-1" style={{ color: balance !== null && balance < 5 ? '#f04060' : '#f0c040' }}>
              ₹{balance !== null ? balance.toFixed(2) : '—'}
            </p>
          </div>
          <button 
            onClick={() => setShowTopUp(true)}
            className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-[#f0c040] text-black hover:bg-[#d4a830] active:scale-95 transition-all shadow-[0_0_12px_rgba(240,192,64,0.15)]"
          >
            Top Up
          </button>
        </div>
        <button 
          onClick={() => navigate('/driver/transactions')}
          className="text-[9px] text-dim hover:text-dim transition-colors mt-3 block text-left"
        >
          Transaction history →
        </button>
      </div>

      {/* ── Active Session Widget ── */}
        {active ? (
        <button onClick={() => navigate('/driver/active')}
          className="w-full rounded-xl p-4 text-left transition-all hover:brightness-110"
          style={{
            background: active.status === 'pending_settlement'
              ? 'linear-gradient(135deg, #1e130a 0%, #24190e 50%, #1e130a 100%)'
              : 'linear-gradient(135deg, #0a1a1a 0%, #0e1a1e 50%, #0a1a1a 100%)',
            boxShadow: active.status === 'pending_settlement'
              ? '0 1px 0 rgba(245,158,11,0.08), 0 0 0 1px rgba(245,158,11,0.06)'
              : '0 1px 0 rgba(0,212,255,0.08), 0 0 0 1px rgba(0,212,255,0.06)',
          }}>
          <div className="flex items-center gap-2 mb-2">
            <span className={`w-2 h-2 rounded-full ${active.status === 'pending_settlement' ? 'bg-[#f59e0b]' : 'bg-[#00d4ff] animate-pulse'}`} />
            <p className={`text-[10px] font-mono uppercase tracking-wider ${active.status === 'pending_settlement' ? 'text-amber' : 'text-cyan'}`}>
              {active.status === 'pending_settlement' ? 'Payment Due' : 'Active Session'}
            </p>
          </div>
          <p className="text-xs text-muted">
            {active.lot_id && <>Lot: {active.lot_id}</>}
            {active.slot && active.slot > 0 && <> · Slot #{active.slot}</>}
          </p>
          {active.status === 'pending_settlement' ? (
            <p className="text-xs text-amber mt-0.5 font-semibold font-mono">${(active.amount_charged ?? 0).toFixed(2)} outstanding</p>
          ) : (
            active.entry_price !== undefined && active.entry_price > 0 && (
              <p className="text-xs text-cyan mt-0.5 font-mono">${active.entry_price.toFixed(2)}/hr</p>
            )
          )}
          <p className="text-[9px] text-dim mt-1">Tap to view →</p>
        </button>
      ) : (
        <button onClick={() => navigate('/driver/find')}
          className="w-full rounded-xl p-4 text-center transition-all hover:brightness-110"
          >
          <p className="text-sm font-medium text-dim">No active session</p>
          <p className="text-xs text-cyan mt-1">Find a parking spot →</p>
        </button>
      )}

      {/* ── Recent Sessions ── */}
      {recent.length > 0 && (
        <div>
          <p className="section-label mb-2">Recent Sessions</p>
          <div className="space-y-2">
            {(active ? recent.filter(s => s.session_id !== active.session_id) : recent).slice(0, 3).map((s) => (
              <div key={s.session_id}
                className="rounded-xl p-3 flex justify-between items-center"
                >
                <div>
                  <p className="text-xs text-white">{s.lot_name || s.lot_id}</p>
                  <p className="text-[9px] text-dim">{s.duration_minutes || 0} min</p>
                </div>
                <div className="text-right">
                  <p className="text-xs text-white font-mono">
                    {s.amount_charged ? `₹${s.amount_charged.toFixed(2)}` : '-'}
                  </p>
                  <span className={`text-[9px] font-mono ${
                    s.status === 'settled' ? 'text-emerald' :
                    s.status === 'running' ? 'text-cyan' : 'text-dim'
                  }`}>{s.status}</span>
                </div>
              </div>
            ))}
          </div>
          <button onClick={() => navigate('/driver/history')}
            className="w-full mt-2 text-[11px] text-dim hover:text-muted transition-colors py-2">
            View all history →
          </button>
        </div>
      )}

      {/* ── Top Up Modal ── */}
      {showTopUp && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
          onClick={() => { setShowTopUp(false); setTopUpAmount(''); setTopUpError(null) }}>
          <div className="relative w-full max-w-sm rounded-2xl p-6 text-left border border-white/10"
            onClick={e => e.stopPropagation()}
            style={{
              background: 'linear-gradient(135deg, #12122a 0%, #0e0e24 100%)',
              boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.5), 0 10px 10px -5px rgba(0, 0, 0, 0.4)',
            }}>
            <h3 className="section-headline text-base mb-1">Top Up Wallet</h3>
            <p className="section-body mb-4">Add funds to your smart parking wallet</p>
            
            {topUpError && (
              <div className="mb-3 p-2 bg-red-950/40 border border-red-500/20 text-red-400 rounded-lg text-xs font-mono">
                {topUpError}
              </div>
            )}

            {/* Presets */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mb-4">
              {[5, 10, 20, 50].map((amt) => (
                <button
                  key={amt}
                  type="button"
                  onClick={() => {
                    setTopUpAmount(amt.toString())
                    setTopUpError(null)
                  }}
                  className={`py-2 rounded-lg text-xs font-mono font-semibold border transition-all active:scale-95 ${
                    topUpAmount === amt.toString()
                      ? 'bg-[#f0c040] text-black border-[#f0c040] shadow-[0_0_12px_rgba(240,192,64,0.3)]'
                      : 'bg-[#1b1b38] text-white border-white/5 hover:border-white/20'
                  }`}
                >
                  ₹{amt}
                </button>
              ))}
            </div>

            {/* Custom Amount Input */}
            <div className="mb-5">
              <label className="block text-[10px] text-dim uppercase tracking-wider font-mono mb-1.5">Custom Amount ($)</label>
              <div className="relative">
                <span className="absolute left-3 top-2 text-xs text-dim font-mono">$</span>
                <input
                  type="number"
                  placeholder="0.00"
                  step="0.01"
                  min="0.01"
                  value={topUpAmount}
                  onChange={(e) => {
                    setTopUpAmount(e.target.value)
                    setTopUpError(null)
                  }}
                  className="w-full bg-[#1b1b38] border border-white/5 rounded-lg py-2 pl-7 pr-3 text-xs font-mono text-white placeholder-[#475569] focus:outline-none focus:border-[#f0c040] transition-colors"
                />
              </div>
            </div>

            {/* Actions */}
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => {
                  setShowTopUp(false)
                  setTopUpAmount('')
                  setTopUpError(null)
                }}
                className="flex-1 py-2 rounded-lg text-xs font-semibold bg-[#1b1b38] text-white border border-white/5 hover:bg-[#25254c] transition-colors"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={topUpLoading}
                onClick={handleTopUp}
                className="flex-1 py-2 rounded-lg text-xs font-semibold bg-[#f0c040] text-black hover:bg-[#d4a830] disabled:opacity-50 disabled:cursor-not-allowed transition-all active:scale-95 shadow-[0_0_12px_rgba(240,192,64,0.2)]"
              >
                {topUpLoading ? 'Processing...' : 'Confirm'}
              </button>
            </div>

            {topUpSlow && (
              <p className="text-[10px] font-mono animate-pulse text-center" style={{ color: '#f59e0b' }}>
                Top-up is taking longer than expected. Please wait...
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
