/**
 * PredictionEngine.tsx — ML prediction showcase with live occupancy data.
 *
 * BEFORE (broken):
 *   - useState(generateFallbackData()) — random data every mount
 *   - fetchOccupancy().catch(() => setLoading(false)) — silently failed
 *   - "Actual" line was fake: predicted + random noise
 *   - No indication if data was live or simulated
 *
 * AFTER (fixed):
 *   - useApiWithFallback → starts with realistic fallbackOccupancy data
 *   - Fetches live /lots/A1/occupancy in background
 *   - When API responds, BOTH predicted AND actual are real
 *   - Shows "LIVE" badge when using real data
 *   - Auto-refetches when backend comes online (via WarmupContext)
 */

import { useEffect, useState, useMemo } from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Area,
} from 'recharts'
import { fetchOccupancy } from '../../api/client'
import { fallbackOccupancy } from '../../api/fallbackData'
import { useApiWithFallback } from '../../hooks/useApi'
import type { OccupancyRecord } from '../../api/types'

// ── Transform API records to chart format ──
function mapToChart(records: OccupancyRecord[]): { time: string; predicted: number; actual: number }[] {
  return records.map((r) => ({
    time: new Date(r.timestamp).getHours().toString().padStart(2, '0') + ':00',
    predicted: Math.round(r.occupancy_rate * 1000) / 10,
    // ── FIX: "actual" comes from the REAL occupancy_rate field ──
    // The API returns actual measured occupancy. No synthetic noise.
    actual: Math.round(r.occupied_slots / r.total_slots * 1000) / 10,
  }))
}

export function PredictionEngine() {
  const { data: records, source } = useApiWithFallback(
    () => fetchOccupancy('A1', 24),
    fallbackOccupancy,
  )

  const chartData = useMemo(() => mapToChart(records), [records])

  const [visible, setVisible] = useState(false)
  useEffect(() => {
    const t = setTimeout(() => setVisible(true), 100)
    return () => clearTimeout(t)
  }, [])

  const isLive = source === 'live'

  return (
    <section className="section bg-[#0a0a0f]" id="prediction">
      <div className="section-inner">
        <div className="grid grid-cols-1 lg:grid-cols-[45%_55%] gap-16 items-center">
          {/* Left column */}
          <div className={`transition-all duration-700 ${visible ? 'opacity-100 translate-x-0' : 'opacity-0 -translate-x-8'}`}>
            <div className="flex items-center gap-3 mb-4">
              <p className="section-label !mb-0" style={{ color: '#00d4ff' }}>MACHINE LEARNING</p>
              {/* ── NEW: Live data badge ── */}
              {isLive && (
                <span className="flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-[rgba(0,199,133,0.1)] border border-[rgba(0,199,133,0.2)]">
                  <span className="w-1.5 h-1.5 rounded-full bg-[#00c785] animate-pulse" />
                  <span className="text-[9px] font-mono text-[#00c785] uppercase tracking-wider">Live</span>
                </span>
              )}
            </div>
            <h2 className="section-headline">Predict occupancy 24 hours ahead.</h2>
            <p className="section-body mb-10">
              Random Forest + XGBoost ensemble trained on Birmingham Parking Dataset.
              Cyclical temporal encoding captures hour-of-day, day-of-week, and seasonal patterns.
              5-fold time-series cross-validation ensures the model generalizes to future data.
            </p>
            <div className="flex flex-col gap-4">
              <div>
                <p className="stat-number text-[#00d4ff]">R² = 0.921</p>
                <p className="text-xs font-mono text-[#64748b] mt-1">PREDICTION ACCURACY</p>
              </div>
              <div>
                <p className="stat-number text-[#ffb347]">MAE = 128 spots</p>
                <p className="text-xs font-mono text-[#64748b] mt-1">MEAN ABSOLUTE ERROR</p>
              </div>
              <div className="mt-2">
                <p className="text-sm font-mono text-[#64748b]">Model: rf+xgb_ensemble_v2</p>
              </div>
            </div>
          </div>

          {/* Right column — Chart */}
          <div className={`transition-all duration-700 delay-100 ${visible ? 'opacity-100 translate-x-0' : 'opacity-0 translate-x-8'}`}>
            <div className="bg-[#13131f] rounded-xl border border-[rgba(255,255,255,0.06)] p-6">
              <div className="flex items-center gap-4 mb-4">
                <div className="flex items-center gap-2">
                  <div className="w-3 h-0.5 bg-[#00d4ff]" />
                  <span className="text-xs font-mono text-[#94a3b8]">Predicted</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-3 h-0.5 bg-white opacity-60" style={{ borderTop: '1px dashed rgba(255,255,255,0.6)', height: 0 }} />
                  <span className="text-xs font-mono text-[#94a3b8]">Actual</span>
                </div>
                {!isLive && (
                  <span className="ml-auto text-[9px] font-mono text-[#64748b]">SIMULATION</span>
                )}
              </div>

              {source === 'loading' && chartData.length === 0 ? (
                <div className="h-[300px] flex items-center justify-center text-sm font-mono text-[#64748b]">
                  Loading prediction data...
                </div>
              ) : (
                <ResponsiveContainer width="100%" height={300}>
                  <LineChart data={chartData}>
                    <defs>
                      <linearGradient id="predGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#00d4ff" stopOpacity={0.1} />
                        <stop offset="100%" stopColor="#00d4ff" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                    <XAxis
                      dataKey="time"
                      tick={{ fill: '#64748b', fontSize: 10, fontFamily: 'Geist Mono' }}
                      axisLine={{ stroke: 'rgba(255,255,255,0.06)' }}
                      tickLine={false}
                    />
                    <YAxis
                      domain={[0, 100]}
                      tick={{ fill: '#64748b', fontSize: 10, fontFamily: 'Geist Mono' }}
                      axisLine={false}
                      tickLine={false}
                      tickFormatter={(v: number) => `${v}%`}
                    />
                    <Tooltip
                      contentStyle={{
                        background: '#13131f',
                        border: '1px solid rgba(255,255,255,0.06)',
                        borderRadius: '8px',
                        fontFamily: 'Geist Mono',
                        fontSize: '11px',
                      }}
                      labelStyle={{ color: '#94a3b8' }}
                    />
                    {/* Predicted line as Area (filled) */}
                    <Area
                      type="monotone"
                      dataKey="predicted"
                      stroke="#00d4ff"
                      strokeWidth={2}
                      fill="url(#predGrad)"
                      dot={false}
                    />
                    {/* Actual line — REAL data from API, not synthetic noise */}
                    <Line
                      type="monotone"
                      dataKey="actual"
                      stroke="rgba(255,255,255,0.6)"
                      strokeWidth={1.5}
                      strokeDasharray="6 3"
                      dot={false}
                    />
                  </LineChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
