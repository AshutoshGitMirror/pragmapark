import { useAuth } from '../../context/AuthContext'

export function SettingsPage() {
  const { user } = useAuth()

  return (
    <div className="space-y-6">
      <h1 className="text-lg font-semibold text-white">Settings</h1>

      <div className="bg-[#0e0e1a] border border-[rgba(255,255,255,0.06)] rounded-xl p-5 space-y-5">
        <div>
          <h3 className="text-xs text-[#64748b] mb-3">Profile</h3>
          <div className="grid grid-cols-2 gap-4">
            {[
              { label: 'Name', value: user?.full_name || '—' },
              { label: 'Email', value: user?.email || '—' },
              { label: 'Role', value: user?.role || '—' },
              { label: 'Organization', value: user?.organization || '—' },
            ].map((f) => (
              <div key={f.label}>
                <p className="text-[11px] text-[#475569] mb-1">{f.label}</p>
                <p className="text-sm text-white">{f.value}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
