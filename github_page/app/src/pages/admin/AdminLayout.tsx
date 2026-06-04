import { type ReactNode } from 'react'
import { useAuth } from '../../context/AuthContext'

const NAV_ITEMS = [
  { label: 'Dashboard', icon: '⊞', hash: '/app/dashboard' },
  { label: 'Parking Lots', icon: '⛊', hash: '/app/lots' },
  { label: 'Analytics', icon: '◈', hash: '/app/analytics' },
  { label: 'Revenue', icon: '¤', hash: '/app/revenue' },
  { label: 'Map', icon: '⌗', hash: '/app/map' },
  { label: 'Micro Slots', icon: '⊡', hash: '/app/micro-slots' },
  { label: 'Alerts', icon: '⚠', hash: '/app/alerts', badge: true },
  { label: 'Settings', icon: '⚙', hash: '/app/settings' },
]

export function AdminLayout({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth()
  const currentHash = window.location.hash.replace('#', '').split('?')[0] || '/app/dashboard'

  const navigate = (hash: string) => {
    window.location.hash = hash
  }

  return (
    <div className="flex h-screen bg-[#0a0a0f] text-white overflow-hidden">
      <aside className="w-56 bg-[#0c0c18] border-r border-[rgba(255,255,255,0.04)] flex flex-col shrink-0">
        <div className="px-5 py-5 border-b border-[rgba(255,255,255,0.04)]">
          <h2 className="text-base font-semibold text-white tracking-tight">Pragma</h2>
          <p className="text-[11px] text-[#475569] mt-0.5">Admin Panel</p>
        </div>
        <nav className="flex-1 py-2 px-2 space-y-0.5">
          {NAV_ITEMS.map((item) => {
            const active = currentHash === item.hash
            return (
              <a
                key={item.hash}
                href={`#${item.hash}`}
                onClick={(e) => { e.preventDefault(); navigate(item.hash) }}
                className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-all duration-150 ${
                  active
                    ? 'bg-[rgba(0,212,255,0.08)] text-[#00d4ff]'
                    : 'text-[#64748b] hover:text-white hover:bg-white/[0.03]'
                }`}
              >
                <span className="text-base w-5 text-center shrink-0">{item.icon}</span>
                <span className="truncate">{item.label}</span>
              </a>
            )
          })}
        </nav>
        <div className="px-4 py-4 border-t border-[rgba(255,255,255,0.04)]">
          <div className="flex items-center gap-2.5 mb-2">
            <div className="w-7 h-7 rounded-full bg-[rgba(0,212,255,0.15)] flex items-center justify-center text-xs text-[#00d4ff] font-medium shrink-0">
              {user?.full_name?.charAt(0) || 'A'}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-medium text-white/80 truncate">{user?.full_name || 'Admin'}</p>
              <p className="text-[10px] text-[#475569] truncate">{user?.role || 'user'}</p>
            </div>
          </div>
          <button
            id="logout-btn"
            onClick={logout}
            className="w-full text-xs text-[#475569] hover:text-red-400 transition-colors py-1"
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
