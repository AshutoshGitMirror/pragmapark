import { type ReactNode } from 'react'
import { useAuth } from '../../context/AuthContext'

// Pipeline stages: each group gets a label + accent color
const PIPELINE_GROUPS: {
  label: string
  stage: string
  accent: string
  items: { label: string; icon: string; hash: string; badge?: boolean }[]
}[] = [
  {
    label: 'Overview',
    stage: '00',
    accent: '#60d4a0',
    items: [
      { label: 'Dashboard', icon: '⊞', hash: '/app/dashboard' },
    ],
  },
  {
    label: 'IoT / Observe',
    stage: '01',
    accent: '#40d4f0',
    items: [
      { label: 'Map', icon: '⌗', hash: '/app/map' },
      { label: 'Parking Lots', icon: '⛊', hash: '/app/lots' },
    ],
  },
  {
    label: 'ML / Predict',
    stage: '02',
    accent: '#a060f0',
    items: [
      { label: 'Analytics', icon: '◈', hash: '/app/analytics' },
    ],
  },
  {
    label: 'RL / Price',
    stage: '03',
    accent: '#f0c040',
    items: [
      { label: 'Revenue', icon: '¤', hash: '/app/revenue' },
    ],
  },
  {
    label: 'Ledger & Slots',
    stage: '04',
    accent: '#f0c040',
    items: [
      { label: 'Micro Slots', icon: '⊡', hash: '/app/micro-slots' },
    ],
  },
  {
    label: 'Actuate',
    stage: '05',
    accent: '#f04060',
    items: [
      { label: 'Alerts', icon: '⚠', hash: '/app/alerts', badge: true },
      { label: 'Actuators', icon: '⚡', hash: '/app/actuator' },
    ],
  },
  {
    label: 'System',
    stage: '',
    accent: '#64748b',
    items: [
      { label: 'Settings', icon: '⚙', hash: '/app/settings' },
    ],
  },
]

export function AdminLayout({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth()
  const currentHash = window.location.hash.replace('#', '').split('?')[0] || '/app/dashboard'

  const navigate = (hash: string) => {
    window.location.hash = hash
  }

  return (
    <div className="flex h-screen text-white overflow-hidden"
      style={{ background: 'linear-gradient(135deg, #07070d 0%, #0a0a18 50%, #07070d 100%)' }}>
      <aside className="w-60 flex flex-col shrink-0 relative overflow-y-auto"
        style={{ background: 'linear-gradient(180deg, #0c0c20 0%, #0a0a18 100%)' }}>
        <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-[rgba(0,212,255,0.2)] to-transparent" />
        
        {/* Brand header */}
        <div className="px-5 py-5 shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-[#00d4ff] to-[#0088cc] flex items-center justify-center text-sm font-bold text-white shadow-[0_0_12px_rgba(0,212,255,0.25)]">
              P
            </div>
            <div>
              <h2 className="text-sm font-semibold text-white tracking-tight font-heading">Pragma</h2>
              <p className="text-[10px] text-[#475569] mt-px font-mono">Admin Panel</p>
            </div>
          </div>
        </div>
        <div className="mx-3 h-px bg-gradient-to-r from-transparent via-[rgba(255,255,255,0.04)] to-transparent shrink-0" />
        
        {/* Pipeline navigation */}
        <nav className="flex-1 py-4 px-2.5 space-y-4">
          {PIPELINE_GROUPS.map((group) => (
            <div key={group.label}>
              {/* Group header */}
              <div className="flex items-center gap-2 px-3 mb-1.5">
                {group.stage && (
                  <span className="text-[9px] font-mono font-semibold tracking-wider uppercase"
                    style={{ color: group.accent }}>
                    {group.stage}
                  </span>
                )}
                <span className="text-[9px] font-mono uppercase tracking-wider text-[#475569]">
                  {group.label}
                </span>
                <div className="flex-1 h-px" style={{ 
                  background: `linear-gradient(to right, ${group.accent}22, transparent)` 
                }} />
              </div>
              
              {/* Group items */}
              <div className="space-y-0.5">
                {group.items.map((item) => {
                  const active = currentHash === item.hash
                  return (
                    <a
                      key={item.hash}
                      href={`#${item.hash}`}
                      onClick={(e) => { e.preventDefault(); navigate(item.hash) }}
                      className={`group relative flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-all duration-150 ${
                        active
                          ? 'font-medium'
                          : 'text-[#5a6a8a] hover:text-white hover:bg-white/[0.04]'
                      }`}
                      style={active ? {
                        background: `${group.accent}0d`,
                        color: group.accent,
                      } : undefined}
                    >
                      {active && (
                        <span className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-4 rounded-r-full"
                          style={{ 
                            background: group.accent,
                            boxShadow: `0 0 6px ${group.accent}66`,
                          }} />
                      )}
                      <span className={`text-base w-5 text-center shrink-0 transition-colors duration-150 ${
                        active ? '' : 'text-[#475569] group-hover:text-white'
                      }`}
                        style={active ? { color: group.accent } : undefined}>
                        {item.icon}
                      </span>
                      <span className="truncate">{item.label}</span>
                      {item.badge && (
                        <span className="w-1.5 h-1.5 rounded-full ml-auto animate-pulse-glow"
                          style={{ backgroundColor: group.accent }} />
                      )}
                    </a>
                  )
                })}
              </div>
            </div>
          ))}
        </nav>
        
        {/* User section */}
        <div className="mx-3 h-px bg-gradient-to-r from-transparent via-[rgba(255,255,255,0.04)] to-transparent shrink-0" />
        <div className="px-4 py-4 shrink-0">
          <div className="flex items-center gap-2.5 mb-2.5">
            <div className="w-8 h-8 rounded-full bg-gradient-to-br from-[rgba(0,212,255,0.2)] to-[rgba(0,136,204,0.1)] flex items-center justify-center text-xs text-[#00d4ff] font-semibold shrink-0 ring-1 ring-[rgba(0,212,255,0.15)]">
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
            className="w-full text-xs text-[#475569] hover:text-[#ff6b6b] transition-colors py-1.5 rounded-lg hover:bg-white/[0.03]"
          >
            Sign Out
          </button>
        </div>
      </aside>
      <main className="flex-1 flex flex-col overflow-hidden">
        <div className="flex-1 overflow-y-auto p-6 md:p-8">
          {children}
        </div>
      </main>
    </div>
  )
}
