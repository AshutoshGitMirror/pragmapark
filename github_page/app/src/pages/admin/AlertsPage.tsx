import { useState, useEffect } from 'react'
import { fetchAlerts, type Alert } from '../../api/adminClient'

export function AlertsPage() {
  const [alerts, setAlerts] = useState<Alert[]>([])
  const [loading, setLoading] = useState(true)

  const load = async () => {
    try {
      const data = await fetchAlerts()
      setAlerts(data)
    } catch {} finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const active = alerts.filter((a) => !a.resolved)

  if (loading) return <div className="flex items-center justify-center h-64"><div className="text-dim animate-pulse">Loading alerts...</div></div>

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-light text-white">Alerts</h1>
        {active.length > 0 && (
          <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-400">
            {active.length} active
          </span>
        )}
      </div>

      {alerts.length === 0 ? (
        <div className="bg-[#13131f] border border-white/5 rounded-xl p-8 text-center">
          <p className="text-sm text-dim">No alerts</p>
        </div>
      ) : (
        <div className="space-y-2">
          {alerts.map((alert) => (
            <div
              key={alert.id}
              className={`bg-[#13131f] border rounded-xl p-4 flex items-start gap-4 ${
                alert.resolved ? 'border-white/5 opacity-50' :
                alert.severity === 'critical' ? 'border-red-500/30' :
                alert.severity === 'warning' ? 'border-amber-500/30' :
                'border-cyan-500/20'
              }`}
            >
              <span className={`text-base ${
                alert.resolved ? 'text-dim' :
                alert.severity === 'critical' ? 'text-red-400' :
                alert.severity === 'warning' ? 'text-amber-400' :
                'text-cyan-400'
              }`}>
                {alert.resolved ? '✓' : alert.severity === 'critical' ? '✕' : alert.severity === 'warning' ? '⚠' : 'ℹ'}
              </span>
              <div className="flex-1 min-w-0">
                <p className="text-sm text-white/90">{alert.message}</p>
                <div className="flex items-center gap-3 mt-1">
                  <span className="text-[10px] text-dim">{alert.type}</span>
                  <span className="text-[10px] text-dim">{alert.created_at}</span>
                  {alert.lot_id && <span className="text-[10px] font-mono text-dim">{alert.lot_id}</span>}
                </div>
              </div>
              <div className="flex items-center gap-2">
                <span className={`text-[10px] px-2 py-0.5 rounded-full ${
                  alert.resolved ? 'bg-emerald-500/10 text-emerald-400' : 'bg-amber-500/10 text-amber-400'
                }`}>
                  {alert.resolved ? 'Resolved' : alert.severity}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
