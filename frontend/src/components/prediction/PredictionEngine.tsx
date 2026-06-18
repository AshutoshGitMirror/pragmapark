import { useState, useEffect, useMemo } from 'react'
import type { DataSource } from '../../hooks/useApi'
import { useReveal } from '../../hooks/useScrollReveal'
import { motion } from 'framer-motion'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, type TooltipProps,
} from 'recharts'
import type { NameType, ValueType } from 'recharts/types/component/DefaultTooltipContent'
import { fetchOccupancy, fetchPredictions, fetchLots } from '../../api/client'
import { useApi } from '../../hooks/useApi'
import { ChartSkeleton } from '../animations/LoadingSkeleton'
import type { PredictionItem, OccupancyRecord } from '../../api/types'

const TIME_RANGES = [6, 12, 24] as const

function CustomTooltip({ active, payload }: TooltipProps<ValueType, NameType>) {
  if (!active || !payload?.length) return null
  const entry = payload[0].payload
  return (
    <div className="bg-surface border border-[rgba(255,255,255,0.1)] rounded-lg px-3 py-2 font-mono text-[10px] shadow-xl">
      <div className="text-muted mb-1">{entry.time}</div>
      <div className="flex justify-between gap-4">
        <span className="text-dim">Actual:</span>
        <span className="text-white opacity-60">{entry.actual}%</span>
      </div>
      {entry.predicted !== null && (
        <>
          <div className="flex justify-between gap-4">
            <span className="text-dim">Predicted:</span>
            <span className="text-cyan">{entry.predicted}%</span>
          </div>
          <div className="flex justify-between gap-4">
            <span className="text-dim">Error:</span>
            <span className={Math.abs(entry.predicted - entry.actual) > 5 ? 'text-amber' : 'text-emerald'}>
              {Math.abs(Math.round((entry.predicted - entry.actual) * 10) / 10)}%
            </span>
          </div>
        </>
      )}
      {entry.raw && (
        <div className="flex justify-between gap-4 border-t border-[rgba(255,255,255,0.04)] mt-1 pt-1">
          <span className="text-dim">Flux:</span>
          <span className="text-muted">{entry.raw.net_flux?.toFixed(1) ?? '-'}</span>
        </div>
      )}
    </div>
  )
}

export function PredictionEngine() {
  const [selectedLot, setSelectedLot] = useState('')
  const [hours, setHours] = useState<typeof TIME_RANGES[number]>(24)
  const [records, setRecords] = useState<OccupancyRecord[]>([])
  const [dataSource, setDataSource] = useState<DataSource>('loading')
  const [predictions, setPredictions] = useState<PredictionItem[]>([])
  const [predError, setPredError] = useState(false)
  const [lotList, setLotList] = useState<string[]>([])

  const { data: lots } = useApi(() => fetchLots())

  useEffect(() => {
    if (lots && lots.length > 0) {
      const ids = lots.map((l: { lot_id: string }) => l.lot_id).sort()
      setLotList(ids)
      if (!selectedLot) setSelectedLot(ids[0])
    }
  }, [lots, selectedLot])

  useEffect(() => {
    if (!selectedLot) return
    let active = true
    setDataSource('loading')

    fetchOccupancy(selectedLot, hours)
      .then((data) => {
        if (active) {
          setRecords(data)
          setDataSource('live')
        }
      })
      .catch(() => {
        if (active) {
          setRecords([])
          setDataSource('error')
        }
      })

    return () => { active = false }
  }, [selectedLot, hours])

  const isLive = dataSource === 'live'

  useEffect(() => {
    if (!isLive || !selectedLot) {
      setPredictions([])
      setPredError(false)
      return
    }
    let active = true
    fetchPredictions(selectedLot, hours)
      .then((data) => {
        if (active) {
          setPredictions(data || [])
          setPredError(false)
        }
      })
      .catch(() => {
        if (active) {
          setPredictions([])
          setPredError(true)
        }
      })
    return () => { active = false }
  }, [selectedLot, hours, isLive])

  const hasPredictions = predictions.length > 0

  const chartData = useMemo(() => {
    if (!records.length) return []
    return records.map((r) => {
      const actual = Math.round(r.occupancy_rate * 1000) / 10
      const matching = hasPredictions ? predictions.find((p) => p.timestamp === r.timestamp) : null
      const predicted = matching ? Math.round(matching.predicted_occupancy_rate * 1000) / 10 : null
      return {
        time: new Date(r.timestamp).getHours().toString().padStart(2, '0') + ':00',
        predicted,
        actual,
        raw: r,
      }
    })
  }, [records, predictions, hasPredictions])

  const visible = useReveal(100)

  return (
    <section className="section bg-[#0a0a0f]" id="prediction">
      <div className="section-inner">
        <div className="grid grid-cols-1 lg:grid-cols-[45%_55%] gap-16 items-center">
          <div className={`transition-all duration-700 ${visible ? 'opacity-100 translate-x-0' : 'opacity-0 -translate-x-8'}`}>
            <div className="flex items-center gap-3 mb-4">
              <p className="section-label !mb-0" style={{ color: '#00d4ff' }}>MACHINE LEARNING</p>
              {isLive && (
                <span className="flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-[rgba(0,199,133,0.1)] border border-[rgba(0,199,133,0.2)]">
                  <span className="w-1.5 h-1.5 rounded-full bg-[#00c785] animate-pulse" />
                  <span className="text-[9px] font-mono text-emerald uppercase tracking-wider">Live</span>
                </span>
              )}
            </div>
            <h2 className="section-headline">Predict occupancy 24 hours ahead.</h2>
            <p className="section-body mb-10">
              Random Forest + XGBoost ensemble trained on Birmingham Parking Dataset.
              Cyclical temporal encoding captures hour-of-day, day-of-week, and seasonal patterns.
              5-fold time-series cross-validation ensures the model generalizes to future data.
            </p>

            <div className="flex items-center gap-3 mb-6">
              <div className="relative">
                <select
                  id="lot-selector"
                  name="lot"
                  value={selectedLot}
                  onChange={(e) => setSelectedLot(e.target.value)}
                  className="appearance-none bg-surface border border-[rgba(255,255,255,0.1)] rounded-lg px-3 py-1.5 text-xs font-mono text-muted cursor-pointer hover:border-cyan transition-colors outline-none pr-7"
                >
                  {lotList.length === 0 && (
                    <option value="" className="bg-surface">Loading lots...</option>
                  )}
                  {lotList.map((id) => (
                    <option key={id} value={id} className="bg-surface">Lot {id}</option>
                  ))}
                </select>
                <span className="absolute right-2 top-1/2 -translate-y-1/2 text-[8px] text-dim pointer-events-none">▼</span>
              </div>

              <div className="flex bg-surface rounded-lg border border-[rgba(255,255,255,0.06)] overflow-hidden">
                {TIME_RANGES.map((h) => (
                  <motion.button
                    key={h}
                    onClick={() => setHours(h)}
                    whileHover={{ scale: 1.03 }}
                    whileTap={{ scale: 0.97 }}
                    className={`px-3 py-1.5 text-[10px] font-mono transition-colors ${
                      hours === h
                        ? 'bg-[#00d4ff]/10 text-cyan'
                        : 'text-dim hover:text-muted'
                    }`}
                  >
                    {h}h
                  </motion.button>
                ))}
              </div>
            </div>

            <div className="flex flex-col gap-4">
              <div>
                <p className="stat-number text-cyan">{hasPredictions ? 'ENABLED' : 'AWAITING DATA'}</p>
                <p className="text-xs font-mono text-dim mt-1">PREDICTION STATUS</p>
              </div>
              <div>
                <p className="stat-number text-amber">{hasPredictions ? predictions.length + ' predictions' : '—'}</p>
                <p className="text-xs font-mono text-dim mt-1">FORECAST POINTS</p>
              </div>
              <div className="mt-2">
                <p className="text-sm font-mono text-dim">RF(100) + XGB(200) ensemble</p>
              </div>
            </div>
          </div>

          <div className={`transition-all duration-700 delay-100 ${visible ? 'opacity-100 translate-x-0' : 'opacity-0 translate-x-8'}`}>
            <div className="bg-surface rounded-xl border border-[rgba(255,255,255,0.06)] p-6">
              <div className="flex items-center gap-4 mb-4">
                {hasPredictions && (
                  <div className="flex items-center gap-2">
                    <div className="w-3 h-0.5 bg-[#00d4ff]" />
                    <span className="text-xs font-mono text-muted">Predicted</span>
                  </div>
                )}
                <div className="flex items-center gap-2">
                  <div className="w-3 h-0.5 bg-white opacity-60" style={{ borderTop: '1px dashed rgba(255,255,255,0.6)', height: 0 }} />
                  <span className="text-xs font-mono text-muted">Actual</span>
                </div>
                {!isLive && !selectedLot && (
                  <span className="ml-auto text-[9px] font-mono text-dim">LOADING</span>
                )}
                {isLive && predError && (
                  <span className="ml-auto text-[9px] font-mono text-amber">MODEL UNAVAILABLE</span>
                )}
                {isLive && !predError && !hasPredictions && (
                  <span className="ml-auto text-[9px] font-mono text-dim">AWAITING DATA</span>
                )}
              </div>

              {dataSource === 'loading' || records.length === 0 ? (
                <ChartSkeleton />
              ) : (
                <ResponsiveContainer width="100%" height={300}>
                  <LineChart data={chartData}>
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
                    <Tooltip content={<CustomTooltip />} />
                    {hasPredictions && (
                      <Line
                        type="monotone"
                        dataKey="predicted"
                        stroke="#00d4ff"
                        strokeWidth={2}
                        dot={false}
                      />
                    )}
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
