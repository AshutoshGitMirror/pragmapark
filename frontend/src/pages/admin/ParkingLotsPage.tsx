import { useState, useEffect } from 'react'
import { fetchLots, createLot, updateLot, deleteLot, type Lot } from '../../api/adminClient'
import { getErrorMessage } from '../../utils/format'

const DEFAULT_FORM = { name: '', address: '', city: '', total_slots: 100, base_price: 2.5, latitude: 0, longitude: 0 }

export function ParkingLotsPage() {
  const [lots, setLots] = useState<Lot[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [retryKey, setRetryKey] = useState(0)
  const [showForm, setShowForm] = useState(false)
  const [editingLot, setEditingLot] = useState<Lot | null>(null)
  const [deletingLot, setDeletingLot] = useState<Lot | null>(null)
  const [saving, setSaving] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [form, setForm] = useState(DEFAULT_FORM)

  useEffect(() => {
    let mounted = true
    const load = async () => {
      try {
        const data = await fetchLots()
        if (mounted) setLots(data)
      } catch (err: unknown) {
        if (mounted) setError(getErrorMessage(err))
      } finally {
        if (mounted) setLoading(false)
      }
    }
    load()
    const interval = setInterval(load, 30000)
    return () => { mounted = false; clearInterval(interval) }
  }, [retryKey])

  const openCreateForm = () => {
    setEditingLot(null)
    setForm(DEFAULT_FORM)
    setFormError(null)
    setShowForm(true)
  }

  const openEditForm = (lot: Lot) => {
    setEditingLot(lot)
    setForm({
      name: lot.name || '',
      address: lot.address || '',
      city: lot.city || '',
      total_slots: lot.total_slots,
      base_price: lot.base_price,
      latitude: lot.latitude || 0,
      longitude: lot.longitude || 0,
    })
    setFormError(null)
    setShowForm(true)
  }

  const closeForm = () => {
    setShowForm(false)
    setEditingLot(null)
    setFormError(null)
  }

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    setFormError(null)
    try {
      if (editingLot) {
        // Only send fields that changed
        const payload: Record<string, unknown> = {}
        if (form.name !== editingLot.name) payload.name = form.name
        if (form.address !== editingLot.address) payload.address = form.address
        if (form.city !== (editingLot.city || '')) payload.city = form.city
        if (form.total_slots !== editingLot.total_slots) payload.total_slots = form.total_slots
        if (form.base_price !== editingLot.base_price) payload.base_price = form.base_price
        if (form.base_price * 2 !== editingLot.price_cap) payload.price_cap = form.base_price * 2
        if (form.latitude !== (editingLot.latitude || 0)) payload.latitude = form.latitude
        if (form.longitude !== (editingLot.longitude || 0)) payload.longitude = form.longitude
        await updateLot(editingLot.lot_id, payload)
      } else {
        const lotId = form.name.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '') || 'lot'
        await createLot({
          lot_id: lotId,
          name: form.name,
          address: form.address,
          city: form.city || 'Unknown',
          total_slots: form.total_slots,
          base_price: form.base_price,
          latitude: form.latitude,
          longitude: form.longitude,
          price_cap: form.base_price * 2,
        })
      }
      closeForm()
      const data = await fetchLots()
      setLots(data)
    } catch (err: unknown) {
      setFormError(getErrorMessage(err, 'Failed to save lot'))
    } finally {
      setSaving(false)
    }
  }

  const confirmDelete = async () => {
    if (!deletingLot) return
    setDeleting(true)
    try {
      await deleteLot(deletingLot.lot_id)
      setDeletingLot(null)
      const data = await fetchLots()
      setLots(data)
    } catch (err: unknown) {
      setFormError(getErrorMessage(err, 'Failed to delete lot'))
    } finally {
      setDeleting(false)
    }
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
        <div className="text-subtle animate-pulse text-sm">Loading lots...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-64 flex-col gap-3">
        <div className="text-amber text-sm font-mono">{error}</div>
        <button onClick={() => setRetryKey((k) => k + 1)}
          className="text-[12px] font-mono px-3 py-2 rounded-lg transition-all"
          style={{
            background: 'rgba(245,158,11,0.08)',
            color: '#f59e0b',
            border: '1px solid rgba(245,158,11,0.2)',
          }}>
          Retry
        </button>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Delete Confirmation Modal */}
      {deletingLot && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={() => !deleting && setDeletingLot(null)}
          onKeyDown={(e) => { if (e.key === 'Escape' && !deleting) setDeletingLot(null) }}>
          <div className="rounded-xl p-6 w-full max-w-sm mx-4" onClick={(e) => e.stopPropagation()}
            style={{ background: '#0c0c20', border: '1px solid rgba(255,255,255,0.08)' }}>
            <h3 className="text-sm font-semibold text-white mb-2">Delete Lot</h3>
            <p className="text-xs text-subtle mb-4">
              Are you sure you want to delete <strong className="text-white">{deletingLot.name}</strong>? This action cannot be undone.
            </p>
            {formError && <p className="text-rose text-xs font-mono mb-3">{formError}</p>}
            <div className="flex gap-2 justify-end">
              <button onClick={() => setDeletingLot(null)} disabled={deleting}
                className="text-xs text-subtle hover:text-white px-3 py-2 transition-colors disabled:opacity-50">
                Cancel
              </button>
              <button onClick={confirmDelete} disabled={deleting}
                className="bg-rose hover:bg-red-600 text-white text-xs font-semibold px-4 py-2 rounded-lg transition-all duration-200 disabled:opacity-50">
                {deleting ? 'Deleting...' : 'Delete'}
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-white">Parking Lots</h1>
          <p className="text-xs text-subtle mt-1">Manage and monitor parking facilities</p>
        </div>
        <button
          onClick={showForm ? closeForm : openCreateForm}
          className="bg-[#00d4ff] hover:bg-[#00e5ff] text-[#0a0a0f] text-xs font-semibold px-4 py-2 rounded-lg transition-all duration-200"
        >
          {showForm ? 'Cancel' : '+ Add Lot'}
        </button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
        {[
          { label: 'Total Lots', value: String(stats.total), accent: '#00e5ff' },
          { label: 'Total Slots', value: String(stats.slots), accent: '#00c785' },
          { label: 'Avg Occupancy', value: `${stats.occ.toFixed(1)}%`, accent: '#f59e0b' },
        ].map((s) => (
          <div key={s.label}
            className="card-dark rounded-xl p-5 transition-all duration-200 hover:scale-[1.02]"
            >
            <p className="text-[11px] font-medium uppercase tracking-wider text-dim mb-2">{s.label}</p>
            <p className="text-[28px] font-bold tracking-tight text-white leading-none">{s.value}</p>
            <div className="mt-3 h-0.5 w-8 rounded-full opacity-60" style={{ background: s.accent }} />
          </div>
        ))}
      </div>

      {showForm && (
        <form onSubmit={handleSave}
          className="rounded-xl p-6 grid grid-cols-1 sm:grid-cols-2 gap-4"
          >
          <h3 className="col-span-2 text-sm font-semibold text-white">
            {editingLot ? `Edit ${editingLot.name}` : 'Add New Lot'}
          </h3>
          <div>
            <label className="block text-xs text-subtle mb-1.5 font-medium">Name *</label>
            <input
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              className="w-full bg-deeper border border-[rgba(255,255,255,0.08)] rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-[rgba(0,212,255,0.3)] placeholder-[#6a7a9a]"
              placeholder="Lot name"
              required
            />
          </div>
          <div>
            <label className="block text-xs text-subtle mb-1.5 font-medium">Address *</label>
            <input
              value={form.address}
              onChange={(e) => setForm({ ...form, address: e.target.value })}
              className="w-full bg-deeper border border-[rgba(255,255,255,0.08)] rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-[rgba(0,212,255,0.3)] placeholder-[#6a7a9a]"
              placeholder="Street address"
              required
            />
          </div>
          <div>
            <label className="block text-xs text-subtle mb-1.5 font-medium">City</label>
            <input
              value={form.city}
              onChange={(e) => setForm({ ...form, city: e.target.value })}
              className="w-full bg-deeper border border-[rgba(255,255,255,0.08)] rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-[rgba(0,212,255,0.3)] placeholder-[#6a7a9a]"
              placeholder="Mumbai"
            />
          </div>
          <div>
            <label className="block text-xs text-subtle mb-1.5 font-medium">Total Slots *</label>
            <input
              type="number"
              min="1"
              value={form.total_slots}
              onChange={(e) => setForm({ ...form, total_slots: Math.max(1, Number(e.target.value)) })}
              className="w-full bg-deeper border border-[rgba(255,255,255,0.08)] rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-[rgba(0,212,255,0.3)]"
              required
            />
          </div>
          <div>
            <label className="block text-xs text-subtle mb-1.5 font-medium">Base Price (₹) *</label>
            <input
              type="number"
              step="0.1"
              min="0.5"
              value={form.base_price}
              onChange={(e) => setForm({ ...form, base_price: Math.max(0.5, Number(e.target.value)) })}
              className="w-full bg-deeper border border-[rgba(255,255,255,0.08)] rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-[rgba(0,212,255,0.3)]"
              required
            />
          </div>
          <div>
            <label className="block text-xs text-subtle mb-1.5 font-medium">Latitude</label>
            <input
              type="number"
              step="0.0001"
              value={form.latitude}
              onChange={(e) => setForm({ ...form, latitude: Number(e.target.value) })}
              className="w-full bg-deeper border border-[rgba(255,255,255,0.08)] rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-[rgba(0,212,255,0.3)] placeholder-[#6a7a9a]"
              placeholder="19.0760"
            />
          </div>
          <div>
            <label className="block text-xs text-subtle mb-1.5 font-medium">Longitude</label>
            <input
              type="number"
              step="0.0001"
              value={form.longitude}
              onChange={(e) => setForm({ ...form, longitude: Number(e.target.value) })}
              className="w-full bg-deeper border border-[rgba(255,255,255,0.08)] rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-[rgba(0,212,255,0.3)] placeholder-[#6a7a9a]"
              placeholder="72.8777"
            />
          </div>
          {formError && (
            <p className="col-span-2 text-rose text-xs font-mono">{formError}</p>
          )}
          <div className="col-span-2 flex gap-2 items-center">
            <button type="submit" disabled={saving}
              className="bg-[#00d4ff] hover:bg-[#00e5ff] text-[#0a0a0f] text-xs font-semibold px-4 py-2 rounded-lg transition-all duration-200 disabled:opacity-50">
              {saving ? 'Saving...' : editingLot ? 'Update Lot' : 'Create Lot'}
            </button>
            <button type="button" onClick={closeForm} disabled={saving}
              className="text-xs text-subtle hover:text-white px-3 py-2 transition-colors disabled:opacity-50">
              Cancel
            </button>
          </div>
        </form>
      )}

      <div className="rounded-xl overflow-hidden"
        >
        <div className="px-5 py-3.5 border-b border-[rgba(255,255,255,0.04)]">
          <div className="relative">
            <input
              placeholder="Search lots by name or address..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="bg-deeper border border-[rgba(255,255,255,0.08)] rounded-lg px-3 py-2 text-xs text-white placeholder-[#6a7a9a] w-full md:w-72 focus:outline-none focus:border-[rgba(0,212,255,0.3)]"
            />
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-[11px] text-[#3a4a6a] border-b border-[rgba(255,255,255,0.03)] bg-white/[0.02]">
                <th className="text-left font-semibold px-5 py-3">Lot</th>
                <th className="text-left font-semibold px-5 py-3">City</th>
                <th className="text-left font-semibold px-5 py-3">Address</th>
                <th className="text-right font-semibold px-5 py-3">Slots</th>
                <th className="text-right font-semibold px-5 py-3">Occupancy</th>
                <th className="text-right font-semibold px-5 py-3">Price</th>
                <th className="text-right font-semibold px-5 py-3">Status</th>
                <th className="text-right font-semibold px-5 py-3">Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 ? (
                <tr>
                  <td colSpan={8} className="px-5 py-8 text-center text-xs text-subtle">
                    {search ? `No lots matching "${search}"` : 'No parking lots yet'}
                  </td>
                </tr>
              ) : (
                filtered.map((lot) => (
                  <tr key={lot.lot_id} className="border-b border-[rgba(255,255,255,0.02)] hover:bg-[rgba(0,212,255,0.02)] transition-colors">
                    <td className="px-5 py-3.5 font-medium text-white/90 text-xs">{lot.name}</td>
                    <td className="px-5 py-3.5 text-subtle text-xs">{lot.city || '-'}</td>
                    <td className="px-5 py-3.5 text-subtle text-xs">{lot.address}</td>
                    <td className="px-5 py-3.5 text-right text-subtle font-mono text-xs">{lot.total_slots}</td>
                    <td className="px-5 py-3.5 text-right font-mono text-xs" style={{ color: (lot.current_occupancy || 0) > 30 ? '#f59e0b' : '#5a6a8a' }}>
                      {lot.current_occupancy !== undefined ? `${lot.current_occupancy.toFixed(1)}%` : '-'}
                    </td>
                    <td className="px-5 py-3.5 text-right font-mono text-xs text-emerald">₹{lot.base_price.toFixed(2)}</td>
                    <td className="px-5 py-3.5 text-right">
                      <span className={`text-[10px] px-2.5 py-0.5 rounded-full font-medium ${
                        lot.status === 'Available'
                          ? 'bg-[rgba(0,199,133,0.1)] text-emerald'
                          : lot.status === 'Full'
                          ? 'bg-[rgba(245,158,11,0.1)] text-amber'
                          : 'bg-[rgba(100,100,140,0.1)] text-subtle'
                      }`}>
                        {lot.status || 'Available'}
                      </span>
                    </td>
                    <td className="px-5 py-3.5 text-right">
                      <div className="flex gap-1.5 justify-end">
                        <button onClick={() => openEditForm(lot)}
                          className="text-[10px] px-2 py-1 rounded bg-white/[0.06] hover:bg-white/[0.1] text-subtle hover:text-white transition-colors"
                          title="Edit lot">
                          ✎ Edit
                        </button>
                        <button onClick={() => { setDeletingLot(lot); setFormError(null) }}
                          className="text-[10px] px-2 py-1 rounded bg-white/[0.06] hover:bg-rose/20 text-subtle hover:text-rose transition-colors"
                          title="Delete lot">
                          ✕ Delete
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
