import { useState, useEffect } from 'react'
import { fetchAlerts, fetchHealth, api, type Alert } from '../../api/adminClient'

const severityColors: Record<string, string> = {
  critical: '#ff4757',
  high: '#ff6b6b',
  medium: '#f59e0b',
  low: '#5a6a8a',
}

export function AlertsPage() {
  const [alerts, setAlerts] = useState<Alert[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [filter, setFilter] = useState('all')
  const [isDemo, setIsDemo] = useState(false)

  useEffect(() => {
    let mounted = true
    const load = async () => {
      try {
        const data = await fetchAlerts()
        if (mounted) setAlerts(data)
        
        const health = await fetchHealth()
        if (mounted) setIsDemo(!!health.is_demo)
      } catch (err: any) {
        if (mounted) setError(err.message)
      } finally {
        if (mounted) setLoading(false)
      }
    }
    load()
    const interval = setInterval(load, 30000)
    return () => { mounted = false; clearInterval(interval) }
  }, [])

  const handleResolve = async (id: number) => {
    try {
      await api.put(`/admin/alerts/${id}/resolve`)
      setAlerts((prev) => prev.filter((a) => a.id !== id))
    } catch { /* empty */ }
  }

  const filtered = filter === 'all' ? alerts : alerts.filter((a) => a.severity === filter)

  const severityCounts = {
    all: alerts.length,
    critical: alerts.filter((a) => a.severity === 'critical').length,
    high: alerts.filter((a) => a.severity === 'high').length,
    medium: alerts.filter((a) => a.severity === 'medium').length,
    low: alerts.filter((a) => a.severity === 'low').length,
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-[#5a6a8a] animate-pulse text-sm">Loading alerts...</div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-white">Alerts</h1>
        <p className="text-xs text-[#5a6a8a] mt-1">Monitor system events and warnings</p>
      </div>

      {isDemo && (
        <div className="relative overflow-hidden rounded-xl p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs"
          style={{
            background: 'linear-gradient(135deg, rgba(30, 27, 75, 0.4) 0%, rgba(15, 23, 42, 0.4) 100%)',
            border: '1px solid rgba(129, 140, 248, 0.15)',
            boxShadow: '0 8px 32px rgba(0, 0, 0, 0.3)',
            backdropFilter: 'blur(8px)',
          }}>
          <div className="flex items-center gap-3">
            <span className="flex h-2 w-2 relative">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-indigo-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-indigo-500"></span>
            </span>
            <span className="text-white/80 leading-normal">
              <span className="font-semibold text-indigo-300">Demo Mode Active:</span> Showing simulated system events and warning alerts.
            </span>
          </div>
          <div className="shrink-0 flex items-center">
            <span className="px-2 py-0.5 rounded text-[10px] uppercase font-mono tracking-wider font-semibold" 
              style={{ background: 'rgba(99, 102, 241, 0.15)', color: '#818cf8', border: '1px solid rgba(99, 102, 241, 0.25)' }}>
              Simulated Alerts
            </span>
          </div>
        </div>
      )}

      <div className="grid grid-cols-4 gap-4">
        {(['all', 'critical', 'high', 'medium'] as const).map((sev) => (
          <button
            key={sev}
            onClick={() => setFilter(sev)}
            className="rounded-xl p-4 text-left transition-all duration-200 hover:scale-[1.02]"
            style={{
              background: filter === sev
                ? 'linear-gradient(135deg, #0e0e24 0%, #12122a 50%, #0e0e24 100%)'
                : 'linear-gradient(135deg, #0a0a18 0%, #0e0e20 50%, #0a0a18 100%)',
              boxShadow: filter === sev
                ? '0 0 0 1px rgba(0,212,255,0.15), 0 1px 0 rgba(255,255,255,0.04)'
                : '0 0 0 1px rgba(255,255,255,0.04)',
            }}>
            <div className="flex items-center justify-between mb-1.5">
              <p className="text-[11px] font-medium uppercase tracking-wider text-[#475569]">{sev}</p>
              {isDemo && (
                <span className="px-1 py-0.5 text-[8px] font-semibold rounded text-[#94a3b8]/70 uppercase tracking-wider bg-white/[0.03] border border-white/[0.05] select-none">
                  Demo
                </span>
              )}
            </div>
            <p className="text-2xl font-bold text-white tracking-tight">{severityCounts[sev]}</p>
          </button>
        ))}
      </div>

      {error && (
        <div className="rounded-xl p-4 text-center"
          style={{
            background: 'linear-gradient(135deg, #0e0e24 0%, #12122a 50%, #0e0e24 100%)',
            boxShadow: '0 1px 0 rgba(255,255,255,0.04), 0 0 0 1px rgba(255,255,255,0.04)',
          }}>
          <p className="text-xs text-red-400">{error}</p>
        </div>
      )}

      {!error && filtered.length === 0 ? (
        <div className="rounded-xl p-10 text-center"
          style={{
            background: 'linear-gradient(135deg, #0e0e24 0%, #12122a 50%, #0e0e24 100%)',
            boxShadow: '0 1px 0 rgba(255,255,255,0.04), 0 0 0 1px rgba(255,255,255,0.04)',
          }}>
          <p className="text-sm text-[#475569]">No alerts to show</p>
        </div>
      ) : (
        <div className="space-y-3">
          {filtered.map((alert) => (
            <div key={alert.id}
              className="rounded-xl p-5 transition-all duration-200 hover:scale-[1.01] flex items-start gap-4"
              style={{
                background: 'linear-gradient(135deg, #0e0e24 0%, #12122a 50%, #0e0e24 100%)',
                boxShadow: '0 1px 0 rgba(255,255,255,0.04), 0 0 0 1px rgba(255,255,255,0.04)',
              }}>
              <div className="w-2.5 h-2.5 rounded-full mt-1 shrink-0" style={{ backgroundColor: severityColors[alert.severity] || '#5a6a8a' }} />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-[10px] font-medium uppercase tracking-wider px-1.5 py-0.5 rounded" style={{
                    backgroundColor: `${severityColors[alert.severity] || '#5a6a8a'}20`,
                    color: severityColors[alert.severity] || '#5a6a8a',
                  }}>{alert.severity}</span>
                  <span className="text-[10px] text-[#475569]">{new Date(alert.created_at).toLocaleString()}</span>
                </div>
                <p className="text-sm text-white/80">{alert.message}</p>
                {alert.lot_id && <p className="text-[11px] text-[#475569] mt-0.5 font-mono">Lot: {alert.lot_id}</p>}
              </div>
              {!alert.resolved && (
                <button
                  onClick={() => handleResolve(alert.id)}
                  className="text-[10px] text-[#475569] hover:text-[#00c785] transition-colors px-2 py-1 rounded hover:bg-white/[0.03] shrink-0"
                >
                  Resolve
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
