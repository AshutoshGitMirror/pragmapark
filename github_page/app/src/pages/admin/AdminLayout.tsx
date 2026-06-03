import { type ReactNode } from 'react'
import { useAuth } from '../../context/AuthContext'

const NAV_ITEMS = [
  { label: 'Dashboard', icon: '⊞', hash: '/dashboard' },
  { label: 'Parking Lots', icon: '⛊', hash: '/lots' },
  { label: 'Analytics', icon: '◈', hash: '/analytics' },
  { label: 'Revenue', icon: '¤', hash: '/revenue' },
  { label: 'Map', icon: '⌗', hash: '/map' },
  { label: 'Micro Slots', icon: '⊡', hash: '/micro-slots' },
  { label: 'Alerts', icon: '⚠', hash: '/alerts', badge: true },
  { label: 'Settings', icon: '⚙', hash: '/settings' },
]

export function AdminLayout({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth()
  const currentHash = window.location.hash.replace('#', '').split('?')[0] || '/dashboard'

  const navigate = (hash: string) => {
    window.location.hash = hash
  }

  return (
    <div className="flex h-screen bg-[#0a0a0f] text-white overflow-hidden">
      <aside className="w-56 bg-[#0d0d1a] border-r border-white/5 flex flex-col shrink-0">
        <div className="px-5 py-5 border-b border-white/5">
          <h2 className="text-lg font-light tracking-wider text-cyan-400">Pragma</h2>
          <p className="text-[10px] text-dim/60 uppercase tracking-[0.15em] mt-0.5">Admin Panel</p>
        </div>
        <nav className="flex-1 py-3 space-y-0.5 px-2">
          {NAV_ITEMS.map((item) => {
            const active = currentHash === item.hash
            return (
              <a
                key={item.hash}
                href={`#${item.hash}`}
                onClick={(e) => { e.preventDefault(); navigate(item.hash) }}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-md text-sm transition-all duration-150 ${
                  active
                    ? 'bg-cyan-500/10 text-cyan-400 border-l-2 border-cyan-400'
                    : 'text-muted hover:text-white hover:bg-white/[0.03] border-l-2 border-transparent'
                }`}
              >
                <span className="text-base w-5 text-center">{item.icon}</span>
                <span>{item.label}</span>
              </a>
            )
          })}
        </nav>
        <div className="px-4 py-4 border-t border-white/5">
          <div className="flex items-center gap-2.5 mb-3">
            <div className="w-7 h-7 rounded-full bg-cyan-500/20 flex items-center justify-center text-xs text-cyan-400 font-medium">
              {user?.full_name?.charAt(0) || 'A'}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-medium truncate">{user?.full_name || 'Admin'}</p>
              <p className="text-[10px] text-dim truncate">{user?.role || 'user'}</p>
            </div>
          </div>
          <button
            onClick={logout}
            className="w-full text-xs text-dim hover:text-red-400 transition-colors py-1.5 text-left"
          >
            Sign Out
          </button>
        </div>
      </aside>
      <main className="flex-1 flex flex-col overflow-hidden">
        <div className="flex-1 overflow-y-auto p-6">
          {children}
        </div>
      </main>
    </div>
  )
}
