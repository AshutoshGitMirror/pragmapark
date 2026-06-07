import { useState, useEffect } from 'react'
import { driverApi, fetchActiveSession, fetchSessionHistory, topupWallet, type SessionHistoryItem } from '../../api/driverClient'
import { useAuth } from '../../context/AuthContext'

type ActiveInfo = { session_id: string; start_time?: string; slot?: number; entry_price?: number; lot_id?: string; status?: string; amount_charged?: number } | null

export function DashboardPage() {
  const [balance, setBalance] = useState<number | null>(null)
  const [active, setActive] = useState<ActiveInfo>(null)
  const [recent, setRecent] = useState<SessionHistoryItem[]>([])
  const [loading, setLoading] = useState(true)
  
  const [showTopUp, setShowTopUp] = useState(false)
  const [topUpAmount, setTopUpAmount] = useState<string>('')
  const [topUpError, setTopUpError] = useState<string | null>(null)
  const [topUpLoading, setTopUpLoading] = useState(false)

  const { user } = useAuth()

  useEffect(() => {
    const load = async () => {
      try {
        const [balRes, act, hist] = await Promise.all([
          driverApi.get('/wallet').catch(() => null),
          fetchActiveSession(),
          fetchSessionHistory(0, 3).catch(() => ({ total_sessions: 0, sessions: [] })),
        ])
        if (balRes?.data?.balance !== undefined) setBalance(balRes.data.balance)
        setActive(act)
        setRecent(hist.sessions || [])
      } catch (err) { console.error('Failed to load driver dashboard:', err) }
      setLoading(false)
    }
    load()
  }, [])

  const nav = (hash: string) => { window.location.hash = hash }

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
    } catch (err: any) {
      setTopUpError(err.response?.data?.detail || 'Top-up failed. Please try again.')
    } finally {
      setTopUpLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-[#5a6a8a] animate-pulse text-sm">Loading...</div>
      </div>
    )
  }

  return (
    <div className="space-y-5">
      {/* Greeting */}
      <div>
        <h2 className="text-lg font-semibold text-white">
          Hello, {user?.full_name || 'Driver'}
        </h2>
        <p className="text-xs text-[#475569] mt-0.5">Here's your parking overview</p>
      </div>

      {/* Wallet Card */}
      <div
        className="w-full rounded-xl p-4 transition-all"
        style={{
          background: 'linear-gradient(135deg, #0e0e24 0%, #12122a 50%, #0e0e24 100%)',
          boxShadow: '0 1px 0 rgba(255,255,255,0.04), 0 0 0 1px rgba(255,255,255,0.04)',
        }}>
        <div className="flex justify-between items-center">
          <div>
            <p className="text-[10px] text-[#64748b] font-mono uppercase tracking-wider">Wallet Balance</p>
            <p className="text-2xl font-bold text-white mt-1 font-mono">
              ${(balance ?? 0).toFixed(2)}
            </p>
          </div>
          <button 
            onClick={() => setShowTopUp(true)}
            className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-[#00d4ff] text-black hover:bg-[#00b5da] active:scale-95 transition-all shadow-[0_0_12px_rgba(0,212,255,0.15)]"
          >
            Top Up
          </button>
        </div>
        <button 
          onClick={() => nav('/driver/transactions')}
          className="text-[9px] text-[#475569] hover:text-[#64748b] transition-colors mt-3 block text-left"
        >
          Tap for transaction history →
        </button>
      </div>

      {/* Active Session Widget */}
      {active ? (
        <button onClick={() => nav('/driver/active')}
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
            <p className={`text-[10px] font-mono uppercase tracking-wider ${active.status === 'pending_settlement' ? 'text-[#f59e0b]' : 'text-[#00d4ff]'}`}>
              {active.status === 'pending_settlement' ? 'Payment Due' : 'Active Session'}
            </p>
          </div>
          <p className="text-xs text-[#94a3b8]">
            {active.lot_id && <>Lot: {active.lot_id}</>}
            {active.slot && active.slot > 0 && <> · Slot #{active.slot}</>}
          </p>
          {active.status === 'pending_settlement' ? (
            <p className="text-xs text-[#f59e0b] mt-0.5 font-semibold font-mono">${(active.amount_charged ?? 0).toFixed(2)} outstanding</p>
          ) : (
            active.entry_price !== undefined && active.entry_price > 0 && (
              <p className="text-xs text-[#00d4ff] mt-0.5">${active.entry_price.toFixed(2)}/hr</p>
            )
          )}
          <p className="text-[9px] text-[#475569] mt-1">Tap to view →</p>
        </button>
      ) : (
        <button onClick={() => nav('/driver/find')}
          className="w-full rounded-xl p-4 text-center transition-all hover:brightness-110"
          style={{
            background: 'linear-gradient(135deg, #0e0e24 0%, #12122a 50%, #0e0e24 100%)',
            boxShadow: '0 1px 0 rgba(255,255,255,0.04), 0 0 0 1px rgba(255,255,255,0.04)',
          }}>
          <p className="text-sm font-medium text-[#64748b]">No active session</p>
          <p className="text-xs text-[#00d4ff] mt-1">Find a parking spot →</p>
        </button>
      )}

      {/* Recent Sessions */}
      {recent.length > 0 && (
        <div>
          <p className="text-[10px] text-[#64748b] font-mono uppercase tracking-wider mb-2">Recent Sessions</p>
          <div className="space-y-2">
            {recent.slice(0, 3).map((s) => (
              <div key={s.session_id}
                className="rounded-xl p-3 flex justify-between items-center"
                style={{
                  background: 'linear-gradient(135deg, #0e0e24 0%, #12122a 50%, #0e0e24 100%)',
                  boxShadow: '0 1px 0 rgba(255,255,255,0.04), 0 0 0 1px rgba(255,255,255,0.04)',
                }}>
                <div>
                  <p className="text-xs text-white">{s.lot_name || s.lot_id}</p>
                  <p className="text-[9px] text-[#475569]">{s.duration_minutes || 0} min</p>
                </div>
                <div className="text-right">
                  <p className="text-xs text-white font-mono">
                    {s.amount_charged ? `$${s.amount_charged.toFixed(2)}` : '-'}
                  </p>
                  <span className={`text-[9px] font-mono ${
                    s.status === 'settled' ? 'text-[#00c785]' :
                    s.status === 'running' ? 'text-[#00d4ff]' : 'text-[#64748b]'
                  }`}>{s.status}</span>
                </div>
              </div>
            ))}
          </div>
          <button onClick={() => nav('/driver/history')}
            className="w-full mt-2 text-[10px] text-[#64748b] hover:text-[#94a3b8] transition-colors py-2">
            View all history →
          </button>
        </div>
      )}

      {/* Top Up Modal */}
      {showTopUp && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
          <div className="relative w-full max-w-sm rounded-2xl p-6 text-left border border-white/10"
            style={{
              background: 'linear-gradient(135deg, #12122a 0%, #0e0e24 100%)',
              boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.5), 0 10px 10px -5px rgba(0, 0, 0, 0.4)',
            }}>
            <h3 className="text-base font-semibold text-white mb-1">Top Up Wallet</h3>
            <p className="text-xs text-[#64748b] mb-4">Add funds to your smart parking wallet</p>
            
            {topUpError && (
              <div className="mb-3 p-2 bg-red-950/40 border border-red-500/20 text-red-400 rounded-lg text-xs font-mono">
                {topUpError}
              </div>
            )}

            {/* Presets */}
            <div className="grid grid-cols-4 gap-2 mb-4">
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
                      ? 'bg-[#00d4ff] text-black border-[#00d4ff] shadow-[0_0_12px_rgba(0,212,255,0.3)]'
                      : 'bg-[#1b1b38] text-white border-white/5 hover:border-white/20'
                  }`}
                >
                  ${amt}
                </button>
              ))}
            </div>

            {/* Custom Amount Input */}
            <div className="mb-5">
              <label className="block text-[10px] text-[#64748b] uppercase tracking-wider font-mono mb-1.5">Custom Amount ($)</label>
              <div className="relative">
                <span className="absolute left-3 top-2 text-xs text-[#64748b] font-mono">$</span>
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
                  className="w-full bg-[#1b1b38] border border-white/5 rounded-lg py-2 pl-7 pr-3 text-xs font-mono text-white placeholder-[#475569] focus:outline-none focus:border-[#00d4ff] transition-colors"
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
                className="flex-1 py-2 rounded-lg text-xs font-semibold bg-[#00d4ff] text-black hover:bg-[#00b5da] disabled:opacity-50 disabled:cursor-not-allowed transition-all active:scale-95 shadow-[0_0_12px_rgba(0,212,255,0.2)]"
              >
                {topUpLoading ? 'Processing...' : 'Confirm'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
