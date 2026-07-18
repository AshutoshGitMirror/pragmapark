import { useState, useEffect, useCallback } from 'react'
import { fetchResidentPermits, createResidentPermit, deactivatePermit, fetchLots } from '../../api/adminClient'
import type { ResidentPermit, Lot } from '../../api/adminClient'

const STALL_THRESHOLD = 15000

export function ResidentManagementPage() {
  const [permits, setPermits] = useState<ResidentPermit[]>([])
  const [lots, setLots] = useState<Lot[]>([])
  const [activeSection, setActiveSection] = useState<'permits' | 'shares'>('permits')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [stallMsg, setStallMsg] = useState('')

  // create permit modal
  const [showCreate, setShowCreate] = useState(false)
  const [newPermit, setNewPermit] = useState({ lot_id: '', slot_index: 1, start_date: '', end_date: '', monthly_rate: 50, registered_vehicle: '' })
  const [createLoading, setCreateLoading] = useState(false)
  const [createError, setCreateError] = useState('')

  // deactivate
  const [confirmDeactivate, setConfirmDeactivate] = useState<number | null>(null)

  const loadData = useCallback(async () => {
    setLoading(true)
    setError('')
    const timer = setTimeout(() => setStallMsg('Taking longer than expected…'), STALL_THRESHOLD)
    try {
      const [p, l] = await Promise.all([fetchResidentPermits(), fetchLots()])
      setPermits(p)
      setLots(l)
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || 'Failed to load data')
    } finally {
      clearTimeout(timer)
      setStallMsg('')
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadData() }, [loadData])

  const handleCreate = async () => {
    setCreateLoading(true)
    setCreateError('')
    const timer = setTimeout(() => setStallMsg('Taking longer than expected…'), STALL_THRESHOLD)
    try {
      await createResidentPermit({
        lot_id: newPermit.lot_id,
        slot_index: newPermit.slot_index,
        start_date: newPermit.start_date,
        end_date: newPermit.end_date,
        monthly_rate: newPermit.monthly_rate,
        registered_vehicle: newPermit.registered_vehicle || undefined,
      })
      setShowCreate(false)
      setNewPermit({ lot_id: '', slot_index: 1, start_date: '', end_date: '', monthly_rate: 50, registered_vehicle: '' })
      loadData()
    } catch (err: any) {
      setCreateError(err?.response?.data?.detail || err?.message || 'Failed to create permit')
    } finally {
      clearTimeout(timer)
      setStallMsg('')
      setCreateLoading(false)
    }
  }

  const handleDeactivate = async (permitId: number) => {
    const timer = setTimeout(() => setStallMsg('Taking longer than expected…'), STALL_THRESHOLD)
    try {
      await deactivatePermit(permitId)
      setConfirmDeactivate(null)
      loadData()
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || 'Deactivate failed')
    } finally {
      clearTimeout(timer)
      setStallMsg('')
    }
  }

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-white font-heading">Resident Management</h1>
      </div>

      <div className="flex gap-4 border-b border-white/[0.04] pb-3">
        <button onClick={() => setActiveSection('permits')}
          className={`text-sm font-medium transition-colors ${activeSection === 'permits' ? 'text-cyan' : 'text-dim hover:text-white'}`}>
          Permits
        </button>
        <button onClick={() => setActiveSection('shares')}
          className={`text-sm font-medium transition-colors ${activeSection === 'shares' ? 'text-cyan' : 'text-dim hover:text-white'}`}>
          Share Listings
        </button>
      </div>

      {stallMsg && (
        <div className="text-xs text-amber/80 bg-amber/[0.05] border border-amber/10 rounded-lg px-4 py-2">{stallMsg}</div>
      )}

      {error && (
        <div className="text-xs text-red/80 bg-red/[0.05] border border-red/10 rounded-lg px-4 py-2 flex items-center justify-between">
          <span>{error}</span>
          <button onClick={loadData} className="ml-3 text-cyan hover:text-white transition-colors">Retry</button>
        </div>
      )}

      {loading ? (
        <div className="flex items-center gap-2 text-xs text-dim">
          <div className="w-3 h-3 border border-cyan border-t-transparent rounded-full animate-spin" />
          Loading…
        </div>
      ) : activeSection === 'permits' ? (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-xs text-dim">{permits.length} permit(s)</p>
            <button onClick={() => setShowCreate(true)}
              className="text-xs bg-cyan/10 text-cyan border border-cyan/20 rounded-lg px-3 py-1.5 font-medium hover:bg-cyan/20 transition-colors">
              + Create Permit
            </button>
          </div>

          {permits.length === 0 ? (
            <p className="text-xs text-dim">No permits found. Create one to get started.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-dim border-b border-white/[0.04]">
                    <th className="text-left py-2 pr-3 font-medium">Lot</th>
                    <th className="text-left py-2 pr-3 font-medium">Slot</th>
                    <th className="text-left py-2 pr-3 font-medium">Type</th>
                    <th className="text-left py-2 pr-3 font-medium">Rate</th>
                    <th className="text-left py-2 pr-3 font-medium">Vehicle</th>
                    <th className="text-left py-2 pr-3 font-medium">Start</th>
                    <th className="text-left py-2 pr-3 font-medium">End</th>
                    <th className="text-left py-2 pr-3 font-medium">Status</th>
                    <th className="text-right py-2 font-medium">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {permits.map((p) => (
                    <tr key={p.id} className="border-b border-white/[0.02] text-white/70">
                      <td className="py-2 pr-3">{p.lot_name || p.lot_id}</td>
                      <td className="py-2 pr-3">{p.slot_index}</td>
                      <td className="py-2 pr-3">{p.permit_type || 'monthly'}</td>
                      <td className="py-2 pr-3">₹{p.monthly_rate?.toFixed(2) || '—'}</td>
                      <td className="py-2 pr-3">{p.registered_vehicle || '—'}</td>
                      <td className="py-2 pr-3">{p.start_date ? new Date(p.start_date).toLocaleDateString() : '—'}</td>
                      <td className="py-2 pr-3">{p.end_date ? new Date(p.end_date).toLocaleDateString() : '—'}</td>
                      <td className="py-2 pr-3">
                        <span className={p.is_active ? 'text-green' : 'text-dim'}>{p.is_active ? 'Active' : 'Inactive'}</span>
                      </td>
                      <td className="py-2 text-right">
                        {p.is_active && (
                          confirmDeactivate === p.id ? (
                            <span className="flex items-center justify-end gap-2">
                              <span className="text-dim">Deactivate?</span>
                              <button onClick={() => handleDeactivate(p.id)}
                                className="text-white bg-red/80 px-2 py-0.5 rounded font-semibold text-[10px]">Yes</button>
                              <button onClick={() => setConfirmDeactivate(null)}
                                className="text-dim hover:text-white text-[10px]">No</button>
                            </span>
                          ) : (
                            <button onClick={() => setConfirmDeactivate(p.id)}
                              className="text-dim hover:text-red transition-colors text-[10px]">Deactivate</button>
                          )
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Create Permit Modal */}
          {showCreate && (
            <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4"
              onClick={() => { if (!createLoading) setShowCreate(false) }}>
              <div onClick={(e) => e.stopPropagation()}
                className="w-full max-w-md rounded-2xl p-6 space-y-4"
                style={{ background: '#0c0c20', border: '1px solid rgba(255,255,255,0.08)' }}>
                <div className="flex items-center justify-between">
                  <h2 className="text-sm font-semibold text-white">Create Permit</h2>
                  <button onClick={() => { if (!createLoading) setShowCreate(false) }}
                    className="text-dim hover:text-white text-lg leading-none">&times;</button>
                </div>
                {createError && (
                  <div className="text-xs text-red bg-red/[0.05] border border-red/20 rounded-lg px-3 py-2">{createError}</div>
                )}
                <div className="space-y-3">
                  <div>
                    <label className="text-[10px] font-mono text-dim block mb-1">Lot</label>
                    <select value={newPermit.lot_id} onChange={(e) => setNewPermit({ ...newPermit, lot_id: e.target.value })}
                      className="w-full bg-white/[0.04] border border-white/[0.08] rounded-lg px-3 py-2 text-xs text-white">
                      <option value="">Select lot…</option>
                      {lots.map((l) => <option key={l.lot_id} value={l.lot_id}>{l.name}</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="text-[10px] font-mono text-dim block mb-1">Slot Index</label>
                    <input type="number" min={1} value={newPermit.slot_index}
                      onChange={(e) => setNewPermit({ ...newPermit, slot_index: parseInt(e.target.value) || 1 })}
                      className="w-full bg-white/[0.04] border border-white/[0.08] rounded-lg px-3 py-2 text-xs text-white" />
                  </div>
                  <div className="flex gap-3">
                    <div className="flex-1">
                      <label className="text-[10px] font-mono text-dim block mb-1">Start Date</label>
                      <input type="date" value={newPermit.start_date} onChange={(e) => setNewPermit({ ...newPermit, start_date: e.target.value })}
                        className="w-full bg-white/[0.04] border border-white/[0.08] rounded-lg px-3 py-2 text-xs text-white" />
                    </div>
                    <div className="flex-1">
                      <label className="text-[10px] font-mono text-dim block mb-1">End Date</label>
                      <input type="date" value={newPermit.end_date} onChange={(e) => setNewPermit({ ...newPermit, end_date: e.target.value })}
                        className="w-full bg-white/[0.04] border border-white/[0.08] rounded-lg px-3 py-2 text-xs text-white" />
                    </div>
                  </div>
                  <div>
                    <label className="text-[10px] font-mono text-dim block mb-1">Monthly Rate (₹)</label>
                    <input type="number" min={1} value={newPermit.monthly_rate}
                      onChange={(e) => setNewPermit({ ...newPermit, monthly_rate: parseFloat(e.target.value) || 50 })}
                      className="w-full bg-white/[0.04] border border-white/[0.08] rounded-lg px-3 py-2 text-xs text-white" />
                  </div>
                  <div>
                    <label className="text-[10px] font-mono text-dim block mb-1">Vehicle (optional)</label>
                    <input type="text" value={newPermit.registered_vehicle}
                      onChange={(e) => setNewPermit({ ...newPermit, registered_vehicle: e.target.value })}
                      placeholder="e.g. MH-01-AB-1234"
                      className="w-full bg-white/[0.04] border border-white/[0.08] rounded-lg px-3 py-2 text-xs text-white placeholder:text-dim" />
                  </div>
                  <button onClick={handleCreate} disabled={createLoading || !newPermit.lot_id || !newPermit.start_date || !newPermit.end_date}
                    className="w-full text-xs bg-cyan text-black font-semibold rounded-lg py-2.5 hover:bg-cyan/90 transition-colors disabled:opacity-40">
                    {createLoading ? 'Creating…' : 'Create Permit'}
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      ) : (
        <div className="space-y-3">
          <p className="text-xs text-dim">Settlements and share listing management.</p>
          {/* Share listings section — relies on permits having related share data */}
          {permits.filter((p) => p.is_active).length === 0 ? (
            <p className="text-xs text-dim">No active permits have share listings yet.</p>
          ) : (
            <p className="text-xs text-dim">Use the Permits tab to manage share listings for active permits.</p>
          )}
        </div>
      )}
    </div>
  )
}
