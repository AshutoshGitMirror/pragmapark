import { type ReactNode, useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'

const VIOLET = '#a855f7'

export function ResidentLayout({ children }: { children: ReactNode }) {
  const navigate = useNavigate()
  const location = useLocation()
  const { user, logout } = useAuth()
  const [confirmSignOut, setConfirmSignOut] = useState(false)
  const currentHash = location.pathname || '/resident/dashboard'

  return (
    <div className="flex flex-col h-screen text-white overflow-hidden"
      style={{ background: 'linear-gradient(135deg, #0c0712 0%, #120a1c 50%, #0c0712 100%)' }}>
      <header className="shrink-0 px-5 py-4 flex items-center justify-between"
        style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg flex items-center justify-center text-sm font-bold text-white shadow-[0_0_12px_rgba(168,85,247,0.25)]"
            style={{ background: `linear-gradient(135deg, ${VIOLET}, #7c3aed)` }}>
            🏠
          </div>
          <div>
            <h1 className="text-sm font-semibold text-white">Resident Portal</h1>
            <p className="text-[10px] text-dim">{user?.full_name || 'Resident'}</p>
          </div>
        </div>
        {confirmSignOut ? (
          <div className="flex items-center gap-2">
            <span className="text-[9px] font-mono" style={{ color: '#7a8aaa' }}>Sign out?</span>
            <button onClick={() => { setConfirmSignOut(false); logout().then(() => { window.location.hash = '/resident/login' }).catch(() => { window.location.hash = '/resident/login' }) }}
              className="text-[10px] text-white bg-[#ff4757] px-2 py-1 rounded transition-colors font-semibold">
              Yes
            </button>
            <button onClick={() => setConfirmSignOut(false)}
              className="text-[10px] text-dim hover:text-white transition-colors px-2 py-1 rounded">
              No
            </button>
          </div>
        ) : (
          <button onClick={() => setConfirmSignOut(true)}
            className="text-[10px] text-dim hover:text-[#ff6b6b] transition-colors px-2 py-1 rounded hover:bg-white/[0.03]">
            Sign Out
          </button>
        )}
      </header>

      <main className="flex-1 overflow-y-auto px-4 py-4 pb-20">
        {children}
      </main>

      <nav className="shrink-0 flex items-center justify-around px-4 py-2"
        style={{
          background: '#140e1f',
          borderTop: '1px solid rgba(255,255,255,0.04)',
          boxShadow: '0 -4px 20px rgba(0,0,0,0.3)',
        }}>
        {[{ label: 'My Slot', icon: '🏠', hash: '/resident/dashboard', color: VIOLET }].map((tab) => {
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
                  style={{ background: tab.color, boxShadow: `0 0 4px ${tab.color}66` }} />
              )}
            </button>
          )
        })}
      </nav>
    </div>
  )
}
