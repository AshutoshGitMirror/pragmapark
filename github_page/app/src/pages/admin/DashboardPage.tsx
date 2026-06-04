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
        <div className="text-[#64748b] animate-pulse text-sm">Loading dashboard...</div>
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
    { label: 'Total Lots', value: data.total_lots, icon: '⛊' },
    { label: 'Avg Occupancy', value: `${data.avg_occupancy.toFixed(1)}%`, icon: '◈' },
    { label: 'Total Revenue', value: `$${(data.total_revenue || 0).toLocaleString()}`, icon: '¤' },
    { label: 'System Health', value: data.system_health?.status || 'Unknown', icon: '⚡',
      healthy: data.system_health?.status === 'healthy' },
  ]

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-white">Dashboard</h1>
        <div className="flex items-center gap-2 text-xs text-[#64748b]">
          <span>{user?.full_name || 'Admin'}</span>
          <span className="px-2 py-0.5 rounded bg-[rgba(255,255,255,0.04)] text-[#475569]">{user?.role || 'user'}</span>
        </div>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {stats.map((s) => (
          <div key={s.label} className="bg-[#0e0e1a] border border-[rgba(255,255,255,0.06)] rounded-xl p-4">
            <div className="flex items-center gap-2 mb-2">
              <span className="text-[#475569] text-xs">{s.icon}</span>
              <p className="text-[11px] text-[#475569]">{s.label}</p>
            </div>
            <p className={`text-lg font-semibold ${s.healthy !== undefined ? (s.healthy ? 'text-[#00c785]' : 'text-[#f59e0b]') : 'text-white'}`}>
              {s.value}
            </p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-[#0e0e1a] border border-[rgba(255,255,255,0.06)] rounded-xl p-5">
          <h3 className="text-xs text-[#64748b] mb-4">Occupancy Trends</h3>
          <div className="h-48">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data.occupancy_trend}>
                <XAxis dataKey="hour" tick={{ fill: '#475569', fontSize: 10 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: '#475569', fontSize: 10 }} axisLine={false} tickLine={false} domain={[0, 100]} />
                <Tooltip
                  contentStyle={{ background: '#12121e', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 8, fontSize: 12 }}
                  labelStyle={{ color: '#94a3b8' }}
                />
                <Bar dataKey="rate" fill="#00d4ff" radius={[2, 2, 0, 0]} opacity={0.7} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
        <div className="bg-[#0e0e1a] border border-[rgba(255,255,255,0.06)] rounded-xl p-5">
          <h3 className="text-xs text-[#64748b] mb-4">Revenue (7 Days)</h3>
          <div className="h-48">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={data.revenue_7d}>
                <XAxis dataKey="date" tick={{ fill: '#475569', fontSize: 10 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: '#475569', fontSize: 10 }} axisLine={false} tickLine={false} />
                <Tooltip
                  contentStyle={{ background: '#12121e', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 8, fontSize: 12 }}
                  labelStyle={{ color: '#94a3b8' }}
                />
                <Area type="monotone" dataKey="revenue" stroke="#00d4ff" fill="#00d4ff" fillOpacity={0.08} strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <div className="bg-[#0e0e1a] border border-[rgba(255,255,255,0.06)] rounded-xl overflow-hidden">
        <div className="p-4 border-b border-[rgba(255,255,255,0.06)]">
          <h3 className="text-xs text-[#64748b]">Parking Lots</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-[11px] text-[#475569] border-b border-[rgba(255,255,255,0.04)]">
                <th className="text-left font-medium px-4 py-2.5">Lot</th>
                <th className="text-left font-medium px-4 py-2.5">Address</th>
                <th className="text-right font-medium px-4 py-2.5">Slots</th>
                <th className="text-right font-medium px-4 py-2.5">Occupancy</th>
                <th className="text-right font-medium px-4 py-2.5">Price</th>
                <th className="text-right font-medium px-4 py-2.5">Status</th>
              </tr>
            </thead>
            <tbody>
              {(data.lots || []).map((lot: Lot) => (
                <tr key={lot.lot_id} className="border-b border-[rgba(255,255,255,0.02)] hover:bg-white/[0.015] transition-colors">
                  <td className="px-4 py-3 font-medium text-white/90 text-xs">{lot.name}</td>
                  <td className="px-4 py-3 text-[#64748b] text-xs">{lot.address}</td>
                  <td className="px-4 py-3 text-right text-[#64748b] font-mono text-xs">{lot.total_slots}</td>
                  <td className="px-4 py-3 text-right font-mono text-xs text-[#f59e0b]">
                    {lot.current_occupancy !== undefined ? `${(lot.current_occupancy * 100).toFixed(1)}%` : '-'}
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-xs text-[#00c785]">${lot.base_price.toFixed(2)}</td>
                  <td className="px-4 py-3 text-right">
                    <span className="text-[10px] px-2 py-0.5 rounded-full bg-[rgba(0,199,133,0.1)] text-[#00c785]">
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
