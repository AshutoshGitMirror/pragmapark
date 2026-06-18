import { useState, useEffect } from 'react'
import { fetchMicroSlots, fetchLots, type MicroSlot, type Lot } from '../../api/adminClient'

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
  const [selectedLot, setSelectedLot] = useState('')
  const [slots, setSlots] = useState<MicroSlot[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [hoverSlot, setHoverSlot] = useState<MicroSlot | null>(null)

  useEffect(() => {
    let mounted = true
    fetchLots().then((data) => {
      if (mounted) {
        setLots(data)
        if (data.length > 0) setSelectedLot(data[0].lot_id)
      }
    })
    return () => { mounted = false }
  }, [])

  useEffect(() => {
    if (!selectedLot) return
    let mounted = true
    setLoading(true)
    setError(null)
    fetchMicroSlots(selectedLot).then((data) => {
      if (mounted) { setSlots(data); setLoading(false) }
    }).catch((err) => {
      if (mounted) { setLoading(false); setError(err?.message || 'Failed to load slots') }
    })
    return () => { mounted = false }
  }, [selectedLot])

  const selectedLotData = lots.find(l => l.lot_id === selectedLot)
  const stats = {
    total: slots.length,
    available: slots.filter(s => s.state === 'available').length,
    occupied: slots.filter(s => s.state === 'occupied').length,
    reserved: slots.filter(s => s.state === 'reserved').length,
    prebooked: slots.filter(s => s.state === 'prebooked').length,
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-subtle animate-pulse text-sm">Loading slots...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="space-y-6">
        <div>
          <p className="text-[10px] font-mono text-muted-alt tracking-[3px] uppercase mb-2">04 / Ledger &amp; Slots</p>
          <h1 className="section-headline">Micro Slots</h1>
        </div>
        <div className="rounded-xl p-6" style={{ background: 'rgba(240,64,64,0.06)', border: '1px solid rgba(240,64,64,0.2)' }}>
          <div className="flex items-center gap-3 mb-3">
            <span className="text-rose text-sm">⚠</span>
            <span className="text-rose text-[11px] font-mono">Failed to load slots</span>
          </div>
          <p className="text-[10px] font-mono text-muted-alt mb-4">{error}</p>
          <button
            onClick={() => {
              setError(null)
              setLoading(true)
              fetchMicroSlots(selectedLot).then((data) => {
                setSlots(data); setLoading(false)
              }).catch((err) => {
                setLoading(false); setError(err?.message || 'Retry failed')
              })
            }}
            className="text-[10px] font-mono px-3 py-1.5 rounded-lg transition-colors"
            style={{ background: 'rgba(240,64,64,0.1)', color: '#f04060', border: '1px solid rgba(240,64,64,0.2)' }}
          >
            Retry
          </button>
        </div>
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
            {lots.map((lot) => (
              <option key={lot.lot_id} value={lot.lot_id}>{lot.name}</option>
            ))}
          </select>
          <span className="absolute right-3 top-1/2 -translate-y-1/2 text-[8px] text-subtle">▼</span>
        </div>

        {/* Quick stats */}
        <div className="flex gap-3 text-[10px] font-mono">
          <span className="text-muted-alt">{stats.total} slots</span>
          <span className="text-[#40d4f0]">{stats.available} free</span>
          <span className="text-gold">{stats.occupied} used</span>
          {stats.reserved > 0 && <span className="text-sage">{stats.reserved} reserved</span>}
          {stats.prebooked > 0 && <span className="text-[#a060f0]">{stats.prebooked} prebooked</span>}
        </div>
      </div>

      {/* ── Legend ── */}
      <div className="flex gap-4 text-[9px] font-mono">
        {Object.entries(stateColors).map(([state, color]) => (
          <div key={state} className="flex items-center gap-1.5">
            <div className="w-2 h-2 rounded-sm" style={{ backgroundColor: color }} />
            <span className="text-subtle uppercase tracking-wider">{stateLabels[state] || state}</span>
          </div>
        ))}
      </div>

      {/* ── Slot grid with CRT background ── */}
      <div className="card-dark relative rounded-xl p-6 overflow-hidden"
        >
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
        <div className="grid grid-cols-5 sm:grid-cols-8 md:grid-cols-10 gap-2 relative z-[1]">
          {slots.map((slot) => {
            const st = slot.state || 'available'
            const color = stateColors[st] || '#40d4f0'
            return (
              <div
                key={slot.id}
                className="aspect-square rounded-lg flex flex-col items-center justify-center text-[9px] font-mono font-medium transition-all duration-150 relative group"
                style={{
                  backgroundColor: `${color}12`,
                  color,
                  border: `1px solid ${color}25`,
                  boxShadow: hoverSlot?.id === slot.id ? `0 0 12px ${color}30` : 'none',
                }}
                onMouseEnter={() => setHoverSlot(slot)}
                onMouseLeave={() => setHoverSlot(null)}
                title={`${slot.row_label}${slot.position} — ${st} (${((slot.probability || 0) * 100).toFixed(0)}%)`}
              >
                <span>{slot.row_label}{slot.position}</span>
                <span className="text-[6px] opacity-60 mt-0.5">{stateLabels[st] || st}</span>

                {/* Hover tooltip */}
                {hoverSlot?.id === slot.id && (
                  <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 z-10 pointer-events-none"
                    style={{ minWidth: '120px' }}>
                    <div className="rounded-lg p-2 text-[9px] font-mono"
                      style={{
                        background: '#0e0e1c',
                        border: '1px solid rgba(255,255,255,0.08)',
                        boxShadow: '0 4px 16px rgba(0,0,0,0.5)',
                      }}>
                      <div className="text-white font-semibold mb-1">{slot.row_label}{slot.position}</div>
                      <div style={{ color }} className="capitalize mb-0.5">{st}</div>
                      <div className="text-subtle">
                        Prob: {((slot.probability || 0) * 100).toFixed(0)}%
                      </div>
                      <div className="text-subtle">
                        Type: {slot.slot_type || 'standard'}
                      </div>
                    </div>
                    <div className="w-2 h-2 absolute top-full left-1/2 -translate-x-1/2 -mt-1 rotate-45"
                      style={{ background: '#0e0e1c', border: '1px solid rgba(255,255,255,0.08)', borderTop: 'none', borderLeft: 'none' }} />
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </div>

      {/* ── Summary narrative ── */}
      <div className="p-3 rounded-lg text-[10px] font-mono italic leading-relaxed"
        style={{ background: `${GOLD}08`, border: `1px solid ${GOLD_DIM}` }}>
        <span style={{ color: GOLD }}>&gt;</span>{' '}
        <span className="text-muted-alt">
          {stats.available > 0
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
