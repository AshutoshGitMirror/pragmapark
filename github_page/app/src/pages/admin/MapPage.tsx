import { useState, useEffect } from 'react'
import { fetchLots, type Lot } from '../../api/adminClient'

const CITY_COORDS: Record<string, { city: string; lat: number; lng: number; lots: Lot[] }> = {}

export function MapPage() {
  const [lots, setLots] = useState<Lot[]>([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('All Cities')

  useEffect(() => {
    fetchLots()
      .then(setLots)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const cities = [...new Set(lots.map((l) => l.city).filter(Boolean))]
  const filtered = filter === 'All Cities' ? lots : lots.filter((l) => l.city === filter)

  if (loading) return <div className="flex items-center justify-center h-64"><div className="text-dim animate-pulse">Loading map data...</div></div>

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-light text-white">Map</h1>
        <select
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="bg-[#0a0a0f] border border-white/10 rounded-lg px-3 py-1.5 text-xs text-muted focus:outline-none focus:border-cyan-500/50"
        >
          <option>All Cities</option>
          {cities.map((c) => <option key={c}>{c}</option>)}
        </select>
      </div>

      <div className="bg-[#13131f] border border-white/5 rounded-xl p-5">
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3">
          {filtered.map((lot) => (
            <div key={lot.lot_id} className="bg-[#0a0a0f] border border-white/5 rounded-lg p-3 hover:border-cyan-500/30 transition-colors">
              <p className="text-xs font-medium text-white/90 truncate">{lot.name}</p>
              <p className="text-[10px] text-dim mt-0.5 truncate">{lot.city}</p>
              <div className="mt-2 flex items-center gap-1.5 text-[10px] font-mono text-dim">
                <span>{lot.latitude.toFixed(4)}</span>
                <span className="text-white/20">/</span>
                <span>{lot.longitude.toFixed(4)}</span>
              </div>
              <div className="mt-1.5 flex items-center justify-between">
                <span className="text-[10px] text-muted">{lot.total_slots} slots</span>
                <span className={`text-[10px] ${lot.current_occupancy ? 'text-amber-400' : 'text-dim'}`}>
                  {lot.current_occupancy ? `${(lot.current_occupancy * 100).toFixed(0)}%` : '—'}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="bg-[#13131f] border border-white/5 rounded-xl p-5">
        <h3 className="text-xs text-dim uppercase tracking-widest mb-3">Cities</h3>
        <div className="flex flex-wrap gap-2">
          {cities.map((city) => {
            const count = lots.filter((l) => l.city === city).length
            return (
              <button
                key={city}
                onClick={() => setFilter(city)}
                className={`text-xs px-3 py-1.5 rounded-lg border transition-colors ${
                  filter === city
                    ? 'border-cyan-500/50 bg-cyan-500/10 text-cyan-400'
                    : 'border-white/5 text-dim hover:text-white hover:border-white/10'
                }`}
              >
                {city} <span className="text-[10px] opacity-60">({count})</span>
              </button>
            )
          })}
        </div>
      </div>
    </div>
  )
}
