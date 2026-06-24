import { useState, useEffect, useCallback, useRef } from 'react'
import { MapContainer, TileLayer, Marker, Popup, useMap, ZoomControl } from 'react-leaflet'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { fetchLots, type Lot } from '../../api/adminClient'

/* ── Fix default Leaflet marker icons ── */
delete (L.Icon.Default.prototype as any)._getIconUrl
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
})

/* ── Custom marker icon factory ── */
function createMarkerIcon(color: string, glowColor: string, isSelected: boolean): L.DivIcon {
  return L.divIcon({
    className: '',
    html: `<div style="
      width: ${isSelected ? 18 : 14}px;
      height: ${isSelected ? 18 : 14}px;
      border-radius: 50%;
      background: ${color};
      box-shadow: 0 0 ${isSelected ? 16 : 8}px ${glowColor}, 0 0 0 ${isSelected ? 3 : 2}px rgba(0,0,0,0.5);
      border: 2px solid rgba(0,0,0,0.6);
      transition: all 0.2s;
      cursor: pointer;
"></div>`,
    iconSize: [isSelected ? 22 : 18, isSelected ? 22 : 18],
    iconAnchor: [isSelected ? 11 : 9, isSelected ? 11 : 9],
  })
}

/* ── Lot occupancy color helpers ── */
function getOccColor(occ: number): string {
  if (occ > 75) return '#f04060'   // rose for high
  if (occ > 40) return '#f0c040'   // gold for medium
  return '#40d4f0'                  // cyan for low
}
function getOccGlow(occ: number): string {
  if (occ > 75) return 'rgba(240,64,96,0.5)'
  if (occ > 40) return 'rgba(240,192,64,0.4)'
  return 'rgba(64,212,240,0.4)'
}

/* ── Auto-fit bounds after lots load ── */
function FitBoundsOnData({ coords }: { coords: [number, number][] }) {
  const map = useMap()
  useEffect(() => {
    if (coords.length === 0) return
    const bounds = L.latLngBounds(coords.map(c => L.latLng(c[0], c[1])))
    map.fitBounds(bounds, { padding: [80, 80], maxZoom: 14 })
  }, [map, coords])
  return null
}

/* ── Map region fly-to handler (city tabs) ── */
function FlyToCenter({ center, zoom }: { center: [number, number]; zoom: number }) {
  const map = useMap()
  useEffect(() => {
    map.flyTo(center, zoom, { duration: 0.8 })
  }, [map, center, zoom])
  return null
}

/* ── City → lat/lng mapping ── */
const CITY_COORDS: Record<string, [number, number]> = {
  'Birmingham': [52.48, -1.89],
  'London': [51.51, -0.13],
  'Mumbai': [19.08, 72.88],
}

const DEFAULT_ZOOM = 4
const CITY_ZOOM = 12

export function MapPage() {
  const [lots, setLots] = useState<Lot[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [cityFilter, setCityFilter] = useState('All')
  const [selectedLot, setSelectedLot] = useState<Lot | null>(null)
  const [mapCenter, setMapCenter] = useState<[number, number]>([20, 80])
  const [mapZoom, setMapZoom] = useState(DEFAULT_ZOOM)
  const [, setHoveredLot] = useState<string | null>(null)
  const mapRef = useRef<L.Map | null>(null)
  const [allCoords, setAllCoords] = useState<[number, number][]>([])

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await fetchLots()
      setLots(data)
      const coords: [number, number][] = []
      for (const lot of data) {
        if (lot.latitude && lot.longitude && lot.latitude !== 0 && lot.longitude !== 0) {
          coords.push([lot.latitude, lot.longitude])
        }
      }
      setAllCoords(coords)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load map lots')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const cities = ['All', ...new Set(lots.map((l) => l.city).filter(Boolean))]

  // Get coordinates for a lot (prefer API lat/lng, fall back to city lookup)
  const getLotCoords = useCallback((lot: Lot): [number, number] | null => {
    if (lot.latitude && lot.longitude && lot.latitude !== 0 && lot.longitude !== 0) {
      return [lot.latitude, lot.longitude]
    }
    if (lot.city && CITY_COORDS[lot.city]) {
      return CITY_COORDS[lot.city]
    }
    return null
  }, [])

  // Filter lots
  const filtered = cityFilter === 'All' ? lots : lots.filter((l) => l.city === cityFilter)

  // When filter changes, fly to appropriate region
  const handleCityFilter = (city: string) => {
    setCityFilter(city)
    setSelectedLot(null)
    if (city !== 'All' && CITY_COORDS[city]) {
      setMapCenter(CITY_COORDS[city])
      setMapZoom(CITY_ZOOM)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-subtle animate-pulse text-sm">Loading map...</div>
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

  const summaryOcc = lots.length > 0
    ? lots.reduce((s, l) => s + (l.current_occupancy ?? 0), 0) / lots.length
    : 0

  return (
    <div className="flex flex-col h-full">
      {/* ── Header ── */}
      <div className="shrink-0 mb-4">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-[10px] font-mono text-muted-alt tracking-[3px] uppercase mb-2">01 / IoT · Observe</p>
            <h1 className="section-headline">Map</h1>
            <p className="section-body mt-1">Live spatial view of all parking lots</p>
          </div>
          {/* Summary stats */}
          <div className="flex items-center gap-6">
            <div className="text-right">
              <p className="display-number text-[#40d4f0]">{lots.length}</p>
              <p className="text-[9px] font-mono text-muted-alt tracking-wider uppercase">Lots</p>
            </div>
            <div className="text-right">
              <p className="display-number text-gold">{Math.round(summaryOcc)}%</p>
              <p className="text-[9px] font-mono text-muted-alt tracking-wider uppercase">Avg Occupancy</p>
            </div>
            <div className="text-right">
              <p className="display-number text-white">{lots.reduce((s, l) => s + l.total_slots, 0)}</p>
              <p className="text-[9px] font-mono text-muted-alt tracking-wider uppercase">Total Slots</p>
            </div>
          </div>
        </div>

        {/* City filter pills */}
        <div className="flex flex-wrap gap-2 mt-4">
          {cities.map((city) => (
            <button
              key={city}
              onClick={() => handleCityFilter(city)}
              className={`text-[11px] font-mono px-3 py-1.5 rounded tracking-wider uppercase transition-all duration-200 ${
                cityFilter === city
                  ? 'text-[#40d4f0] bg-[rgba(64,212,240,0.1)] border border-[rgba(64,212,240,0.3)]'
                  : 'text-muted-alt border border-[rgba(255,255,255,0.06)] hover:text-white hover:border-[rgba(255,255,255,0.15)]'
              }`}
            >
              {city} {city !== 'All' && `(${lots.filter(l => l.city === city).length})`}
            </button>
          ))}
        </div>
      </div>

      {/* ── Map + Detail Panel ── */}
      <div className="flex-1 flex gap-4 min-h-0">
        {/* Map */}
        <div className={`relative rounded-xl overflow-hidden border border-[rgba(255,255,255,0.06)] transition-all duration-300 ${selectedLot ? 'flex-1' : 'w-full'}`}
          style={{ background: '#04040a' }}>
          <MapContainer
            center={mapCenter}
            zoom={mapZoom}
            zoomControl={false}
            className="w-full h-full"
            ref={mapRef}
            style={{ background: '#04040a' }}
          >
            <ZoomControl position="bottomright" />
            {cityFilter === 'All' ? (
              <FitBoundsOnData coords={allCoords} />
            ) : (
              <FlyToCenter center={mapCenter} zoom={mapZoom} />
            )}

            {/* CartoDB dark tiles */}
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> &copy; <a href="https://carto.com">CARTO</a>'
              url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
            />

            {/* Lot markers */}
            {filtered.map((lot) => {
              const coords = getLotCoords(lot)
              if (!coords) return null
              const occ = lot.current_occupancy ?? 0
              const color = getOccColor(occ)
              const glow = getOccGlow(occ)
              const isSelected = selectedLot?.lot_id === lot.lot_id
              const icon = createMarkerIcon(color, glow, isSelected)

              return (
                <Marker
                  key={lot.lot_id}
                  position={coords}
                  icon={icon}
                  eventHandlers={{
                    click: () => setSelectedLot(lot),
                    mouseover: () => setHoveredLot(lot.lot_id),
                    mouseout: () => setHoveredLot(null),
                  }}
                >
                  <Popup>
                    <div style={{
                      fontFamily:"'DM Mono', monospace",
                      fontSize: '11px',
                      background: '#0e0e1c',
                      color: '#e8e4dc',
                      border: 'none',
                      minWidth: '160px',
                    }}>
                      <div style={{ fontWeight: 600, fontSize: '13px', marginBottom: '4px', fontFamily:"'Syne', sans-serif" }}>
                        {lot.name}
                      </div>
                      <div style={{ color: '#9a97b0' }}>{lot.address}</div>
                      <div style={{ marginTop: '8px', borderTop: '1px solid rgba(255,255,255,0.06)', paddingTop: '8px' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                          <span style={{ color: '#9a97b0' }}>Occupancy</span>
                          <span style={{ color, fontWeight: 500 }}>{occ.toFixed(1)}%</span>
                        </div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                          <span style={{ color: '#9a97b0' }}>Slots</span>
                          <span style={{ color: '#e8e4dc' }}>{lot.total_slots}</span>
                        </div>
                        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                          <span style={{ color: '#9a97b0' }}>Rate</span>
                          <span style={{ color: '#60d4a0', fontWeight: 500 }}>${lot.base_price.toFixed(2)}/hr</span>
                        </div>
                      </div>
                    </div>
                  </Popup>
                </Marker>
              )
            })}
          </MapContainer>

          {/* Map overlay watermark */}
          <div className="absolute bottom-3 left-3 z-[1000] pointer-events-none">
            <span className="text-[8px] font-mono text-[#3a3a5a] tracking-widest uppercase">
              Pragma · IoT Grid
            </span>
          </div>
        </div>

        {/* Lot detail panel (sticky, like landing page pattern) */}
        {selectedLot && (
          <div className="w-full md:w-80 shrink-0 rounded-xl overflow-hidden transition-all duration-300"
            style={{
              background: 'linear-gradient(135deg, #0e0e1c 0%, #0a0a18 100%)',
              border: '1px solid rgba(255,255,255,0.06)',
              boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
            }}>
            <div className="p-5">
              <button
                onClick={() => setSelectedLot(null)}
                className="float-right text-sm font-mono text-[#7a8aaa] hover:text-white transition-colors w-6 h-6 flex items-center justify-center rounded hover:bg-[rgba(255,255,255,0.06)]"
              >
                ✕
              </button>

              {/* Section number */}
              <p className="text-[9px] font-mono text-muted-alt tracking-[3px] uppercase mb-1">Lot Detail</p>

              {/* Lot name */}
              <h3 className="font-heading text-lg font-semibold text-white mb-1">{selectedLot.name}</h3>
              <p className="text-[11px] font-mono text-muted-alt mb-4">{selectedLot.address}</p>

              {/* Occupancy meter (like landing page rush-occ-track) */}
              {selectedLot.current_occupancy !== undefined && (
                <div className="mb-5">
                  <div className="flex justify-between text-[9px] font-mono text-muted-alt mb-1.5">
                    <span>OCCUPANCY</span>
                    <span style={{ color: getOccColor(selectedLot.current_occupancy) }}>
                      {selectedLot.current_occupancy.toFixed(1)}%
                    </span>
                  </div>
                  <div className="h-2 bg-[rgba(255,255,255,0.04)] relative overflow-hidden rounded-full">
                    <div className="h-full rounded-full transition-all duration-500"
                      style={{
                        width: `${Math.min(selectedLot.current_occupancy, 100)}%`,
                        background: getOccColor(selectedLot.current_occupancy),
                        boxShadow: `0 0 8px ${getOccGlow(selectedLot.current_occupancy)}`,
                      }} />
                  </div>
                  {selectedLot.current_occupancy > 0 && (
                    <div className="mt-0.5 text-right text-[8px] font-mono text-[#5a6a8a]">{selectedLot.current_occupancy.toFixed(1)}% live</div>
                  )}
                </div>
              )}

              {/* Key metrics (like rush-meta grid) */}
              <div className="grid grid-cols-2 gap-2 mb-4">
                <div className="border border-[rgba(255,255,255,0.06)] p-2.5">
                  <p className="text-[8px] font-mono text-muted-alt uppercase tracking-wider mb-1">Total Slots</p>
                  <p className="font-mono text-sm font-medium text-white">{selectedLot.total_slots}</p>
                </div>
                <div className="border border-[rgba(255,255,255,0.06)] p-2.5">
                  <p className="text-[8px] font-mono text-muted-alt uppercase tracking-wider mb-1">Base Rate</p>
                  <p className="font-mono text-sm font-medium" style={{ color: '#60d4a0' }}>${selectedLot.base_price.toFixed(2)}</p>
                </div>
                <div className="border border-[rgba(255,255,255,0.06)] p-2.5">
                  <p className="text-[8px] font-mono text-muted-alt uppercase tracking-wider mb-1">City</p>
                  <p className="font-mono text-sm font-medium text-white">{selectedLot.city}</p>
                </div>
                <div className="border border-[rgba(255,255,255,0.06)] p-2.5">
                  <p className="text-[8px] font-mono text-muted-alt uppercase tracking-wider mb-1">Price Cap</p>
                  <p className="font-mono text-sm font-medium" style={{ color: '#f0c040' }}>${selectedLot.price_cap?.toFixed(2) || '—'}</p>
                </div>
              </div>

              {/* Available / Occupied */}
              {selectedLot.current_occupancy !== undefined && (
                <div className="border border-[rgba(255,255,255,0.06)] p-2.5 mb-2">
                  <p className="text-[8px] font-mono text-muted-alt uppercase tracking-wider mb-1">Status</p>
                  <p className="text-xs font-mono text-white">
                    {Math.round(selectedLot.total_slots * (selectedLot.current_occupancy / 100))} occupied · {Math.round(selectedLot.total_slots * (1 - selectedLot.current_occupancy / 100))} free
                  </p>
                </div>
              )}

              {/* Narrative story */}
              <div className="mt-4 p-3 rounded border border-[rgba(255,255,255,0.04)] bg-[rgba(0,0,0,0.2)]">
                <p className="text-[10px] font-mono text-muted-alt italic leading-relaxed">
                  {selectedLot.current_occupancy && selectedLot.current_occupancy > 75
                    ? `IoT sensors reporting high density at ${selectedLot.name}. RL agent adjusting rate toward cap. Actuator bridge signaling congestion.`
                    : selectedLot.current_occupancy && selectedLot.current_occupancy > 40
                    ? `${selectedLot.name} at moderate occupancy. ML forecast predicts ${selectedLot.current_occupancy > 50 ? 'continued filling' : 'stable demand'} over next 15 min.`
                    : `${selectedLot.name} is quiet. ${selectedLot.total_slots} slots available. Dynamic pricing at base rate.`
                  }
                </p>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
