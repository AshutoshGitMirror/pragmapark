import { useState, useEffect, type ReactNode } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { AuthProvider, useAuth } from './context/AuthContext'
import { AdminLayout } from './pages/admin/AdminLayout'
import { LoginPage } from './pages/admin/LoginPage'
import { DashboardPage } from './pages/admin/DashboardPage'
import { ParkingLotsPage } from './pages/admin/ParkingLotsPage'
import { AnalyticsPage } from './pages/admin/AnalyticsPage'
import { RevenuePage } from './pages/admin/RevenuePage'
import { MapPage } from './pages/admin/MapPage'
import { MicroSlotsPage } from './pages/admin/MicroSlotsPage'
import { AlertsPage } from './pages/admin/AlertsPage'
import { SettingsPage } from './pages/admin/SettingsPage'
import { ActuatorPage } from './pages/admin/ActuatorPage'
import { DriverLoginPage } from './pages/driver/DriverLoginPage'
import { DriverLayout } from './pages/driver/DriverLayout'
import { FindPage } from './pages/driver/FindPage'
import { ActiveSessionPage } from './pages/driver/ActiveSessionPage'
import { HistoryPage } from './pages/driver/HistoryPage'
import { DashboardPage as DriverDashboardPage } from './pages/driver/DashboardPage'
import { BookingsPage } from './pages/driver/BookingsPage'
import { TransactionsPage } from './pages/driver/TransactionsPage'
import { ErrorBoundary } from './components/ErrorBoundary'

const ADMIN_PAGES = [
  { path: 'dashboard', element: <DashboardPage /> },
  { path: 'lots', element: <ParkingLotsPage /> },
  { path: 'analytics', element: <AnalyticsPage /> },
  { path: 'revenue', element: <RevenuePage /> },
  { path: 'map', element: <MapPage /> },
  { path: 'micro-slots', element: <MicroSlotsPage /> },
  { path: 'alerts', element: <AlertsPage /> },
  { path: 'settings', element: <SettingsPage /> },
  { path: 'actuator', element: <ActuatorPage /> },
]

function AdminGuard({ children }: { children: ReactNode }) {
  const { isAuthenticated } = useAuth()
  if (!isAuthenticated) return <Navigate to="/login" replace />
  return <AdminLayout>{children}</AdminLayout>
}

function DriverGuard({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth()
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#07070d]">
        <div className="w-8 h-8 border-2 border-[#00d4ff] border-t-transparent rounded-full animate-spin" />
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
    <div className="relative min-h-screen flex items-center justify-center p-6 overflow-hidden" style={{ background: '#04040a' }}>
      {/* Background gradients */}
      <div className="absolute inset-0 opacity-[0.025]" style={{ backgroundImage: 'radial-gradient(circle, #fff 1px, transparent 1px)', backgroundSize: '48px 48px' }} />
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 w-[600px] h-[600px] rounded-full blur-[140px] opacity-20" style={{ background: 'radial-gradient(circle, rgba(0,212,255,0.15), transparent)' }} />
      <div className="absolute bottom-1/4 left-1/3 w-[400px] h-[400px] rounded-full blur-[100px] opacity-10" style={{ background: 'radial-gradient(circle, rgba(240,192,64,0.1), transparent)' }} />

      <div className="relative w-full max-w-4xl flex flex-col items-center">
        {/* Title / branding */}
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
            <span className="text-[10px] font-mono tracking-[4px] uppercase text-[#9a97b0]">Smart Parking Ecosystem</span>
            <span className="w-8 h-px bg-gradient-to-l from-transparent to-[#f0c040]" />
          </motion.div>

          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.3, duration: 0.6 }}
            className="text-xs text-[#9a97b0] max-w-md mx-auto leading-relaxed"
          >
            Select your access portal to enter the AI-driven smart city infrastructure, featuring multi-agent reinforcement learning, IoT fusion, and blockchain ledger settlement.
          </motion.p>
        </div>

        {/* Portal Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8 w-full">
          {/* Driver Portal */}
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
              <h3 className="text-lg font-heading font-semibold text-white mb-2 group-hover:text-[#00d4ff] transition-colors">
                Driver Portal
              </h3>
              <p className="text-xs text-[#9a97b0] leading-relaxed">
                Locate real-time parking spaces, pre-book slots, top up your digital wallet, and manage active session payments with automated smart contract settlement.
              </p>
            </div>

            <div className="flex items-center gap-2 text-[10px] font-mono text-[#00d4ff] uppercase tracking-wider mt-4">
              <span>Enter Portal</span>
              <span className="transform group-hover:translate-x-1 transition-transform">→</span>
            </div>
          </motion.div>

          {/* Admin/Owner Portal */}
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
              <h3 className="text-lg font-heading font-semibold text-white mb-2 group-hover:text-[#f0c040] transition-colors">
                Operator & Admin Portal
              </h3>
              <p className="text-xs text-[#9a97b0] leading-relaxed">
                Monitor live occupancy maps, inspect ML demand forecasting models, analyze real-time dynamic pricing heatmaps, and audit block mining on the blockchain ledger.
              </p>
            </div>

            <div className="flex items-center gap-2 text-[10px] font-mono text-[#f0c040] uppercase tracking-wider mt-4">
              <span>Enter Portal</span>
              <span className="transform group-hover:translate-x-1 transition-transform">→</span>
            </div>
          </motion.div>
        </div>

        {/* Footer info */}
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
  )
}

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/" element={<ErrorBoundary><PortalSelectorPage /></ErrorBoundary>} />
        <Route path="/login" element={<ErrorBoundary><LoginPage /></ErrorBoundary>} />
        {ADMIN_PAGES.map((p) => (
          <Route key={p.path} path={`/app/${p.path}`} element={<ErrorBoundary><AdminGuard>{p.element}</AdminGuard></ErrorBoundary>} />
        ))}
        <Route path="/app" element={<Navigate to="/app/dashboard" replace />} />

        <Route path="/driver/login" element={<ErrorBoundary><DriverLoginPage /></ErrorBoundary>} />
        <Route path="/driver/dashboard" element={<ErrorBoundary><DriverGuard><DriverDashboardPage /></DriverGuard></ErrorBoundary>} />
        <Route path="/driver/find" element={<ErrorBoundary><DriverGuard><FindPage /></DriverGuard></ErrorBoundary>} />
        <Route path="/driver/active" element={<ErrorBoundary><DriverGuard><ActiveSessionPage /></DriverGuard></ErrorBoundary>} />
        <Route path="/driver/history" element={<ErrorBoundary><DriverGuard><HistoryPage /></DriverGuard></ErrorBoundary>} />
        <Route path="/driver/transactions" element={<ErrorBoundary><DriverGuard><TransactionsPage /></DriverGuard></ErrorBoundary>} />
        <Route path="/driver/bookings" element={<ErrorBoundary><DriverGuard><BookingsPage /></DriverGuard></ErrorBoundary>} />
        <Route path="/driver" element={<Navigate to="/driver/dashboard" replace />} />

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AuthProvider>
  )
}
