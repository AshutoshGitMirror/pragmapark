interface SidebarProps {
  currentView: string; onNavigate: (v: string) => void; isAdmin: boolean;
}

const NAV_ITEMS = [
  { view: 'dashboard', label: 'Dashboard', icon: 'chart-pie' },
  { view: 'lots', label: 'Parking Lots', icon: 'warehouse' },
  { view: 'analytics', label: 'Analytics', icon: 'chart-line' },
  { view: 'revenue', label: 'Revenue', icon: 'dollar-sign' },
  { view: 'map', label: 'Map', icon: 'map-marked-alt' },
  { view: 'slots', label: 'Micro Slots', icon: 'th' },
  { view: 'alerts', label: 'Alerts', icon: 'bell' },
  { view: 'my-lots', label: 'My Lots', icon: 'edit' },
  { view: 'settings', label: 'Settings', icon: 'cog' },
]

export default function Sidebar({ currentView, onNavigate, isAdmin }: SidebarProps) {
  return (
    <aside
      className="fixed left-0 top-0 bottom-0 w-[240px] z-100 flex flex-col p-7 max-md:fixed max-md:left-[-280px] max-md:w-[260px] max-md:transition-all max-md:duration-300 max-md:z-100"
      style={{
        background: 'rgba(255,255,255,0.04)',
        backdropFilter: 'blur(32px)',
        WebkitBackdropFilter: 'blur(32px)',
        borderRight: '1px solid rgba(255,255,255,0.06)',
      }}
    >
      <div className="flex items-center gap-2.5 mb-9">
        <i className="fas fa-parking text-accent text-[22px]" />
        <span className="text-xl font-bold" style={{ color: '#e2b84d', textShadow: '0 0 30px rgba(226,184,77,0.25)' }}>Pragma</span>
      </div>
      <nav className="flex flex-col gap-0.5">
        {NAV_ITEMS.map(({ view, label, icon }) => {
          const isActive = currentView === view
          return (
            <a
              key={view}
              href="#"
              onClick={(e) => { e.preventDefault(); onNavigate(view) }}
              className="flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm no-underline transition-all duration-200"
              style={{
                color: isActive ? '#e2b84d' : '#a49fc4',
                background: isActive ? 'rgba(226,184,77,0.08)' : 'transparent',
              }}
              onMouseEnter={(e) => { if (!isActive) { e.currentTarget.style.background = 'rgba(255,255,255,0.09)'; e.currentTarget.style.color = '#f0eef8' } }}
              onMouseLeave={(e) => { if (!isActive) { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = '#a49fc4' } }}
            >
              <i className={`fas fa-${icon} w-5 text-center`} />
              {label}
            </a>
          )
        })}
      </nav>
      <div className="mt-auto pt-4" style={{ borderTop: '1px solid rgba(255,255,255,0.06)' }}>
        <div className="flex items-center gap-2 px-3 py-2 text-xs" style={{ color: 'rgba(240,238,248,0.4)' }}>
          <i className="fas fa-parking" />
          <span>v2.0.0</span>
        </div>
      </div>
    </aside>
  )
}
