import { useState, useEffect, useCallback } from 'react'
import { fetchDashboard, type DashboardData, type Lot } from '../../api/adminClient'
import { useAuth } from '../../context/AuthContext'
import { CircularNexus } from '../../components/CircularNexus'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  AreaChart, Area,
} from 'recharts'

/* ── Helper: CountUp with Fraunces display styling ── */
function CountUp({ value, suffix = '', className = '' }: { value: number; suffix?: string; className?: string }) {
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

  return <span className={className}>{d}{suffix}</span>
}

/* ── Occupancy bar ── */
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

/* ── Lot card ── */
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

/* ── Narrative event type ── */
interface NarrativeEvent {
  id: number
  timestamp: number
  layer: number
  label: string
  detail: string
  severity: 'info' | 'warn' | 'success' | 'error'
}

const LAYER_COLORS = ['#00ff66', '#00f0ff', '#ffaa00', '#f43f5e', '#a855f7', '#94a3b8']
const LAYER_NAMES = ['IoT', 'ML', 'Blockchain', 'RL', 'Digital Twin', 'Actuator']

/* ── Narrative Feed ── */
function NarrativeFeed({ events }: { events: NarrativeEvent[] }) {
  const [isPaused, setIsPaused] = useState(false)
  const [scrollIdx, setScrollIdx] = useState(0)

  useEffect(() => {
    if (isPaused) return
    const t = setInterval(() => {
      setScrollIdx((prev) => {
        const next = prev + 1
        return next >= events.length ? Math.max(0, events.length - 12) : next
      })
    }, 3000)
    return () => clearInterval(t)
  }, [isPaused, events.length])

  const visible = events.slice(scrollIdx, scrollIdx + 12)

  if (events.length === 0) {
    return (
      <div className="text-[10px] font-mono text-[#4e5f73] py-8 text-center">
        No events yet — system will populate as data flows.
      </div>
    )
  }

  return (
    <div className="relative">
      {/* Pause toggle */}
      <button
        onClick={() => setIsPaused((p) => !p)}
        className="absolute top-0 right-0 text-[9px] font-mono px-2 py-0.5 rounded border transition-colors"
        style={{
          borderColor: isPaused ? '#00ff6640' : 'rgba(255,255,255,0.06)',
          color: isPaused ? '#00ff66' : '#475569',
          background: isPaused ? 'rgba(0,255,102,0.06)' : 'transparent',
        }}
      >
        {isPaused ? 'LIVE ▸' : 'PAUSE ▍▍'}
      </button>

      <div className="space-y-0.5 mt-5">
        {visible.map((ev) => {
          const ago = Math.floor((Date.now() - ev.timestamp) / 1000)
          const timeStr = ago < 60 ? `${ago}s` : ago < 3600 ? `${Math.floor(ago / 60)}m` : `${Math.floor(ago / 3600)}h`
          return (
            <div
              key={ev.id}
              className="group flex items-start gap-3 py-1.5 px-2 rounded hover:bg-white/[0.02] transition-colors"
            >
              {/* Layer dot */}
              <span
                className="w-1.5 h-1.5 rounded-full mt-1 shrink-0"
                style={{ backgroundColor: LAYER_COLORS[ev.layer % LAYER_COLORS.length] }}
              />
              {/* Severity indicator */}
              <span className="text-[11px] font-mono shrink-0 w-6"
                style={{
                  color: ev.severity === 'error' ? '#f04060'
                    : ev.severity === 'warn' ? '#f0c040'
                    : ev.severity === 'success' ? '#00c785'
                    : '#5a6a8a',
                }}
              >
                {ev.severity === 'error' ? '✕' : ev.severity === 'warn' ? '△' : ev.severity === 'success' ? '✓' : '○'}
              </span>
              {/* Event text */}
              <div className="flex-1 min-w-0">
                <span className="text-[11px] font-mono text-white/70 group-hover:text-white transition-colors">
                  <span className="text-[#475569]">[{ev.label}]</span> {ev.detail}
                </span>
              </div>
              {/* Timestamp */}
              <span className="text-[9px] font-mono text-[#3a4a6a] shrink-0">{timeStr}</span>
            </div>
          )
        })}
      </div>

      {/* Scroll indicator */}
      {scrollIdx + 12 < events.length && (
        <div className="text-center mt-2">
          <span className="text-[9px] font-mono text-[#3a4a6a] animate-pulse">
            {events.length - scrollIdx - 12} more events ↓
          </span>
        </div>
      )}
    </div>
  )
}

/* ── Build narrative events from dashboard data ── */
function buildNarrativeEvents(data: DashboardData): NarrativeEvent[] {
  const events: NarrativeEvent[] = []
  const now = Date.now()
  let id = 1

  // System health event
  events.push({
    id: id++,
    timestamp: now - 3000,
    layer: 0,
    label: 'SYS',
    detail: `System health: ${data.system_health?.status ?? 'unknown'} · ${data.system_health?.uptime ?? '?'} uptime`,
    severity: data.system_health?.status === 'healthy' ? 'success' : 'warn',
  })

  // Occupancy events
  const highOcc = (data.lots || []).filter((l) => (l.current_occupancy ?? 0) > 75)
  const medOcc = (data.lots || []).filter((l) => {
    const o = l.current_occupancy ?? 0; return o > 40 && o <= 75
  })
  const lowOcc = (data.lots || []).filter((l) => (l.current_occupancy ?? 0) <= 40)

  if (highOcc.length > 0) {
    events.push({
      id: id++,
      timestamp: now - 5000,
      layer: 0,
      label: 'IOT',
      detail: `${highOcc.length} lot${highOcc.length > 1 ? 's' : ''} at critical occupancy (>75%) — ${highOcc.map(l => l.name).join(', ')}`,
      severity: 'warn',
    })
  }
  if (medOcc.length > 0) {
    events.push({
      id: id++,
      timestamp: now - 7000,
      layer: 1,
      label: 'ML',
      detail: `Occupancy forecast: ${medOcc.length} lot${medOcc.length > 1 ? 's' : ''} trending moderate, ${highOcc.length} high`,
      severity: 'info',
    })
  }
  if (lowOcc.length > 0) {
    events.push({
      id: id++,
      timestamp: now - 9000,
      layer: 2,
      label: 'RL',
      detail: `Low-demand pricing adjustment triggered for ${lowOcc.length} underutilized lot${lowOcc.length > 1 ? 's' : ''}`,
      severity: 'info',
    })
  }

  // Revenue event
  if (data.total_revenue > 0) {
    events.push({
      id: id++,
      timestamp: now - 12000,
      layer: 2,
      label: 'BC',
      detail: `Revenue contract executed · $${data.total_revenue.toLocaleString()} across ${data.total_transactions} txns`,
      severity: 'success',
    })
    if (data.total_transactions > 0) {
      const avg = data.total_revenue / data.total_transactions
      events.push({
        id: id++,
        timestamp: now - 15000,
        layer: 3,
        label: 'RL',
        detail: `Avg revenue per transaction: $${avg.toFixed(2)} · RL agent optimizing tariff rates`,
        severity: 'info',
      })
    }
  }

  // Alert events
  ;(data.alerts || []).slice(0, 5).forEach((a) => {
    events.push({
      id: id++,
      timestamp: now - 20000 + id * 100,
      layer: a.type === 'sensor' ? 0 : a.type === 'blockchain' ? 2 : a.type === 'pricing' ? 3 : 5,
      label: (a.type || 'SYS').slice(0, 3).toUpperCase(),
      detail: a.message,
      severity: a.severity === 'critical' ? 'error' : a.severity === 'warning' ? 'warn' : 'info',
    })
  })

  // Slot events
  const totalSlots = data.total_slots ?? 0
  const occupiedNow = Math.round(totalSlots * data.avg_occupancy / 100)
  events.push({
    id: id++,
    timestamp: now - 25000,
    layer: 4,
    label: 'DT',
    detail: `Digital twin state: ${occupiedNow}/${totalSlots} slots occupied · ${data.avg_occupancy.toFixed(1)}% utilization`,
    severity: 'info',
  })

  // Sort by timestamp descending
  events.sort((a, b) => b.timestamp - a.timestamp)
  return events
}

/* ── Stat card with Fraunces display number ── */
function StatCard({
  value,
  suffix = '',
  label,
  sublabel,
  color = '#00d4ff',
}: {
  value: number
  suffix?: string
  label: string
  sublabel: string
  color?: string
}) {
  return (
    <div className="rounded-xl p-4 relative overflow-hidden group hover:scale-[1.01] transition-transform duration-200"
      style={{
        background: 'linear-gradient(135deg, #0e0e24 0%, #12122a 50%, #0e0e24 100%)',
        boxShadow: '0 1px 0 rgba(255,255,255,0.04), 0 0 0 1px rgba(255,255,255,0.04)',
      }}>
      {/* Accent bar */}
      <div
        className="absolute top-0 left-0 w-full h-px opacity-0 group-hover:opacity-100 transition-opacity"
        style={{ background: `linear-gradient(to right, transparent, ${color}, transparent)` }}
      />
      <div className="flex items-center justify-between">
        <p className="display-number" style={{ color }}>
          <CountUp value={value} suffix={suffix} />
        </p>
      </div>
      <p className="section-label mt-1">{label}</p>
      <p className="text-[10px] text-[#475569]">{sublabel}</p>
    </div>
  )
}

/* ── Main Dashboard ── */
export function DashboardPage() {
  const { user } = useAuth()
  const [data, setData] = useState<DashboardData | null>(null)
  const [ready, setReady] = useState(false)

  const load = useCallback(async () => {
    try {
      const d = await fetchDashboard()
      setData(d)
      setReady(true)
    } catch (err) { console.error('Failed to load dashboard data:', err) }
  }, [])

  useEffect(() => {
    load()
    const t = setInterval(load, 15000)
    return () => clearInterval(t)
  }, [load])

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

  const narrativeEvents = buildNarrativeEvents(data)

  return (
    <div className="space-y-8">
      {/* ── Header ── */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="section-headline">Dashboard</h1>
          <p className="section-body mt-1">Platform overview</p>
        </div>
        <div className="flex items-center gap-3 text-[10px] text-[#5a6a8a]">
          <span className="flex items-center gap-1.5">
            <span className={`w-1.5 h-1.5 rounded-full ${healthy ? 'bg-[#00c785] animate-pulse' : 'bg-[#f59e0b]'}`} />
            {healthy ? 'Live' : 'Degraded'}
          </span>
          <span className="text-[#475569]">{user?.full_name || 'Admin'}</span>
          <span className="px-2 py-0.5 rounded bg-white/[0.04] text-[#475569] text-[10px]">{user?.role || 'user'}</span>
        </div>
      </div>

      {/* ── Demo banner ── */}
      {data.is_demo && (
        <div className="relative overflow-hidden rounded-xl p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs"
          style={{
            background: 'linear-gradient(135deg, rgba(30, 27, 75, 0.4) 0%, rgba(15, 23, 42, 0.4) 100%)',
            border: '1px solid rgba(129, 140, 248, 0.15)',
            boxShadow: '0 8px 32px rgba(0, 0, 0, 0.3)',
            backdropFilter: 'blur(8px)',
          }}>
          <div className="flex items-center gap-3">
            <span className="flex h-2 w-2 relative">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-indigo-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-indigo-500"></span>
            </span>
            <span className="text-white/80 leading-normal">
              <span className="font-semibold text-indigo-300">Demo Mode Active:</span> Showing simulated parking lots, transactions, and alerts. Create real parking lots to start tracking live sensor data.
            </span>
          </div>
          <div className="shrink-0 flex items-center">
            <span className="px-2 py-0.5 rounded text-[10px] uppercase font-mono tracking-wider font-semibold" 
              style={{ background: 'rgba(99, 102, 241, 0.15)', color: '#818cf8', border: '1px solid rgba(99, 102, 241, 0.25)' }}>
              Simulated Data
            </span>
          </div>
        </div>
      )}

      {/* ── Pipeline Nexus Visualization ── */}
      <CircularNexus />

      {/* ── Stats grid with Fraunces display numbers ── */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-5">
        <StatCard
          value={data.avg_occupancy}
          suffix="%"
          label="Avg Occupancy"
          sublabel={`${occupiedNow.toLocaleString()} slots filled`}
          color="#00d4ff"
        />
        <StatCard
          value={highOcc}
          label="Busy Lots (&gt;75%)"
          sublabel="high occupancy lots"
          color="#f59e0b"
        />
        <StatCard
          value={medOcc}
          label="Moderate (40–75%)"
          sublabel="medium occupancy lots"
          color="#60d4a0"
        />
        <StatCard
          value={lowOcc}
          label="Quiet (&le;40%)"
          sublabel="low occupancy lots"
          color="#5a6a8a"
        />
      </div>

      {/* ── Revenue row ── */}
      <div className="rounded-xl p-6"
        style={{
          background: 'linear-gradient(135deg, #0e0e24 0%, #12122a 50%, #0e0e24 100%)',
          boxShadow: '0 1px 0 rgba(255,255,255,0.04), 0 0 0 1px rgba(255,255,255,0.04)',
        }}>
        <div className="flex items-center justify-between">
          <div className="flex items-baseline gap-3">
            <span className="text-[11px] font-medium uppercase tracking-wider text-[#475569]">Revenue</span>
            <span className="text-[10px] text-[#475569]">{data.total_transactions.toLocaleString()} transactions</span>
          </div>
          {data.is_demo && (
            <span className="px-1.5 py-0.5 text-[9px] font-semibold rounded text-[#94a3b8] uppercase tracking-wider bg-white/[0.04] border border-white/[0.06] select-none">
              Demo
            </span>
          )}
        </div>
        <p className="display-number mt-2" style={{ color: '#f0c040' }}>
          $<CountUp value={Math.round(data.total_revenue)} />
        </p>
        <div className="flex items-center gap-4 mt-2 text-[11px] text-[#475569]">
          <span>{data.total_lots} lots · {data.total_slots.toLocaleString()} slots</span>
          <span className="w-px h-3 bg-[rgba(255,255,255,0.06)]" />
          <span>{data.avg_occupancy.toFixed(1)}% avg occupancy</span>
          <span className="w-px h-3 bg-[rgba(255,255,255,0.06)]" />
          <span>${revPerTx.toFixed(2)} avg per tx</span>
        </div>
        <div className="h-0.5 w-12 rounded-full mt-4 opacity-60" style={{ background: '#f0c040' }} />
      </div>

      {/* ── Lots grid ── */}
      <div>
        <h3 className="section-label mb-4">All Lots</h3>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3">
          {(data.lots || []).map((lot) => (
            <LotCard key={lot.lot_id} lot={lot} />
          ))}
        </div>
      </div>

      {/* ── Charts + Narrative Feed ── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Charts take 2 columns */}
        <div className="lg:col-span-2 space-y-6">
          {/* Occupancy chart */}
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

          {/* Revenue chart */}
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
                  <Area type="monotone" dataKey="revenue" stroke="#f0c040" fill="url(#rg)" strokeWidth={2.5} dot={false} />
                  <defs>
                    <linearGradient id="rg" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#f0c040" stopOpacity={0.2} />
                      <stop offset="100%" stopColor="#f0c040" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>

        {/* Narrative feed takes 1 column */}
        <div className="rounded-xl p-5"
          style={{
            background: 'linear-gradient(135deg, #0e0e24 0%, #12122a 50%, #0e0e24 100%)',
            boxShadow: '0 1px 0 rgba(255,255,255,0.04), 0 0 0 1px rgba(255,255,255,0.04)',
          }}>
          <div className="flex items-center gap-2 mb-3">
            <span className="text-[11px] font-medium uppercase tracking-wider text-[#475569]">Event Feed</span>
            <span className="w-1.5 h-1.5 rounded-full bg-[#00ff66] animate-pulse" />
          </div>
          <div className="h-[400px] overflow-y-auto scrollbar-thin">
            <NarrativeFeed events={narrativeEvents} />
          </div>
        </div>
      </div>
    </div>
  )
}
