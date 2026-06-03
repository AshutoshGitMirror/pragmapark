import { useState } from 'react'
import { updateProfile } from '../../api/client'
import type { User } from '../../api/types'

interface SettingsViewProps { user: User | null; onUpdate: (u: User) => void }

export default function SettingsView({ user, onUpdate }: SettingsViewProps) {
  const [form, setForm] = useState({
    full_name: user?.full_name || '',
    organization: user?.organization || '',
  })
  const [saving, setSaving] = useState(false)
  const [msg, setMsg] = useState('')

  const handleSave = async () => {
    setSaving(true); setMsg('')
    try {
      const updated = await updateProfile(form)
      onUpdate({ ...user!, ...form })
      setMsg('Profile updated')
    } catch { setMsg('Failed to update') }
    finally { setSaving(false) }
  }

  return (
    <div className="max-w-2xl">
      <div className="p-[22px] rounded-2xl mb-6" style={{
        background: 'rgba(255,255,255,0.06)', backdropFilter: 'blur(16px)',
        border: '1px solid rgba(255,255,255,0.06)',
      }}>
        <h2 className="text-lg font-semibold mb-4">
          <i className="fas fa-user-cog mr-2" style={{ color: '#e2b84d' }} />
          Profile Settings
        </h2>
        <div className="flex flex-col gap-4">
          <div>
            <label className="text-[11px] uppercase tracking-[0.8px] block mb-1.5" style={{ color: 'rgba(240,238,248,0.55)' }}>
              <i className="fas fa-envelope mr-1" /> Email
            </label>
            <p className="text-sm px-3 py-2.5 rounded-xl" style={{ background: 'rgba(255,255,255,0.04)', color: '#a49fc4' }}>
              {user?.email || 'N/A'}
            </p>
          </div>
          <div>
            <label className="text-[11px] uppercase tracking-[0.8px] block mb-1.5" style={{ color: 'rgba(240,238,248,0.55)' }}>
              <i className="fas fa-id-badge mr-1" /> Role
            </label>
            <p className="text-sm px-3 py-2.5 rounded-xl capitalize" style={{ background: 'rgba(255,255,255,0.04)', color: '#a49fc4' }}>
              {user?.role?.replace('_', ' ') || 'N/A'}
            </p>
          </div>
          <div>
            <label className="text-[11px] uppercase tracking-[0.8px] block mb-1.5" style={{ color: 'rgba(240,238,248,0.55)' }}>
              <i className="fas fa-signature mr-1" /> Full Name
            </label>
            <input value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })}
              className="w-full px-3 py-2.5 rounded-xl text-sm outline-none transition-all"
              style={{ background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.06)', color: '#f0eef8' }}
              onFocus={(e) => e.currentTarget.style.borderColor = 'rgba(226,184,77,0.3)'}
              onBlur={(e) => e.currentTarget.style.borderColor = 'rgba(255,255,255,0.06)'}
            />
          </div>
          <div>
            <label className="text-[11px] uppercase tracking-[0.8px] block mb-1.5" style={{ color: 'rgba(240,238,248,0.55)' }}>
              <i className="fas fa-building mr-1" /> Organization
            </label>
            <input value={form.organization} onChange={(e) => setForm({ ...form, organization: e.target.value })}
              className="w-full px-3 py-2.5 rounded-xl text-sm outline-none transition-all"
              style={{ background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.06)', color: '#f0eef8' }}
              onFocus={(e) => e.currentTarget.style.borderColor = 'rgba(226,184,77,0.3)'}
              onBlur={(e) => e.currentTarget.style.borderColor = 'rgba(255,255,255,0.06)'}
            />
          </div>
          <button onClick={handleSave} disabled={saving}
            className="self-start px-5 py-2.5 rounded-xl text-sm font-semibold cursor-pointer transition-all"
            style={{ background: '#e2b84d', color: '#0a0a0f', opacity: saving ? 0.6 : 1 }}
          >
            {saving ? 'Saving...' : 'Save Changes'}
          </button>
          {msg && <p className="text-xs" style={{ color: msg.includes('Failed') ? '#f87171' : '#34d399' }}>{msg}</p>}
        </div>
      </div>

      <div className="p-[22px] rounded-2xl" style={{
        background: 'rgba(255,255,255,0.06)', backdropFilter: 'blur(16px)',
        border: '1px solid rgba(255,255,255,0.06)',
      }}>
        <h3 className="text-[11px] mb-3 uppercase tracking-[0.8px]" style={{ color: 'rgba(240,238,248,0.55)' }}>
          <i className="fas fa-info-circle mr-1" /> System Info
        </h3>
        <div className="grid gap-3 text-sm" style={{ gridTemplateColumns: '1fr 1fr' }}>
          {[
            ['App Version', '2.1.0'],
            ['UI Framework', 'React 18 + TypeScript'],
            ['API Base', import.meta.env.VITE_API_URL || '/api'],
            ['Python Backend', 'FastAPI + PostgreSQL'],
            ['ML Engine', 'Prophet + XGBoost'],
            ['Blockchain', 'Ethereum Sepolia'],
          ].map(([label, value]) => (
            <div key={label}>
              <p className="text-[11px]" style={{ color: 'rgba(240,238,248,0.4)' }}>{label}</p>
              <p style={{ color: '#a49fc4' }}>{value}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
