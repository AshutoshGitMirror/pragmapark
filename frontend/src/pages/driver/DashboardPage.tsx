import { useState, useEffect } from 'react'
import { driverApi, fetchActiveSession, fetchSessionHistory, type SessionHistoryItem } from '../../api/driverClient'
import { getDriverUser } from '../../api/driverClient'

type ActiveInfo = { session_id: string; start_time?: string; slot?: number; entry_price?: number; lot_id?: string } | null

export function DashboardPage() {
  const [balance, setBalance] = useState<number | null>(null)
  const [active, setActive] = useState<ActiveInfo>(null)
  const [recent, setRecent] = useState<SessionHistoryItem[]>([])
  const [loading, setLoading] = useState(true)
  const user = getDriverUser()

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
      } catch { /* silent */ }
      setLoading(false)
    }
    load()
  }, [])

  const nav = (hash: string) => { window.location.hash = hash }

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
      <button onClick={() => nav('/driver/history')}
        className="w-full rounded-xl p-4 text-left transition-all hover:brightness-110"
        style={{
          background: 'linear-gradient(135deg, #0e0e24 0%, #12122a 50%, #0e0e24 100%)',
          boxShadow: '0 1px 0 rgba(255,255,255,0.04), 0 0 0 1px rgba(255,255,255,0.04)',
        }}>
        <p className="text-[10px] text-[#64748b] font-mono uppercase tracking-wider">Wallet Balance</p>
        <p className="text-2xl font-bold text-white mt-1 font-mono">
          ${(balance ?? 0).toFixed(2)}
        </p>
        <p className="text-[9px] text-[#475569] mt-1">Tap for transaction history →</p>
      </button>

      {/* Active Session Widget */}
      {active ? (
        <button onClick={() => nav('/driver/active')}
          className="w-full rounded-xl p-4 text-left transition-all hover:brightness-110"
          style={{
            background: 'linear-gradient(135deg, #0a1a1a 0%, #0e1a1e 50%, #0a1a1a 100%)',
            boxShadow: '0 1px 0 rgba(0,212,255,0.08), 0 0 0 1px rgba(0,212,255,0.06)',
          }}>
          <div className="flex items-center gap-2 mb-2">
            <span className="w-2 h-2 rounded-full bg-[#00d4ff] animate-pulse" />
            <p className="text-[10px] text-[#00d4ff] font-mono uppercase tracking-wider">Active Session</p>
          </div>
          <p className="text-xs text-[#94a3b8]">
            {active.lot_id && <>Lot: {active.lot_id}</>}
            {active.slot && active.slot > 0 && <> · Slot #{active.slot}</>}
          </p>
          {active.entry_price !== undefined && active.entry_price > 0 && (
            <p className="text-xs text-[#00d4ff] mt-0.5">${active.entry_price.toFixed(2)}/hr</p>
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
    </div>
  )
}
