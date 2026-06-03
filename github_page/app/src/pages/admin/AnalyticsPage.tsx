import { useState, useEffect } from 'react'
import { fetchAnalytics, type AnalyticsData } from '../../api/adminClient'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar, PieChart, Pie, Cell } from 'recharts'

export function AnalyticsPage() {
  const [data, setData] = useState<AnalyticsData | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchAnalytics().then(setData).catch(() => {}).finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="flex items-center justify-center h-64"><div className="text-dim animate-pulse">Loading analytics...</div></div>
  if (!data) return <div className="text-dim text-sm">No analytics data available</div>

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-light text-white">Analytics</h1>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-[#13131f] border border-white/5 rounded-xl p-5">
          <h3 className="text-xs text-dim uppercase tracking-widest mb-4">Hourly Occupancy Pattern</h3>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data.hourly_occupancy}>
                <XAxis dataKey="hour" tick={{ fill: '#64748b', fontSize: 10 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: '#64748b', fontSize: 10 }} axisLine={false} tickLine={false} domain={[0, 100]} />
                <Tooltip contentStyle={{ background: '#1a1a2e', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, fontSize: 12 }} />
                <Bar dataKey="rate" fill="#00d4ff" radius={[2, 2, 0, 0]} opacity={0.7} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="bg-[#13131f] border border-white/5 rounded-xl p-5">
          <h3 className="text-xs text-dim uppercase tracking-widest mb-4">Lot Comparison</h3>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <RadarChart data={data.lot_comparison.slice(0, 6)}>
                <PolarGrid stroke="rgba(255,255,255,0.06)" />
                <PolarAngleAxis dataKey="name" tick={{ fill: '#94a3b8', fontSize: 9 }} />
                <PolarRadiusAxis tick={{ fill: '#64748b', fontSize: 9 }} domain={[0, 100]} />
                <Radar name="Occupancy" dataKey="occupancy" stroke="#00d4ff" fill="#00d4ff" fillOpacity={0.1} strokeWidth={1.5} />
                <Radar name="Efficiency" dataKey="efficiency" stroke="#ffb347" fill="#ffb347" fillOpacity={0.1} strokeWidth={1.5} />
              </RadarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-[#13131f] border border-white/5 rounded-xl p-5">
          <h3 className="text-xs text-dim uppercase tracking-widest mb-4">System Performance</h3>
          <div className="h-48 flex items-center justify-center">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={data.system_performance.map((m) => ({ name: m.metric, value: m.value }))}
                  cx="50%" cy="50%" innerRadius={50} outerRadius={80}
                  dataKey="value"
                >
                  {data.system_performance.map((_, i) => (
                    <Cell key={i} fill={['#00d4ff', '#00c785', '#ffb347', '#64748b'][i % 4]} opacity={0.7} />
                  ))}
                </Pie>
                <Tooltip contentStyle={{ background: '#1a1a2e', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, fontSize: 12 }} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="bg-[#13131f] border border-white/5 rounded-xl p-5">
          <h3 className="text-xs text-dim uppercase tracking-widest mb-4">Performance Metrics</h3>
          <div className="space-y-3">
            {data.system_performance.map((m) => (
              <div key={m.metric} className="flex items-center justify-between py-2 border-b border-white/[0.02]">
                <span className="text-sm text-muted">{m.metric}</span>
                <div className="flex items-center gap-3">
                  <span className="text-sm font-mono text-white">{m.value}{m.unit}</span>
                  <span className={`text-[10px] px-2 py-0.5 rounded-full ${
                    m.status === 'healthy' ? 'bg-emerald-500/10 text-emerald-400' :
                    m.status === 'warning' ? 'bg-amber-500/10 text-amber-400' :
                    'bg-red-500/10 text-red-400'
                  }`}>{m.status}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
