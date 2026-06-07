import { useState, useEffect } from 'react'
import { fetchSessionHistory, type SessionHistoryItem } from '../../api/driverClient'

function StatusBadge({ status }: { status: string }) {
  const color = status === 'settled' ? '#00c785' : status === 'running' ? '#00d4ff' : '#f59e0b'
  return (
    <span className="text-[9px] font-medium px-1.5 py-0.5 rounded" style={{ background: `${color}15`, color }}>
      {status}
    </span>
  )
}

export function HistoryPage() {
  const [sessions, setSessions] = useState<SessionHistoryItem[]>([])
  const [loading, setLoading] = useState(true)
  const [total, setTotal] = useState(0)

  const load = async () => {
    try {
      const data = await fetchSessionHistory()
      setSessions(data.sessions || [])
      setTotal(data.total_sessions || 0)
    } catch (err) { console.error('Failed to load session history:', err) }
    setLoading(false)
  }

  useEffect(() => { load() }, [])

  return (
    <div className="space-y-4 pt-2">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold text-white">History</h1>
          <p className="text-xs text-[#475569] mt-0.5">{total} total sessions</p>
        </div>
      </div>

      {loading ? (
        <div className="text-[#5a6a8a] text-sm animate-pulse text-center py-12">Loading history...</div>
      ) : sessions.length === 0 ? (
        <div className="rounded-xl p-10 text-center"
          style={{
            background: 'linear-gradient(135deg, #0e0e24 0%, #12122a 50%, #0e0e24 100%)',
            boxShadow: '0 1px 0 rgba(255,255,255,0.04), 0 0 0 1px rgba(255,255,255,0.04)',
          }}>
          <p className="text-sm text-[#475569]">No parking history yet</p>
        </div>
      ) : (
        <div className="space-y-2">
          {sessions.map((s) => (
            <div key={s.session_id}
              className="rounded-xl p-4"
              style={{
                background: 'linear-gradient(135deg, #0e0e24 0%, #12122a 50%, #0e0e24 100%)',
                boxShadow: '0 1px 0 rgba(255,255,255,0.04), 0 0 0 1px rgba(255,255,255,0.04)',
              }}>
              <div className="flex items-start justify-between mb-1">
                <div>
                  <p className="text-sm font-medium text-white/90">{s.lot_name}</p>
                  <p className="text-[10px] text-[#475569] mt-0.5">{s.lot_id}</p>
                </div>
                <StatusBadge status={s.status} />
              </div>
              <div className="flex items-center gap-3 text-[10px] text-[#475569] mt-2">
                {s.start_time && <span>{new Date(s.start_time).toLocaleDateString()}</span>}
                {s.duration_minutes && <span>{s.duration_minutes}m</span>}
                {s.amount_charged !== undefined && s.amount_charged !== null && (
                  <span className="text-white/60 font-mono">${s.amount_charged.toFixed(2)}</span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
