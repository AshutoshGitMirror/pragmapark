import { useState, useEffect } from 'react'
import { fetchAnalytics, type AnalyticsData } from '../../api/adminClient'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  RadarChart, Radar, PolarGrid, PolarAngleAxis,
  PieChart, Pie, Cell,
} from 'recharts'

const PIE_COLORS = ['#00d4ff', '#00c785', '#f59e0b', '#475569']

export function AnalyticsPage() {
  const [data, setData] = useState<AnalyticsData | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let mounted = true
    const load = async () => {
      try {
        const d = await fetchAnalytics()
        if (mounted) setData(d)
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
        <div className="text-[#64748b] animate-pulse text-sm">Loading analytics...</div>
      </div>
    )
  }

  if (!data) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-[#64748b] text-sm">No analytics data available.</div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <h1 className="text-lg font-semibold text-white">Analytics</h1>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-[#0e0e1a] border border-[rgba(255,255,255,0.06)] rounded-xl p-5">
          <h3 className="text-xs text-[#64748b] mb-4">Hourly Occupancy</h3>
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data.hourly_occupancy}>
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
          <h3 className="text-xs text-[#64748b] mb-4">Lot Comparison</h3>
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <RadarChart data={data.lot_comparison}>
                <PolarGrid stroke="rgba(255,255,255,0.06)" />
                <PolarAngleAxis dataKey="name" tick={{ fill: '#64748b', fontSize: 10 }} />
                <Tooltip
                  contentStyle={{ background: '#12121e', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 8, fontSize: 12 }}
                  labelStyle={{ color: '#94a3b8' }}
                />
                <Radar name="Occupancy" dataKey="occupancy" stroke="#00d4ff" fill="#00d4ff" fillOpacity={0.15} strokeWidth={1.5} />
                <Radar name="Efficiency" dataKey="efficiency" stroke="#f59e0b" fill="#f59e0b" fillOpacity={0.15} strokeWidth={1.5} />
              </RadarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="bg-[#0e0e1a] border border-[rgba(255,255,255,0.06)] rounded-xl p-5">
          <h3 className="text-xs text-[#64748b] mb-4">System Performance</h3>
          <div className="h-56 flex items-center justify-center">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={data.system_performance.map((m) => ({ name: m.metric, value: m.value }))}
                  dataKey="value"
                  nameKey="name"
                  cx="50%"
                  cy="50%"
                  innerRadius={50}
                  outerRadius={80}
                  paddingAngle={2}
                >
                  {data.system_performance.map((_: any, idx: number) => (
                    <Cell key={idx} fill={PIE_COLORS[idx % PIE_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{ background: '#12121e', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 8, fontSize: 12 }}
                  labelStyle={{ color: '#94a3b8' }}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="bg-[#0e0e1a] border border-[rgba(255,255,255,0.06)] rounded-xl p-5">
          <h3 className="text-xs text-[#64748b] mb-4">Performance Metrics</h3>
          <div className="space-y-4">
            {data.system_performance.map((m: any, idx: number) => (
              <div key={idx} className="flex items-center justify-between py-2 border-b border-[rgba(255,255,255,0.02)] last:border-0">
                <span className="text-xs text-[#64748b]">{m.metric}</span>
                <div className="flex items-center gap-3">
                  <span className="text-xs font-mono text-white">{m.value}{m.unit}</span>
                  <span
                    className={`text-[10px] px-2 py-0.5 rounded-full ${
                      m.status === 'healthy' ? 'bg-[rgba(0,199,133,0.1)] text-[#00c785]' :
                      m.status === 'warning' ? 'bg-[rgba(245,158,11,0.1)] text-[#f59e0b]' :
                      'bg-red-500/10 text-red-400'
                    }`}
                  >
                    {m.status}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
