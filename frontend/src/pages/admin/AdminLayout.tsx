import { type ReactNode, useState, useEffect, useCallback } from 'react'
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
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [confirmSignOut, setConfirmSignOut] = useState(false)

  const navigate = useCallback((hash: string) => {
    window.location.hash = hash
    setSidebarOpen(false)
  }, [])

  // Close sidebar on Escape key
  useEffect(() => {
    if (!sidebarOpen) return
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setSidebarOpen(false)
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [sidebarOpen])

  // Auto-scroll active nav link into view
  useEffect(() => {
    const nav = document.querySelector('nav')
    if (!nav) return
    const activeLink = nav.querySelector(`a[href="#${currentHash}"]`) as HTMLElement | null
    if (activeLink) {
      activeLink.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
    }
  }, [currentHash])

  const sidebarContent = (
    <>
      {/* Brand header */}
      <div className="px-5 py-5 shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-[#00d4ff] to-[#0088cc] flex items-center justify-center text-sm font-bold text-white shadow-[0_0_12px_rgba(0,212,255,0.25)]">
            P
          </div>
          <div>
            <h2 className="text-sm font-semibold text-white tracking-tight font-heading">Pragma</h2>
            <p className="text-[10px] text-dim mt-px font-mono">Admin Panel</p>
          </div>
        </div>
      </div>
      <div className="mx-3 h-px bg-gradient-to-r from-transparent via-[rgba(255,255,255,0.04)] to-transparent shrink-0" />

      {/* Pipeline navigation */}
      <nav className="flex-1 py-4 px-2.5 space-y-4">
        {PIPELINE_GROUPS.map((group) => (
          <div key={group.label}>
            <div className="flex items-center gap-2 px-3 mb-1.5">
              {group.stage && (
                <span className="text-[9px] font-mono font-semibold tracking-wider uppercase"
                  style={{ color: group.accent }}>
                  {group.stage}
                </span>
              )}
              <span className="text-[9px] font-mono uppercase tracking-wider text-dim">
                {group.label}
              </span>
              <div className="flex-1 h-px" style={{ 
                background: `linear-gradient(to right, ${group.accent}22, transparent)` 
              }} />
            </div>
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
                        : 'text-subtle hover:text-white hover:bg-white/[0.04]'
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
                      active ? '' : 'text-dim group-hover:text-white'
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
          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-[rgba(0,212,255,0.2)] to-[rgba(0,136,204,0.1)] flex items-center justify-center text-xs text-cyan font-semibold shrink-0 ring-1 ring-[rgba(0,212,255,0.15)]">
            {user?.full_name?.charAt(0) || 'A'}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-xs font-medium text-white/80 truncate">{user?.full_name || 'Admin'}</p>
            <p className="text-[10px] text-dim truncate">{user?.role || 'user'}</p>
          </div>
        </div>
        {confirmSignOut ? (
          <div className="flex items-center gap-2 px-2">
            <span className="text-[9px] font-mono" style={{ color: '#7a8aaa' }}>Sign out?</span>
            <button id="logout-btn"
              onClick={() => { setConfirmSignOut(false); logout() }}
              className="text-xs text-white bg-[#ff4757] px-2 py-1 rounded font-semibold">
              Yes
            </button>
            <button onClick={() => setConfirmSignOut(false)}
              className="text-xs text-dim hover:text-white transition-colors px-2 py-1 rounded">
              No
            </button>
          </div>
        ) : (
          <button onClick={() => setConfirmSignOut(true)}
            className="w-full text-xs text-dim hover:text-[#ff6b6b] transition-colors py-1.5 rounded-lg hover:bg-white/[0.03]"
          >
            Sign Out
          </button>
        )}
      </div>
    </>
  )

  return (
    <div className="flex h-screen text-white overflow-hidden"
      style={{ background: 'linear-gradient(135deg, #07070d 0%, #0a0a18 50%, #07070d 100%)' }}>
      
      {/* Mobile sidebar overlay backdrop */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm lg:hidden"
          onClick={() => setSidebarOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* Sidebar: fixed overlay on mobile, static on desktop */}
      <aside
        className={`
          fixed inset-y-0 left-0 z-50 w-60 flex flex-col shrink-0 overflow-y-auto
          transition-transform duration-300 ease-in-out
          lg:relative lg:translate-x-0
          ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}
        `}
        style={{ background: 'linear-gradient(180deg, #0c0c20 0%, #0a0a18 100%)' }}
        aria-label="Admin navigation sidebar"
      >
        <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-[rgba(0,212,255,0.2)] to-transparent" />
        
        {/* Close button (mobile only) */}
        <button
          onClick={() => setSidebarOpen(false)}
          className="absolute top-4 right-4 w-8 h-8 flex items-center justify-center rounded-lg lg:hidden text-dim hover:text-white hover:bg-white/[0.04] transition-colors"
          aria-label="Close sidebar"
        >
          <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>

        {sidebarContent}

        {/* Scroll gradient indicator — fades at bottom when content overflows */}
        <div className="sticky bottom-0 left-0 right-0 h-8 pointer-events-none shrink-0"
          style={{
            background: 'linear-gradient(to top, #0c0c20 40%, transparent)',
          }}
        />
      </aside>

      {/* Main content area */}
      <main className="flex-1 flex flex-col overflow-hidden min-w-0">
        {/* Top bar with hamburger (mobile) */}
        <div className="flex items-center gap-3 px-4 py-3 md:px-6 md:py-4 shrink-0 lg:hidden border-b border-white/[0.04]">
          <button
            onClick={() => setSidebarOpen(true)}
            className="w-9 h-9 flex items-center justify-center rounded-lg text-dim hover:text-white hover:bg-white/[0.04] transition-colors"
            aria-label="Open sidebar menu"
          >
            <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" />
            </svg>
          </button>
          <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-[#00d4ff] to-[#0088cc] flex items-center justify-center text-[10px] font-bold text-white shrink-0">
            P
          </div>
          <span className="text-sm font-heading font-semibold text-white">Pragma</span>
        </div>

        <div className="flex-1 overflow-y-auto p-6 md:p-8">
          {children}
        </div>
      </main>
    </div>
  )
}
