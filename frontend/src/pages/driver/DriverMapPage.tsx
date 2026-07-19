import { useState, useEffect, useCallback } from 'react'
import { MapContainer, TileLayer, Marker, Popup, useMap, ZoomControl, Polyline, CircleMarker, useMapEvents } from 'react-leaflet'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { fetchDriverLots, fetchRoute, type DriverLot, type RoutePointT, type RouteResponseT } from '../../api/driverClient'
import { fetchResidentialMap, type ResidentialMapSlot } from '../../api/adminClient'

/* ── Fix default Leaflet marker icons ── */
delete (L.Icon.Default.prototype as any)._getIconUrl
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
})

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

/* ── Auto-fit bounds after lots load ── */
function FitBoundsOnData({ coords }: { coords: [number, number][] }) {
  const map = useMap()
  useEffect(() => {
    if (coords.length === 0) return
    const bounds = L.latLngBounds(coords.map((c) => L.latLng(c[0], c[1])))
    map.fitBounds(bounds, { padding: [80, 80], maxZoom: 14 })
  }, [map, coords])
  return null
}

/* ── Drop-pin handler — must be a descendant of <MapContainer> ── */
function ClickToSetOrigin({
  picking,
  onPick,
}: {
  picking: boolean
  onPick: (p: { lat: number; lng: number }) => void
}) {
  useMapEvents({
    click(e) {
      if (!picking) return
      onPick({ lat: e.latlng.lat, lng: e.latlng.lng })
    },
  })
  return null
}

const MUMBAI_CENTER: [number, number] = [19.076, 72.877]
const DEFAULT_ZOOM = 12

export function DriverMapPage() {
  const [lots, setLots] = useState<DriverLot[]>([])
  const [residential, setResidential] = useState<ResidentialMapSlot[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [origin, setOrigin] = useState<RoutePointT | null>(null)
  const [destination, setDestination] = useState<DriverLot | null>(null)
  const [route, setRoute] = useState<RouteResponseT | null>(null)
  const [routeErr, setRouteErr] = useState<string | null>(null)
  const [routeLoading, setRouteLoading] = useState(false)
  const [mode, setMode] = useState<'drive' | 'walk'>('drive')
  const [picking, setPicking] = useState(false)
  const [allCoords, setAllCoords] = useState<[number, number][]>([])
  const [layers, setLayers] = useState({ lots: true, shared: true })

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await fetchDriverLots()
      setLots(data)
      const coords: [number, number][] = []
      for (const lot of data) {
        if (lot.latitude && lot.longitude && lot.latitude !== 0 && lot.longitude !== 0) {
          coords.push([lot.latitude, lot.longitude])
        }
      }
      setAllCoords(coords)
      try {
        const res = await fetchResidentialMap()
        setResidential(res)
      } catch {
        setResidential([])
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load map')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  // Compute route whenever origin + destination + mode change
  useEffect(() => {
    if (!origin || !destination) {
      setRoute(null)
      return
    }
    if (!destination.latitude || !destination.longitude) return
    let cancelled = false
    setRouteLoading(true)
    setRouteErr(null)
    fetchRoute(origin, { lat: destination.latitude, lng: destination.longitude }, mode)
      .then((res) => {
        if (cancelled) return
        setRoute(res)
        if (!res.found) setRouteErr(res.message || 'No route found')
      })
      .catch((err) => {
        if (cancelled) return
        setRouteErr(err instanceof Error ? err.message : 'Routing failed')
      })
      .finally(() => {
        if (!cancelled) setRouteLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [origin, destination, mode])

  const useMyLocation = () => {
    if (!navigator.geolocation) {
      setRouteErr('Geolocation is not available in this browser')
      return
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => setOrigin({ lat: pos.coords.latitude, lng: pos.coords.longitude }),
      () => setRouteErr('Could not get your location — tap the map to drop a pin instead'),
      { enableHighAccuracy: true, timeout: 10000 },
    )
  }

  const routePath: [number, number][] = route?.geometry.map((p) => [p.lat, p.lng]) ?? []

  const formatDuration = (s: number) => {
    const m = Math.round(s / 60)
    if (m < 60) return `${m} min`
    return `${Math.floor(m / 60)}h ${m % 60}m`
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-subtle animate-pulse text-sm">Loading map…</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-64 flex-col gap-3">
        <div className="text-rose text-sm font-mono">{error}</div>
        <button onClick={load}
          className="text-[12px] font-mono px-3 py-2 rounded-lg transition-all"
          style={{ background: 'rgba(240,64,96,0.08)', color: '#f04060', border: '1px solid rgba(240,64,96,0.2)' }}>
          Retry
        </button>
      </div>
    )
  }

  const sharedCount = residential.filter((r) => r.is_shared).length

  return (
    <div className="flex flex-col h-full">
      <div className="shrink-0 mb-4">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-[10px] font-mono text-muted-alt tracking-[3px] uppercase mb-2">Route · Mumbai</p>
            <h1 className="section-headline">Map</h1>
            <p className="section-body mt-1">Plan your drive from your location to a parking lot</p>
          </div>
          <div className="text-right">
            <p className="display-number text-[#00d4ff]">{lots.length}</p>
            <p className="text-[9px] font-mono text-muted-alt tracking-wider uppercase">Lots</p>
          </div>
        </div>

        {/* Controls */}
        <div className="flex flex-wrap items-center gap-2 mt-4">
          <button onClick={useMyLocation}
            className="text-[11px] font-mono px-3 py-1.5 rounded tracking-wider uppercase transition-all"
            style={{ color: origin ? '#00d4ff' : '#cfd6e6', background: 'rgba(0,212,255,0.08)', border: '1px solid rgba(0,212,255,0.25)' }}>
            ◎ Use my location
          </button>
          <button onClick={() => setPicking((p) => !p)}
            className="text-[11px] font-mono px-3 py-1.5 rounded tracking-wider uppercase transition-all"
            style={picking
              ? { color: '#f0c040', background: 'rgba(240,192,64,0.1)', border: '1px solid rgba(240,192,64,0.4)' }
              : { color: '#cfd6e6', border: '1px solid rgba(255,255,255,0.1)' }}>
            {picking ? 'Tap map to drop pin…' : '◉ Drop origin pin'}
          </button>

          {/* Mode toggle */}
          <div className="flex items-center rounded overflow-hidden border border-[rgba(255,255,255,0.1)]">
            {(['drive', 'walk'] as const).map((m) => (
              <button key={m} onClick={() => setMode(m)}
                className="text-[11px] font-mono px-3 py-1.5 tracking-wider uppercase transition-all"
                style={mode === m
                  ? { color: '#07070d', background: '#00c785', fontWeight: 600 }
                  : { color: '#9a97b0' }}>
                {m}
              </button>
            ))}
          </div>

          {origin && destination && (
            <button onClick={() => { setOrigin(null); setDestination(null); setRoute(null) }}
              className="text-[11px] font-mono px-3 py-1.5 rounded tracking-wider uppercase transition-all"
              style={{ color: '#f04060', border: '1px solid rgba(240,64,96,0.3)' }}>
              Clear
            </button>
          )}
        </div>

        {/* Origin / destination readout + route summary */}
        <div className="flex flex-wrap items-center gap-3 mt-3 text-[11px] font-mono">
          <span style={{ color: origin ? '#00d4ff' : '#5a6a8a' }}>
            ● Origin: {origin ? `${origin.lat.toFixed(4)}, ${origin.lng.toFixed(4)}` : 'not set'}
          </span>
          <span style={{ color: destination ? '#00c785' : '#5a6a8a' }}>
            ● Destination: {destination ? destination.name : 'tap a lot'}
          </span>
          {routeLoading && <span style={{ color: '#f0c040' }}>Routing…</span>}
          {route && route.found && (
            <span style={{ color: '#60d4a0' }}>
              {Math.round(route.distance_m)} m · {formatDuration(route.duration_s)}
            </span>
          )}
          {routeErr && <span style={{ color: '#f04060' }}>{routeErr}</span>}
        </div>

        {/* Layer toggles */}
        <div className="flex flex-wrap gap-2 mt-3">
          {([
            ['lots', 'Lots', '#00d4ff'],
            ['shared', `Shared (${sharedCount})`, '#f04060'],
          ] as const).map(([key, label, color]) => (
            <button key={key}
              onClick={() => setLayers((p) => ({ ...p, [key]: !p[key] }))}
              className="text-[10px] font-mono px-2.5 py-1 rounded tracking-wider uppercase transition-all duration-200 flex items-center gap-1.5"
              style={layers[key]
                ? { color, background: 'rgba(255,255,255,0.04)', border: `1px solid ${color}55` }
                : { color: '#5a6a8a', border: '1px solid rgba(255,255,255,0.06)' }}>
              <span className="w-2 h-2 rounded-full" style={{ background: layers[key] ? color : '#3a3a5a' }} />
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Map */}
      <div className="flex-1 flex gap-4 min-h-0">
        <div className="relative flex-1 rounded-xl overflow-hidden border border-[rgba(255,255,255,0.06)]"
          style={{ background: '#04040a' }}>
          <MapContainer
            center={MUMBAI_CENTER}
            zoom={DEFAULT_ZOOM}
            zoomControl={false}
            className="w-full h-full"
            style={{ background: '#04040a' }}
          >
            <ZoomControl position="bottomright" />
            <FitBoundsOnData coords={allCoords} />
            <ClickToSetOrigin picking={picking} onPick={(p) => { setOrigin(p); setPicking(false) }} />

            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> &copy; <a href="https://carto.com">CARTO</a>'
              url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
            />

            {/* Origin pin */}
            {origin && (
              <CircleMarker center={[origin.lat, origin.lng]} radius={8}
                pathOptions={{ color: '#00d4ff', fillColor: '#00d4ff', fillOpacity: 0.9, weight: 2 }} />
            )}

            {/* Commercial lot markers */}
            {layers.lots && lots.map((lot) => {
              if (!lot.latitude || !lot.longitude) return null
              const isDest = destination?.lot_id === lot.lot_id
              const icon = createMarkerIcon('#00d4ff', 'rgba(0,212,255,0.5)', isDest)
              return (
                <Marker key={lot.lot_id} position={[lot.latitude, lot.longitude]} icon={icon}
                  eventHandlers={{ click: () => setDestination(lot) }}>
                  <Popup>
                    <div style={{ fontFamily: "'DM Mono', monospace", fontSize: '11px', background: '#0e0e1c', color: '#e8e4dc', border: 'none', minWidth: '170px' }}>
                      <div style={{ fontWeight: 600, fontSize: '13px', marginBottom: '4px', fontFamily: "'Syne', sans-serif" }}>{lot.name}</div>
                      <div style={{ color: '#9a97b0' }}>{lot.address}</div>
                      <div style={{ marginTop: '8px', borderTop: '1px solid rgba(255,255,255,0.06)', paddingTop: '8px' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                          <span style={{ color: '#9a97b0' }}>Free</span>
                          <span style={{ color: '#60d4a0', fontWeight: 500 }}>{lot.available_spots}</span>
                        </div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                          <span style={{ color: '#9a97b0' }}>Rate</span>
                          <span style={{ color: '#60d4a0', fontWeight: 500 }}>₹{lot.dynamic_price.toFixed(2)}/hr</span>
                        </div>
                        <button onClick={() => setDestination(lot)}
                          style={{ marginTop: '6px', width: '100%', background: '#00c785', color: '#07070d', border: 'none', borderRadius: '6px', padding: '5px', fontFamily: "'DM Mono', monospace", fontSize: '11px', fontWeight: 600, cursor: 'pointer' }}>
                          Route here
                        </button>
                      </div>
                    </div>
                  </Popup>
                </Marker>
              )
            })}

            {/* Shared residential slots */}
            {layers.shared && residential
              .filter((r) => r.is_shared)
              .map((r) => (
                <CircleMarker key={`shr-${r.slot_id}`} center={[r.latitude, r.longitude]} radius={7}
                  pathOptions={{ color: '#f04060', fillColor: '#f04060', fillOpacity: 0.85 }}>
                  <Popup>
                    <div className="text-xs">
                      <p className="font-bold mb-1">Shared Slot #{r.slot_id}</p>
                      <p className="font-mono">Spatial ID: {r.spatial_id}</p>
                      <p>Owner: {r.resident_name ?? '—'}</p>
                      <p>Available: {r.available_from ?? '—'} → {r.available_until ?? '—'}</p>
                      <p>Price: ₹{r.price_per_hour ?? 0}/hr</p>
                    </div>
                  </Popup>
                </CircleMarker>
              ))}

            {/* Route polyline */}
            {routePath.length > 1 && (
              <Polyline positions={routePath}
                pathOptions={{ color: '#00c785', weight: 5, opacity: 0.9 }} />
            )}
          </MapContainer>

          <div className="absolute bottom-3 left-3 z-[1000] pointer-events-none">
            <span className="text-[8px] font-mono text-[#3a3a5a] tracking-widest uppercase">Pragma · Routing</span>
          </div>
        </div>
      </div>
    </div>
  )
}
