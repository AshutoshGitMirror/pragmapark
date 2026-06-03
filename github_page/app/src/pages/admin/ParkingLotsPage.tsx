import { useState, useEffect } from 'react'
import { fetchLots, createLot, deleteLot, type Lot } from '../../api/adminClient'

export function ParkingLotsPage() {
  const [lots, setLots] = useState<Lot[]>([])
  const [loading, setLoading] = useState(true)
  const [showAdd, setShowAdd] = useState(false)
  const [search, setSearch] = useState('')

  const load = async () => {
    try {
      const data = await fetchLots()
      setLots(data)
    } catch { /* ignore */ } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const filtered = lots.filter((l) =>
    l.name.toLowerCase().includes(search.toLowerCase()) ||
    l.lot_id.toLowerCase().includes(search.toLowerCase())
  )

  const totalSlots = lots.reduce((s, l) => s + l.total_slots, 0)
  const avgOcc = lots.length
    ? (lots.reduce((s, l) => s + (l.current_occupancy || 0), 0) / lots.length * 100).toFixed(1)
    : '0.0'
  const avgPrice = lots.length
    ? (lots.reduce((s, l) => s + l.base_price, 0) / lots.length).toFixed(2)
    : '0.00'

  if (loading) {
    return <div className="flex items-center justify-center h-64"><div className="text-dim animate-pulse">Loading lots...</div></div>
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-light text-white">Parking Lots</h1>
        <button
          onClick={() => setShowAdd(!showAdd)}
          className="text-xs px-3.5 py-2 rounded-lg bg-cyan-500 hover:bg-cyan-400 text-black font-medium transition-colors"
        >
          + Add Lot
        </button>
      </div>

      <div className="grid grid-cols-3 gap-4">
        {[
          { label: 'TOTAL LOTS', value: lots.length, color: 'text-cyan-400' },
          { label: 'AVG OCCUPANCY', value: `${avgOcc}%`, color: 'text-amber-400' },
          { label: 'TOTAL SLOTS', value: totalSlots, color: 'text-muted' },
        ].map((s) => (
          <div key={s.label} className="bg-[#13131f] border border-white/5 rounded-xl p-4">
            <p className="text-[10px] text-dim uppercase tracking-widest mb-1">{s.label}</p>
            <p className={`text-lg font-mono ${s.color}`}>{s.value}</p>
          </div>
        ))}
      </div>

      {showAdd && (
        <AddLotForm onDone={() => { setShowAdd(false); load() }} />
      )}

      <div className="bg-[#13131f] border border-white/5 rounded-xl overflow-hidden">
        <div className="p-3 border-b border-white/5">
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search lots..."
            className="w-full bg-[#0a0a0f] border border-white/10 rounded-lg px-3 py-2 text-xs text-white placeholder-dim/50 focus:outline-none focus:border-cyan-500/50"
          />
        </div>
        <div className="overflow-x-auto max-h-[600px] overflow-y-auto">
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-[#13131f]">
              <tr className="text-[10px] text-dim uppercase tracking-wider border-b border-white/5">
                <th className="text-left p-3 font-medium">Lot ID</th>
                <th className="text-left p-3 font-medium">Name</th>
                <th className="text-right p-3 font-medium">Slots</th>
                <th className="text-right p-3 font-medium">Occupancy</th>
                <th className="text-right p-3 font-medium">Price</th>
                <th className="text-right p-3 font-medium">Lat</th>
                <th className="text-right p-3 font-medium">Lng</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((lot) => (
                <tr key={lot.lot_id} className="border-b border-white/[0.02] hover:bg-white/[0.02] transition-colors">
                  <td className="p-3 font-mono text-[11px] text-dim">{lot.lot_id}</td>
                  <td className="p-3 font-medium text-white/90">{lot.name}</td>
                  <td className="p-3 text-right font-mono text-xs text-muted">{lot.total_slots}</td>
                  <td className="p-3 text-right font-mono text-xs text-amber-400">
                    {lot.current_occupancy !== undefined ? `${(lot.current_occupancy * 100).toFixed(1)}%` : '-'}
                  </td>
                  <td className="p-3 text-right font-mono text-xs text-emerald-400">${lot.base_price.toFixed(2)}</td>
                  <td className="p-3 text-right font-mono text-[11px] text-dim">{lot.latitude.toFixed(4)}</td>
                  <td className="p-3 text-right font-mono text-[11px] text-dim">{lot.longitude.toFixed(4)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

function AddLotForm({ onDone }: { onDone: () => void }) {
  const [form, setForm] = useState({ name: '', address: '', city: '', total_slots: 100, base_price: 10, latitude: 0, longitude: 0 })
  const [saving, setSaving] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    try {
      await createLot(form)
      onDone()
    } catch { } finally {
      setSaving(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="bg-[#13131f] border border-white/5 rounded-xl p-5 grid grid-cols-2 gap-4">
      <input className="col-span-2 bg-[#0a0a0f] border border-white/10 rounded-lg px-3 py-2 text-sm text-white placeholder-dim/50 focus:outline-none focus:border-cyan-500/50" placeholder="Lot Name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
      <input className="bg-[#0a0a0f] border border-white/10 rounded-lg px-3 py-2 text-sm text-white placeholder-dim/50 focus:outline-none focus:border-cyan-500/50" placeholder="Address" value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })} required />
      <input className="bg-[#0a0a0f] border border-white/10 rounded-lg px-3 py-2 text-sm text-white placeholder-dim/50 focus:outline-none focus:border-cyan-500/50" placeholder="City" value={form.city} onChange={(e) => setForm({ ...form, city: e.target.value })} required />
      <input className="bg-[#0a0a0f] border border-white/10 rounded-lg px-3 py-2 text-sm text-white placeholder-dim/50 focus:outline-none focus:border-cyan-500/50" type="number" placeholder="Total Slots" value={form.total_slots} onChange={(e) => setForm({ ...form, total_slots: +e.target.value })} required />
      <input className="bg-[#0a0a0f] border border-white/10 rounded-lg px-3 py-2 text-sm text-white placeholder-dim/50 focus:outline-none focus:border-cyan-500/50" type="number" step="0.01" placeholder="Base Price" value={form.base_price} onChange={(e) => setForm({ ...form, base_price: +e.target.value })} required />
      <input className="bg-[#0a0a0f] border border-white/10 rounded-lg px-3 py-2 text-sm text-white placeholder-dim/50 focus:outline-none focus:border-cyan-500/50" type="number" step="0.0001" placeholder="Latitude" value={form.latitude} onChange={(e) => setForm({ ...form, latitude: +e.target.value })} />
      <input className="bg-[#0a0a0f] border border-white/10 rounded-lg px-3 py-2 text-sm text-white placeholder-dim/50 focus:outline-none focus:border-cyan-500/50" type="number" step="0.0001" placeholder="Longitude" value={form.longitude} onChange={(e) => setForm({ ...form, longitude: +e.target.value })} />
      <div className="col-span-2 flex gap-2 justify-end">
        <button type="button" onClick={onDone} className="text-xs px-3 py-2 rounded-lg border border-white/10 text-dim hover:text-white transition-colors">Cancel</button>
        <button type="submit" disabled={saving} className="text-xs px-4 py-2 rounded-lg bg-cyan-500 hover:bg-cyan-400 text-black font-medium transition-colors disabled:opacity-50">
          {saving ? 'Creating...' : 'Create Lot'}
        </button>
      </div>
    </form>
  )
}
