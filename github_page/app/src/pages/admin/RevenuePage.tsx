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
        <div className="text-[#64748b] animate-pulse text-sm">Loading revenue...</div>
      </div>
    )
  }

  if (!data) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-[#64748b] text-sm">No revenue data.</div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-white">Revenue</h1>
        <select
          value={days}
          onChange={(e) => setDays(Number(e.target.value))}
          className="bg-[#0a0a0f] border border-[rgba(255,255,255,0.08)] rounded-lg px-3 py-1.5 text-xs text-[#64748b] focus:outline-none focus:border-[rgba(0,212,255,0.4)]"
        >
          <option value={7}>7 days</option>
          <option value={30}>30 days</option>
          <option value={90}>90 days</option>
        </select>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-[#0e0e1a] border border-[rgba(255,255,255,0.06)] rounded-xl p-4">
          <p className="text-[11px] text-[#475569] mb-1">Total Revenue</p>
          <p className="text-lg font-semibold text-[#00c785]">${(data.total_revenue || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</p>
        </div>
        <div className="bg-[#0e0e1a] border border-[rgba(255,255,255,0.06)] rounded-xl p-4">
          <p className="text-[11px] text-[#475569] mb-1">Total Transactions</p>
          <p className="text-lg font-semibold text-white">{(data.total_transactions || 0).toLocaleString()}</p>
        </div>
        <div className="bg-[#0e0e1a] border border-[rgba(255,255,255,0.06)] rounded-xl p-4">
          <p className="text-[11px] text-[#475569] mb-1">Period Revenue</p>
          <p className="text-lg font-semibold text-white">${(data.period_revenue || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</p>
        </div>
        <div className="bg-[#0e0e1a] border border-[rgba(255,255,255,0.06)] rounded-xl p-4">
          <p className="text-[11px] text-[#475569] mb-1">Period Txns</p>
          <p className="text-lg font-semibold text-white">{(data.period_transactions || 0).toLocaleString()}</p>
        </div>
      </div>

      <div className="bg-[#0e0e1a] border border-[rgba(255,255,255,0.06)] rounded-xl p-5">
        <h3 className="text-xs text-[#64748b] mb-4">Daily Revenue</h3>
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data.daily_revenue}>
              <XAxis dataKey="date" tick={{ fill: '#475569', fontSize: 10 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: '#475569', fontSize: 10 }} axisLine={false} tickLine={false} />
              <Tooltip
                contentStyle={{ background: '#12121e', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 8, fontSize: 12 }}
                labelStyle={{ color: '#94a3b8' }}
              />
              <Bar dataKey="revenue" fill="#00d4ff" radius={[2, 2, 0, 0]} opacity={0.7} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="bg-[#0e0e1a] border border-[rgba(255,255,255,0.06)] rounded-xl overflow-hidden">
        <div className="p-4 border-b border-[rgba(255,255,255,0.06)]">
          <h3 className="text-xs text-[#64748b]">Revenue by Lot</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-[11px] text-[#475569] border-b border-[rgba(255,255,255,0.04)]">
                <th className="text-left font-medium px-4 py-2.5">Lot</th>
                <th className="text-right font-medium px-4 py-2.5">Revenue</th>
                <th className="text-right font-medium px-4 py-2.5">Transactions</th>
              </tr>
            </thead>
            <tbody>
              {(data.revenue_by_lot || []).map((lot: any) => (
                <tr key={lot.lot_id} className="border-b border-[rgba(255,255,255,0.02)] hover:bg-white/[0.015] transition-colors">
                  <td className="px-4 py-3 font-medium text-white/90 text-xs">{lot.name}</td>
                  <td className="px-4 py-3 text-right font-mono text-xs text-[#00c785]">${lot.revenue.toFixed(2)}</td>
                  <td className="px-4 py-3 text-right font-mono text-xs text-[#64748b]">{lot.transactions}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
