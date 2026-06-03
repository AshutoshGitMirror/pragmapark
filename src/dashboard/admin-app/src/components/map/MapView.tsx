import { useEffect, useRef } from 'react'
import L from 'leaflet'
import type { Lot } from '../../api/types'

interface MapViewProps { lots: Lot[] }

const CITY_COLORS: Record<string, string> = {
  Birmingham: '#818cf8', London: '#e2b84d', Manchester: '#34d399',
  'New York': '#f87171', 'San Francisco': '#a78bfa', Tokyo: '#fbbf24',
  Dubai: '#f472b6', Singapore: '#2dd4bf', Mumbai: '#fb923c', Berlin: '#60a5fa',
}

export default function MapView({ lots }: MapViewProps) {
  const mapRef = useRef<HTMLDivElement>(null)
  const mapInstance = useRef<L.Map | null>(null)
  const markersRef = useRef<L.Marker[]>([])

  useEffect(() => {
    if (!mapRef.current || mapInstance.current) return

    const map = L.map(mapRef.current, {
      center: [40, -10],
      zoom: 3,
      zoomControl: true,
      attributionControl: true,
    })

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>',
      maxZoom: 19,
    }).addTo(map)

    mapInstance.current = map

    const handleResize = () => map.invalidateSize()
    window.addEventListener('resize', handleResize)
    return () => {
      window.removeEventListener('resize', handleResize)
    }
  }, [])

  useEffect(() => {
    const map = mapInstance.current
    if (!map || !lots.length) return

    markersRef.current.forEach((m) => map.removeLayer(m))
    markersRef.current = []

    const bounds: [number, number][] = []
    const cities = [...new Set(lots.map((l) => l.city).filter(Boolean))]

    cities.forEach((city) => {
      const cityLots = lots.filter((l) => l.city === city)
      const avgLat = cityLots.reduce((s, l) => s + (l.latitude || 0), 0) / cityLots.length
      const avgLng = cityLots.reduce((s, l) => s + (l.longitude || 0), 0) / cityLots.length
      if (!avgLat && !avgLng) return

      const color = CITY_COLORS[city] || '#818cf8'
      const occ = cityLots.reduce((s, l) => s + (l.predicted_occupancy || 0), 0) / cityLots.length
      const avail = cityLots.reduce((s, l) => s + (l.available_spots || 0), 0)

      const marker = L.marker([avgLat, avgLng], {
        icon: L.divIcon({
          className: '',
          html: `<div style="background:${color};width:16px;height:16px;border-radius:50%;border:2px solid rgba(255,255,255,0.3);box-shadow:0 0 12px ${color}40;"></div>`,
          iconSize: [16, 16],
          iconAnchor: [8, 8],
        }),
      })

      marker.bindPopup(`
        <div style="background:#14141e;border:1px solid rgba(255,255,255,0.06);border-radius:12px;padding:16px;min-width:200px;color:#f0eef8;">
          <h3 style="margin:0 0 8px;font-size:14px;color:#e2b84d;">${city}</h3>
          <p style="margin:0 0 4px;font-size:12px;color:#a49fc4;">${cityLots.length} lot${cityLots.length > 1 ? 's' : ''}</p>
          <p style="margin:0 0 4px;font-size:12px;color:#a49fc4;">Occupancy: <strong style="color:${occ > 0.8 ? '#f87171' : occ > 0.5 ? '#fbbf24' : '#34d399'}">${(occ * 100).toFixed(0)}%</strong></p>
          <p style="margin:0;font-size:12px;color:#a49fc4;">Available: <strong style="color:#34d399;">${avail}</strong></p>
        </div>
      `)

      marker.addTo(map)
      markersRef.current.push(marker)
      if (avgLat && avgLng) bounds.push([avgLat, avgLng] as any)
    })

    if (bounds.length) {
      try {
        map.fitBounds(bounds, { padding: [50, 50], maxZoom: 10 })
      } catch { map.setView([40, -10], 3) }
    }
  }, [lots])

  return (
    <div>
      <div className="flex items-center gap-2.5 mb-4 flex-wrap">
        <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl" style={{
          background: 'rgba(255,255,255,0.06)', backdropFilter: 'blur(12px)',
          border: '1px solid rgba(255,255,255,0.06)',
        }}>
          <i className="fas fa-city text-[13px]" style={{ color: '#e2b84d' }} />
          <select className="bg-transparent border-none text-[13px] outline-none cursor-pointer" style={{ color: '#f0eef8' }}>
            <option value="" style={{ background: '#1a1a28' }}>All Cities</option>
            {[...new Set(lots.map((l) => l.city).filter(Boolean))].map((c) => (
              <option key={c} value={c} style={{ background: '#1a1a28' }}>{c}</option>
            ))}
          </select>
        </div>
        <div className="flex gap-2 flex-wrap text-[11px]" style={{ color: '#a49fc4' }}>
          {Object.entries(CITY_COLORS).map(([city, color]) => (
            <span key={city} className="flex items-center gap-1">
              <span className="inline-block w-2.5 h-2.5 rounded-full" style={{ background: color }} />
              {city}
            </span>
          ))}
        </div>
      </div>
      <div className="rounded-2xl overflow-hidden" style={{ border: '1px solid rgba(255,255,255,0.06)' }}>
        <div ref={mapRef} style={{ height: 600, width: '100%', borderRadius: 12 }} />
      </div>
    </div>
  )
}
