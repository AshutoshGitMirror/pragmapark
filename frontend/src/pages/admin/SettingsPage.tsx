import { useAuth } from '../../context/AuthContext'

export function SettingsPage() {
  const { user } = useAuth()

  return (
    <div className="space-y-6">
      {/* Section header */}
      <div>
        <p className="text-[10px] font-mono text-muted-alt tracking-[3px] uppercase mb-2">System · Account</p>
        <h1 className="section-headline">Settings</h1>
        <p className="section-body mt-1">Account and profile configuration</p>
      </div>

      <div className="card-dark rounded-xl p-6"
        >
        {/* Avatar row */}
        <div className="flex items-center gap-4 mb-6">
          <div className="w-14 h-14 rounded-full flex items-center justify-center text-2xl font-bold"
            style={{
              background: 'linear-gradient(135deg, #0e0e24 0%, #1a1a3e 100%)',
              color: '#9a97b0',
              border: '1px solid rgba(255,255,255,0.06)',
            }}>
            {user?.full_name?.charAt(0)?.toUpperCase() || 'A'}
          </div>
          <div>
            <h3 className="font-display text-lg font-bold text-white">{user?.full_name || 'Admin'}</h3>
            <p className="text-[10px] font-mono text-subtle uppercase tracking-wider">{user?.role || 'user'}</p>
          </div>
        </div>

        {/* Fields grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {[
            { label: 'Name', value: user?.full_name || '—' },
            { label: 'Email', value: user?.email || '—' },
            { label: 'Role', value: user?.role || '—' },
            { label: 'Organization', value: user?.organization || '—' },
          ].map((f) => (
            <div key={f.label} className="p-4 rounded-lg" style={{ background: 'rgba(255,255,255,0.02)' }}>
              <p className="text-[9px] font-mono font-semibold uppercase tracking-wider mb-1" style={{ color: '#5a6a8a' }}>{f.label}</p>
              <p className="text-sm text-white font-mono">{f.value}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
