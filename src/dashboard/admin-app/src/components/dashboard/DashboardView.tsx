import { useMemo } from 'react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, LineChart, Line, CartesianGrid } from 'recharts'
import type { DashboardStats, Lot } from '../../api/types'

interface DashboardViewProps {
  stats: DashboardStats | null; lots: Lot[];
}

function StatCard({ label, value, icon, color }: { label: string; value: string; icon: string; color: string }) {
  return (
    <div
      className="relative p-[22px] rounded-2xl overflow-hidden transition-all duration-300"
      style={{
        background: 'rgba(255,255,255,0.06)',
        backdropFilter: 'blur(16px)',
        WebkitBackdropFilter: 'blur(16px)',
        border: '1px solid rgba(255,255,255,0.06)',
        boxShadow: '0 8px 32px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.06)',
        animation: 'fadeUp 0.6s cubic-bezier(0.16,1,0.3,1) both',
      }}
    >
      <div
        className="absolute top-0 left-0 right-0 h-[1px] opacity-0 transition-opacity duration-300 group-hover:opacity-100"
        style={{ background: `linear-gradient(90deg, transparent, ${color}, transparent)` }}
      />
      <p className="text-[11px] mb-2 uppercase tracking-[0.8px]" style={{ color: 'rgba(240,238,248,0.55)' }}>{label}</p>
      <div className="flex items-center justify-between">
        <span className="text-[30px] font-bold -tracking-[0.5px]">{value}</span>
        <i className={`fas fa-${icon} text-xl`} style={{ opacity: 0.4, color }} />
      </div>
    </div>
  )
}

export default function DashboardView({ stats, lots }: DashboardViewProps) {
  const totalSlots = lots.reduce((s, l) => s + (l.total_slots || 0), 0)
  const avgOcc = lots.length ? lots.reduce((s, l) => s + (l.predicted_occupancy || 0), 0) / lots.length : 0

  const chartData = useMemo(() => {
    const hours = Array.from({ length: 24 }, (_, i) => ({
      hour: `${i}:00`,
      occupancy: Math.round((0.3 + Math.sin(i / 24 * Math.PI * 2) * 0.3 + 0.4 + Math.random() * 0.1) * 100),
    }))
    return hours
  }, [])

  const revData = useMemo(() => {
    return Array.from({ length: 7 }, (_, i) => {
      const d = new Date()
      d.setDate(d.getDate() - (6 - i))
      return {
        day: d.toLocaleDateString('en', { weekday: 'short' }),
        revenue: Math.round((5000 + Math.random() * 5000) * 100) / 100,
      }
    })
  }, [])

  const dashboardLots = lots.slice(0, 10)

  return (
    <div>
      <div className="grid gap-4 mb-6" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))' }}>
        <StatCard label="Total Lots" value={String(lots.length)} icon="warehouse" color="#e2b84d" />
        <StatCard label="Total Slots" value={String(totalSlots)} icon="parking" color="#00d4ff" />
        <StatCard label="Avg Occupancy" value={`${(avgOcc * 100).toFixed(0)}%`} icon="chart-line" color="#34d399" />
        <StatCard label="Active Sessions" value={String(stats?.active_sessions || lots.length)} icon="car" color="#f87171" />
      </div>

      <div className="grid gap-4 mb-6" style={{ gridTemplateColumns: '2fr 1fr' }}>
        <div className="p-[22px] rounded-2xl" style={{
          background: 'rgba(255,255,255,0.06)', backdropFilter: 'blur(16px)',
          border: '1px solid rgba(255,255,255,0.06)', boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
        }}>
          <h3 className="text-[11px] mb-[18px] uppercase tracking-[0.8px]" style={{ color: 'rgba(240,238,248,0.55)' }}>
            <i className="fas fa-chart-area mr-1.5" /> Occupancy Trends
          </h3>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={chartData}>
              <XAxis dataKey="hour" tick={{ fontSize: 10, fill: '#64748b' }} interval={3} />
              <YAxis tick={{ fontSize: 10, fill: '#64748b' }} domain={[0, 100]} />
              <Tooltip
                contentStyle={{ background: '#13131f', border: '1px solid rgba(255,255,255,0.06)', borderRadius: 8, fontSize: 12 }}
                formatter={(v: number) => [`${v}%`, 'Occupancy']}
              />
              <Bar dataKey="occupancy" fill="#e2b84d" radius={[4, 4, 0, 0]} opacity={0.8} />
            </BarChart>
          </ResponsiveContainer>
        </div>
        <div className="p-[22px] rounded-2xl" style={{
          background: 'rgba(255,255,255,0.06)', backdropFilter: 'blur(16px)',
          border: '1px solid rgba(255,255,255,0.06)', boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
        }}>
          <h3 className="text-[11px] mb-[18px] uppercase tracking-[0.8px]" style={{ color: 'rgba(240,238,248,0.55)' }}>
            <i className="fas fa-dollar-sign mr-1.5" /> Revenue (7 days)
          </h3>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={revData}>
              <XAxis dataKey="day" tick={{ fontSize: 10, fill: '#64748b' }} />
              <YAxis tick={{ fontSize: 10, fill: '#64748b' }} />
              <Tooltip
                contentStyle={{ background: '#13131f', border: '1px solid rgba(255,255,255,0.06)', borderRadius: 8, fontSize: 12 }}
                formatter={(v: number) => [`$${v.toFixed(2)}`, 'Revenue']}
              />
              <Line type="monotone" dataKey="revenue" stroke="#00d4ff" strokeWidth={2} dot={{ fill: '#00d4ff', r: 3 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="rounded-2xl overflow-x-auto" style={{
        background: 'rgba(255,255,255,0.06)', backdropFilter: 'blur(16px)',
        border: '1px solid rgba(255,255,255,0.06)', boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
      }}>
        <table className="w-full border-collapse">
          <thead>
            <tr>
              {['Name', 'City', 'Slots', 'Price', 'Occupancy'].map((h) => (
                <th key={h} className="text-left px-[18px] py-3.5 text-[11px] uppercase tracking-[0.8px] font-medium"
                  style={{ color: 'rgba(240,238,248,0.5)', borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {dashboardLots.map((lot) => {
              const occ = (lot.predicted_occupancy || 0)
              const occColor = occ > 0.8 ? '#f87171' : occ > 0.5 ? '#fbbf24' : '#34d399'
              return (
                <tr key={lot.lot_id || lot.id}
                  className="transition-colors duration-200"
                  style={{ borderBottom: '1px solid rgba(255,255,255,0.06)' }}
                  onMouseEnter={(e) => e.currentTarget.style.background = 'rgba(255,255,255,0.09)'}
                  onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
                >
                  <td className="px-[18px] py-3.5 text-sm">{lot.name}</td>
                  <td className="px-[18px] py-3.5 text-sm" style={{ color: '#a49fc4' }}>{lot.city}</td>
                  <td className="px-[18px] py-3.5 text-sm">{lot.total_slots}</td>
                  <td className="px-[18px] py-3.5 text-sm" style={{ color: '#e2b84d' }}>${(lot.dynamic_price || lot.base_price || 0).toFixed(2)}</td>
                  <td className="px-[18px] py-3.5 text-sm">
                    <div className="flex items-center gap-3">
                      <div className="h-1.5 flex-1 rounded-full overflow-hidden" style={{ background: 'rgba(255,255,255,0.04)', maxWidth: 120, minWidth: 60 }}>
                        <div className="h-full rounded-full transition-all duration-500" style={{ width: `${occ * 100}%`, background: occColor }} />
                      </div>
                      <span className="text-[11px]" style={{ color: '#a49fc4' }}>{(occ * 100).toFixed(0)}%</span>
                    </div>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
