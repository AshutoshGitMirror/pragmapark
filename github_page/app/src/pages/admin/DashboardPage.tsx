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
        <div className="text-[#5a6a8a] animate-pulse text-sm">Loading dashboard...</div>
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
    { label: 'Total Lots', value: String(data.total_lots), icon: '⛊', accent: '#00e5ff' },
    { label: 'Avg Occupancy', value: `${data.avg_occupancy.toFixed(1)}%`, icon: '◈', accent: '#f59e0b' },
    { label: 'Total Revenue', value: `$${(data.total_revenue || 0).toLocaleString()}`, icon: '¤', accent: '#00c785' },
    { label: 'System Health', value: data.system_health?.status || 'Unknown', icon: '⚡',
      accent: data.system_health?.status === 'healthy' ? '#00c785' : '#f59e0b' },
  ]

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-white">Dashboard</h1>
          <p className="text-xs text-[#5a6a8a] mt-1">Platform overview and key metrics</p>
        </div>
        <div className="flex items-center gap-2 text-xs text-[#5a6a8a]">
          <span>{user?.full_name || 'Admin'}</span>
          <span className="px-2 py-0.5 rounded bg-white/[0.04] text-[#475569]">{user?.role || 'user'}</span>
        </div>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-5">
        {stats.map((s) => (
          <div key={s.label}
            className="rounded-xl p-5 transition-all duration-200 hover:scale-[1.02]"
            style={{
              background: 'linear-gradient(135deg, #0e0e24 0%, #12122a 50%, #0e0e24 100%)',
              boxShadow: '0 1px 0 rgba(255,255,255,0.04), 0 0 0 1px rgba(255,255,255,0.04)',
            }}>
            <div className="flex items-center gap-2.5 mb-3">
              <span className="text-lg" style={{ color: s.accent }}>{s.icon}</span>
              <p className="text-[11px] font-medium uppercase tracking-wider text-[#475569]">{s.label}</p>
            </div>
            <p className="text-[28px] font-bold tracking-tight text-white leading-none">{s.value}</p>
            <div className="mt-3 h-0.5 w-8 rounded-full opacity-60" style={{ background: s.accent }} />
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="rounded-xl p-6"
          style={{
            background: 'linear-gradient(135deg, #0e0e24 0%, #12122a 50%, #0e0e24 100%)',
            boxShadow: '0 1px 0 rgba(255,255,255,0.04), 0 0 0 1px rgba(255,255,255,0.04)',
          }}>
          <div className="flex items-center justify-between mb-5">
            <h3 className="text-sm font-medium text-white/80">Occupancy Trends</h3>
            <span className="text-[10px] text-[#475569] px-2 py-0.5 rounded bg-white/[0.03]">Today</span>
          </div>
          <div className="h-52">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data.occupancy_trend}>
                <XAxis dataKey="hour" tick={{ fill: '#3a4a6a', fontSize: 10 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: '#3a4a6a', fontSize: 10 }} axisLine={false} tickLine={false} domain={[0, 100]} />
                <Tooltip
                  contentStyle={{ background: '#16163a', border: '1px solid rgba(0,212,255,0.15)', borderRadius: 10, fontSize: 12, boxShadow: '0 8px 32px rgba(0,0,0,0.4)' }}
                  labelStyle={{ color: '#94a3b8' }}
                  cursor={{ fill: 'rgba(0,212,255,0.04)' }}
                />
                <Bar dataKey="rate" fill="#00d4ff" radius={[3, 3, 0, 0]} opacity={0.8} maxBarSize={24} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
        <div className="rounded-xl p-6"
          style={{
            background: 'linear-gradient(135deg, #0e0e24 0%, #12122a 50%, #0e0e24 100%)',
            boxShadow: '0 1px 0 rgba(255,255,255,0.04), 0 0 0 1px rgba(255,255,255,0.04)',
          }}>
          <div className="flex items-center justify-between mb-5">
            <h3 className="text-sm font-medium text-white/80">Revenue (7 Days)</h3>
            <span className="text-[10px] text-[#475569] px-2 py-0.5 rounded bg-white/[0.03]">Weekly</span>
          </div>
          <div className="h-52">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={data.revenue_7d}>
                <XAxis dataKey="date" tick={{ fill: '#3a4a6a', fontSize: 10 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: '#3a4a6a', fontSize: 10 }} axisLine={false} tickLine={false} />
                <Tooltip
                  contentStyle={{ background: '#16163a', border: '1px solid rgba(0,212,255,0.15)', borderRadius: 10, fontSize: 12, boxShadow: '0 8px 32px rgba(0,0,0,0.4)' }}
                  labelStyle={{ color: '#94a3b8' }}
                />
                <Area type="monotone" dataKey="revenue" stroke="#00d4ff" fill="url(#revenueGrad)" strokeWidth={2.5} dot={false} />
                <defs>
                  <linearGradient id="revenueGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#00d4ff" stopOpacity={0.2} />
                    <stop offset="100%" stopColor="#00d4ff" stopOpacity={0} />
                  </linearGradient>
                </defs>
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <div className="rounded-xl overflow-hidden"
        style={{
          background: 'linear-gradient(135deg, #0e0e24 0%, #12122a 50%, #0e0e24 100%)',
          boxShadow: '0 1px 0 rgba(255,255,255,0.04), 0 0 0 1px rgba(255,255,255,0.04)',
        }}>
        <div className="px-6 py-4 border-b border-[rgba(255,255,255,0.04)] flex items-center justify-between">
          <h3 className="text-sm font-medium text-white/80">Parking Lots</h3>
          <span className="text-[10px] text-[#475569]">{data.lots?.length || 0} lots</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-[11px] text-[#3a4a6a] border-b border-[rgba(255,255,255,0.03)] bg-white/[0.02]">
                <th className="text-left font-semibold px-5 py-3">Lot</th>
                <th className="text-left font-semibold px-5 py-3">Address</th>
                <th className="text-right font-semibold px-5 py-3">Slots</th>
                <th className="text-right font-semibold px-5 py-3">Occupancy</th>
                <th className="text-right font-semibold px-5 py-3">Price</th>
                <th className="text-right font-semibold px-5 py-3">Status</th>
              </tr>
            </thead>
            <tbody>
              {(data.lots || []).map((lot: Lot) => (
                <tr key={lot.lot_id} className="border-b border-[rgba(255,255,255,0.02)] hover:bg-[rgba(0,212,255,0.02)] transition-colors">
                  <td className="px-5 py-3.5 font-medium text-white/90 text-xs">{lot.name}</td>
                  <td className="px-5 py-3.5 text-[#5a6a8a] text-xs">{lot.address}</td>
                  <td className="px-5 py-3.5 text-right text-[#5a6a8a] font-mono text-xs">{lot.total_slots}</td>
                  <td className="px-5 py-3.5 text-right font-mono text-xs" style={{ color: (lot.current_occupancy || 0) > 0.3 ? '#f59e0b' : '#5a6a8a' }}>
                    {lot.current_occupancy !== undefined ? `${(lot.current_occupancy * 100).toFixed(1)}%` : '-'}
                  </td>
                  <td className="px-5 py-3.5 text-right font-mono text-xs text-[#00c785]">${lot.base_price.toFixed(2)}</td>
                  <td className="px-5 py-3.5 text-right">
                    <span className="text-[10px] px-2.5 py-0.5 rounded-full bg-[rgba(0,199,133,0.1)] text-[#00c785] font-medium">
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
