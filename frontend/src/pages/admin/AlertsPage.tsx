import { useState, useEffect } from 'react'
import { fetchAlerts, fetchHealth, api, type Alert } from '../../api/adminClient'
import { getErrorMessage } from '../../utils/format'

const ROSE = '#f04060'
const ROSE_DIM = 'rgba(240,64,96,0.12)'

const severityColors: Record<string, string> = {
  critical: '#f04060',
  high: '#f59e0b',
  medium: '#f0c040',
  low: '#5a6a8a',
}

const severityLabels: Record<string, string> = {
  all: 'All Events',
  critical: 'Critical',
  high: 'High',
  medium: 'Medium',
  low: 'Low',
}

export function AlertsPage() {
  const [alerts, setAlerts] = useState<Alert[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [filter, setFilter] = useState('all')

  useEffect(() => {
    let mounted = true
    const load = async () => {
      try {
        const data = await fetchAlerts()
        if (mounted) setAlerts(data)
        const health = await fetchHealth()
        if (mounted) {/* health check done */}
      } catch (err: unknown) {
        if (mounted) setError(getErrorMessage(err))
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
    } catch (err) {
      console.error('Failed to resolve alert', err)
    }
  }

  const filtered = filter === 'all' ? alerts : alerts.filter((a) => a.severity === filter)

  const severityCounts: Record<string, number> = {
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
      {/* ── Header ── */}
      <div>
        <p className="text-[10px] font-mono text-[#9a97b0] tracking-[3px] uppercase mb-2">05 / Actuate · System Events</p>
        <h1 className="section-headline">Alerts</h1>
        <p className="section-body mt-1">System events, warnings, and actuator notifications</p>
      </div>

      {/* ── Severity filter pills ── */}
      <div className="flex flex-wrap gap-2">
        {(['all', 'critical', 'high', 'medium', 'low'] as const).map((sev) => {
          const sevColor = sev === 'all' ? ROSE : severityColors[sev]
          return (
            <button
              key={sev}
              onClick={() => setFilter(sev)}
              className="relative flex items-center gap-2 px-4 py-2.5 rounded-xl text-left transition-all duration-200"
              style={{
                background: filter === sev
                  ? `linear-gradient(135deg, ${sevColor}10 0%, rgba(10,10,24,0.8) 100%)`
                  : 'linear-gradient(135deg, #0a0a18 0%, #0e0e20 100%)',
                boxShadow: filter === sev
                  ? `0 0 0 1px ${sevColor}30, 0 1px 0 rgba(255,255,255,0.04)`
                  : '0 0 0 1px rgba(255,255,255,0.04)',
              }}>
              <div className="flex items-center gap-2">
                {/* Severity dot */}
                <span className={`w-2 h-2 rounded-full ${sev === 'all' ? '' : ''}`}
                  style={{
                    backgroundColor: sevColor,
                    boxShadow: filter === sev ? `0 0 6px ${sevColor}66` : 'none',
                  }} />
                <span className="text-[11px] font-mono uppercase tracking-wider"
                  style={{ color: filter === sev ? sevColor : '#5a6a8a' }}>
                  {severityLabels[sev]}
                </span>
              </div>
              <span className="text-sm font-bold font-mono" style={{ color: filter === sev ? '#fff' : '#5a6a8a' }}>
                {severityCounts[sev]}
              </span>
            </button>
          )
        })}
      </div>

      {/* ── Error state ── */}
      {error && (
        <div className="rounded-xl p-4 text-center"
          style={{
            background: 'linear-gradient(135deg, #0e0e24 0%, #12122a 50%, #0e0e24 100%)',
            boxShadow: '0 1px 0 rgba(255,255,255,0.04), 0 0 0 1px rgba(255,255,255,0.04)',
          }}>
          <p className="text-xs font-mono" style={{ color: ROSE }}>{error}</p>
        </div>
      )}

      {/* ── Empty state ── */}
      {!error && filtered.length === 0 ? (
        <div className="rounded-xl p-10 text-center"
          style={{
            background: 'linear-gradient(135deg, #0e0e24 0%, #12122a 50%, #0e0e24 100%)',
            boxShadow: '0 1px 0 rgba(255,255,255,0.04), 0 0 0 1px rgba(255,255,255,0.04)',
          }}>
          <div className="text-2xl mb-2 opacity-20" style={{ color: ROSE }}>✓</div>
          <p className="text-sm text-[#5a6a8a] font-mono">No alerts to show</p>
        </div>
      ) : (
        <div className="space-y-2.5">
          {filtered.map((alert) => {
            const sevColor = severityColors[alert.severity] || '#5a6a8a'
            return (
              <div key={alert.id}
                className="rounded-xl p-5 transition-all duration-200 group"
                style={{
                  background: 'linear-gradient(135deg, #0e0e24 0%, #12122a 50%, #0e0e24 100%)',
                  boxShadow: '0 1px 0 rgba(255,255,255,0.04), 0 0 0 1px rgba(255,255,255,0.04)',
                }}>
                <div className="flex items-start gap-4">
                  {/* Severity glow dot */}
                  <div className="relative mt-1 shrink-0">
                    <span className="w-2.5 h-2.5 rounded-full block"
                      style={{
                        backgroundColor: sevColor,
                        boxShadow: `0 0 8px ${sevColor}50`,
                      }} />
                    {alert.severity === 'critical' && (
                      <span className="absolute inset-0 w-2.5 h-2.5 rounded-full animate-ping"
                        style={{ backgroundColor: sevColor, opacity: 0.4 }} />
                    )}
                  </div>

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1.5">
                      <span className="text-[9px] font-mono font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded"
                        style={{
                          backgroundColor: `${sevColor}18`,
                          color: sevColor,
                          border: `1px solid ${sevColor}25`,
                        }}>
                        {alert.severity}
                      </span>
                      <span className="text-[9px] font-mono text-[#5a6a8a]">
                        {new Date(alert.created_at).toLocaleString()}
                      </span>
                      {alert.type && (
                        <span className="text-[8px] font-mono text-[#3a4a6a] uppercase tracking-wider">
                          · {alert.type}
                        </span>
                      )}
                    </div>
                    <p className="text-[12px] text-white/80 leading-relaxed">{alert.message}</p>
                    {alert.lot_id && (
                      <p className="text-[9px] font-mono text-[#5a6a8a] mt-1">
                        Lot: {alert.lot_id}
                      </p>
                    )}
                  </div>

                  {!alert.resolved && (
                    <button
                      onClick={() => handleResolve(alert.id)}
                      className="text-[9px] font-mono px-2.5 py-1.5 rounded-lg transition-all active:scale-95 shrink-0 opacity-0 group-hover:opacity-100"
                      style={{
                        background: 'rgba(96,212,160,0.08)',
                        color: '#60d4a0',
                        border: '1px solid rgba(96,212,160,0.2)',
                      }}
                    >
                      Resolve
                    </button>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
