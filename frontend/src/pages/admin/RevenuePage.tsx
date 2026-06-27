import { useState, useEffect } from 'react'
import { fetchRevenue, type RevenueOverview } from '../../api/adminClient'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
} from 'recharts'

const GOLD = '#f0c040'
const GOLD_DIM = 'rgba(240,192,64,0.12)'
const GOLD_GLOW = 'rgba(240,192,64,0.3)'

function CountUp({ value, prefix = '', suffix = '' }: { value: number; prefix?: string; suffix?: string }) {
  const [d, setD] = useState(0)
  const [k, setK] = useState(0)
  useEffect(() => { setK((x) => x + 1) }, [value])
  useEffect(() => {
    if (k === 0) return
    const t0 = performance.now()
    let id: number
    const draw = (t: number) => {
      const p = Math.min((t - t0) / 500, 1)
      setD(Math.round((1 - Math.pow(1 - p, 3)) * value))
      if (p < 1) id = requestAnimationFrame(draw)
    }
    id = requestAnimationFrame(draw)
    return () => cancelAnimationFrame(id)
  }, [k, value])
  return <>{prefix}{d}{suffix}</>
}

/* ── Smart Contract Split Display ── */
function ContractSplit({ total }: { total: number }) {
  const platformShare = total * 0.6
  const ownerShare = total * 0.4
  return (
    <div className="card-dark rounded-xl p-5"
      >
      <div className="flex items-center gap-2 mb-4">
        <span className="text-[9px] font-mono px-2 py-0.5 rounded" style={{ background: GOLD_DIM, color: GOLD }}>Smart Contract</span>
      </div>
      <div className="space-y-3">
        <div>
          <div className="flex justify-between text-[10px] font-mono text-muted-alt mb-1">
            <span>Platform Share (60%)</span>
            <span style={{ color: GOLD }}>${platformShare.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
          </div>
          <div className="h-2 rounded-full bg-[rgba(255,255,255,0.04)] overflow-hidden">
            <div className="h-full rounded-full transition-all duration-700"
              style={{ width: '60%', background: `linear-gradient(90deg, ${GOLD}, #f0a030)`, boxShadow: `0 0 6px ${GOLD_GLOW}` }} />
          </div>
        </div>
        <div>
          <div className="flex justify-between text-[10px] font-mono text-muted-alt mb-1">
            <span>Lot Owner Share (40%)</span>
            <span style={{ color: '#60d4a0' }}>${ownerShare.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
          </div>
          <div className="h-2 rounded-full bg-[rgba(255,255,255,0.04)] overflow-hidden">
            <div className="h-full rounded-full transition-all duration-700"
              style={{ width: '40%', background: 'linear-gradient(90deg, #60d4a0, #40b080)', boxShadow: '0 0 6px rgba(96,212,160,0.3)' }} />
          </div>
        </div>
      </div>
      <p className="text-[9px] font-mono text-subtle mt-3 italic">
        RevenueShareContract executes on every payment. Distribution recorded in ledger.
      </p>
    </div>
  )
}

export function RevenuePage() {
  const [data, setData] = useState<RevenueOverview | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [days, setDays] = useState(30)
  const [retryKey, setRetryKey] = useState(0)

  useEffect(() => {
    let mounted = true
    setLoading(true)
    setError(null)
    const load = async () => {
      try {
        const d = await fetchRevenue(days)
        if (mounted) setData(d)
      } catch (err) {
        if (mounted) setError(err instanceof Error ? err.message : 'Failed to load revenue data')
      } finally {
        if (mounted) setLoading(false)
      }
    }
    load()
    return () => { mounted = false }
  }, [days, retryKey])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-subtle animate-pulse text-sm">Loading revenue...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-64 flex-col gap-3">
        <div className="text-amber text-sm font-mono">{error}</div>
        <button onClick={() => setRetryKey((k) => k + 1)}
          className="text-[12px] font-mono px-3 py-2 rounded-lg transition-all"
          style={{
            background: 'rgba(245,158,11,0.08)',
            color: '#f59e0b',
            border: '1px solid rgba(245,158,11,0.2)',
          }}>
          Retry
        </button>
      </div>
    )
  }

  if (!data) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-subtle text-sm">No revenue data.</div>
      </div>
    )
  }

  const avgPerTx = data.total_transactions > 0 ? data.total_revenue / data.total_transactions : 0

  return (
    <div className="space-y-8">
      {/* ── Header ── */}
      <div className="flex items-start justify-between">
        <div>
          <p className="text-[10px] font-mono text-muted-alt tracking-[3px] uppercase mb-2">03 / RL · Price</p>
          <h1 className="section-headline">Revenue</h1>
          <p className="section-body mt-1">Financial overview and smart contract distribution</p>
        </div>
        <select
          value={days}
          onChange={(e) => setDays(Number(e.target.value))}
          className="bg-[#0e0e24] border border-[rgba(255,255,255,0.06)] rounded-lg px-3 py-1.5 text-[10px] font-mono text-subtle focus:outline-none"
          style={{ borderColor: days ? 'rgba(240,192,64,0.15)' : 'rgba(255,255,255,0.06)' }}
        >
          <option value={7}>7 days</option>
          <option value={30}>30 days</option>
          <option value={90}>90 days</option>
        </select>
      </div>

      {/* ── Stats grid ── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-5">
        {[
          { label: 'Total Revenue', value: Math.round(data.total_revenue || 0), prefix: '$', accent: GOLD },
          { label: 'Total Transactions', value: data.total_transactions || 0, suffix: '', accent: '#40d4f0' },
          { label: 'Period Revenue', value: Math.round(data.period_revenue || 0), prefix: '$', accent: GOLD },
          { label: 'Period Txns', value: data.period_transactions || 0, suffix: '', accent: '#60d4a0' },
        ].map((s) => (
          <div key={s.label}
            className="rounded-xl p-5 relative overflow-hidden group hover:scale-[1.01] transition-transform duration-200"
            >
            <div className="absolute top-0 left-0 w-full h-px opacity-0 group-hover:opacity-100 transition-opacity"
              style={{ background: `linear-gradient(to right, transparent, ${s.accent}, transparent)` }} />
            <p className="section-label mb-2">{s.label}</p>
            <p className="display-number" style={{ color: s.accent }}>
              {s.prefix}<CountUp value={s.value} />
            </p>
            <div className="mt-3 h-0.5 w-8 rounded-full opacity-40" style={{ background: s.accent }} />
          </div>
        ))}
      </div>

      {/* ── Narrative + Contract Split row ── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Narrative */}
        <div className="rounded-xl p-5"
          style={{
            background: `linear-gradient(135deg, ${GOLD_DIM} 0%, rgba(10,10,24,0.6) 100%)`,
            border: `1px solid ${GOLD_DIM}`,
          }}>
          <span className="text-[9px] font-mono tracking-wider uppercase" style={{ color: GOLD }}>Revenue Flow</span>
          <div className="mt-3 space-y-2.5">
            {[
              { label: 'RL Agent', val: 'NumPy DQN optimizing rates' },
              { label: 'Contract', val: '60/40 RevenueShare split' },
              { label: 'Avg/Tx', val: `$${avgPerTx.toFixed(2)} per session` },
              { label: 'Settlement', val: 'SHA-256 sealed in ledger' },
            ].map((r) => (
              <div key={r.label} className="flex items-center gap-2 text-[10px] font-mono">
                <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: GOLD }} />
                <span className="text-subtle">{r.label}:</span>
                <span className="text-white/70">{r.val}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Smart Contract Split */}
        <div className="lg:col-span-2">
          <ContractSplit total={data.total_revenue} />
        </div>
      </div>

      {/* ── Daily Revenue Chart ── */}
      <div className="rounded-xl p-6"
        >
        <div className="flex items-center justify-between mb-5">
          <h3 className="text-sm font-medium text-white/80">Daily Revenue</h3>
          <span className="text-[9px] font-mono px-2 py-0.5 rounded" style={{ background: GOLD_DIM, color: GOLD }}>RL Price Stage</span>
        </div>
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data.daily_revenue}>
              <XAxis dataKey="date" tick={{ fill: '#6a7a9a', fontSize: 10 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: '#6a7a9a', fontSize: 10 }} axisLine={false} tickLine={false} />
              <Tooltip
                contentStyle={{ background: '#16163a', border: `1px solid ${GOLD}25`, borderRadius: 10, fontSize: 12, boxShadow: '0 8px 32px rgba(0,0,0,0.4)' }}
                labelStyle={{ color: '#94a3b8' }}
                cursor={{ fill: `${GOLD}08` }}
                formatter={(v: number) => [`$${v.toLocaleString()}`, 'Revenue']}
              />
              <Bar dataKey="revenue" fill={GOLD} radius={[3, 3, 0, 0]} opacity={0.8} maxBarSize={32} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* ── Revenue by Lot Table ── */}
      <div className="rounded-xl overflow-hidden"
        >
        <div className="px-6 py-4 border-b border-[rgba(255,255,255,0.04)] flex items-center justify-between">
          <h3 className="text-sm font-medium text-white/80">Revenue by Lot</h3>
          <span className="text-[9px] font-mono" style={{ color: GOLD }}>{data.revenue_by_lot?.length || 0} lots</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-[11px] text-subtle border-b border-[rgba(255,255,255,0.03)]" style={{ background: `${GOLD}06` }}>
                <th className="text-left font-semibold px-5 py-3 font-mono">Lot</th>
                <th className="text-right font-semibold px-5 py-3 font-mono">Revenue</th>
                <th className="text-right font-semibold px-5 py-3 font-mono">Transactions</th>
              </tr>
            </thead>
            <tbody>
              {(data.revenue_by_lot || []).length === 0 ? (
                <tr>
                  <td colSpan={3} className="px-5 py-8 text-center text-xs text-dim font-mono">
                    No revenue data available yet
                  </td>
                </tr>
              ) : (
                (data.revenue_by_lot || []).map((lot) => (
                  <tr key={lot.lot_id} className="border-b border-[rgba(255,255,255,0.02)] hover:bg-[rgba(240,192,64,0.02)] transition-colors">
                    <td className="px-5 py-3.5 font-medium text-white/90 text-xs">{lot.name}</td>
                    <td className="px-5 py-3.5 text-right font-mono text-xs" style={{ color: GOLD }}>${lot.revenue.toFixed(2)}</td>
                    <td className="px-5 py-3.5 text-right font-mono text-xs text-subtle">{lot.transactions}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
