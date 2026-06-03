import { useState, useEffect } from 'react'
import { fetchDashboard, type DashboardData, type Lot } from '../../api/adminClient'
import { useAuth } from '../../context/AuthContext'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  AreaChart, Area,
} from 'recharts'

export function DashboardPage() {
  const { user } = useAuth()
  const [data, setData] = useState<DashboardData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let mounted = true
    const load = async () => {
      try {
        const d = await fetchDashboard()
        if (mounted) setData(d)
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

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-dim animate-pulse">Loading dashboard...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-red-400 text-sm">{error}</div>
      </div>
    )
  }

  if (!data) return null

  const stats = [
    { label: 'TOTAL LOTS', value: data.total_lots, color: 'text-cyan-400' },
    { label: 'AVG OCCUPANCY', value: `${data.avg_occupancy.toFixed(1)}%`, color: 'text-amber-400' },
    { label: 'TOTAL REVENUE', value: `$${(data.total_revenue || 0).toLocaleString()}`, color: 'text-emerald-400' },
    { label: 'SYSTEM HEALTH', value: data.system_health?.status || 'Unknown', color: data.system_health?.status === 'healthy' ? 'text-emerald-400' : 'text-amber-400' },
  ]

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-light text-white">Dashboard</h1>
        <div className="flex items-center gap-3 text-xs text-dim">
          <span>{user?.full_name || 'Admin'}</span>
          <span className="px-2 py-0.5 rounded bg-white/5 text-dim">{user?.role || 'user'}</span>
        </div>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {stats.map((s) => (
          <div key={s.label} className="bg-[#13131f] border border-white/5 rounded-xl p-4">
            <p className="text-[10px] text-dim uppercase tracking-widest mb-1.5">{s.label}</p>
            <p className={`text-xl font-mono ${s.color}`}>{s.value}</p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-[#13131f] border border-white/5 rounded-xl p-5">
          <h3 className="text-xs text-dim uppercase tracking-widest mb-4">Occupancy Trends</h3>
          <div className="h-48">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data.occupancy_trend}>
                <XAxis dataKey="hour" tick={{ fill: '#64748b', fontSize: 10 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: '#64748b', fontSize: 10 }} axisLine={false} tickLine={false} domain={[0, 100]} />
                <Tooltip
                  contentStyle={{ background: '#1a1a2e', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, fontSize: 12 }}
                  labelStyle={{ color: '#94a3b8' }}
                />
                <Bar dataKey="rate" fill="#00d4ff" radius={[2, 2, 0, 0]} opacity={0.7} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
        <div className="bg-[#13131f] border border-white/5 rounded-xl p-5">
          <h3 className="text-xs text-dim uppercase tracking-widest mb-4">Revenue (7 Days)</h3>
          <div className="h-48">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={data.revenue_7d}>
                <XAxis dataKey="date" tick={{ fill: '#64748b', fontSize: 10 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: '#64748b', fontSize: 10 }} axisLine={false} tickLine={false} />
                <Tooltip
                  contentStyle={{ background: '#1a1a2e', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, fontSize: 12 }}
                  labelStyle={{ color: '#94a3b8' }}
                />
                <Area type="monotone" dataKey="revenue" stroke="#00c785" fill="#00c785" fillOpacity={0.1} strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <div className="bg-[#13131f] border border-white/5 rounded-xl overflow-hidden">
        <div className="p-4 border-b border-white/5">
          <h3 className="text-xs text-dim uppercase tracking-widest">Parking Lots</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-[10px] text-dim uppercase tracking-wider border-b border-white/5">
                <th className="text-left p-3 font-medium">Lot</th>
                <th className="text-left p-3 font-medium">Address</th>
                <th className="text-right p-3 font-medium">Slots</th>
                <th className="text-right p-3 font-medium">Occupancy</th>
                <th className="text-right p-3 font-medium">Price</th>
                <th className="text-right p-3 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {(data.lots || []).map((lot: Lot) => (
                <tr key={lot.lot_id} className="border-b border-white/[0.02] hover:bg-white/[0.02] transition-colors">
                  <td className="p-3 font-medium text-white/90">{lot.name}</td>
                  <td className="p-3 text-dim text-xs">{lot.address}</td>
                  <td className="p-3 text-right font-mono text-xs text-muted">{lot.total_slots}</td>
                  <td className="p-3 text-right font-mono text-xs text-amber-400">
                    {lot.current_occupancy !== undefined ? `${(lot.current_occupancy * 100).toFixed(1)}%` : '-'}
                  </td>
                  <td className="p-3 text-right font-mono text-xs text-emerald-400">${lot.base_price.toFixed(2)}</td>
                  <td className="p-3 text-right">
                    <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400">
                      {lot.status || 'Available'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
