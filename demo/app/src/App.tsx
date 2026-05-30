/**
 * App.tsx — Root component.
 *
 * BEFORE (broken):
 *   - Rendered NOTHING until WarmupOverlay called onReady() after fake 6s timer
 *   - All 10 sections were blocked behind a boolean gate
 *   - Users saw a spinner for 6s, then everything appeared at once
 *   - No actual backend check happened
 *
 * AFTER (fixed):
 *   - WarmupProvider wraps everything — provides shared backend state
 *   - ALL sections render IMMEDIATELY with fallback data
 *   - WarmupOverlay is a visual layer on top — doesn't block rendering
 *   - When backend comes online, components auto-refetch via useApiWithFallback
 *   - Content is visible within ~100ms of page load (not 6s)
 */

import { useState, useEffect } from 'react'
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

export default function App() {
  const [dismissed, setDismissed] = useState(false)

  // Listen for manual dismiss from WarmupOverlay
  useEffect(() => {
    const handler = () => setDismissed(true)
    window.addEventListener('pragma:warmup-dismiss', handler)
    return () => window.removeEventListener('pragma:warmup-dismiss', handler)
  }, [])

  return (
    <WarmupProvider>
      <div className="bg-[#0a0a0f] text-white min-h-screen overflow-x-hidden">
        {/* ── CRITICAL FIX: Sections render immediately ── */}
        {/* They use useApiWithFallback which shows fallback data instantly, */}
        {/* then auto-refetches when backend comes online. */}
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

        {/* ── Overlay sits on top, doesn't block rendering ── */}
        {!dismissed && <WarmupOverlay />}
      </div>
    </WarmupProvider>
  )
}
