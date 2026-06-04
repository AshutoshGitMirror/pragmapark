import { useState, useEffect } from 'react'
import { fetchAlerts, type Alert } from '../../api/adminClient'

const severityColors: Record<string, { text: string; bg: string; border: string; dot: string }> = {
  critical: { text: 'text-red-400', bg: 'bg-red-500/8', border: 'border-red-500/20', dot: 'bg-red-400' },
  warning: { text: 'text-[#f59e0b]', bg: 'bg-amber-500/8', border: 'border-amber-500/20', dot: 'bg-[#f59e0b]' },
  info: { text: 'text-[#00d4ff]', bg: 'bg-[rgba(0,212,255,0.06)]', border: 'border-[rgba(0,212,255,0.15)]', dot: 'bg-[#00d4ff]' },
}

export function AlertsPage() {
  const [alerts, setAlerts] = useState<Alert[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let mounted = true
    const load = async () => {
      try {
        const res = await fetchAlerts()
        if (mounted) setAlerts(res)
      } catch { /* empty */ } finally {
        if (mounted) setLoading(false)
      }
    }
    load()
    const interval = setInterval(load, 30000)
    return () => { mounted = false; clearInterval(interval) }
  }, [])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-[#64748b] animate-pulse text-sm">Loading alerts...</div>
      </div>
    )
  }

  const activeAlerts = alerts.filter((a) => !a.resolved)

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-white">Alerts</h1>
        {activeAlerts.length > 0 && (
          <span className="text-[11px] px-2 py-0.5 rounded-full bg-[rgba(245,158,11,0.1)] text-[#f59e0b]">
            {activeAlerts.length} active
          </span>
        )}
      </div>

      {alerts.length === 0 ? (
        <div className="bg-[#0e0e1a] border border-[rgba(255,255,255,0.06)] rounded-xl p-8 text-center">
          <p className="text-[#64748b] text-sm">All clear — no alerts to show.</p>
        </div>
      ) : (
        <div className="space-y-2">
          {alerts.map((alert: Alert) => {
            const sc = severityColors[alert.severity] || severityColors.info
            return (
              <div
                key={alert.id}
                className={`bg-[#0e0e1a] border ${sc.border} rounded-xl p-4 flex items-start gap-3 ${alert.resolved ? 'opacity-50' : ''}`}
              >
                <span className={`w-2 h-2 rounded-full ${sc.dot} mt-1.5 shrink-0`} />
                <div className="flex-1 min-w-0">
                  <p className={`text-sm ${alert.resolved ? 'text-[#64748b]' : 'text-white/90'}`}>{alert.message}</p>
                  <div className="flex items-center gap-2 mt-1">
                    <span className={`text-[10px] ${sc.text}`}>{alert.severity}</span>
                    <span className="text-[#475569] text-[10px]">&middot;</span>
                    <span className="text-[#475569] text-[10px]">{alert.type}</span>
                    {alert.lot_id && (
                      <>
                        <span className="text-[#475569] text-[10px]">&middot;</span>
                        <span className="text-[#475569] text-[10px]">{alert.lot_id}</span>
                      </>
                    )}
                  </div>
                </div>
                <div>
                  {alert.resolved ? (
                    <span className="text-[10px] px-2 py-0.5 rounded-full bg-[rgba(0,199,133,0.1)] text-[#00c785]">Resolved</span>
                  ) : (
                    <span className={`text-[10px] px-2 py-0.5 rounded-full ${sc.bg} ${sc.text}`}>Active</span>
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
