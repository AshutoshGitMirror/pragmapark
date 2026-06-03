import { useState } from 'react'
import { useAuth } from '../../context/AuthContext'

export function SettingsPage() {
  const { user } = useAuth()
  const [simSpeed, setSimSpeed] = useState(1)

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-light text-white">Settings</h1>

      <div className="bg-[#13131f] border border-white/5 rounded-xl p-5 space-y-5">
        <div>
          <h3 className="text-xs text-dim uppercase tracking-widest mb-3">Profile</h3>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-[10px] text-dim uppercase tracking-wider mb-1">Name</label>
              <p className="text-sm text-white">{user?.full_name || '-'}</p>
            </div>
            <div>
              <label className="block text-[10px] text-dim uppercase tracking-wider mb-1">Email</label>
              <p className="text-sm text-white">{user?.email || '-'}</p>
            </div>
            <div>
              <label className="block text-[10px] text-dim uppercase tracking-wider mb-1">Role</label>
              <p className="text-sm text-white">{user?.role || '-'}</p>
            </div>
            <div>
              <label className="block text-[10px] text-dim uppercase tracking-wider mb-1">Organization</label>
              <p className="text-sm text-white">{user?.organization || '-'}</p>
            </div>
          </div>
        </div>

        <div className="border-t border-white/5 pt-5">
          <h3 className="text-xs text-dim uppercase tracking-widest mb-3">Simulation</h3>
          <div className="flex items-center gap-3">
            <span className="text-xs text-muted">Speed:</span>
            {[1, 10, 60].map((s) => (
              <button
                key={s}
                onClick={() => setSimSpeed(s)}
                className={`text-xs px-3 py-1.5 rounded-lg border transition-colors ${
                  simSpeed === s
                    ? 'border-cyan-500/50 bg-cyan-500/10 text-cyan-400'
                    : 'border-white/5 text-dim hover:text-white'
                }`}
              >
                {s}x
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
