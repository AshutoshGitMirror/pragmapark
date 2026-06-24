import { type ReactNode } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'

const TABS: { label: string; icon: string; hash: string; color: string }[] = [
  { label: 'Home', icon: '■', hash: '/driver/dashboard', color: '#f0c040' },
  { label: 'Find', icon: '⌕', hash: '/driver/find', color: '#00d4ff' },
  { label: 'Parking', icon: '◷', hash: '/driver/active', color: '#00c785' },
  { label: 'History', icon: '☰', hash: '/driver/history', color: '#a060f0' },
  { label: 'Transactions', icon: '⇄', hash: '/driver/transactions', color: '#f04060' },
  { label: 'Bookings', icon: '🗓', hash: '/driver/bookings', color: '#60d4a0' },
]

export function DriverLayout({ children }: { children: ReactNode }) {
  const navigate = useNavigate()
  const location = useLocation()
  const { user, logout } = useAuth()
  const currentHash = location.pathname || '/driver/dashboard'

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
            <p className="text-[10px] text-dim">{user?.full_name || 'Driver'}</p>
          </div>
        </div>
        <button onClick={() => { logout().then(() => { window.location.hash = '/driver/login' }).catch(() => { window.location.hash = '/driver/login' }) }}
          className="text-[10px] text-dim hover:text-[#ff6b6b] transition-colors px-2 py-1 rounded hover:bg-white/[0.03]">
          Sign Out
        </button>
      </header>

      <main className="flex-1 overflow-y-auto px-4 py-4 pb-20">
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
              className="group flex flex-col items-center gap-0.5 py-2 px-4 rounded-lg transition-all duration-150"
              style={{ color: active ? tab.color : '#475569' }}>
              <span className="text-lg transition-transform duration-200"
                style={{ transform: active ? 'scale(1.1)' : 'scale(1)' }}>
                {tab.icon}
              </span>
              <span className="text-[11px] font-medium">{tab.label}</span>
              {active && (
                <span className="w-4 h-0.5 rounded-full mt-0.5 transition-all"
                  style={{
                    background: tab.color,
                    boxShadow: `0 0 4px ${tab.color}66`,
                  }} />
              )}
            </button>
          )
        })}
      </nav>
    </div>
  )
}
