import { useState, useEffect, useCallback } from 'react'
import { fetchMicroSlots, fetchLots, type MicroSlot, type Lot } from '../../api/adminClient'
import { getErrorMessage } from '../../utils/format'

const GOLD = '#f0c040'
const GOLD_DIM = 'rgba(240,192,64,0.12)'

const stateColors: Record<string, string> = {
  available: '#40d4f0',
  occupied: '#f0c040',
  reserved: '#60d4a0',
  prebooked: '#a060f0',
  maintenance: '#f04060',
}

const stateLabels: Record<string, string> = {
  available: 'Open',
  occupied: 'In Use',
  reserved: 'Reserved',
  prebooked: 'Pre-booked',
  maintenance: 'Maint.',
}

export function MicroSlotsPage() {
  const [lots, setLots] = useState<Lot[]>([])
  const [lotsError, setLotsError] = useState<string | null>(null)
  const [selectedLot, setSelectedLot] = useState('')
  const [slots, setSlots] = useState<MicroSlot[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [hoverSlot, setHoverSlot] = useState<MicroSlot | null>(null)
  const [inspectSlot, setInspectSlot] = useState<MicroSlot | null>(null)
  const [search, setSearch] = useState('')
  const [filterState, setFilterState] = useState<string>('all')

  // Load lots list
  useEffect(() => {
    let cancelled = false
    fetchLots()
      .then((data) => {
        if (cancelled) return
        setLots(data)
        if (data.length > 0) setSelectedLot(data[0].lot_id)
      })
      .catch((err: unknown) => {
        if (!cancelled) setLotsError(getErrorMessage(err, 'Failed to load lots'))
      })
    return () => { cancelled = true }
  }, [])

  // Load slots for selected lot with auto-refresh
  const loadSlots = useCallback(async () => {
    if (!selectedLot) return
    try {
      setError(null)
      const data = await fetchMicroSlots(selectedLot)
      setSlots(data)
    } catch (err: unknown) {
      setError(getErrorMessage(err, 'Failed to load slots'))
    } finally {
      setLoading(false)
    }
  }, [selectedLot])

  useEffect(() => {
    if (!selectedLot) return
    setLoading(true)
    setSearch('')
    setFilterState('all')
    loadSlots()
    const interval = setInterval(loadSlots, 15000)
    return () => clearInterval(interval)
  }, [selectedLot, loadSlots])

  const selectedLotData = lots.find(l => l.lot_id === selectedLot)

  // Filter slots by search and state
  const filteredSlots = slots.filter((s) => {
    if (filterState !== 'all' && s.state !== filterState) return false
    if (search) {
      const label = `${s.row_label || ''}${s.position || ''}`.toLowerCase()
      if (!label.includes(search.toLowerCase())) return false
    }
    return true
  })

  const stats = {
    total: slots.length,
    available: slots.filter(s => s.state === 'available').length,
    occupied: slots.filter(s => s.state === 'occupied').length,
    reserved: slots.filter(s => s.state === 'reserved').length,
    prebooked: slots.filter(s => s.state === 'prebooked').length,
  }

  if (lotsError) {
    return (
      <div className="space-y-6">
        <div>
          <p className="text-[10px] font-mono text-muted-alt tracking-[3px] uppercase mb-2">04 / Ledger &amp; Slots</p>
          <h1 className="section-headline">Micro Slots</h1>
        </div>
        <div className="rounded-xl p-6" style={{ background: 'rgba(240,64,64,0.06)', border: '1px solid rgba(240,64,64,0.2)' }}>
          <p className="text-rose text-[11px] font-mono">Failed to load parking lots: {lotsError}</p>
        </div>
      </div>
    )
  }

  if (loading && slots.length === 0) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-subtle animate-pulse text-sm">Loading slots...</div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* ── Header ── */}
      <div>
        <p className="text-[10px] font-mono text-muted-alt tracking-[3px] uppercase mb-2">04 / Ledger &amp; Slots</p>
        <h1 className="section-headline">Micro Slots</h1>
        <p className="section-body mt-1">Individual slot status, occupancy, and event registration</p>
      </div>

      {/* ── Controls row ── */}
      <div className="flex items-center gap-4 flex-wrap">
        <div className="relative">
          <select
            value={selectedLot}
            onChange={(e) => setSelectedLot(e.target.value)}
            className="bg-[#0e0e1c] border border-[rgba(255,255,255,0.06)] rounded-lg px-4 py-2 text-xs font-mono text-white/80 focus:outline-none appearance-none pr-8"
            style={{ borderColor: selectedLot ? `${GOLD}25` : 'rgba(255,255,255,0.06)' }}
          >
            {lots.length === 0 && <option value="">No lots available</option>}
            {lots.map((lot) => (
              <option key={lot.lot_id} value={lot.lot_id}>{lot.name}</option>
            ))}
          </select>
          <span className="absolute right-3 top-1/2 -translate-y-1/2 text-[8px] text-subtle">▼</span>
        </div>

        {/* Search */}
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search slot (e.g. B12)..."
          className="bg-[#0e0e1c] border border-[rgba(255,255,255,0.06)] rounded-lg px-3 py-2 text-xs font-mono text-white/80 focus:outline-none w-36 placeholder-[#4a5a7a]"
        />

        {/* State filter */}
        <select
          value={filterState}
          onChange={(e) => setFilterState(e.target.value)}
          className="bg-[#0e0e1c] border border-[rgba(255,255,255,0.06)] rounded-lg px-3 py-2 text-xs font-mono text-white/80 focus:outline-none appearance-none pr-6"
        >
          <option value="all">All States</option>
          {Object.entries(stateLabels).map(([state, label]) => (
            <option key={state} value={state}>{label}</option>
          ))}
        </select>

        {/* Quick stats */}
        <div className="flex gap-3 text-[10px] font-mono">
          <span className="text-muted-alt">{stats.total} slots</span>
          <span className="text-[#40d4f0]">{stats.available} free</span>
          <span className="text-gold">{stats.occupied} used</span>
          {stats.reserved > 0 && <span className="text-sage">{stats.reserved} reserved</span>}
          {stats.prebooked > 0 && <span className="text-[#a060f0]">{stats.prebooked} prebooked</span>}
          {search && <span className="text-[#f0c040]">{filteredSlots.length} matching</span>}
        </div>
      </div>

      {/* ── Error state ── */}
      {error && (
        <div className="rounded-xl p-4 flex items-center gap-3"
          style={{ background: 'rgba(240,64,64,0.06)', border: '1px solid rgba(240,64,64,0.2)' }}>
          <span className="text-rose text-sm">⚠</span>
          <span className="text-rose text-[11px] font-mono flex-1">Failed to load slots: {error}</span>
          <button onClick={loadSlots}
            className="text-[11px] font-mono px-3 py-1.5 rounded-lg transition-colors"
            style={{ background: 'rgba(240,64,64,0.1)', color: '#f04060', border: '1px solid rgba(240,64,64,0.2)' }}>
            Retry
          </button>
        </div>
      )}

      {/* ── Legend ── */}
      <div className="flex gap-4 text-[9px] font-mono">
        {Object.entries(stateColors).map(([state, color]) => (
          <button key={state} onClick={() => setFilterState(filterState === state ? 'all' : state)}
            className="flex items-center gap-1.5 transition-opacity hover:opacity-80"
            style={{ opacity: filterState !== 'all' && filterState !== state ? 0.4 : 1 }}>
            <div className="w-2 h-2 rounded-sm" style={{ backgroundColor: color }} />
            <span className="text-subtle uppercase tracking-wider">{stateLabels[state] || state}</span>
          </button>
        ))}
        {filterState !== 'all' && (
          <button onClick={() => setFilterState('all')}
            className="text-[#f0c040] underline underline-offset-2">
            Clear filter
          </button>
        )}
      </div>

      {/* ── Slot grid ── */}
      <div className="card-dark relative rounded-xl p-6 overflow-hidden">
        {/* CRT grid overlay */}
        <div className="absolute inset-0 pointer-events-none opacity-[0.03]"
          style={{
            backgroundImage: `
              linear-gradient(rgba(240,192,64,0.5) 1px, transparent 1px),
              linear-gradient(90deg, rgba(240,192,64,0.5) 1px, transparent 1px)
            `,
            backgroundSize: '40px 40px',
          }} />

        {/* Lot occupancy bar */}
        {selectedLotData?.current_occupancy !== undefined && (
          <div className="mb-5">
            <div className="flex justify-between text-[9px] font-mono text-muted-alt mb-1">
              <span>OCCUPANCY</span>
              <span style={{ color: GOLD }}>{selectedLotData.current_occupancy.toFixed(1)}%</span>
            </div>
            <div className="h-1.5 bg-[rgba(255,255,255,0.04)] rounded-full overflow-hidden">
              <div className="h-full rounded-full transition-all duration-500"
                style={{
                  width: `${Math.min(selectedLotData.current_occupancy, 100)}%`,
                  background: `linear-gradient(90deg, ${GOLD}, #f0a030)`,
                  boxShadow: `0 0 8px ${GOLD_DIM}`,
                }} />
            </div>
          </div>
        )}

        {/* Slot grid */}
        {filteredSlots.length === 0 ? (
          <div className="text-center py-12">
            <p className="text-xs text-subtle font-mono">
              {search
                ? `No slots matching "₹{search}"`
                : filterState !== 'all'
                ? `No slots with state "₹{stateLabels[filterState] || filterState}"`
                : 'No slots available'}
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-5 sm:grid-cols-8 md:grid-cols-10 gap-2 relative z-[1]">
            {filteredSlots.map((slot) => {
              const st = slot.state || 'available'
              const color = stateColors[st] || '#40d4f0'
              const isInspected = inspectSlot?.id === slot.id
              const isHovered = hoverSlot?.id === slot.id
              return (
                <div
                  key={slot.id}
                  role="button"
                  tabIndex={0}
                  onClick={() => setInspectSlot(isInspected ? null : slot)}
                  onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setInspectSlot(isInspected ? null : slot) } }}
                  className="aspect-square rounded-lg flex flex-col items-center justify-center text-[9px] font-mono font-medium transition-all duration-150 relative group cursor-pointer"
                  style={{
                    backgroundColor: `${color}12`,
                    color,
                    border: `1px solid ${isHovered || isInspected ? color : `${color}25`}`,
                    boxShadow: isInspected
                      ? `0 0 16px ${color}40, inset 0 0 8px ${color}15`
                      : isHovered ? `0 0 12px ${color}30` : 'none',
                    transform: isInspected ? 'scale(1.05)' : 'none',
                  }}
                  onMouseEnter={() => setHoverSlot(slot)}
                  onMouseLeave={() => setHoverSlot(null)}
                  title={`${slot.row_label}${slot.position} — ${st}`}
                >
                  <span>{slot.row_label}{slot.position}</span>
                  <span className="text-[6px] opacity-60 mt-0.5">{stateLabels[st] || st}</span>
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* ── Slot inspection modal ── */}
      {inspectSlot && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60"
          onClick={() => setInspectSlot(null)}
          onKeyDown={(e) => { if (e.key === 'Escape') setInspectSlot(null) }}>
          <div className="rounded-xl p-5 w-full max-w-xs mx-4" onClick={(e) => e.stopPropagation()}
            style={{ background: '#0c0c20', border: '1px solid rgba(255,255,255,0.08)' }}>
            <div className="text-center mb-4">
              <div className="text-[20px] font-mono font-bold text-white mb-1">
                {inspectSlot.row_label}{inspectSlot.position}
              </div>
              <div className="text-[11px] font-mono" style={{ color: stateColors[inspectSlot.state || 'available'] || '#40d4f0' }}>
                {stateLabels[inspectSlot.state || 'available'] || inspectSlot.state}
              </div>
            </div>

            <div className="space-y-2 text-[10px] font-mono">
              <div className="flex justify-between">
                <span className="text-subtle">Slot ID</span>
                <span className="text-white/80">{inspectSlot.id}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-subtle">Type</span>
                <span className="text-white/80 capitalize">{inspectSlot.slot_type || 'standard'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-subtle">Lot</span>
                <span className="text-white/80">{selectedLotData?.name || inspectSlot.lot_id}</span>
              </div>
              {inspectSlot.probability !== undefined && (
                <div className="flex justify-between">
                  <span className="text-subtle">Probability</span>
                  <span className="text-white/80">{(inspectSlot.probability * 100).toFixed(0)}%</span>
                </div>
              )}
            </div>

            <button onClick={() => setInspectSlot(null)}
              className="w-full mt-4 py-2 rounded-lg text-xs font-semibold transition-all"
              style={{ background: `${GOLD}20`, color: GOLD, border: `1px solid ${GOLD_DIM}` }}>
              Close
            </button>
          </div>
        </div>
      )}

      {/* ── Summary narrative ── */}
      <div className="p-3 rounded-lg text-[10px] font-mono italic leading-relaxed"
        style={{ background: `${GOLD}08`, border: `1px solid ${GOLD_DIM}` }}>
        <span style={{ color: GOLD }}>&gt;</span>{' '}
        <span className="text-muted-alt">
          {search
            ? `Showing ${filteredSlots.length} of ${stats.total} slots matching "₹{search}".`
            : filterState !== 'all'
            ? `Showing ${filteredSlots.length} ${stateLabels[filterState] || filterState} slots of ${stats.total}.`
            : stats.available > 0
            ? `${stats.available} of ${stats.total} slots open. ${selectedLotData?.name || ''} at ${selectedLotData?.current_occupancy?.toFixed(1) || '?'}% occupancy.`
            : stats.occupied > 0
            ? `All ${stats.total} slots filled at ${selectedLotData?.name || ''}. MARL overflow protocol standing by.`
            : `Slot grid for ${selectedLotData?.name || 'selected lot'} — ${stats.total} registered positions.`
          }
          {stats.prebooked > 0 && ` ${stats.prebooked} slot${stats.prebooked > 1 ? 's' : ''} prebooked.`}
          {stats.reserved > 0 && ` ${stats.reserved} reservation${stats.reserved > 1 ? 's' : ''} active.`}
        </span>
      </div>
    </div>
  )
}
