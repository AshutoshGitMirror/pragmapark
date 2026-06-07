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
    } catch (err) { console.error('Failed to create lot:', err) }
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
        <div className="text-[#5a6a8a] animate-pulse text-sm">Loading lots...</div>
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
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-white">Parking Lots</h1>
          <p className="text-xs text-[#5a6a8a] mt-1">Manage and monitor parking facilities</p>
        </div>
        <button
          onClick={() => setShowForm(!showForm)}
          className="bg-[#00d4ff] hover:bg-[#00e5ff] text-[#0a0a0f] text-xs font-semibold px-4 py-2 rounded-lg transition-all duration-200"
        >
          {showForm ? 'Cancel' : '+ Add Lot'}
        </button>
      </div>

      <div className="grid grid-cols-3 gap-5">
        {[
          { label: 'Total Lots', value: String(stats.total), accent: '#00e5ff' },
          { label: 'Total Slots', value: String(stats.slots), accent: '#00c785' },
          { label: 'Avg Occupancy', value: `${(stats.occ * 100).toFixed(1)}%`, accent: '#f59e0b' },
        ].map((s) => (
          <div key={s.label}
            className="rounded-xl p-5 transition-all duration-200 hover:scale-[1.02]"
            style={{
              background: 'linear-gradient(135deg, #0e0e24 0%, #12122a 50%, #0e0e24 100%)',
              boxShadow: '0 1px 0 rgba(255,255,255,0.04), 0 0 0 1px rgba(255,255,255,0.04)',
            }}>
            <p className="text-[11px] font-medium uppercase tracking-wider text-[#475569] mb-2">{s.label}</p>
            <p className="text-[28px] font-bold tracking-tight text-white leading-none">{s.value}</p>
            <div className="mt-3 h-0.5 w-8 rounded-full opacity-60" style={{ background: s.accent }} />
          </div>
        ))}
      </div>

      {showForm && (
        <form onSubmit={handleCreate}
          className="rounded-xl p-6 grid grid-cols-2 gap-4"
          style={{
            background: 'linear-gradient(135deg, #0e0e24 0%, #12122a 50%, #0e0e24 100%)',
            boxShadow: '0 1px 0 rgba(255,255,255,0.04), 0 0 0 1px rgba(255,255,255,0.04)',
          }}>
          <div>
            <label className="block text-xs text-[#5a6a8a] mb-1.5 font-medium">Name</label>
            <input
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              className="w-full bg-[#0a0a18] border border-[rgba(255,255,255,0.08)] rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-[rgba(0,212,255,0.3)] placeholder-[#3a4a6a]"
              placeholder="Lot name"
              required
            />
          </div>
          <div>
            <label className="block text-xs text-[#5a6a8a] mb-1.5 font-medium">Address</label>
            <input
              value={form.address}
              onChange={(e) => setForm({ ...form, address: e.target.value })}
              className="w-full bg-[#0a0a18] border border-[rgba(255,255,255,0.08)] rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-[rgba(0,212,255,0.3)] placeholder-[#3a4a6a]"
              placeholder="Street address"
              required
            />
          </div>
          <div>
            <label className="block text-xs text-[#5a6a8a] mb-1.5 font-medium">Total Slots</label>
            <input
              type="number"
              value={form.total_slots}
              onChange={(e) => setForm({ ...form, total_slots: Number(e.target.value) })}
              className="w-full bg-[#0a0a18] border border-[rgba(255,255,255,0.08)] rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-[rgba(0,212,255,0.3)]"
            />
          </div>
          <div>
            <label className="block text-xs text-[#5a6a8a] mb-1.5 font-medium">Base Price ($)</label>
            <input
              type="number"
              step="0.1"
              value={form.base_price}
              onChange={(e) => setForm({ ...form, base_price: Number(e.target.value) })}
              className="w-full bg-[#0a0a18] border border-[rgba(255,255,255,0.08)] rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-[rgba(0,212,255,0.3)]"
            />
          </div>
          <div className="col-span-2 flex gap-2">
            <button type="submit" className="bg-[#00d4ff] hover:bg-[#00e5ff] text-[#0a0a0f] text-xs font-semibold px-4 py-2 rounded-lg transition-all duration-200">
              Create Lot
            </button>
            <button type="button" onClick={() => setShowForm(false)} className="text-xs text-[#5a6a8a] hover:text-white px-3 py-2 transition-colors">
              Cancel
            </button>
          </div>
        </form>
      )}

      <div className="rounded-xl overflow-hidden"
        style={{
          background: 'linear-gradient(135deg, #0e0e24 0%, #12122a 50%, #0e0e24 100%)',
          boxShadow: '0 1px 0 rgba(255,255,255,0.04), 0 0 0 1px rgba(255,255,255,0.04)',
        }}>
        <div className="px-5 py-3.5 border-b border-[rgba(255,255,255,0.04)]">
          <div className="relative">
            <input
              placeholder="Search lots by name or address..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="bg-[#0a0a18] border border-[rgba(255,255,255,0.08)] rounded-lg px-3 py-2 text-xs text-white placeholder-[#3a4a6a] w-72 focus:outline-none focus:border-[rgba(0,212,255,0.3)]"
            />
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-[11px] text-[#3a4a6a] border-b border-[rgba(255,255,255,0.03)] bg-white/[0.02]">
                <th className="text-left font-semibold px-5 py-3">Lot</th>
                <th className="text-left font-semibold px-5 py-3">Address</th>
                <th className="text-right font-semibold px-5 py-3">Slots</th>
                <th className="text-right font-semibold px-5 py-3">Occupancy</th>
                <th className="text-right font-semibold px-5 py-3">Price</th>
                <th className="text-right font-semibold px-5 py-3">Status</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((lot) => (
                <tr key={lot.lot_id} className="border-b border-[rgba(255,255,255,0.02)] hover:bg-[rgba(0,212,255,0.02)] transition-colors">
                  <td className="px-5 py-3.5 font-medium text-white/90 text-xs">{lot.name}</td>
                  <td className="px-5 py-3.5 text-[#5a6a8a] text-xs">{lot.address}</td>
                  <td className="px-5 py-3.5 text-right text-[#5a6a8a] font-mono text-xs">{lot.total_slots}</td>
                  <td className="px-5 py-3.5 text-right font-mono text-xs" style={{ color: (lot.current_occupancy || 0) > 0.3 ? '#f59e0b' : '#5a6a8a' }}>
                    {lot.current_occupancy !== undefined ? `${(lot.current_occupancy * 100).toFixed(1)}%` : '-'}
                  </td>
                  <td className="px-5 py-3.5 text-right font-mono text-xs text-[#00c785]">${lot.base_price.toFixed(2)}</td>
                  <td className="px-5 py-3.5 text-right">
                    <span className="text-[10px] px-2.5 py-0.5 rounded-full bg-[rgba(0,199,133,0.1)] text-[#00c785] font-medium">
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
