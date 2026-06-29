import { useState, useEffect, useCallback, useRef } from 'react'
import { fetchDashboard, type DashboardData, type Lot } from '../../api/adminClient'
import { useAuth } from '../../context/AuthContext'
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

  return <span className={className}>{d.toLocaleString()}{suffix}</span>
}

/* ── Occupancy bar ── */
function OccupancyBar({ pct }: { pct: number }) {
  const w = Math.max(4, Math.min(100, pct))
  const color = pct > 75 ? '#f59e0b' : pct > 40 ? '#00d4ff' : '#6a7a9a'
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
    <div className="card-dark rounded-xl p-4 hover:bg-[rgba(255,255,255,0.02)] transition-colors cursor-default"
      >
      <div className="flex items-start justify-between mb-2.5">
        <div>
          <p className="text-sm font-medium text-white/90 leading-tight">{lot.name}</p>
          <p className="text-[10px] text-dim mt-0.5">{lot.city}</p>
        </div>
        <span className="text-xs font-mono font-semibold" style={{ color: occ > 75 ? '#f59e0b' : occ > 40 ? '#00d4ff' : '#5a6a8a' }}>
          {occ.toFixed(1)}%
        </span>
      </div>
      <OccupancyBar pct={occ} />
      <div className="flex items-center justify-between mt-2 text-[10px] text-dim">
        <span>{filled}/{lot.total_slots}</span>
        <span>₹{lot.base_price.toFixed(2)}</span>
      </div>
    </div>
  )
}

/* ── Narrative event type ── */
interface NarrativeEvent {
  id: number
  layer: number
  label: string
  detail: string
  severity: 'info' | 'warn' | 'success' | 'error'
}

const LAYER_COLORS_ARR = ['#00ff66', '#00f0ff', '#ffaa00', '#f43f5e', '#a855f7', '#94a3b8']

const PIPELINE_COLORS: Record<string, string> = {
  iot: '#00ff66', ml: '#00f0ff', blockchain: '#ffaa00',
  rl: '#f43f5e', digital_twin: '#a855f7', actuator: '#94a3b8',
}
const PIPELINE_LABELS: Record<string, string> = {
  iot: 'IoT Fusion', ml: 'ML Forecast', blockchain: 'Blockchain',
  rl: 'RL Pricing', digital_twin: 'Digital Twin', actuator: 'Actuator',
}

/* ── Pipeline Health (live from backend) ── */
function PipelineHealth({ layers }: { layers: Record<string, string> }) {
  const entries = Object.entries(layers)
  if (entries.length === 0) return null
  return (
    <div className="rounded-xl p-5"
      >
      <div className="flex items-center gap-2 mb-4">
        <span className="text-[11px] font-medium uppercase tracking-wider text-dim">Pipeline Health</span>
        <span className="w-1.5 h-1.5 rounded-full bg-[#00ff66] animate-pulse" />
      </div>
      <div className="flex flex-wrap gap-3">
        {entries.map(([key, val]) => {
          const c = PIPELINE_COLORS[key] || '#5a6a8a'
          const ok = val === 'operational'
          return (
            <div key={key}
              className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-[10px] font-mono"
              style={{
                background: ok ? `${c}10` : 'rgba(240,64,96,0.08)',
                border: `1px solid ${ok ? `${c}25` : 'rgba(240,64,96,0.2)'}`,
              }}>
              <span className={`w-1.5 h-1.5 rounded-full ${ok ? '' : 'animate-pulse'}`}
                style={{
                  background: ok ? c : '#f04060',
                  boxShadow: ok ? `0 0 6px ${c}66` : '0 0 6px rgba(240,64,96,0.6)',
                }} />
              <span style={{ color: ok ? c : '#f04060' }}>{PIPELINE_LABELS[key] || key}</span>
              <span className="text-[8px] uppercase tracking-wider" style={{ color: ok ? `${c}99` : '#f0406099' }}>
                {ok ? '● live' : `● ${val}`}
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

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
        {visible.map((ev) => (
          <div
            key={ev.id}
            className="group flex items-start gap-3 py-1.5 px-2 rounded hover:bg-white/[0.02] transition-colors"
          >
            {/* Layer dot */}
            <span
              className="w-1.5 h-1.5 rounded-full mt-1 shrink-0"
              style={{ backgroundColor: LAYER_COLORS_ARR[ev.layer % LAYER_COLORS_ARR.length] }}
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
                <span className="text-dim">[{ev.label}]</span> {ev.detail}
              </span>
            </div>
          </div>
        ))}
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
  let id = 1

  // System health event
  events.push({
    id: id++,
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
      layer: 0,
      label: 'IOT',
      detail: `${highOcc.length} lot${highOcc.length > 1 ? 's' : ''} at critical occupancy (>75%) — ${highOcc.map(l => l.name).join(', ')}`,
      severity: 'warn',
    })
  }
  if (medOcc.length > 0) {
    events.push({
      id: id++,
      layer: 1,
      label: 'ML',
      detail: `Occupancy forecast: ${medOcc.length} lot${medOcc.length > 1 ? 's' : ''} trending moderate, ${highOcc.length} high`,
      severity: 'info',
    })
  }
  if (lowOcc.length > 0) {
    events.push({
      id: id++,
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
      layer: 2,
      label: 'BC',
      detail: `Revenue contract executed · $${data.total_revenue.toLocaleString()} across ${data.total_transactions} txns`,
      severity: 'success',
    })
    if (data.total_transactions > 0) {
      const avg = data.total_revenue / data.total_transactions
      events.push({
        id: id++,
        layer: 3,
        label: 'RL',
        detail: `Avg revenue per transaction: ₹${avg.toFixed(2)} · RL agent optimizing tariff rates`,
        severity: 'info',
      })
    }
  }

  // Alert events
  ;(data.alerts || []).slice(0, 5).forEach((a) => {
    events.push({
      id: id++,
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
    layer: 4,
    label: 'DT',
    detail: `Digital twin state: ${occupiedNow}/${totalSlots} slots occupied · ${data.avg_occupancy.toFixed(1)}% utilization`,
    severity: 'info',
  })

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
      >
      {/* Accent bar */}
      <div
        className="absolute top-0 left-0 w-full h-px opacity-0 group-hover:opacity-100 transition-opacity"
        style={{ background: `linear-gradient(to right, transparent, ₹{color}, transparent)` }}
      />
      <div className="flex items-center justify-between">
        <p className="display-number" style={{ color }}>
          <CountUp value={value} suffix={suffix} />
        </p>
      </div>
      <p className="section-label mt-1">{label}</p>
      <p className="text-[10px] text-dim">{sublabel}</p>
    </div>
  )
}

/* ── Main Dashboard ── */
export function DashboardPage() {
  const { user } = useAuth()
  const [data, setData] = useState<DashboardData | null>(null)
  const [ready, setReady] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const retried = useRef(false)

  const load = useCallback(async () => {
    if (!retried.current) {
      // Initial load — show loading
    } else {
      // Auto-refresh — preserve existing data on error
    }
    try {
      const d = await fetchDashboard()
      setData(d)
      setReady(true)
      setError(null)
      retried.current = true
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to load dashboard data'
      if (!retried.current) {
        // Auto-retry once on initial load
        retried.current = true
        setTimeout(() => load(), 4000)
        setError('Loading dashboard failed. Retrying...')
      } else {
        setError(msg)
        setReady(true)
      }
    }
  }, [])

  useEffect(() => {
    load()
    const t = setInterval(load, 15000)
    return () => clearInterval(t)
  }, [load])

  if (!ready) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-subtle animate-pulse text-sm">Loading dashboard...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-64 flex-col gap-3">
        <div className="text-rose text-sm font-mono">{error}</div>
        <button onClick={load}
          className="text-[12px] font-mono px-3 py-2 rounded-lg transition-all"
          style={{
            background: 'rgba(240,64,96,0.08)',
            color: '#f04060',
            border: '1px solid rgba(240,64,96,0.2)',
          }}>
          Retry
        </button>
      </div>
    )
  }

  if (!data) {
    return (
      <div className="flex items-center justify-center h-64 flex-col gap-3">
        <div className="text-amber text-sm font-mono">No dashboard data available</div>
        <button onClick={load}
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
        <div className="flex items-center gap-3 text-[10px] text-subtle">
          <span className="flex items-center gap-1.5">
            <span className={`w-1.5 h-1.5 rounded-full ${healthy ? 'bg-[#00c785] animate-pulse' : 'bg-[#f59e0b]'}`} />
            {healthy ? 'Live' : 'Degraded'}
          </span>
          <span className="text-dim">{user?.full_name || 'Admin'}</span>
          <span className="px-2 py-0.5 rounded bg-white/[0.04] text-dim text-[10px]">{user?.role || 'user'}</span>
        </div>
      </div>

      {/* ── Pipeline Health (live layer status) ── */}
      <PipelineHealth layers={data.system_health?.layers ?? {}} />

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
        >
        <div className="flex items-center justify-between">
          <div className="flex items-baseline gap-3">
            <span className="text-[11px] font-medium uppercase tracking-wider text-dim">Revenue</span>
            <span className="text-[10px] text-dim">{data.total_transactions.toLocaleString()} transactions</span>
          </div>
        </div>
        <p className="display-number mt-2" style={{ color: '#f0c040' }}>
          $<CountUp value={Math.round(data.total_revenue)} />
        </p>
        <div className="flex items-center gap-4 mt-2 text-[11px] text-dim">
          <span>{data.total_lots} lots · {data.total_slots.toLocaleString()} slots</span>
          <span className="w-px h-3 bg-[rgba(255,255,255,0.06)]" />
          <span>{data.avg_occupancy.toFixed(1)}% avg occupancy</span>
          <span className="w-px h-3 bg-[rgba(255,255,255,0.06)]" />
          <span>₹{revPerTx.toFixed(2)} avg per tx</span>
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
            >
            <div className="flex items-center justify-between mb-5">
              <h3 className="text-sm font-medium text-white/80">Occupancy</h3>
              <span className="text-[10px] text-dim px-2 py-0.5 rounded bg-white/[0.03]">24h</span>
            </div>
            <div className="h-48">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={data.occupancy_trend}>
                  <XAxis dataKey="hour" tick={{ fill: '#6a7a9a', fontSize: 10 }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fill: '#6a7a9a', fontSize: 10 }} axisLine={false} tickLine={false} domain={[0, 100]} />
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
            >
            <div className="flex items-center justify-between mb-5">
              <h3 className="text-sm font-medium text-white/80">Revenue</h3>
              <span className="text-[10px] text-dim px-2 py-0.5 rounded bg-white/[0.03]">7 days</span>
            </div>
            <div className="h-48">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={data.revenue_7d}>
                  <XAxis dataKey="date" tick={{ fill: '#6a7a9a', fontSize: 10 }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fill: '#6a7a9a', fontSize: 10 }} axisLine={false} tickLine={false} />
                  <Tooltip
                    contentStyle={{ background: '#16163a', border: '1px solid rgba(0,212,255,0.15)', borderRadius: 10, fontSize: 12, boxShadow: '0 8px 32px rgba(0,0,0,0.4)' }}
                    labelStyle={{ color: '#94a3b8' }}
                    formatter={(v: number) => [`₹${v.toLocaleString()}`, 'Revenue']}
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
          >
          <div className="flex items-center gap-2 mb-3">
            <span className="text-[11px] font-medium uppercase tracking-wider text-dim">Event Feed</span>
            <span className="w-1.5 h-1.5 rounded-full bg-[#00ff66] animate-pulse" />
          </div>
          <div className="h-[400px] overflow-y-auto">
            <NarrativeFeed events={narrativeEvents} />
          </div>
        </div>
      </div>
    </div>
  )
}
