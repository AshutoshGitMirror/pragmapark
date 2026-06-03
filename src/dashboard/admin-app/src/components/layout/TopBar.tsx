import type { User } from '../../api/types'

interface TopBarProps {
  user: User; view: string; simSpeed: number;
  onSpeedChange: (s: number) => void; onLogout: () => void; isAdmin: boolean;
}

const VIEW_TITLES: Record<string, string> = {
  dashboard: 'Dashboard', lots: 'Parking Lots', analytics: 'Analytics',
  revenue: 'Revenue', map: 'Map', slots: 'Slots', alerts: 'Alerts',
  'my-lots': 'My Lots', settings: 'Settings',
}

export default function TopBar({ user, view, simSpeed, onSpeedChange, onLogout, isAdmin }: TopBarProps) {
  return (
    <div
      className="flex justify-between items-center mb-7 pb-5"
      style={{ borderBottom: '1px solid rgba(255,255,255,0.06)' }}
    >
      <h1 className="text-[26px] font-semibold -tracking-[0.3px]">
        {VIEW_TITLES[view] || 'Dashboard'}
      </h1>
      <div className="flex items-center gap-4">
        {isAdmin && (
          <div className="flex gap-1.5 items-center max-md:hidden">
            {[1, 10, 60].map((s) => (
              <button
                key={s}
                onClick={() => onSpeedChange(s)}
                className="px-2 py-1 text-[11px] rounded-md cursor-pointer font-inherit transition-all duration-200"
                style={{
                  background: simSpeed === s ? 'rgba(226,184,77,0.15)' : 'rgba(255,255,255,0.03)',
                  border: `1px solid ${simSpeed === s ? '#e2b84d' : 'rgba(255,255,255,0.06)'}`,
                  color: simSpeed === s ? '#e2b84d' : '#a49fc4',
                }}
              >
                {s}x
              </button>
            ))}
          </div>
        )}
        <div className="flex items-center gap-3 text-sm" style={{ color: '#a49fc4' }}>
          <span>{user.full_name || user.email}</span>
          <span className="text-xs" style={{ color: '#e2b84d' }}>{user.role}</span>
          <div
            className="w-9 h-9 rounded-full flex items-center justify-center font-semibold text-sm"
            style={{
              background: 'linear-gradient(135deg, #e2b84d, #c9a33e)',
              color: '#0b0b12',
              boxShadow: '0 0 20px rgba(226,184,77,0.15)',
            }}
          >
            {(user.full_name || user.email).charAt(0).toUpperCase()}
          </div>
          <button
            onClick={onLogout}
            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs cursor-pointer transition-all duration-200"
            style={{
              background: 'rgba(255,255,255,0.03)',
              border: '1px solid rgba(255,255,255,0.06)',
              color: '#a49fc4',
            }}
            onMouseEnter={(e) => { e.currentTarget.style.borderColor = 'rgba(226,184,77,0.3)'; e.currentTarget.style.color = '#e2b84d' }}
            onMouseLeave={(e) => { e.currentTarget.style.borderColor = 'rgba(255,255,255,0.06)'; e.currentTarget.style.color = '#a49fc4' }}
          >
            <i className="fas fa-sign-out-alt" /> Sign Out
          </button>
        </div>
      </div>
    </div>
  )
}
