import { useState, useEffect, type ReactNode } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { WarmupProvider } from './components/layout/WarmupContext'
import { WarmupOverlay } from './components/layout/WarmupOverlay'
import { AnimatedSection } from './components/animations/AnimatedSection'
import { Hero } from './components/hero/Hero'
import { PredictionEngine } from './components/prediction/PredictionEngine'
import { RevenueIntelligence } from './components/revenue/RevenueIntelligence'
import { BlockchainLedger } from './components/blockchain/BlockchainLedger'
import { DigitalTwinSection } from './components/digital-twin/DigitalTwinSection'
import { MicroSlotGrid } from './components/slots/MicroSlotGrid'
import { ArchitectureDiagram } from './components/architecture/ArchitectureDiagram'
import { LiveTerminal } from './components/terminal/LiveTerminal'
import { TestimonialsSection } from './components/testimonials/TestimonialsSection'
import { Footer } from './components/footer/Footer'
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

function LandingPage() {
  const [dismissed, setDismissed] = useState(false)
  useEffect(() => {
    const handler = () => setDismissed(true)
    window.addEventListener('pragma:warmup-dismiss', handler)
    return () => window.removeEventListener('pragma:warmup-dismiss', handler)
  }, [])
  return (
    <WarmupProvider>
      <div className="bg-[#0a0a0f] text-white min-h-screen overflow-x-hidden relative">
        {/* Visual distinction badge identifying the interactive app vs static marketing page */}
        <div className="absolute top-4 left-4 z-50 flex items-center gap-2 px-3 py-1.5 rounded-full bg-[#00d4ff]/10 border border-[#00d4ff]/30 text-[10px] font-mono text-[#00d4ff] uppercase tracking-wider backdrop-blur-sm shadow-[0_0_12px_rgba(0,212,255,0.1)]">
          <span className="w-1.5 h-1.5 rounded-full bg-[#00d4ff] animate-pulse" />
          <span>Interactive App Platform</span>
        </div>
        <Hero />
        <AnimatedSection><PredictionEngine /></AnimatedSection>
        <AnimatedSection delay={0.1}><RevenueIntelligence /></AnimatedSection>
        <AnimatedSection delay={0.15}><BlockchainLedger /></AnimatedSection>
        <AnimatedSection delay={0.1}><DigitalTwinSection /></AnimatedSection>
        <AnimatedSection delay={0.15}><MicroSlotGrid /></AnimatedSection>
        <AnimatedSection delay={0.1}><ArchitectureDiagram /></AnimatedSection>
        <AnimatedSection delay={0.15}><LiveTerminal /></AnimatedSection>
        <AnimatedSection delay={0.1}><TestimonialsSection /></AnimatedSection>
        <AnimatedSection delay={0.2}><Footer /></AnimatedSection>
        {!dismissed && <WarmupOverlay />}
      </div>
    </WarmupProvider>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/" element={<ErrorBoundary><LandingPage /></ErrorBoundary>} />
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
