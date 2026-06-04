import { useState, useEffect } from 'react'
import { fetchRevenue, type RevenueOverview } from '../../api/adminClient'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
} from 'recharts'

export function RevenuePage() {
  const [data, setData] = useState<RevenueOverview | null>(null)
  const [loading, setLoading] = useState(true)
  const [days, setDays] = useState(30)

  useEffect(() => {
    let mounted = true
    const load = async () => {
      try {
        const d = await fetchRevenue(days)
        if (mounted) setData(d)
      } catch { /* empty */ } finally {
        if (mounted) setLoading(false)
      }
    }
    load()
    return () => { mounted = false }
  }, [days])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-[#5a6a8a] animate-pulse text-sm">Loading revenue...</div>
      </div>
    )
  }

  if (!data) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-[#5a6a8a] text-sm">No revenue data.</div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-white">Revenue</h1>
          <p className="text-xs text-[#5a6a8a] mt-1">Financial overview and transaction history</p>
        </div>
        <select
          value={days}
          onChange={(e) => setDays(Number(e.target.value))}
          className="bg-[#0e0e24] border border-[rgba(255,255,255,0.08)] rounded-lg px-3 py-1.5 text-xs text-[#5a6a8a] focus:outline-none focus:border-[rgba(0,212,255,0.3)]"
        >
          <option value={7}>7 days</option>
          <option value={30}>30 days</option>
          <option value={90}>90 days</option>
        </select>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-5">
        {[
          { label: 'Total Revenue', value: `$${(data.total_revenue || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`, accent: '#00c785' },
          { label: 'Total Transactions', value: (data.total_transactions || 0).toLocaleString(), accent: '#00e5ff' },
          { label: 'Period Revenue', value: `$${(data.period_revenue || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`, accent: '#f59e0b' },
          { label: 'Period Txns', value: (data.period_transactions || 0).toLocaleString(), accent: '#00c785' },
        ].map((s) => (
          <div key={s.label}
            className="rounded-xl p-5 transition-all duration-200 hover:scale-[1.02]"
            style={{
              background: 'linear-gradient(135deg, #0e0e24 0%, #12122a 50%, #0e0e24 100%)',
              boxShadow: '0 1px 0 rgba(255,255,255,0.04), 0 0 0 1px rgba(255,255,255,0.04)',
            }}>
            <p className="text-[11px] font-medium uppercase tracking-wider text-[#475569] mb-2">{s.label}</p>
            <p className="text-[28px] font-bold tracking-tight text-white leading-none">{s.value}</p>
            <div className="mt-3 h-0.5 w-8 rounded-full opacity-60" style={{ background: s.accent }} />
          </div>
        ))}
      </div>

      <div className="rounded-xl p-6"
        style={{
          background: 'linear-gradient(135deg, #0e0e24 0%, #12122a 50%, #0e0e24 100%)',
          boxShadow: '0 1px 0 rgba(255,255,255,0.04), 0 0 0 1px rgba(255,255,255,0.04)',
        }}>
        <div className="flex items-center justify-between mb-5">
          <h3 className="text-sm font-medium text-white/80">Daily Revenue</h3>
        </div>
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data.daily_revenue}>
              <XAxis dataKey="date" tick={{ fill: '#3a4a6a', fontSize: 10 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: '#3a4a6a', fontSize: 10 }} axisLine={false} tickLine={false} />
              <Tooltip
                contentStyle={{ background: '#16163a', border: '1px solid rgba(0,212,255,0.15)', borderRadius: 10, fontSize: 12, boxShadow: '0 8px 32px rgba(0,0,0,0.4)' }}
                labelStyle={{ color: '#94a3b8' }}
                cursor={{ fill: 'rgba(0,212,255,0.04)' }}
              />
              <Bar dataKey="revenue" fill="#00d4ff" radius={[3, 3, 0, 0]} opacity={0.8} maxBarSize={32} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="rounded-xl overflow-hidden"
        style={{
          background: 'linear-gradient(135deg, #0e0e24 0%, #12122a 50%, #0e0e24 100%)',
          boxShadow: '0 1px 0 rgba(255,255,255,0.04), 0 0 0 1px rgba(255,255,255,0.04)',
        }}>
        <div className="px-6 py-4 border-b border-[rgba(255,255,255,0.04)]">
          <h3 className="text-sm font-medium text-white/80">Revenue by Lot</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-[11px] text-[#3a4a6a] border-b border-[rgba(255,255,255,0.03)] bg-white/[0.02]">
                <th className="text-left font-semibold px-5 py-3">Lot</th>
                <th className="text-right font-semibold px-5 py-3">Revenue</th>
                <th className="text-right font-semibold px-5 py-3">Transactions</th>
              </tr>
            </thead>
            <tbody>
              {(data.revenue_by_lot || []).map((lot: any) => (
                <tr key={lot.lot_id} className="border-b border-[rgba(255,255,255,0.02)] hover:bg-[rgba(0,212,255,0.02)] transition-colors">
                  <td className="px-5 py-3.5 font-medium text-white/90 text-xs">{lot.name}</td>
                  <td className="px-5 py-3.5 text-right font-mono text-xs text-[#00c785]">${lot.revenue.toFixed(2)}</td>
                  <td className="px-5 py-3.5 text-right font-mono text-xs text-[#5a6a8a]">{lot.transactions}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
