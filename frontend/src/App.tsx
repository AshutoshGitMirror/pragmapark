import { type ReactNode, type ComponentType, lazy, Suspense } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { AuthProvider, useAuth } from './context/AuthContext'
import { AdminLayout } from './pages/admin/AdminLayout'
import { DriverLayout } from './pages/driver/DriverLayout'
import { ErrorBoundary } from './components/ErrorBoundary'

const LoginPage = lazy(() => import('./pages/admin/LoginPage').then(m => ({ default: m.LoginPage as unknown as ComponentType<any> })))
const DashboardPage = lazy(() => import('./pages/admin/DashboardPage').then(m => ({ default: m.DashboardPage as unknown as ComponentType<any> })))
const ParkingLotsPage = lazy(() => import('./pages/admin/ParkingLotsPage').then(m => ({ default: m.ParkingLotsPage as unknown as ComponentType<any> })))
const AnalyticsPage = lazy(() => import('./pages/admin/AnalyticsPage').then(m => ({ default: m.AnalyticsPage as unknown as ComponentType<any> })))
const RevenuePage = lazy(() => import('./pages/admin/RevenuePage').then(m => ({ default: m.RevenuePage as unknown as ComponentType<any> })))
const MapPage = lazy(() => import('./pages/admin/MapPage').then(m => ({ default: m.MapPage as unknown as ComponentType<any> })))
const MicroSlotsPage = lazy(() => import('./pages/admin/MicroSlotsPage').then(m => ({ default: m.MicroSlotsPage as unknown as ComponentType<any> })))
const AlertsPage = lazy(() => import('./pages/admin/AlertsPage').then(m => ({ default: m.AlertsPage as unknown as ComponentType<any> })))
const SettingsPage = lazy(() => import('./pages/admin/SettingsPage').then(m => ({ default: m.SettingsPage as unknown as ComponentType<any> })))
const ActuatorPage = lazy(() => import('./pages/admin/ActuatorPage').then(m => ({ default: m.ActuatorPage as unknown as ComponentType<any> })))

const DriverLoginPage = lazy(() => import('./pages/driver/DriverLoginPage').then(m => ({ default: m.DriverLoginPage as unknown as ComponentType<any> })))
const DriverDashboardPage = lazy(() => import('./pages/driver/DashboardPage').then(m => ({ default: m.DashboardPage as unknown as ComponentType<any> })))
const FindPage = lazy(() => import('./pages/driver/FindPage').then(m => ({ default: m.FindPage as unknown as ComponentType<any> })))
const ActiveSessionPage = lazy(() => import('./pages/driver/ActiveSessionPage').then(m => ({ default: m.ActiveSessionPage as unknown as ComponentType<any> })))
const HistoryPage = lazy(() => import('./pages/driver/HistoryPage').then(m => ({ default: m.HistoryPage as unknown as ComponentType<any> })))
const BookingsPage = lazy(() => import('./pages/driver/BookingsPage').then(m => ({ default: m.BookingsPage as unknown as ComponentType<any> })))
const TransactionsPage = lazy(() => import('./pages/driver/TransactionsPage').then(m => ({ default: m.TransactionsPage as unknown as ComponentType<any> })))

const Spinner = () => (
  <div className="min-h-screen flex items-center justify-center bg-[#07070d]">
    <div className="w-8 h-8 border-2 border-[#f0c040] border-t-transparent rounded-full animate-spin" />
  </div>
)

type RouteConfig = { path: string; Component: React.LazyExoticComponent<ComponentType<any>> }

const ADMIN_PAGES: RouteConfig[] = [
  { path: 'dashboard', Component: DashboardPage },
  { path: 'lots', Component: ParkingLotsPage },
  { path: 'analytics', Component: AnalyticsPage },
  { path: 'revenue', Component: RevenuePage },
  { path: 'map', Component: MapPage },
  { path: 'micro-slots', Component: MicroSlotsPage },
  { path: 'alerts', Component: AlertsPage },
  { path: 'settings', Component: SettingsPage },
  { path: 'actuator', Component: ActuatorPage },
]

function AdminGuard({ children }: { children: ReactNode }) {
  const { user, isAuthenticated, loading } = useAuth()
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#07070d]">
        <div className="w-8 h-8 border-2 border-[#f0c040] border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }
  if (!isAuthenticated) return <Navigate to="/login" replace />
  if (user && user.role === 'driver') return <Navigate to="/driver/dashboard" replace />
  return <AdminLayout>{children}</AdminLayout>
}

function DriverGuard({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth()
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#07070d]">
        <div className="w-8 h-8 border-2 border-cyan border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }
  if (!user || user.role !== 'driver') return <Navigate to="/driver/login" replace />
  return <DriverLayout>{children}</DriverLayout>
}

function PortalSelectorPage() {
  const navigate = (path: string) => {
    window.location.hash = path
  }

  return (
    <>
      <div className="relative min-h-screen flex items-center justify-center p-6 overflow-hidden" style={{ background: '#04040a' }}>
        <div className="absolute inset-0 opacity-[0.025]" style={{ backgroundImage: 'radial-gradient(circle, #fff 1px, transparent 1px)', backgroundSize: '48px 48px' }} />
        <div className="absolute top-1/4 left-1/2 -translate-x-1/2 w-[600px] h-[600px] rounded-full blur-[140px] opacity-20" style={{ background: 'radial-gradient(circle, rgba(0,212,255,0.15), transparent)' }} />
        <div className="absolute bottom-1/4 left-1/3 w-[400px] h-[400px] rounded-full blur-[100px] opacity-10" style={{ background: 'radial-gradient(circle, rgba(240,192,64,0.1), transparent)' }} />

        <div className="relative w-full max-w-4xl flex flex-col items-center">
          <div className="text-center mb-12">
            <motion.div
              initial={{ opacity: 0, y: -20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6 }}
              className="font-display text-[48px] font-black italic leading-none mb-3"
              style={{ color: '#f0c040', letterSpacing: '-2px' }}
            >
              Pragma<span style={{ color: '#5a6a8a' }}>.</span>
            </motion.div>

            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.2, duration: 0.6 }}
              className="flex items-center gap-2 justify-center mb-6"
            >
              <span className="w-8 h-px bg-gradient-to-r from-transparent to-[#f0c040]" />
              <span className="text-[10px] font-mono tracking-[4px] uppercase text-muted-alt">Smart Parking Ecosystem</span>
              <span className="w-8 h-px bg-gradient-to-l from-transparent to-[#f0c040]" />
            </motion.div>

            <motion.p
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.3, duration: 0.6 }}
              className="text-xs text-muted-alt max-w-md mx-auto leading-relaxed"
            >
              Select your access portal to enter the AI-driven smart city infrastructure, featuring multi-agent reinforcement learning, IoT fusion, and blockchain ledger settlement.
            </motion.p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-8 w-full">
            <motion.div
              initial={{ opacity: 0, x: -40 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.4, duration: 0.6 }}
              whileHover={{ y: -6, transition: { duration: 0.2 } }}
              onClick={() => navigate('/driver/login')}
              className="group relative cursor-pointer rounded-2xl p-8 overflow-hidden flex flex-col justify-between h-[280px]"
              style={{
                background: 'linear-gradient(135deg, rgba(14,14,28,0.8) 0%, rgba(10,10,24,0.8) 100%)',
                border: '1px solid rgba(255,255,255,0.06)',
                boxShadow: '0 8px 32px rgba(0,0,0,0.3)',
              }}
            >
              <div className="absolute top-0 left-0 w-full h-[2px] bg-gradient-to-r from-transparent via-[#00d4ff] to-transparent opacity-40 group-hover:opacity-100 transition-opacity" />
              <div className="absolute inset-0 bg-gradient-to-b from-[#00d4ff]/[0.02] to-transparent opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none" />

              <div>
                <div className="w-12 h-12 rounded-xl flex items-center justify-center mb-6 text-2xl"
                  style={{
                    background: 'rgba(0, 212, 255, 0.1)',
                    color: '#00d4ff',
                    border: '1px solid rgba(0, 212, 255, 0.2)',
                    boxShadow: '0 0 15px rgba(0, 212, 255, 0.1)',
                  }}
                >
                  ⌕
                </div>
                <h3 className="text-lg font-heading font-semibold text-white mb-2 group-hover:text-cyan transition-colors">
                  Driver Portal
                </h3>
                <p className="text-xs text-muted-alt leading-relaxed">
                  Locate real-time parking spaces, pre-book slots, top up your digital wallet, and manage active session payments with automated smart contract settlement.
                </p>
              </div>

              <div className="flex items-center gap-2 text-[10px] font-mono text-cyan uppercase tracking-wider mt-4">
                <span>Enter Portal</span>
                <span className="transform group-hover:translate-x-1 transition-transform">→</span>
              </div>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, x: 40 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.5, duration: 0.6 }}
              whileHover={{ y: -6, transition: { duration: 0.2 } }}
              onClick={() => navigate('/login')}
              className="group relative cursor-pointer rounded-2xl p-8 overflow-hidden flex flex-col justify-between h-[280px]"
              style={{
                background: 'linear-gradient(135deg, rgba(14,14,28,0.8) 0%, rgba(10,10,24,0.8) 100%)',
                border: '1px solid rgba(255,255,255,0.06)',
                boxShadow: '0 8px 32px rgba(0,0,0,0.3)',
              }}
            >
              <div className="absolute top-0 left-0 w-full h-[2px] bg-gradient-to-r from-transparent via-[#f0c040] to-transparent opacity-40 group-hover:opacity-100 transition-opacity" />
              <div className="absolute inset-0 bg-gradient-to-b from-[#f0c040]/[0.02] to-transparent opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none" />

              <div>
                <div className="w-12 h-12 rounded-xl flex items-center justify-center mb-6 text-2xl"
                  style={{
                    background: 'rgba(240, 192, 64, 0.1)',
                    color: '#f0c040',
                    border: '1px solid rgba(240, 192, 64, 0.2)',
                    boxShadow: '0 0 15px rgba(240, 192, 64, 0.1)',
                  }}
                >
                  ⚙
                </div>
                <h3 className="text-lg font-heading font-semibold text-white mb-2 group-hover:text-gold transition-colors">
                  Operator & Admin Portal
                </h3>
                <p className="text-xs text-muted-alt leading-relaxed">
                  Monitor live occupancy maps, inspect ML demand forecasting models, analyze real-time dynamic pricing heatmaps, and audit block mining on the blockchain ledger.
                </p>
              </div>

              <div className="flex items-center gap-2 text-[10px] font-mono text-gold uppercase tracking-wider mt-4">
                <span>Enter Portal</span>
                <span className="transform group-hover:translate-x-1 transition-transform">→</span>
              </div>
            </motion.div>
          </div>

          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.7, duration: 0.6 }}
            className="mt-16 text-center"
          >
            <p className="text-[8px] font-mono text-[#3a3a5a] tracking-[4px] uppercase">
              AI · MARL · Blockchain · City-Scale
            </p>
          </motion.div>
        </div>
      </div>
    </>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/" element={<ErrorBoundary><PortalSelectorPage /></ErrorBoundary>} />
        <Route path="/login" element={<ErrorBoundary><Suspense fallback={<Spinner />}><LoginPage /></Suspense></ErrorBoundary>} />
        {ADMIN_PAGES.map((p) => (
          <Route key={p.path} path={`/app/${p.path}`} element={<ErrorBoundary><AdminGuard><Suspense fallback={<Spinner />}><p.Component /></Suspense></AdminGuard></ErrorBoundary>} />
        ))}
        <Route path="/app" element={<Navigate to="/app/dashboard" replace />} />

        <Route path="/driver/login" element={<ErrorBoundary><Suspense fallback={<Spinner />}><DriverLoginPage /></Suspense></ErrorBoundary>} />
        <Route path="/driver/dashboard" element={<ErrorBoundary><DriverGuard><Suspense fallback={<Spinner />}><DriverDashboardPage /></Suspense></DriverGuard></ErrorBoundary>} />
        <Route path="/driver/find" element={<ErrorBoundary><DriverGuard><Suspense fallback={<Spinner />}><FindPage /></Suspense></DriverGuard></ErrorBoundary>} />
        <Route path="/driver/active" element={<ErrorBoundary><DriverGuard><Suspense fallback={<Spinner />}><ActiveSessionPage /></Suspense></DriverGuard></ErrorBoundary>} />
        <Route path="/driver/history" element={<ErrorBoundary><DriverGuard><Suspense fallback={<Spinner />}><HistoryPage /></Suspense></DriverGuard></ErrorBoundary>} />
        <Route path="/driver/transactions" element={<ErrorBoundary><DriverGuard><Suspense fallback={<Spinner />}><TransactionsPage /></Suspense></DriverGuard></ErrorBoundary>} />
        <Route path="/driver/bookings" element={<ErrorBoundary><DriverGuard><Suspense fallback={<Spinner />}><BookingsPage /></Suspense></DriverGuard></ErrorBoundary>} />
        <Route path="/driver" element={<Navigate to="/driver/dashboard" replace />} />

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AuthProvider>
  )
}
