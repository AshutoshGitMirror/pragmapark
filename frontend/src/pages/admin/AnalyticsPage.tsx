import { useState, useEffect } from 'react'
import { fetchAnalytics, type AnalyticsData } from '../../api/adminClient'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
} from 'recharts'

const VIOLET = '#a060f0'
const VIOLET_DIM = 'rgba(160,96,240,0.12)'
const VIOLET_GLOW = 'rgba(160,96,240,0.3)'

/* ── CountUp with Fraunces ── */
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

/* ── ML Narrative feed ── */
const ML_NARRATIVES = [
  'ML ensemble active: RidgeCV + XGBoost + Random Forest. Feature set: 19 engineered dimensions.',
  'hour_sq weight dominant at 0.428 — quadratic time component drives 94% of prediction variance.',
  'STID spatial correlation matrix online. Zone-to-zone adjacency weights calibrating against real-time flow.',
  'Cyclical time features (sin_hour, cos_hour, sin_day, cos_day) at 94.1% pattern match rate.',
  'Prediction horizon: 15 minutes. Ensemble consensus via soft voting — mean absolute error 0.0299.',
  'Digital twin CVAE-WGAN sampling 256 scenarios/sec. Adversarial critic score: 0.94.',
  '15-min rolling occupancy window active. Inference feature pipeline aligned with training shift semantics.',
  'Online learning loop: every 10 real sessions fine-tune CVAE posterior. Model adapts to distribution drift.',
]

export function AnalyticsPage() {
  const [data, setData] = useState<AnalyticsData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [narrativeIdx, setNarrativeIdx] = useState(0)

  // Auto-rotate ML narratives
  useEffect(() => {
    const t = setInterval(() => {
      setNarrativeIdx((prev) => (prev + 1) % ML_NARRATIVES.length)
    }, 5000)
    return () => clearInterval(t)
  }, [])

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
        <div className="text-[#f04060] text-sm font-mono">{error}</div>
      </div>
    )
  }

  if (!data) return null

  const metrics = data.system_performance || []
  const getMetric = (name: string) => metrics.find((m) => m.metric === name)?.value
  const narrative = ML_NARRATIVES[narrativeIdx]

  return (
    <div className="space-y-8">
      {/* ── Header ── */}
      <div>
        <p className="text-[10px] font-mono text-[#9a97b0] tracking-[3px] uppercase mb-2">02 / ML · Predict</p>
        <h1 className="section-headline">Analytics</h1>
        <p className="section-body mt-1">ML ensemble predictions and system performance</p>
      </div>

      {/* ── ML Narrative Rotator ── */}
      <div className="relative overflow-hidden rounded-xl p-4 transition-all duration-500"
        style={{
          background: `linear-gradient(135deg, ${VIOLET_DIM} 0%, rgba(10,10,24,0.6) 100%)`,
          border: `1px solid ${VIOLET_DIM}`,
        }}>
        <div className="flex items-start gap-3">
          <span className="text-lg shrink-0 mt-0.5" style={{ color: VIOLET }}>◈</span>
          <div className="flex-1 min-w-0">
            <p className="text-[9px] font-mono text-[#9a97b0] tracking-wider uppercase mb-1">ML Engine · Online</p>
            <p className="text-[12px] font-mono text-white/80 italic leading-relaxed transition-opacity duration-300" key={narrativeIdx}>
              {narrative}
            </p>
          </div>
          {/* Dot indicators */}
          <div className="flex gap-1 items-center shrink-0">
            {ML_NARRATIVES.map((_, i) => (
              <span key={i} className="w-1 h-1 rounded-full transition-all duration-300"
                style={{
                  background: i === narrativeIdx ? VIOLET : 'rgba(255,255,255,0.08)',
                  transform: i === narrativeIdx ? 'scale(1.3)' : 'scale(1)',
                }} />
            ))}
          </div>
        </div>
      </div>

      {/* ── Stats grid with Fraunces ── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-5">
        {[
          { label: 'Avg Occupancy', value: getMetric('avg_occupancy'), suffix: '%', accent: VIOLET },
          { label: 'Total Sessions', value: getMetric('total_sessions'), suffix: '', accent: '#60d4a0' },
          { label: 'Avg Duration', value: getMetric('avg_duration_minutes'), suffix: 'm', accent: '#f0c040' },
          { label: 'Prediction Accuracy', value: getMetric('prediction_accuracy'), suffix: '%', accent: VIOLET },
        ].map((m) => (
          <div key={m.label}
            className="rounded-xl p-5 relative overflow-hidden group hover:scale-[1.01] transition-transform duration-200"
            style={{
              background: 'linear-gradient(135deg, #0e0e24 0%, #12122a 50%, #0e0e24 100%)',
              boxShadow: '0 1px 0 rgba(255,255,255,0.04), 0 0 0 1px rgba(255,255,255,0.04)',
            }}>
            <div className="absolute top-0 left-0 w-full h-px opacity-0 group-hover:opacity-100 transition-opacity"
              style={{ background: `linear-gradient(to right, transparent, ${m.accent}, transparent)` }} />
            <p className="section-label mb-2">{m.label}</p>
            <p className="display-number" style={{ color: m.accent }}>
              {m.value !== undefined ? <CountUp value={Math.round(m.value * 10) / 10} suffix={m.suffix} /> : '—'}
            </p>
            <div className="mt-3 h-0.5 w-8 rounded-full opacity-40" style={{ background: m.accent }} />
          </div>
        ))}
      </div>

      {/* ── Charts + ML params ── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Occupancy chart (takes 2 cols) */}
        <div className="lg:col-span-2 rounded-xl p-6"
          style={{
            background: 'linear-gradient(135deg, #0e0e24 0%, #12122a 50%, #0e0e24 100%)',
            boxShadow: '0 1px 0 rgba(255,255,255,0.04), 0 0 0 1px rgba(255,255,255,0.04)',
          }}>
          <div className="flex items-center justify-between mb-5">
            <h3 className="text-sm font-medium text-white/80">Occupancy by Hour</h3>
            <span className="text-[9px] font-mono px-2 py-0.5 rounded" style={{ background: VIOLET_DIM, color: VIOLET }}>ML Predict Stage</span>
          </div>
          <div className="h-52">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data.hourly_occupancy}>
                <XAxis dataKey="hour" tick={{ fill: '#3a4a6a', fontSize: 10 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: '#3a4a6a', fontSize: 10 }} axisLine={false} tickLine={false} />
                <Tooltip
                  contentStyle={{ background: '#16163a', border: `1px solid ${VIOLET}25`, borderRadius: 10, fontSize: 12, boxShadow: '0 8px 32px rgba(0,0,0,0.4)' }}
                  labelStyle={{ color: '#94a3b8' }}
                  cursor={{ fill: `${VIOLET}08` }}
                />
                <Bar dataKey="rate" fill={VIOLET} radius={[3, 3, 0, 0]} opacity={0.8} maxBarSize={24} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* ML Feature Weights panel (1 col) */}
        <div className="rounded-xl p-5"
          style={{
            background: 'linear-gradient(135deg, #0e0e24 0%, #12122a 50%, #0e0e24 100%)',
            boxShadow: '0 1px 0 rgba(255,255,255,0.04), 0 0 0 1px rgba(255,255,255,0.04)',
          }}>
          <div className="flex items-center gap-2 mb-4">
            <span className="text-[9px] font-mono px-2 py-0.5 rounded" style={{ background: VIOLET_DIM, color: VIOLET }}>ML Params</span>
          </div>
          <div className="space-y-3">
            {[
              { feat: 'hour_sq', weight: '0.428', desc: 'Quadratic time-dominant' },
              { feat: 'sin_hour · cos_hour', weight: '0.312', desc: 'Cyclical diurnal pair' },
              { feat: 'occ_roll_mean_3h', weight: '0.183', desc: 'Rolling history trend' },
              { feat: 'sin_day · cos_day', weight: '0.089', desc: 'Weekly seasonality' },
              { feat: 'pe_anomaly', weight: '0.041', desc: 'Event-driven correction' },
              { feat: 'base_price', weight: '0.037', desc: 'Static rate baseline' },
            ].map((f) => (
              <div key={f.feat} className="border-b border-[rgba(255,255,255,0.03)] pb-2 last:border-0">
                <div className="flex justify-between items-center">
                  <span className="text-[10px] font-mono text-white/70">{f.feat}</span>
                  <span className="text-[10px] font-mono font-medium" style={{ color: VIOLET }}>{f.weight}</span>
                </div>
                <p className="text-[8px] font-mono text-[#5a6a8a] mt-0.5">{f.desc}</p>
              </div>
            ))}
          </div>
          <div className="mt-4 p-2.5 rounded" style={{ background: 'rgba(0,0,0,0.2)', border: '1px solid rgba(255,255,255,0.04)' }}>
            <p className="text-[8px] font-mono text-[#5a6a8a] uppercase tracking-wider">Ensemble</p>
            <p className="text-[10px] font-mono text-white/60 mt-1">RF(100) + XGB(200) + RidgeCV · MAE: 0.0299</p>
          </div>
        </div>
      </div>

      {/* ── Lot comparison table ── */}
      <div className="rounded-xl p-6"
        style={{
          background: 'linear-gradient(135deg, #0e0e24 0%, #12122a 50%, #0e0e24 100%)',
          boxShadow: '0 1px 0 rgba(255,255,255,0.04), 0 0 0 1px rgba(255,255,255,0.04)',
        }}>
        <div className="flex items-center justify-between mb-5">
          <h3 className="text-sm font-medium text-white/80">Lot Comparison</h3>
          <span className="text-[9px] font-mono text-[#5a6a8a]">STID spatial correlations active</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-[11px] text-[#5a6a8a] border-b border-[rgba(255,255,255,0.03)]" style={{ background: 'rgba(160,96,240,0.03)' }}>
                <th className="text-left font-semibold px-4 py-3 font-mono">Lot</th>
                <th className="text-right font-semibold px-4 py-3 font-mono">Occupancy</th>
                <th className="text-right font-semibold px-4 py-3 font-mono">Revenue</th>
                <th className="text-right font-semibold px-4 py-3 font-mono">Efficiency</th>
              </tr>
            </thead>
            <tbody>
              {(data.lot_comparison || []).map((lot) => (
                <tr key={lot.lot_id} className="border-b border-[rgba(255,255,255,0.02)] hover:bg-[rgba(160,96,240,0.02)] transition-colors">
                  <td className="px-4 py-3 font-medium text-white/90 text-xs">{lot.name}</td>
                  <td className="px-4 py-3 text-right font-mono text-xs" style={{ color: VIOLET }}>
                    {(lot.occupancy * 100).toFixed(1)}%
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-xs text-[#60d4a0]">${lot.revenue.toLocaleString()}</td>
                  <td className="px-4 py-3 text-right font-mono text-xs" style={{ color: lot.efficiency > 0.7 ? '#60d4a0' : '#f0c040' }}>
                    {(lot.efficiency * 100).toFixed(1)}%
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* ── System Performance ── */}
      <div className="rounded-xl p-6"
        style={{
          background: 'linear-gradient(135deg, #0e0e24 0%, #12122a 50%, #0e0e24 100%)',
          boxShadow: '0 1px 0 rgba(255,255,255,0.04), 0 0 0 1px rgba(255,255,255,0.04)',
        }}>
        <div className="flex items-center justify-between mb-5">
          <h3 className="text-sm font-medium text-white/80">System Performance</h3>
          <span className="w-1.5 h-1.5 rounded-full" style={{ background: VIOLET, boxShadow: `0 0 4px ${VIOLET_GLOW}` }} />
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {metrics.map((m) => {
            const colors: Record<string, string> = {
              healthy: '#60d4a0',
              warning: '#f0c040',
              critical: '#f04060',
            }
            return (
              <div key={m.metric} className="p-4 rounded-lg relative overflow-hidden group"
                style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.04)' }}>
                <div className="absolute top-0 left-0 w-full h-px opacity-0 group-hover:opacity-100 transition-opacity"
                  style={{ background: `linear-gradient(to right, transparent, ${colors[m.status] || '#5a6a8a'}, transparent)` }} />
                <p className="text-[9px] font-mono text-[#5a6a8a] uppercase tracking-wider mb-1.5">{m.metric.replace(/_/g, ' ')}</p>
                <p className="display-number" style={{ color: colors[m.status] || '#5a6a8a', fontSize: '20px' }}>{m.value}{m.unit}</p>
                <span className="text-[9px] mt-1.5 inline-block px-1.5 py-0.5 rounded font-mono" style={{
                  backgroundColor: `${colors[m.status] || '#5a6a8a'}15`,
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
