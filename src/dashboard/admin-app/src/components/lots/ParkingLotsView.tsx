import { useState } from 'react'
import { fetchLotDetail, fetchLots } from '../../api/client'
import type { Lot, LotDetail } from '../../api/types'

interface ParkingLotsViewProps { lots: Lot[]; onRefresh: () => void; }

export default function ParkingLotsView({ lots, onRefresh }: ParkingLotsViewProps) {
  const [selected, setSelected] = useState<LotDetail | null>(null)
  const [loading, setLoading] = useState(false)
  const [cityFilter, setCityFilter] = useState('')
  const [filteredLots, setFilteredLots] = useState<Lot[]>(lots)

  const cities = [...new Set(lots.map((l) => l.city).filter(Boolean))].sort()

  const handleCityChange = async (city: string) => {
    setCityFilter(city); setLoading(true)
    try { const data = await fetchLots(city || undefined); setFilteredLots(data) }
    catch { setFilteredLots(lots) }
    finally { setLoading(false) }
  }

  const handleSelect = async (lotId: string) => {
    setLoading(true)
    try { const data = await fetchLotDetail(lotId); setSelected(data) }
    catch {}
    finally { setLoading(false) }
  }

  if (selected) {
    const occ = selected.recent_occupancy?.[0]
    const occRate = occ?.occupancy_rate ?? 0.5
    const occColor = occRate > 0.8 ? '#f87171' : occRate > 0.5 ? '#fbbf24' : '#34d399'
    return (
      <div>
        <button onClick={() => setSelected(null)}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs cursor-pointer mb-4 transition-all"
          style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)', color: '#a49fc4' }}
          onMouseEnter={(e) => { e.currentTarget.style.borderColor = 'rgba(226,184,77,0.3)'; e.currentTarget.style.color = '#e2b84d' }}
          onMouseLeave={(e) => { e.currentTarget.style.borderColor = 'rgba(255,255,255,0.06)'; e.currentTarget.style.color = '#a49fc4' }}
        >
          <i className="fas fa-arrow-left" /> Back to Lots
        </button>
        <div className="p-[22px] rounded-2xl mb-4" style={{
          background: 'rgba(255,255,255,0.06)', backdropFilter: 'blur(16px)',
          border: '1px solid rgba(255,255,255,0.06)',
        }}>
          <h2 className="text-xl font-semibold mb-1">{selected.name}</h2>
          <p className="text-sm mb-4" style={{ color: '#a49fc4' }}>
            <i className="fas fa-map-marker-alt mr-1" /> {selected.address || selected.city || 'Unknown'}
          </p>
          <div className="flex gap-6 mb-3 flex-wrap">
            <div><span className="text-xs" style={{ color: '#a49fc4' }}>Total Spots</span><br /><strong>{selected.total_slots}</strong></div>
            <div><span className="text-xs" style={{ color: '#a49fc4' }}>Base Price</span><br /><strong style={{ color: '#e2b84d' }}>${(selected.base_price || 0).toFixed(2)}</strong></div>
            <div><span className="text-xs" style={{ color: '#a49fc4' }}>Predicted</span><br /><strong style={{ color: occColor }}>{(occRate * 100).toFixed(0)}%</strong></div>
            <div><span className="text-xs" style={{ color: '#a49fc4' }}>Available</span><br /><strong style={{ color: '#34d399' }}>{selected.available_spots ?? 0}</strong></div>
          </div>
          <div className="h-1.5 rounded-full overflow-hidden" style={{ background: 'rgba(255,255,255,0.04)' }}>
            <div className="h-full rounded-full" style={{ width: `${occRate * 100}%`, background: occColor }} />
          </div>
        </div>
        {selected.recent_occupancy && selected.recent_occupancy.length > 1 && (
          <div className="p-[22px] rounded-2xl" style={{
            background: 'rgba(255,255,255,0.06)', backdropFilter: 'blur(16px)',
            border: '1px solid rgba(255,255,255,0.06)',
          }}>
            <h3 className="text-[11px] mb-3 uppercase tracking-[0.8px]" style={{ color: 'rgba(240,238,248,0.55)' }}>
              <i className="fas fa-clock mr-1" /> Recent Occupancy (24h)
            </h3>
            <div className="flex gap-0.5 h-6 items-end">
              {selected.recent_occupancy.slice(0, 48).map((r, i) => {
                const c = r.occupancy_rate > 0.8 ? '#f87171' : r.occupancy_rate > 0.5 ? '#fbbf24' : '#34d399'
                return <div key={i} className="flex-1 rounded-sm" style={{ height: `${r.occupancy_rate * 100}%`, background: c, opacity: 0.8 }} title={`${(r.occupancy_rate * 100).toFixed(0)}%`} />
              })}
            </div>
          </div>
        )}
      </div>
    )
  }

  return (
    <div>
      <div className="flex gap-2.5 items-center mb-4 flex-wrap">
        <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl" style={{
          background: 'rgba(255,255,255,0.06)', backdropFilter: 'blur(12px)',
          border: '1px solid rgba(255,255,255,0.06)',
        }}>
          <i className="fas fa-city text-[13px]" style={{ color: '#e2b84d' }} />
          <select value={cityFilter} onChange={(e) => handleCityChange(e.target.value)}
            className="bg-transparent border-none text-[13px] outline-none cursor-pointer"
            style={{ color: '#f0eef8' }}>
            <option value="" style={{ background: '#1a1a28' }}>All Cities</option>
            {cities.map((c) => <option key={c} value={c} style={{ background: '#1a1a28' }}>{c}</option>)}
          </select>
        </div>
        <button onClick={onRefresh}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs cursor-pointer transition-all"
          style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)', color: '#a49fc4' }}>
          <i className="fas fa-redo" /> Refresh
        </button>
      </div>

      <div className="grid gap-4" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))' }}>
        {filteredLots.map((lot) => {
          const occ = lot.predicted_occupancy || 0
          const occColor = occ > 0.8 ? '#f87171' : occ > 0.5 ? '#fbbf24' : '#34d399'
          return (
            <div key={lot.lot_id || lot.id} onClick={() => handleSelect(lot.lot_id || String(lot.id))}
              className="p-4 rounded-2xl cursor-pointer transition-all duration-200"
              style={{
                background: 'rgba(255,255,255,0.06)', backdropFilter: 'blur(16px)',
                border: '1px solid rgba(255,255,255,0.06)',
              }}
              onMouseEnter={(e) => { e.currentTarget.style.borderColor = 'rgba(226,184,77,0.2)'; e.currentTarget.style.background = 'rgba(255,255,255,0.08)' }}
              onMouseLeave={(e) => { e.currentTarget.style.borderColor = 'rgba(255,255,255,0.06)'; e.currentTarget.style.background = 'rgba(255,255,255,0.06)' }}
            >
              <div className="flex justify-between items-start mb-2">
                <div>
                  <h3 className="text-sm font-semibold">{lot.name}</h3>
                  <p className="text-[11px]" style={{ color: '#a49fc4' }}>{lot.city}{lot.address ? `, ${lot.address}` : ''}</p>
                </div>
                <span className="text-sm font-bold" style={{ color: '#e2b84d' }}>${(lot.dynamic_price || lot.base_price || 0).toFixed(2)}</span>
              </div>
              <div className="flex items-center gap-3 text-xs mb-2" style={{ color: '#a49fc4' }}>
                <span><i className="fas fa-car mr-1" />{(occ * 100).toFixed(0)}% full</span>
                <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold`}
                  style={{
                    background: lot.available_spots && lot.available_spots > 0 ? 'rgba(52,211,153,0.15)' : 'rgba(248,113,113,0.15)',
                    color: lot.available_spots && lot.available_spots > 0 ? '#34d399' : '#f87171',
                  }}
                >
                  {lot.available_spots && lot.available_spots > 0 ? `${lot.available_spots} spots` : 'Full'}
                </span>
              </div>
              <div className="h-1 rounded-full overflow-hidden" style={{ background: 'rgba(255,255,255,0.04)' }}>
                <div className="h-full rounded-full transition-all duration-500" style={{ width: `${occ * 100}%`, background: occColor }} />
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
