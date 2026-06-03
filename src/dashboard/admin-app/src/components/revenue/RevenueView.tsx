import type { RevenueData } from '../../api/types'

interface RevenueViewProps { revenue: RevenueData | null }

export default function RevenueView({ revenue }: RevenueViewProps) {
  if (!revenue) {
    return (
      <div className="text-center py-16 text-sm" style={{ color: '#64748b' }}>
        <i className="fas fa-dollar-sign text-3xl block mb-3 opacity-50" />
        Loading revenue data...
      </div>
    )
  }

  const formatCurrency = (v: number) =>
    v >= 1_000_000 ? `$${(v / 1_000_000).toFixed(2)}M` :
    v >= 1_000 ? `$${(v / 1_000).toFixed(1)}K` : `$${v.toFixed(2)}`

  return (
    <div>
      <div className="grid gap-4 mb-6" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))' }}>
        {[
          { label: 'Total Revenue', value: formatCurrency(revenue.total_revenue), icon: 'dollar-sign', color: '#e2b84d' },
          { label: 'Transactions', value: (revenue.total_transactions || 0).toLocaleString(), icon: 'receipt', color: '#00d4ff' },
          { label: 'Avg Daily Revenue', value: formatCurrency(revenue.avg_daily), icon: 'chart-line', color: '#34d399' },
          { label: 'Active Lots', value: String(revenue.active_lots), icon: 'warehouse', color: '#a78bfa' },
        ].map(({ label, value, icon, color }) => (
          <div key={label} className="p-[22px] rounded-2xl" style={{
            background: 'rgba(255,255,255,0.06)', backdropFilter: 'blur(16px)',
            border: '1px solid rgba(255,255,255,0.06)',
          }}>
            <p className="text-[11px] mb-2 uppercase tracking-[0.8px]" style={{ color: 'rgba(240,238,248,0.55)' }}>{label}</p>
            <div className="flex items-center justify-between">
              <span className="text-[30px] font-bold -tracking-[0.5px]">{value}</span>
              <i className={`fas fa-${icon} text-xl`} style={{ opacity: 0.4, color }} />
            </div>
          </div>
        ))}
      </div>

      <div className="rounded-2xl overflow-x-auto" style={{
        background: 'rgba(255,255,255,0.06)', backdropFilter: 'blur(16px)',
        border: '1px solid rgba(255,255,255,0.06)',
      }}>
        <table className="w-full border-collapse">
          <thead>
            <tr>
              {['Lot', 'Total Revenue', 'Transactions', 'Avg Daily'].map((h) => (
                <th key={h} className="text-left px-[18px] py-3.5 text-[11px] uppercase tracking-[0.8px] font-medium"
                  style={{ color: 'rgba(240,238,248,0.5)', borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {(revenue.lots || []).map((lot) => (
              <tr key={lot.lot_id} className="transition-colors duration-200"
                style={{ borderBottom: '1px solid rgba(255,255,255,0.06)' }}
                onMouseEnter={(e) => e.currentTarget.style.background = 'rgba(255,255,255,0.09)'}
                onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
              >
                <td className="px-[18px] py-3.5 text-sm font-medium">{lot.name}</td>
                <td className="px-[18px] py-3.5 text-sm" style={{ color: '#e2b84d' }}>${(lot.revenue || 0).toLocaleString()}</td>
                <td className="px-[18px] py-3.5 text-sm">{(lot.transactions || 0).toLocaleString()}</td>
                <td className="px-[18px] py-3.5 text-sm" style={{ color: '#a49fc4' }}>${(lot.avg_daily || 0).toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {(!revenue.lots || revenue.lots.length === 0) && (
          <p className="text-center py-10 text-sm" style={{ color: '#64748b' }}>No revenue data available</p>
        )}
      </div>
    </div>
  )
}
