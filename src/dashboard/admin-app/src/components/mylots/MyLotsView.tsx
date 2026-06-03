import { useState } from 'react'
import { fetchLotDetail, updateLotConfig } from '../../api/client'
import type { Lot, LotDetail } from '../../api/types'

interface MyLotsViewProps { lots: Lot[]; onRefresh: () => void }

export default function MyLotsView({ lots, onRefresh }: MyLotsViewProps) {
  const [selected, setSelected] = useState<string>('')
  const [detail, setDetail] = useState<LotDetail | null>(null)
  const [editing, setEditing] = useState(false)
  const [form, setForm] = useState({ base_price: 5, total_slots: 100 })
  const [saving, setSaving] = useState(false)
  const [msg, setMsg] = useState('')

  const handleSelect = async (lotId: string) => {
    setSelected(lotId); setDetail(null)
    if (!lotId) return
    try {
      const data = await fetchLotDetail(lotId)
      setDetail(data)
      setForm({ base_price: data.base_price || 5, total_slots: data.total_slots || 100 })
    } catch {}
  }

  const handleSave = async () => {
    if (!selected) return
    setSaving(true); setMsg('')
    try {
      await updateLotConfig(selected, form)
      setMsg('Saved successfully')
      setEditing(false)
      onRefresh()
    } catch { setMsg('Failed to save') }
    finally { setSaving(false) }
  }

  return (
    <div className="grid gap-4" style={{ gridTemplateColumns: '300px 1fr' }}>
      <div className="p-[18px] rounded-2xl" style={{
        background: 'rgba(255,255,255,0.06)', backdropFilter: 'blur(16px)',
        border: '1px solid rgba(255,255,255,0.06)',
      }}>
        <h3 className="text-[11px] mb-3 uppercase tracking-[0.8px]" style={{ color: 'rgba(240,238,248,0.55)' }}>
          <i className="fas fa-warehouse mr-1" /> Your Lots
        </h3>
        <div className="flex flex-col gap-1">
          {lots.map((lot) => (
            <button key={lot.lot_id || lot.id} onClick={() => handleSelect(lot.lot_id || String(lot.id))}
              className="w-full text-left px-3 py-2 rounded-xl text-[13px] transition-all cursor-pointer"
              style={{
                background: selected === (lot.lot_id || String(lot.id)) ? 'rgba(226,184,77,0.12)' : 'transparent',
                color: selected === (lot.lot_id || String(lot.id)) ? '#e2b84d' : '#f0eef8',
                border: `1px solid ${selected === (lot.lot_id || String(lot.id)) ? 'rgba(226,184,77,0.15)' : 'transparent'}`,
              }}
            >
              {lot.name}
            </button>
          ))}
        </div>
      </div>

      <div>
        {!selected && (
          <div className="text-center py-20 text-sm" style={{ color: '#64748b' }}>
            <i className="fas fa-hand-pointer text-3xl block mb-3 opacity-50" />
            Select a lot from the list
          </div>
        )}
        {detail && (
          <div className="p-[22px] rounded-2xl" style={{
            background: 'rgba(255,255,255,0.06)', backdropFilter: 'blur(16px)',
            border: '1px solid rgba(255,255,255,0.06)',
          }}>
            <h2 className="text-lg font-semibold mb-4">{detail.name}</h2>
            {editing ? (
              <div className="flex flex-col gap-4">
                <div>
                  <label className="text-[11px] uppercase tracking-[0.8px] block mb-1.5" style={{ color: 'rgba(240,238,248,0.55)' }}>Base Price ($/hr)</label>
                  <input type="number" step="0.5" min="0" value={form.base_price}
                    onChange={(e) => setForm({ ...form, base_price: parseFloat(e.target.value) || 0 })}
                    className="w-full px-3 py-2 rounded-xl text-sm outline-none transition-all"
                    style={{ background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.06)', color: '#f0eef8' }}
                    onFocus={(e) => e.currentTarget.style.borderColor = 'rgba(226,184,77,0.3)'}
                    onBlur={(e) => e.currentTarget.style.borderColor = 'rgba(255,255,255,0.06)'}
                  />
                </div>
                <div>
                  <label className="text-[11px] uppercase tracking-[0.8px] block mb-1.5" style={{ color: 'rgba(240,238,248,0.55)' }}>Total Slots</label>
                  <input type="number" min="1" value={form.total_slots}
                    onChange={(e) => setForm({ ...form, total_slots: parseInt(e.target.value) || 1 })}
                    className="w-full px-3 py-2 rounded-xl text-sm outline-none transition-all"
                    style={{ background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.06)', color: '#f0eef8' }}
                    onFocus={(e) => e.currentTarget.style.borderColor = 'rgba(226,184,77,0.3)'}
                    onBlur={(e) => e.currentTarget.style.borderColor = 'rgba(255,255,255,0.06)'}
                  />
                </div>
                <div className="flex gap-2">
                  <button onClick={handleSave} disabled={saving}
                    className="px-4 py-2 rounded-xl text-xs font-semibold cursor-pointer transition-all"
                    style={{ background: '#e2b84d', color: '#0a0a0f', opacity: saving ? 0.6 : 1 }}
                  >
                    {saving ? 'Saving...' : 'Save Changes'}
                  </button>
                  <button onClick={() => setEditing(false)}
                    className="px-4 py-2 rounded-xl text-xs cursor-pointer transition-all"
                    style={{ border: '1px solid rgba(255,255,255,0.06)', color: '#a49fc4' }}
                  >
                    Cancel
                  </button>
                </div>
                {msg && <p className="text-xs" style={{ color: msg.includes('Failed') ? '#f87171' : '#34d399' }}>{msg}</p>}
              </div>
            ) : (
              <div>
                <div className="flex gap-6 mb-4 flex-wrap">
                  <div><span className="text-xs" style={{ color: '#a49fc4' }}>Base Price</span><br /><strong style={{ color: '#e2b84d' }}>${(detail.base_price || 0).toFixed(2)}</strong></div>
                  <div><span className="text-xs" style={{ color: '#a49fc4' }}>Total Slots</span><br /><strong>{detail.total_slots}</strong></div>
                  <div><span className="text-xs" style={{ color: '#a49fc4' }}>Available</span><br /><strong style={{ color: '#34d399' }}>{detail.available_spots ?? 0}</strong></div>
                </div>
                <button onClick={() => setEditing(true)}
                  className="px-4 py-2 rounded-xl text-xs cursor-pointer transition-all flex items-center gap-1.5"
                  style={{ border: '1px solid rgba(255,255,255,0.06)', color: '#e2b84d' }}
                >
                  <i className="fas fa-pen" /> Edit Configuration
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
