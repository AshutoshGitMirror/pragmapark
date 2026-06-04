import { useState, useEffect } from 'react'
import { fetchLots, createLot, type Lot } from '../../api/adminClient'

export function ParkingLotsPage() {
  const [lots, setLots] = useState<Lot[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [search, setSearch] = useState('')
  const [form, setForm] = useState({ name: '', address: '', total_slots: 100, base_price: 2.5 })

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

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      await createLot({ ...form, city: 'Unknown', latitude: 0, longitude: 0, price_cap: form.base_price * 2 })
      setShowForm(false)
      setForm({ name: '', address: '', total_slots: 100, base_price: 2.5 })
      const data = await fetchLots()
      setLots(data)
    } catch { /* empty */ }
  }

  const filtered = lots.filter((l) =>
    l.name.toLowerCase().includes(search.toLowerCase()) ||
    l.address?.toLowerCase().includes(search.toLowerCase())
  )

  const stats = {
    total: lots.length,
    slots: lots.reduce((s, l) => s + l.total_slots, 0),
    occ: lots.length ? lots.reduce((s, l) => s + (l.current_occupancy || 0), 0) / lots.length : 0,
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-[#64748b] animate-pulse text-sm">Loading lots...</div>
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
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-white">Parking Lots</h1>
        <button
          onClick={() => setShowForm(!showForm)}
          className="bg-[#00d4ff] hover:bg-[#00e5ff] text-[#0a0a0f] text-xs font-medium px-3 py-1.5 rounded-lg transition-colors"
        >
          {showForm ? 'Cancel' : '+ Add Lot'}
        </button>
      </div>

      <div className="grid grid-cols-3 gap-4">
        <div className="bg-[#0e0e1a] border border-[rgba(255,255,255,0.06)] rounded-xl p-4">
          <p className="text-[11px] text-[#475569] mb-1">Total Lots</p>
          <p className="text-lg font-semibold text-white">{stats.total}</p>
        </div>
        <div className="bg-[#0e0e1a] border border-[rgba(255,255,255,0.06)] rounded-xl p-4">
          <p className="text-[11px] text-[#475569] mb-1">Total Slots</p>
          <p className="text-lg font-semibold text-white">{stats.slots}</p>
        </div>
        <div className="bg-[#0e0e1a] border border-[rgba(255,255,255,0.06)] rounded-xl p-4">
          <p className="text-[11px] text-[#475569] mb-1">Avg Occupancy</p>
          <p className="text-lg font-semibold text-[#f59e0b]">{(stats.occ * 100).toFixed(1)}%</p>
        </div>
      </div>

      {showForm && (
        <form onSubmit={handleCreate} className="bg-[#0e0e1a] border border-[rgba(255,255,255,0.06)] rounded-xl p-5 grid grid-cols-2 gap-4">
          <div>
            <label className="block text-xs text-[#64748b] mb-1">Name</label>
            <input
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              className="w-full bg-[#0a0a0f] border border-[rgba(255,255,255,0.08)] rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none focus:border-[rgba(0,212,255,0.4)]"
              required
            />
          </div>
          <div>
            <label className="block text-xs text-[#64748b] mb-1">Address</label>
            <input
              value={form.address}
              onChange={(e) => setForm({ ...form, address: e.target.value })}
              className="w-full bg-[#0a0a0f] border border-[rgba(255,255,255,0.08)] rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none focus:border-[rgba(0,212,255,0.4)]"
              required
            />
          </div>
          <div>
            <label className="block text-xs text-[#64748b] mb-1">Total Slots</label>
            <input
              type="number"
              value={form.total_slots}
              onChange={(e) => setForm({ ...form, total_slots: Number(e.target.value) })}
              className="w-full bg-[#0a0a0f] border border-[rgba(255,255,255,0.08)] rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none focus:border-[rgba(0,212,255,0.4)]"
            />
          </div>
          <div>
            <label className="block text-xs text-[#64748b] mb-1">Base Price ($)</label>
            <input
              type="number"
              step="0.1"
              value={form.base_price}
              onChange={(e) => setForm({ ...form, base_price: Number(e.target.value) })}
              className="w-full bg-[#0a0a0f] border border-[rgba(255,255,255,0.08)] rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none focus:border-[rgba(0,212,255,0.4)]"
            />
          </div>
          <div className="col-span-2 flex gap-2">
            <button type="submit" className="bg-[#00d4ff] hover:bg-[#00e5ff] text-[#0a0a0f] text-xs font-medium px-4 py-1.5 rounded-lg transition-colors">
              Create Lot
            </button>
            <button type="button" onClick={() => setShowForm(false)} className="text-xs text-[#64748b] hover:text-white px-3 py-1.5 transition-colors">
              Cancel
            </button>
          </div>
        </form>
      )}

      <div className="bg-[#0e0e1a] border border-[rgba(255,255,255,0.06)] rounded-xl overflow-hidden">
        <div className="p-3 border-b border-[rgba(255,255,255,0.06)]">
          <input
            placeholder="Search lots..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="bg-[#0a0a0f] border border-[rgba(255,255,255,0.08)] rounded-lg px-3 py-1.5 text-xs text-white placeholder-[#475569] w-64 focus:outline-none focus:border-[rgba(0,212,255,0.4)]"
          />
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-[11px] text-[#475569] border-b border-[rgba(255,255,255,0.04)]">
                <th className="text-left font-medium px-4 py-2.5">Lot</th>
                <th className="text-left font-medium px-4 py-2.5">Address</th>
                <th className="text-right font-medium px-4 py-2.5">Slots</th>
                <th className="text-right font-medium px-4 py-2.5">Occupancy</th>
                <th className="text-right font-medium px-4 py-2.5">Price</th>
                <th className="text-right font-medium px-4 py-2.5">Status</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((lot) => (
                <tr key={lot.lot_id} className="border-b border-[rgba(255,255,255,0.02)] hover:bg-white/[0.015] transition-colors">
                  <td className="px-4 py-3 font-medium text-white/90 text-xs">{lot.name}</td>
                  <td className="px-4 py-3 text-[#64748b] text-xs">{lot.address}</td>
                  <td className="px-4 py-3 text-right text-[#64748b] font-mono text-xs">{lot.total_slots}</td>
                  <td className="px-4 py-3 text-right font-mono text-xs text-[#f59e0b]">
                    {lot.current_occupancy !== undefined ? `${(lot.current_occupancy * 100).toFixed(1)}%` : '-'}
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-xs text-[#00c785]">${lot.base_price.toFixed(2)}</td>
                  <td className="px-4 py-3 text-right">
                    <span className="text-[10px] px-2 py-0.5 rounded-full bg-[rgba(0,199,133,0.1)] text-[#00c785]">
                      {lot.status || 'Available'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
