import { useState, useEffect } from 'react'
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

function AdminGuard({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, user } = useAuth()
  if (!isAuthenticated) return <LoginPage />
  return <AdminLayout>{children}</AdminLayout>
}

function DriverGuard({ children }: { children: React.ReactNode }) {
  const token = sessionStorage.getItem('pragma_driver_token')
  if (!token) return <DriverLoginPage />
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
      <div className="bg-[#0a0a0f] text-white min-h-screen overflow-x-hidden">
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
        <Route path="/" element={<LandingPage />} />
        <Route path="/login" element={<LoginPage />} />
        {ADMIN_PAGES.map((p) => (
          <Route key={p.path} path={`/app/${p.path}`} element={<AdminGuard>{p.element}</AdminGuard>} />
        ))}
        <Route path="/app" element={<Navigate to="/app/dashboard" replace />} />

        <Route path="/driver/login" element={<DriverLoginPage />} />
        <Route path="/driver/find" element={<DriverGuard><FindPage /></DriverGuard>} />
        <Route path="/driver/active" element={<DriverGuard><ActiveSessionPage /></DriverGuard>} />
        <Route path="/driver/history" element={<DriverGuard><HistoryPage /></DriverGuard>} />
        <Route path="/driver" element={<Navigate to="/driver/find" replace />} />

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AuthProvider>
  )
}
