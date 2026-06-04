import { useState, useEffect } from 'react'
import { fetchDashboard, type DashboardData, type Lot } from '../../api/adminClient'
import { useAuth } from '../../context/AuthContext'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  AreaChart, Area,
} from 'recharts'

function CountUp({ value, suffix = '' }: { value: number; suffix?: string }) {
  const [d, setD] = useState(0)
  const [k, setK] = useState(0)

  useEffect(() => { setK((x) => x + 1) }, [value])

  useEffect(() => {
    if (k === 0) return
    const t0 = performance.now()
    let id: number
    const draw = (t: number) => {
      const p = Math.min((t - t0) / 400, 1)
      setD(Math.round((1 - Math.pow(1 - p, 3)) * value))
      if (p < 1) id = requestAnimationFrame(draw)
    }
    id = requestAnimationFrame(draw)
    return () => cancelAnimationFrame(id)
  }, [k, value])

  return <>{d}{suffix}</>
}

function OccupancyBar({ pct }: { pct: number }) {
  const w = Math.max(4, Math.min(100, pct))
  const color = pct > 75 ? '#f59e0b' : pct > 40 ? '#00d4ff' : '#3a4a6a'
  return (
    <div className="h-1.5 rounded-full bg-[rgba(255,255,255,0.04)] w-full overflow-hidden">
      <div className="h-full rounded-full transition-all duration-700 ease-out"
        style={{ width: `${w}%`, background: color }} />
    </div>
  )
}

function LotCard({ lot }: { lot: Lot }) {
  const occ = lot.current_occupancy ?? 0
  const filled = Math.round(occ * lot.total_slots / 100)
  return (
    <div className="rounded-xl p-4 hover:bg-[rgba(255,255,255,0.02)] transition-colors cursor-default"
      style={{
        background: 'linear-gradient(135deg, #0e0e24 0%, #12122a 50%, #0e0e24 100%)',
        boxShadow: '0 1px 0 rgba(255,255,255,0.04), 0 0 0 1px rgba(255,255,255,0.04)',
      }}>
      <div className="flex items-start justify-between mb-2.5">
        <div>
          <p className="text-sm font-medium text-white/90 leading-tight">{lot.name}</p>
          <p className="text-[10px] text-[#475569] mt-0.5">{lot.city}</p>
        </div>
        <span className="text-xs font-mono font-semibold" style={{ color: occ > 75 ? '#f59e0b' : occ > 40 ? '#00d4ff' : '#5a6a8a' }}>
          {occ.toFixed(1)}%
        </span>
      </div>
      <OccupancyBar pct={occ} />
      <div className="flex items-center justify-between mt-2 text-[10px] text-[#475569]">
        <span>{filled}/{lot.total_slots}</span>
        <span>${lot.base_price.toFixed(2)}</span>
      </div>
    </div>
  )
}

export function DashboardPage() {
  const { user } = useAuth()
  const [data, setData] = useState<DashboardData | null>(null)
  const [ready, setReady] = useState(false)

  const load = async () => {
    try {
      const d = await fetchDashboard()
      setData(d)
      setReady(true)
    } catch { /* silent */ }
  }

  useEffect(() => {
    load()
    const t = setInterval(load, 15000)
    return () => clearInterval(t)
  }, [])

  if (!ready || !data) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-[#5a6a8a] animate-pulse text-sm">Loading dashboard...</div>
      </div>
    )
  }

  const occupiedNow = Math.round(data.total_slots * data.avg_occupancy / 100)
  const revPerTx = data.total_transactions > 0 ? data.total_revenue / data.total_transactions : 0
  const healthy = data.system_health?.status === 'healthy'

  const highOcc = (data.lots || []).filter((l) => (l.current_occupancy ?? 0) > 75).length
  const medOcc = (data.lots || []).filter((l) => {
    const o = l.current_occupancy ?? 0; return o > 40 && o <= 75
  }).length
  const lowOcc = (data.lots || []).filter((l) => (l.current_occupancy ?? 0) <= 40).length

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-white">Dashboard</h1>
          <p className="text-xs text-[#5a6a8a] mt-1">Platform overview</p>
        </div>
        <div className="flex items-center gap-3 text-[10px] text-[#5a6a8a]">
          <span className="flex items-center gap-1.5">
            <span className={`w-1.5 h-1.5 rounded-full ${healthy ? 'bg-[#00c785] animate-pulse' : 'bg-[#f59e0b]'}`} />
            {healthy ? 'Live' : 'Degraded'}
          </span>
          <span className="text-[#475569]">{user?.full_name || 'Admin'}</span>
          <span className="px-2 py-0.5 rounded bg-white/[0.04] text-[#475569]">{user?.role || 'user'}</span>
        </div>
      </div>

      <div className="rounded-xl p-6"
        style={{
          background: 'linear-gradient(135deg, #0e0e24 0%, #12122a 50%, #0e0e24 100%)',
          boxShadow: '0 1px 0 rgba(255,255,255,0.04), 0 0 0 1px rgba(255,255,255,0.04)',
        }}>
        <div className="flex items-baseline gap-3">
          <span className="text-[11px] font-medium uppercase tracking-wider text-[#475569]">Revenue</span>
          <span className="text-[10px] text-[#475569]">{data.total_transactions.toLocaleString()} transactions</span>
        </div>
        <p className="text-4xl font-bold tracking-tight text-white mt-2 font-mono">
          $<CountUp value={Math.round(data.total_revenue)} />
        </p>
        <div className="flex items-center gap-4 mt-2 text-[11px] text-[#475569]">
          <span>{data.total_lots} lots · {data.total_slots.toLocaleString()} slots</span>
          <span className="w-px h-3 bg-[rgba(255,255,255,0.06)]" />
          <span>{data.avg_occupancy.toFixed(1)}% avg occupancy</span>
          <span className="w-px h-3 bg-[rgba(255,255,255,0.06)]" />
          <span>${revPerTx.toFixed(2)} avg per tx</span>
        </div>
        <div className="h-0.5 w-12 rounded-full mt-4 opacity-60" style={{ background: '#00c785' }} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-5">
        <div className="rounded-xl p-4"
          style={{
            background: 'linear-gradient(135deg, #0e0e24 0%, #12122a 50%, #0e0e24 100%)',
            boxShadow: '0 1px 0 rgba(255,255,255,0.04), 0 0 0 1px rgba(255,255,255,0.04)',
          }}>
          <p className="text-2xl font-bold text-white font-mono"><CountUp value={data.avg_occupancy} suffix="%" /></p>
          <p className="text-[10px] text-[#475569] mt-1">Avg Occupancy</p>
          <p className="text-[10px] text-[#475569]">{occupiedNow.toLocaleString()} slots filled</p>
        </div>
        <div className="rounded-xl p-4"
          style={{
            background: 'linear-gradient(135deg, #0e0e24 0%, #12122a 50%, #0e0e24 100%)',
            boxShadow: '0 1px 0 rgba(255,255,255,0.04), 0 0 0 1px rgba(255,255,255,0.04)',
          }}>
          <p className="text-2xl font-bold text-white font-mono"><CountUp value={highOcc} /></p>
          <p className="text-[10px] text-[#475569] mt-1">Busy (&gt;75%)</p>
          <p className="text-[10px] text-[#475569]">high occupancy lots</p>
        </div>
        <div className="rounded-xl p-4"
          style={{
            background: 'linear-gradient(135deg, #0e0e24 0%, #12122a 50%, #0e0e24 100%)',
            boxShadow: '0 1px 0 rgba(255,255,255,0.04), 0 0 0 1px rgba(255,255,255,0.04)',
          }}>
          <p className="text-2xl font-bold text-white font-mono"><CountUp value={medOcc} /></p>
          <p className="text-[10px] text-[#475569] mt-1">Moderate</p>
          <p className="text-[10px] text-[#475569]">40–75% occupancy</p>
        </div>
        <div className="rounded-xl p-4"
          style={{
            background: 'linear-gradient(135deg, #0e0e24 0%, #12122a 50%, #0e0e24 100%)',
            boxShadow: '0 1px 0 rgba(255,255,255,0.04), 0 0 0 1px rgba(255,255,255,0.04)',
          }}>
          <p className="text-2xl font-bold text-white font-mono"><CountUp value={lowOcc} /></p>
          <p className="text-[10px] text-[#475569] mt-1">Quiet (&le;40%)</p>
          <p className="text-[10px] text-[#475569]">low occupancy lots</p>
        </div>
      </div>

      <div>
        <h3 className="text-sm font-medium text-white/80 mb-4">All Lots</h3>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3">
          {(data.lots || []).map((lot) => (
            <LotCard key={lot.lot_id} lot={lot} />
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="rounded-xl p-6"
          style={{
            background: 'linear-gradient(135deg, #0e0e24 0%, #12122a 50%, #0e0e24 100%)',
            boxShadow: '0 1px 0 rgba(255,255,255,0.04), 0 0 0 1px rgba(255,255,255,0.04)',
          }}>
          <div className="flex items-center justify-between mb-5">
            <h3 className="text-sm font-medium text-white/80">Occupancy</h3>
            <span className="text-[10px] text-[#475569] px-2 py-0.5 rounded bg-white/[0.03]">24h</span>
          </div>
          <div className="h-48">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data.occupancy_trend}>
                <XAxis dataKey="hour" tick={{ fill: '#3a4a6a', fontSize: 10 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: '#3a4a6a', fontSize: 10 }} axisLine={false} tickLine={false} domain={[0, 100]} />
                <Tooltip
                  contentStyle={{ background: '#16163a', border: '1px solid rgba(0,212,255,0.15)', borderRadius: 10, fontSize: 12, boxShadow: '0 8px 32px rgba(0,0,0,0.4)' }}
                  labelStyle={{ color: '#94a3b8' }}
                  cursor={{ fill: 'rgba(0,212,255,0.04)' }}
                  formatter={(v: number) => [`${v}%`, 'Occupancy']}
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
            <h3 className="text-sm font-medium text-white/80">Revenue</h3>
            <span className="text-[10px] text-[#475569] px-2 py-0.5 rounded bg-white/[0.03]">7 days</span>
          </div>
          <div className="h-48">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={data.revenue_7d}>
                <XAxis dataKey="date" tick={{ fill: '#3a4a6a', fontSize: 10 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: '#3a4a6a', fontSize: 10 }} axisLine={false} tickLine={false} />
                <Tooltip
                  contentStyle={{ background: '#16163a', border: '1px solid rgba(0,212,255,0.15)', borderRadius: 10, fontSize: 12, boxShadow: '0 8px 32px rgba(0,0,0,0.4)' }}
                  labelStyle={{ color: '#94a3b8' }}
                  formatter={(v: number) => [`$${v.toLocaleString()}`, 'Revenue']}
                />
                <Area type="monotone" dataKey="revenue" stroke="#00d4ff" fill="url(#rg)" strokeWidth={2.5} dot={false} />
                <defs>
                  <linearGradient id="rg" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#00d4ff" stopOpacity={0.2} />
                    <stop offset="100%" stopColor="#00d4ff" stopOpacity={0} />
                  </linearGradient>
                </defs>
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </div>
  )
}
