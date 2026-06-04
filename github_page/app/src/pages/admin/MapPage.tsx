import { useState, useEffect } from 'react'
import { fetchLots, type Lot } from '../../api/adminClient'

export function MapPage() {
  const [lots, setLots] = useState<Lot[]>([])
  const [loading, setLoading] = useState(true)
  const [cityFilter, setCityFilter] = useState('All')

  useEffect(() => {
    let mounted = true
    const load = async () => {
      try {
        const data = await fetchLots()
        if (mounted) setLots(data)
      } catch { /* empty */ } finally {
        if (mounted) setLoading(false)
      }
    }
    load()
    return () => { mounted = false }
  }, [])

  const cities = ['All', ...new Set(lots.map((l) => l.city).filter(Boolean))]
  const filtered = cityFilter === 'All' ? lots : lots.filter((l) => l.city === cityFilter)

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-[#5a6a8a] animate-pulse text-sm">Loading lots...</div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-white">Map</h1>
        <p className="text-xs text-[#5a6a8a] mt-1">Parking lots overview by location</p>
      </div>

      <div className="flex flex-wrap gap-2">
        {cities.map((city) => (
          <button
            key={city}
            onClick={() => setCityFilter(city)}
            className={`text-xs px-3 py-1.5 rounded-lg transition-all duration-200 ${
              cityFilter === city
                ? 'bg-[rgba(0,212,255,0.1)] text-[#00e5ff] font-medium'
                : 'bg-white/[0.04] text-[#5a6a8a] hover:text-white hover:bg-white/[0.06]'
            }`}
          >
            {city}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {filtered.map((lot) => {
          const occ = lot.current_occupancy || 0
          return (
            <div
              key={lot.lot_id}
              className="rounded-xl p-5 transition-all duration-200 hover:scale-[1.02] cursor-pointer"
              style={{
                background: 'linear-gradient(135deg, #0e0e24 0%, #12122a 50%, #0e0e24 100%)',
                boxShadow: '0 1px 0 rgba(255,255,255,0.04), 0 0 0 1px rgba(255,255,255,0.04)',
              }}>
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-medium text-white/90">{lot.name}</h3>
                <div className="flex items-center gap-1.5">
                  <div className="w-2 h-2 rounded-full" style={{
                    backgroundColor: occ > 0.7 ? '#f59e0b' : occ > 0.3 ? '#00c785' : '#00d4ff',
                  }} />
                  <span className="text-[10px] text-[#475569]">{lot.city}</span>
                </div>
              </div>
              <p className="text-[11px] text-[#5a6a8a] mb-3">{lot.address}</p>
              <div className="flex items-center gap-4 text-xs">
                <div>
                  <p className="text-[10px] text-[#475569] mb-0.5">Slots</p>
                  <p className="font-mono text-white/70">{lot.total_slots}</p>
                </div>
                <div>
                  <p className="text-[10px] text-[#475569] mb-0.5">Occupancy</p>
                  <p className="font-mono" style={{ color: occ > 0.7 ? '#f59e0b' : '#00c785' }}>{(occ * 100).toFixed(1)}%</p>
                </div>
                <div>
                  <p className="text-[10px] text-[#475569] mb-0.5">Price</p>
                  <p className="font-mono text-[#00c785]">${lot.base_price.toFixed(2)}</p>
                </div>
              </div>
              {occ > 0 && (
                <div className="mt-3 h-1 rounded-full bg-white/[0.06] overflow-hidden">
                  <div className="h-full rounded-full transition-all duration-500" style={{
                    width: `${Math.min(occ * 100, 100)}%`,
                    background: occ > 0.7 ? '#f59e0b' : 'linear-gradient(90deg, #00d4ff, #00c785)',
                  }} />
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
