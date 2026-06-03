import type { Alert } from '../../api/types'

interface AlertsViewProps { alerts: Alert[] }

export default function AlertsView({ alerts }: AlertsViewProps) {
  if (!alerts || alerts.length === 0) {
    return (
      <div className="text-center py-20 text-sm" style={{ color: '#64748b' }}>
        <i className="fas fa-check-circle text-3xl block mb-3 opacity-50" />
        No alerts to display
      </div>
    )
  }

  return (
    <div className="rounded-2xl overflow-hidden" style={{
      background: 'rgba(255,255,255,0.06)', backdropFilter: 'blur(16px)',
      border: '1px solid rgba(255,255,255,0.06)',
    }}>
      <div className="divide-y" style={{ borderColor: 'rgba(255,255,255,0.06)' }}>
        {alerts.map((alert, i) => {
          const severity = (alert.severity || 'info').toLowerCase()
          const color = severity === 'critical' ? '#f87171' : severity === 'warning' ? '#fbbf24' : severity === 'error' ? '#f87171' : '#00d4ff'
          const icon = severity === 'critical' ? 'exclamation-triangle' : severity === 'warning' ? 'exclamation-circle' : severity === 'error' ? 'times-circle' : 'info-circle'

          return (
            <div key={alert.id || i} className="flex items-start gap-3 px-[18px] py-3.5 transition-colors duration-200"
              onMouseEnter={(e) => e.currentTarget.style.background = 'rgba(255,255,255,0.09)'}
              onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
            >
              <i className={`fas fa-${icon} mt-0.5`} style={{ color }} />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium mb-0.5">{alert.message || alert.title}</p>
                {(alert.description || alert.detail) && (
                  <p className="text-xs" style={{ color: '#a49fc4' }}>{alert.description || alert.detail}</p>
                )}
                {alert.lot_name && (
                  <span className="inline-block mt-1 text-[10px] px-2 py-0.5 rounded-full" style={{ background: 'rgba(226,184,77,0.1)', color: '#e2b84d' }}>
                    {alert.lot_name}
                  </span>
                )}
              </div>
              <div className="text-right flex-shrink-0">
                {alert.timestamp && (
                  <p className="text-[11px]" style={{ color: '#64748b' }}>
                    {new Date(alert.timestamp).toLocaleString()}
                  </p>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
