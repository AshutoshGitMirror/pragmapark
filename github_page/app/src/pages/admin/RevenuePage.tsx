import { useState, useEffect } from 'react'
import { fetchRevenue, type RevenueOverview } from '../../api/adminClient'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'

export function RevenuePage() {
  const [data, setData] = useState<RevenueOverview | null>(null)
  const [loading, setLoading] = useState(true)
  const [days, setDays] = useState(30)

  useEffect(() => {
    setLoading(true)
    fetchRevenue(days).then(setData).catch(() => {}).finally(() => setLoading(false))
  }, [days])

  if (loading) return <div className="flex items-center justify-center h-64"><div className="text-dim animate-pulse">Loading revenue data...</div></div>
  if (!data) return <div className="text-dim text-sm">No revenue data available</div>

  const stats = [
    { label: 'TOTAL REVENUE', value: `$${(data.total_revenue || 0).toLocaleString()}`, color: 'text-emerald-400' },
    { label: 'TOTAL TRANSACTIONS', value: (data.total_transactions || 0).toLocaleString(), color: 'text-cyan-400' },
    { label: 'PERIOD REVENUE', value: `$${(data.period_revenue || 0).toLocaleString()}`, color: 'text-amber-400' },
    { label: 'PERIOD TXNS', value: (data.period_transactions || 0).toLocaleString(), color: 'text-muted' },
  ]

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-light text-white">Revenue</h1>
        <select
          value={days}
          onChange={(e) => setDays(+e.target.value)}
          className="bg-[#0a0a0f] border border-white/10 rounded-lg px-3 py-1.5 text-xs text-muted focus:outline-none focus:border-cyan-500/50"
        >
          <option value={7}>7 days</option>
          <option value={30}>30 days</option>
          <option value={90}>90 days</option>
        </select>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {stats.map((s) => (
          <div key={s.label} className="bg-[#13131f] border border-white/5 rounded-xl p-4">
            <p className="text-[10px] text-dim uppercase tracking-widest mb-1">{s.label}</p>
            <p className={`text-lg font-mono ${s.color}`}>{s.value}</p>
          </div>
        ))}
      </div>

      <div className="bg-[#13131f] border border-white/5 rounded-xl p-5">
        <h3 className="text-xs text-dim uppercase tracking-widest mb-4">Daily Revenue</h3>
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data.daily_revenue}>
              <XAxis dataKey="date" tick={{ fill: '#64748b', fontSize: 10 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: '#64748b', fontSize: 10 }} axisLine={false} tickLine={false} />
              <Tooltip contentStyle={{ background: '#1a1a2e', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, fontSize: 12 }} />
              <Bar dataKey="revenue" fill="#00c785" radius={[2, 2, 0, 0]} opacity={0.7} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="bg-[#13131f] border border-white/5 rounded-xl overflow-hidden">
        <div className="p-4 border-b border-white/5">
          <h3 className="text-xs text-dim uppercase tracking-widest">Revenue by Lot</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-[10px] text-dim uppercase tracking-wider border-b border-white/5">
                <th className="text-left p-3 font-medium">Lot</th>
                <th className="text-right p-3 font-medium">Revenue</th>
                <th className="text-right p-3 font-medium">Transactions</th>
              </tr>
            </thead>
            <tbody>
              {data.revenue_by_lot?.map((lot) => (
                <tr key={lot.lot_id} className="border-b border-white/[0.02] hover:bg-white/[0.02] transition-colors">
                  <td className="p-3 font-medium text-white/90">{lot.name}</td>
                  <td className="p-3 text-right font-mono text-xs text-emerald-400">${lot.revenue.toLocaleString()}</td>
                  <td className="p-3 text-right font-mono text-xs text-muted">{lot.transactions.toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
