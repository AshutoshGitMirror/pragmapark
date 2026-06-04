import { type ReactNode } from 'react'
import { getDriverUser, clearDriverAuth } from '../../api/driverClient'

const TABS = [
  { label: 'Find', icon: '⌕', hash: '/driver/find' },
  { label: 'Parking', icon: '◷', hash: '/driver/active' },
  { label: 'History', icon: '☰', hash: '/driver/history' },
]

export function DriverLayout({ children }: { children: ReactNode }) {
  const user = getDriverUser()
  const currentHash = window.location.hash.replace('#', '').split('?')[0] || '/driver/find'

  const navigate = (hash: string) => { window.location.hash = hash }

  return (
    <div className="flex flex-col h-screen text-white overflow-hidden"
      style={{ background: 'linear-gradient(135deg, #07070d 0%, #0a0a18 50%, #07070d 100%)' }}>
      <header className="shrink-0 px-5 py-4 flex items-center justify-between"
        style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-[#00d4ff] to-[#0088cc] flex items-center justify-center text-sm font-bold text-white shadow-[0_0_12px_rgba(0,212,255,0.25)]">
            P
          </div>
          <div>
            <h1 className="text-sm font-semibold text-white">Pragma</h1>
            <p className="text-[10px] text-[#475569]">{user?.full_name || 'Driver'}</p>
          </div>
        </div>
        <button onClick={() => { clearDriverAuth(); navigate('/driver/login') }}
          className="text-[10px] text-[#475569] hover:text-[#ff6b6b] transition-colors px-2 py-1 rounded hover:bg-white/[0.03]">
          Sign Out
        </button>
      </header>

      <main className="flex-1 overflow-y-auto px-4 py-4">
        {children}
      </main>

      <nav className="shrink-0 flex items-center justify-around px-4 py-2"
        style={{
          background: '#0c0c20',
          borderTop: '1px solid rgba(255,255,255,0.04)',
          boxShadow: '0 -4px 20px rgba(0,0,0,0.3)',
        }}>
        {TABS.map((tab) => {
          const active = currentHash.startsWith(tab.hash)
          return (
            <button key={tab.hash} onClick={() => navigate(tab.hash)}
              className={`flex flex-col items-center gap-0.5 py-2 px-4 rounded-lg transition-all duration-150 ${
                active ? 'text-[#00d4ff]' : 'text-[#475569]'
              }`}>
              <span className="text-lg">{tab.icon}</span>
              <span className="text-[10px] font-medium">{tab.label}</span>
              {active && <span className="w-4 h-0.5 rounded-full bg-[#00d4ff] mt-0.5" />}
            </button>
          )
        })}
      </nav>
    </div>
  )
}
