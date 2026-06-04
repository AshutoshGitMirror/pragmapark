import { useAuth } from '../../context/AuthContext'

export function SettingsPage() {
  const { user } = useAuth()

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-white">Settings</h1>
        <p className="text-xs text-[#5a6a8a] mt-1">Account and profile configuration</p>
      </div>

      <div className="rounded-xl p-6"
        style={{
          background: 'linear-gradient(135deg, #0e0e24 0%, #12122a 50%, #0e0e24 100%)',
          boxShadow: '0 1px 0 rgba(255,255,255,0.04), 0 0 0 1px rgba(255,255,255,0.04)',
        }}>
        <div className="flex items-center gap-4 mb-6">
          <div className="w-12 h-12 rounded-full bg-gradient-to-br from-[rgba(0,212,255,0.2)] to-[rgba(0,136,204,0.1)] flex items-center justify-center text-lg text-[#00d4ff] font-semibold ring-1 ring-[rgba(0,212,255,0.2)]">
            {user?.full_name?.charAt(0) || 'A'}
          </div>
          <div>
            <h3 className="text-sm font-medium text-white/90">{user?.full_name || 'Admin'}</h3>
            <p className="text-xs text-[#5a6a8a]">{user?.role || 'user'}</p>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-6">
          {[
            { label: 'Name', value: user?.full_name || '—' },
            { label: 'Email', value: user?.email || '—' },
            { label: 'Role', value: user?.role || '—' },
            { label: 'Organization', value: user?.organization || '—' },
          ].map((f) => (
            <div key={f.label} className="p-4 rounded-lg bg-white/[0.02]">
              <p className="text-[10px] font-medium uppercase tracking-wider text-[#475569] mb-1.5">{f.label}</p>
              <p className="text-sm text-white">{f.value}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
