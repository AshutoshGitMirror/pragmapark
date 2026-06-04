import { useState, useEffect } from 'react'
import { fetchAnalytics, type AnalyticsData } from '../../api/adminClient'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
} from 'recharts'

export function AnalyticsPage() {
  const [data, setData] = useState<AnalyticsData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let mounted = true
    const load = async () => {
      try {
        const d = await fetchAnalytics()
        if (mounted) setData(d)
      } catch (err: any) {
        if (mounted) setError(err.message)
      } finally {
        if (mounted) setLoading(false)
      }
    }
    load()
    return () => { mounted = false }
  }, [])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-[#5a6a8a] animate-pulse text-sm">Loading analytics...</div>
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

  const metrics = data.system_performance || []
  const getMetric = (name: string) => metrics.find((m) => m.metric === name)?.value

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-xl font-semibold text-white">Analytics</h1>
        <p className="text-xs text-[#5a6a8a] mt-1">Performance metrics and insights</p>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-5">
        {[
          { label: 'Avg Occupancy', value: getMetric('avg_occupancy'), suffix: '%', accent: '#00e5ff' },
          { label: 'Total Sessions', value: getMetric('total_sessions'), suffix: '', accent: '#00c785' },
          { label: 'Avg Duration', value: getMetric('avg_duration_minutes'), suffix: 'm', accent: '#f59e0b' },
          { label: 'Prediction Accuracy', value: getMetric('prediction_accuracy'), suffix: '%', accent: '#00e5ff' },
        ].map((m) => (
          <div key={m.label}
            className="rounded-xl p-5 transition-all duration-200 hover:scale-[1.02]"
            style={{
              background: 'linear-gradient(135deg, #0e0e24 0%, #12122a 50%, #0e0e24 100%)',
              boxShadow: '0 1px 0 rgba(255,255,255,0.04), 0 0 0 1px rgba(255,255,255,0.04)',
            }}>
            <p className="text-[11px] font-medium uppercase tracking-wider text-[#475569] mb-2">{m.label}</p>
            <p className="text-[28px] font-bold tracking-tight text-white leading-none">
              {m.value !== undefined ? `${m.value.toFixed(1)}${m.suffix}` : '—'}
            </p>
            <div className="mt-3 h-0.5 w-8 rounded-full opacity-60" style={{ background: m.accent }} />
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
            <h3 className="text-sm font-medium text-white/80">Occupancy by Hour</h3>
          </div>
          <div className="h-52">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data.hourly_occupancy}>
                <XAxis dataKey="hour" tick={{ fill: '#3a4a6a', fontSize: 10 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: '#3a4a6a', fontSize: 10 }} axisLine={false} tickLine={false} />
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
            <h3 className="text-sm font-medium text-white/80">Lot Comparison</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-[11px] text-[#3a4a6a] border-b border-[rgba(255,255,255,0.03)] bg-white/[0.02]">
                  <th className="text-left font-semibold px-4 py-3">Lot</th>
                  <th className="text-right font-semibold px-4 py-3">Occupancy</th>
                  <th className="text-right font-semibold px-4 py-3">Revenue</th>
                  <th className="text-right font-semibold px-4 py-3">Efficiency</th>
                </tr>
              </thead>
              <tbody>
                {(data.lot_comparison || []).map((lot) => (
                  <tr key={lot.lot_id} className="border-b border-[rgba(255,255,255,0.02)] hover:bg-[rgba(0,212,255,0.02)] transition-colors">
                    <td className="px-4 py-3 font-medium text-white/90 text-xs">{lot.name}</td>
                    <td className="px-4 py-3 text-right font-mono text-xs text-[#f59e0b]">{(lot.occupancy * 100).toFixed(1)}%</td>
                    <td className="px-4 py-3 text-right font-mono text-xs text-[#00c785]">${lot.revenue.toLocaleString()}</td>
                    <td className="px-4 py-3 text-right font-mono text-xs" style={{ color: lot.efficiency > 0.7 ? '#00c785' : '#f59e0b' }}>
                      {(lot.efficiency * 100).toFixed(1)}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <div className="rounded-xl p-6"
        style={{
          background: 'linear-gradient(135deg, #0e0e24 0%, #12122a 50%, #0e0e24 100%)',
          boxShadow: '0 1px 0 rgba(255,255,255,0.04), 0 0 0 1px rgba(255,255,255,0.04)',
        }}>
        <div className="flex items-center justify-between mb-5">
          <h3 className="text-sm font-medium text-white/80">System Performance</h3>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {metrics.map((m) => {
            const colors: Record<string, string> = {
              healthy: '#00c785',
              warning: '#f59e0b',
              critical: '#ff4757',
            }
            return (
              <div key={m.metric} className="p-4 rounded-lg bg-white/[0.02]">
                <p className="text-[10px] text-[#475569] font-medium uppercase tracking-wider mb-1.5 break-all">{m.metric.replace(/_/g, ' ')}</p>
                <p className="text-lg font-bold text-white">{m.value}{m.unit}</p>
                <span className="text-[10px] mt-1.5 inline-block px-1.5 py-0.5 rounded" style={{
                  backgroundColor: `${colors[m.status] || '#5a6a8a'}20`,
                  color: colors[m.status] || '#5a6a8a',
                }}>{m.status}</span>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
