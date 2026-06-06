import { useState, useEffect, useCallback, createContext, useContext, ReactNode } from 'react'
import { login, register, logout, fetchCurrentUser, fetchDashboard, fetchLots, fetchRevenue, fetchSlotGrid, fetchAlerts, fetchSimulationStatus, setSimulationSpeed, updateProfile } from './api/client'
import type { User, DashboardStats, Lot, RevenueData, SlotGridData, Alert, MicroSlot } from './api/types'
import Sidebar from './components/layout/Sidebar'
import TopBar from './components/layout/TopBar'
import LoginView from './components/auth/LoginView'
import RegisterView from './components/auth/RegisterView'
import DashboardView from './components/dashboard/DashboardView'
import ParkingLotsView from './components/lots/ParkingLotsView'
import AnalyticsView from './components/analytics/AnalyticsView'
import RevenueView from './components/revenue/RevenueView'
import MapView from './components/map/MapView'
import MicroSlotsView from './components/slots/MicroSlotsView'
import AlertsView from './components/alerts/AlertsView'
import MyLotsView from './components/mylots/MyLotsView'
import SettingsView from './components/settings/SettingsView'

interface AuthCtx {
  user: User | null; token: string | null; loading: boolean;
  onLogin: (email: string, password: string) => Promise<void>;
  onRegister: (data: any) => Promise<void>;
  onLogout: () => void;
}

export const AuthContext = createContext<AuthCtx>(null!)

export function useAuth() { return useContext(AuthContext) }

export default function App() {
  const [user, setUser] = useState<User | null>(null)
  const [token, setToken] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [view, setView] = useState('dashboard')
  const [showRegister, setShowRegister] = useState(false)
  const [stats, setStats] = useState<DashboardStats | null>(null)
  const [lots, setLots] = useState<Lot[]>([])
  const [revenue, setRevenue] = useState<RevenueData | null>(null)
  const [alerts, setAlerts] = useState<Alert[]>([])
  const [slotGrid, setSlotGrid] = useState<SlotGridData | null>(null)
  const [simSpeed, setSimSpeed] = useState(1)
  const [isAdmin, setIsAdmin] = useState(false)

  useEffect(() => {
    const handler = () => { setUser(null); setToken(null) }
    window.addEventListener('pragma:unauthorized', handler)
    return () => window.removeEventListener('pragma:unauthorized', handler)
  }, [])

  useEffect(() => {
    setLoading(true)
    fetchCurrentUser()
      .then((u) => {
        setUser(u)
        setIsAdmin(u.role === 'admin' || u.role === 'lot_owner' || u.role === 'city_planner')
        setLoading(false)
      })
      .catch(() => {
        setUser(null)
        setLoading(false)
      })
  }, [token])

  const refreshData = useCallback(async () => {
    try {
      const d = await fetchDashboard()
      setStats(d.stats as any)
      setLots(d.lots)
      if (d.alerts) setAlerts(d.alerts)
    } catch {}
    try {
      const r = await fetchRevenue()
      setRevenue(r)
    } catch {}
    try {
      const sim = await fetchSimulationStatus()
      setSimSpeed(sim.speedup)
    } catch {}
  }, [])

  useEffect(() => {
    if (user) refreshData()
    const interval = setInterval(() => { if (user) refreshData() }, 15000)
    return () => clearInterval(interval)
  }, [user, refreshData])

  const handleLogin = async (email: string, password: string) => {
    const data = await login(email, password)
    setToken(data.access_token || 'authenticated')
  }

  const handleRegister = async (data: any) => {
    const res = await register(data)
    setToken(res.access_token || 'authenticated')
  }

  const handleLogout = async () => {
    await logout()
    setUser(null)
    setToken(null)
    setStats(null)
    setLots([])
  }

  const handleSpeedChange = async (speed: number) => {
    try {
      await setSimulationSpeed(speed)
      setSimSpeed(speed)
    } catch {}
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: '#0a0a0f' }}>
        <div className="text-center">
          <div className="w-8 h-8 border-2 border-[#e2b84d] border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-muted text-sm">Loading...</p>
        </div>
      </div>
    )
  }

  if (!user) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{
        background: '#0a0a0f',
        backgroundImage: 'radial-gradient(ellipse at 20% 50%, rgba(226,184,77,0.15) 0%, transparent 50%), radial-gradient(ellipse at 80% 50%, rgba(129,140,248,0.10) 0%, transparent 50%)',
      }}>
        {showRegister ? (
          <RegisterView onRegister={handleRegister} onBack={() => setShowRegister(false)} />
        ) : (
          <LoginView onLogin={handleLogin} onRegister={() => setShowRegister(true)} />
        )}
      </div>
    )
  }

  const renderView = () => {
    switch (view) {
      case 'dashboard': return <DashboardView stats={stats} lots={lots} />
      case 'lots': return <ParkingLotsView lots={lots} onRefresh={refreshData} />
      case 'analytics': return <AnalyticsView lots={lots} />
      case 'revenue': return <RevenueView revenue={revenue} />
      case 'map': return <MapView lots={lots} />
      case 'slots': return <MicroSlotsView lots={lots} slotGrid={slotGrid} onSlotGrid={setSlotGrid} />
      case 'alerts': return <AlertsView alerts={alerts} />
      case 'my-lots': return <MyLotsView lots={lots} onRefresh={refreshData} />
      case 'settings': return <SettingsView user={user} onUpdate={(u) => setUser(u)} />
      default: return <DashboardView stats={stats} lots={lots} />
    }
  }

  return (
    <AuthContext.Provider value={{ user, token, loading, onLogin: handleLogin, onRegister: handleRegister, onLogout: handleLogout }}>
      <div className="min-h-screen flex" style={{ background: '#0a0a0f' }}>
        <Sidebar currentView={view} onNavigate={setView} isAdmin={isAdmin} />
        <main className="flex-1 ml-[240px] p-7 max-md:ml-0 max-md:p-4" style={{ animation: 'fadeUp 0.5s ease both' }}>
          <TopBar
            user={user}
            view={view}
            simSpeed={simSpeed}
            onSpeedChange={handleSpeedChange}
            onLogout={handleLogout}
            isAdmin={isAdmin}
          />
          {renderView()}
        </main>
      </div>
    </AuthContext.Provider>
  )
}
