import { useState, useEffect } from 'react'
import { fetchLots, type Lot } from '../../api/adminClient'

export function MapPage() {
  const [lots, setLots] = useState<Lot[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedCity, setSelectedCity] = useState('All')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let mounted = true
    const load = async () => {
      try {
        const data = await fetchLots()
        if (mounted) setLots(data)
      } catch (err: any) {
        if (mounted) setError(err.message)
      } finally {
        if (mounted) setLoading(false)
      }
    }
    load()
    const interval = setInterval(load, 30000)
    return () => { mounted = false; clearInterval(interval) }
  }, [])

  const cities = [...new Set(lots.map((l) => l.city || 'Unknown'))].sort()
  const filtered = selectedCity === 'All' ? lots : lots.filter((l) => l.city === selectedCity)

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-[#64748b] animate-pulse text-sm">Loading map...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-red-400 text-sm">{error}</div>
      </div>
    )
  }

  return (
    <div className="space-y-5">
      <h1 className="text-lg font-semibold text-white">Map</h1>

      <div className="bg-[#0e0e1a] border border-[rgba(255,255,255,0.06)] rounded-xl p-5">
        <h3 className="text-xs text-[#64748b] mb-3">Parking Lots</h3>
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3">
          {filtered.map((lot) => {
            const occ = lot.current_occupancy !== undefined ? lot.current_occupancy * 100 : null
            return (
              <div
                key={lot.lot_id}
                className="bg-[#0a0a0f] border border-[rgba(255,255,255,0.06)] rounded-lg p-3 hover:border-[rgba(0,212,255,0.3)] transition-colors"
              >
                <p className="text-xs text-white/90 font-medium">{lot.name}</p>
                <p className="text-[10px] text-[#64748b] mt-0.5 truncate">{lot.city || '—'}</p>
                {lot.latitude && lot.longitude && (
                  <p className="text-[9px] text-[#475569] mt-1 font-mono">
                    {lot.latitude.toFixed(4)}, {lot.longitude.toFixed(4)}
                  </p>
                )}
                <div className="flex items-center justify-between mt-2 pt-2 border-t border-[rgba(255,255,255,0.04)]">
                  <span className="text-[10px] text-[#475569]">{lot.total_slots} slots</span>
                  <span className={`text-[10px] font-mono ${occ !== null ? 'text-[#f59e0b]' : 'text-[#475569]'}`}>
                    {occ !== null ? `${occ.toFixed(0)}%` : '—'}
                  </span>
                </div>
              </div>
            )
          })}
        </div>
      </div>

      <div className="bg-[#0e0e1a] border border-[rgba(255,255,255,0.06)] rounded-xl p-5">
        <h3 className="text-xs text-[#64748b] mb-3">Cities</h3>
        <div className="flex flex-wrap gap-2">
          {['All', ...cities].map((city) => (
            <button
              key={city}
              onClick={() => setSelectedCity(city)}
              className={`text-xs px-3 py-1.5 rounded-lg border transition-colors ${
                selectedCity === city
                  ? 'border-[rgba(0,212,255,0.5)] bg-[rgba(0,212,255,0.08)] text-[#00d4ff]'
                  : 'border-[rgba(255,255,255,0.06)] text-[#64748b] hover:text-white hover:border-[rgba(255,255,255,0.1)]'
              }`}
            >
              {city}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
