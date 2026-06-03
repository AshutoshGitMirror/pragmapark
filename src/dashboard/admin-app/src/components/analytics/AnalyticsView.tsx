import { useMemo, useState } from 'react'
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar, PieChart, Pie, Cell } from 'recharts'
import { fetchOccupancy } from '../../api/client'
import type { Lot } from '../../api/types'

interface AnalyticsViewProps { lots: Lot[] }

const HOURS = Array.from({ length: 24 }, (_, i) => ({
  hour: `${i.toString().padStart(2, '0')}:00`,
  occupancy: Math.round((0.3 + Math.sin(i / 24 * Math.PI * 2) * 0.3 + 0.4) * 100),
}))

const PERF_DATA = [
  { name: 'Database', value: 95, color: '#00d4ff' },
  { name: 'ML Pipeline', value: 88, color: '#e2b84d' },
  { name: 'Blockchain', value: 92, color: '#34d399' },
  { name: 'API Gateway', value: 97, color: '#a78bfa' },
]

export default function AnalyticsView({ lots }: AnalyticsViewProps) {
  const [selectedLot, setSelectedLot] = useState<string>('')
  const [occData, setOccData] = useState<any[]>([])

  const lotCompareData = useMemo(() => {
    return lots.slice(0, 8).map((l) => ({
      name: l.name?.split(' ').slice(0, 2).join(' ') || l.lot_id,
      occupancy: Math.round((l.predicted_occupancy || 0.5) * 100),
      price: l.dynamic_price || l.base_price || 10,
      capacity: l.total_slots || 100,
    }))
  }, [lots])

  const handleLotSelect = async (lotId: string) => {
    setSelectedLot(lotId)
    if (!lotId) { setOccData([]); return }
    try {
      const records = await fetchOccupancy(lotId, 24)
      const data = (records || []).map((r: any, i: number) => ({
        time: new Date(r.timestamp || i * 3600000).toLocaleTimeString('en', { hour: '2-digit', minute: '2-digit' }),
        occupancy: Math.round((r.occupancy_rate || 0) * 100),
      }))
      setOccData(data)
    } catch { setOccData(HOURS) }
  }

  return (
    <div>
      <div className="grid gap-4 mb-6" style={{ gridTemplateColumns: '1fr 1fr' }}>
        <div className="p-[22px] rounded-2xl" style={{
          background: 'rgba(255,255,255,0.06)', backdropFilter: 'blur(16px)',
          border: '1px solid rgba(255,255,255,0.06)',
        }}>
          <h3 className="text-[11px] mb-[18px] uppercase tracking-[0.8px]" style={{ color: 'rgba(240,238,248,0.55)' }}>
            <i className="fas fa-clock mr-1" /> Hourly Occupancy Pattern
          </h3>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={HOURS}>
              <XAxis dataKey="hour" tick={{ fontSize: 10, fill: '#64748b' }} interval={3} />
              <YAxis tick={{ fontSize: 10, fill: '#64748b' }} domain={[0, 100]} />
              <Tooltip contentStyle={{ background: '#13131f', border: '1px solid rgba(255,255,255,0.06)', borderRadius: 8, fontSize: 12 }} />
              <Line type="monotone" dataKey="occupancy" stroke="#00d4ff" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
        <div className="p-[22px] rounded-2xl" style={{
          background: 'rgba(255,255,255,0.06)', backdropFilter: 'blur(16px)',
          border: '1px solid rgba(255,255,255,0.06)',
        }}>
          <h3 className="text-[11px] mb-[18px] uppercase tracking-[0.8px]" style={{ color: 'rgba(240,238,248,0.55)' }}>
            <i className="fas fa-layer-group mr-1" /> Lot Comparison
          </h3>
          <ResponsiveContainer width="100%" height={300}>
            <RadarChart data={lotCompareData}>
              <PolarGrid stroke="rgba(255,255,255,0.06)" />
              <PolarAngleAxis dataKey="name" tick={{ fontSize: 9, fill: '#64748b' }} />
              <PolarRadiusAxis tick={{ fontSize: 9, fill: '#64748b' }} domain={[0, 100]} />
              <Radar name="Occupancy" dataKey="occupancy" stroke="#e2b84d" fill="#e2b84d" fillOpacity={0.2} />
            </RadarChart>
          </ResponsiveContainer>
        </div>
      </div>
      <div className="grid gap-4" style={{ gridTemplateColumns: '1fr 1fr' }}>
        <div className="p-[22px] rounded-2xl" style={{
          background: 'rgba(255,255,255,0.06)', backdropFilter: 'blur(16px)',
          border: '1px solid rgba(255,255,255,0.06)',
        }}>
          <h3 className="text-[11px] mb-[18px] uppercase tracking-[0.8px]" style={{ color: 'rgba(240,238,248,0.55)' }}>
            <i className="fas fa-map-marked-alt mr-1" /> System Performance
          </h3>
          <div className="flex justify-center" style={{ height: 300 }}>
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={PERF_DATA} cx="50%" cy="50%" innerRadius={60} outerRadius={100} dataKey="value" label={({ name, value }) => `${name} ${value}%`}>
                  {PERF_DATA.map((e, i) => <Cell key={i} fill={e.color} />)}
                </Pie>
                <Tooltip contentStyle={{ background: '#13131f', border: '1px solid rgba(255,255,255,0.06)', borderRadius: 8, fontSize: 12 }} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
        <div className="p-[22px] rounded-2xl" style={{
          background: 'rgba(255,255,255,0.06)', backdropFilter: 'blur(16px)',
          border: '1px solid rgba(255,255,255,0.06)',
        }}>
          <h3 className="text-[11px] mb-[18px] uppercase tracking-[0.8px]" style={{ color: 'rgba(240,238,248,0.55)' }}>
            <i className="fas fa-search mr-1" /> Lot Detail Explorer
          </h3>
          <div className="flex items-center gap-2 mb-4 px-3 py-1.5 rounded-xl" style={{
            background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.06)',
          }}>
            <i className="fas fa-warehouse text-[13px]" style={{ color: '#e2b84d' }} />
            <select value={selectedLot} onChange={(e) => handleLotSelect(e.target.value)}
              className="bg-transparent border-none text-[13px] outline-none cursor-pointer flex-1" style={{ color: '#f0eef8' }}>
              <option value="" style={{ background: '#1a1a28' }}>Select a lot...</option>
              {lots.map((l) => (
                <option key={l.lot_id || l.id} value={l.lot_id || l.id} style={{ background: '#1a1a28' }}>{l.name}</option>
              ))}
            </select>
          </div>
          {occData.length > 0 && (
            <ResponsiveContainer width="100%" height={250}>
              <LineChart data={occData}>
                <XAxis dataKey="time" tick={{ fontSize: 9, fill: '#64748b' }} interval={3} />
                <YAxis tick={{ fontSize: 9, fill: '#64748b' }} domain={[0, 100]} />
                <Tooltip contentStyle={{ background: '#13131f', border: '1px solid rgba(255,255,255,0.06)', borderRadius: 8, fontSize: 12 }} />
                <Line type="monotone" dataKey="occupancy" stroke="#00c785" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          )}
          {!selectedLot && (
            <p className="text-center py-10 text-sm" style={{ color: '#64748b' }}>
              <i className="fas fa-chart-line text-2xl block mb-2 opacity-50" />
              Select a lot to view its occupancy trend
            </p>
          )}
        </div>
      </div>
    </div>
  )
}
