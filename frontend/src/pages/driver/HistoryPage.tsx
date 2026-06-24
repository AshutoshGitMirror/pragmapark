import { useState, useEffect } from 'react'
import { fetchSessionHistory, type SessionHistoryItem } from '../../api/driverClient'

const VIOLET = '#a78bfa'
const VIOLET_DIM = 'rgba(167,139,250,0.10)'

function StatusBadge({ status }: { status: string }) {
  const color = status === 'settled' ? '#00c785' : status === 'running' ? '#00d4ff' : '#f59e0b'
  return (
    <span className="text-[9px] font-mono font-semibold uppercase tracking-wider px-2 py-0.5 rounded"
      style={{ background: `${color}15`, color }}>
      {status}
    </span>
  )
}

export function HistoryPage() {
  const [sessions, setSessions] = useState<SessionHistoryItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [total, setTotal] = useState(0)

  const load = async (isRetry = false) => {
    setLoading(true)
    setError(null)
    try {
      const data = await fetchSessionHistory()
      setSessions(data.sessions || [])
      setTotal(data.total_sessions || 0)
      setLoading(false)
    } catch (err) {
      setLoading(false)
      if (!isRetry) {
        setTimeout(() => { load(true) }, 4000)
        setError('Loading history failed. Retrying...')
      } else {
        setError(err instanceof Error ? err.message : 'Failed to load session history')
      }
    }
  }

  useEffect(() => { load() }, [])

  return (
    <div className="space-y-5 pt-2">
      {/* Header */}
      <div>
        <p className="text-[9px] font-mono text-muted-alt tracking-[3px] uppercase mb-1"
          style={{ color: '#9a97b0' }}>
          Parking History
        </p>
        <div className="flex items-end justify-between">
          <h1 className="text-lg font-heading font-semibold text-white">History</h1>
          <span className="font-display text-sm" style={{ color: VIOLET }}>{total.toLocaleString()}</span>
        </div>
      </div>

      {error && (
        <div className="rounded-xl py-3 px-4 text-xs font-mono text-center flex items-center justify-center gap-2"
          style={{ background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.2)', color: '#f59e0b' }}>
          <span>⚠</span> {error}
          <button onClick={() => load()} className="underline hover:no-underline">Retry</button>
        </div>
      )}

      {loading ? (
        <div className="text-subtle font-mono text-[11px] animate-pulse text-center py-16">Loading history...</div>
      ) : !error && sessions.length === 0 ? (
        <div className="card-dark rounded-xl p-12 text-center" >
          <svg className="w-8 h-8 mx-auto mb-3" viewBox="0 0 24 24" fill="none" stroke="#5a6a8a" strokeWidth={1.2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <p className="text-sm text-subtle font-mono">No parking history yet</p>
        </div>
      ) : (
        <div className="space-y-2">
          {sessions.map((s) => (
            <div key={s.session_id}
              className="rounded-xl p-4 transition-all duration-200"
              >
              <div className="flex items-start justify-between mb-2">
                <div className="flex items-center gap-2.5">
                  {/* Timeline dot */}
                  <div className="w-2 h-2 rounded-full shrink-0" style={{
                    background: s.status === 'settled' ? '#00c785' : VIOLET,
                    boxShadow: `0 0 6px ${s.status === 'settled' ? 'rgba(0,199,133,0.4)' : `${VIOLET_DIM}`}`,
                  }} />
                  <div>
                    <p className="text-sm font-medium text-white/90">{s.lot_name}</p>
                    <p className="text-[9px] font-mono text-subtle mt-0.5">{s.lot_id}</p>
                  </div>
                </div>
                <StatusBadge status={s.status} />
              </div>
              <div className="flex items-center gap-4 text-[10px] font-mono text-subtle ml-4">
                {s.start_time && <span>{new Date(s.start_time.includes('Z') || s.start_time.includes('+') ? s.start_time : s.start_time + 'Z').toLocaleDateString()}</span>}
                {s.duration_minutes && <span>{s.duration_minutes}m</span>}
                {s.amount_charged !== undefined && s.amount_charged !== null && (
                  <span className="text-white/60 font-semibold">${s.amount_charged.toFixed(2)}</span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
