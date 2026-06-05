/**
 * Hero.tsx — Command center hero with live lot + dashboard data.
 *
 * BEFORE (broken):
 *   - fetchLots().catch(() => {}) + fetchDashboard().catch(() => {})
 *   - MetricTicker received undefined for lotsCount, totalRevenue, totalSessions
 *   - Ticker pills showed hardcoded values: "21 Cities", "50000+ Slots"
 *
 * AFTER (fixed):
 *   - Two useApiWithFallback calls: one for lots, one for dashboard
 *   - MetricTicker receives real data (or consistent fallback)
 *   - "21 Cities Active" → actual lots.length
 *   - "50K+ Slots Managed" → actual sum of total_slots
 *   - Shows "LIVE" indicator when connected
 */

import { useEffect, useState, useMemo } from 'react'
import { ThreeGlobe } from './ThreeGlobe'
import { MetricTicker } from './MetricTicker'
import { fetchLots, fetchDashboard } from '../../api/client'
import { fallbackLots, fallbackDashboard } from '../../api/fallbackData'
import { useApiWithFallback } from '../../hooks/useApi'

export function Hero() {
  // ── FIX: Two independent useApiWithFallback calls ──
  const { data: lots, source: lotsSource } = useApiWithFallback(
    () => fetchLots(),
    fallbackLots,
  )
  const { data: dashboard, source: dashSource } = useApiWithFallback(
    () => fetchDashboard(),
    fallbackDashboard,
  )

  const isLive = lotsSource === 'live' || dashSource === 'live'

  // Compute real metrics from lot data
  const totalSlots = useMemo(
    () => lots.reduce((a, l) => a + (l.total_slots || 0), 0),
    [lots],
  )

  const [showTitles, setShowTitles] = useState(false)
  useEffect(() => {
    const t = setTimeout(() => setShowTitles(true), 200)
    return () => clearTimeout(t)
  }, [])

  return (
    <section className="relative min-h-screen flex flex-col items-center justify-center overflow-hidden bg-[#0a0a0f]">
      <ThreeGlobe />

      <div className="relative z-10 flex flex-col items-center text-center px-6">
        {/* Status line */}
        <p
          className={`font-mono text-xs tracking-[0.1em] text-[#94a3b8] uppercase mb-8 transition-all duration-800 ${
            showTitles ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4'
          }`}
          style={{ transitionDelay: '150ms' }}
        >
          AI · MARL · Blockchain · City-Scale Infrastructure
          {isLive && (
            <span className="ml-3 inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-[rgba(0,199,133,0.1)] border border-[rgba(0,199,133,0.2)]">
              <span className="w-1.5 h-1.5 rounded-full bg-[#00c785] animate-pulse" />
              <span className="text-[9px] font-mono text-[#00c785]">LIVE</span>
            </span>
          )}
        </p>

        {/* Title */}
        <h1 className="mb-4">
          <span
            className={`block text-[clamp(3rem,10vw,96px)] font-[300] tracking-[-0.03em] text-white leading-[1] transition-all duration-1000 ${
              showTitles ? 'opacity-100' : 'opacity-0'
            }`}
            style={{
              clipPath: showTitles ? 'inset(0)' : 'inset(0 100% 0 0)',
              transition: 'clip-path 1.2s cubic-bezier(0.23,1,0.32,1)',
            }}
          >
            PRAGMA
          </span>
          <span
            className={`block text-[clamp(1rem,2vw,20px)] font-mono text-[#94a3b8] tracking-[0.05em] uppercase mt-2 transition-all duration-800 ${
              showTitles ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-5'
            }`}
            style={{ transitionDelay: '1.5s' }}
          >
            Autonomous Parking Intelligence
          </span>
        </h1>

        {/* Tagline */}
        <p
          className={`text-lg text-[#94a3b8] max-w-[560px] leading-relaxed mb-8 transition-all duration-800 ${
            showTitles ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-5'
          }`}
          style={{ transitionDelay: '1.8s' }}
        >
          Where AI prediction meets blockchain truth. Every slot. Every second. Optimized.
        </p>

        {/* Try Now CTA */}
        <a
          href="#/login"
          className={`inline-flex items-center gap-2 px-6 py-3 rounded-lg text-sm font-mono font-medium bg-[#00d4ff]/10 border border-[#00d4ff]/30 text-[#00d4ff] hover:bg-[#00d4ff]/20 hover:border-[#00d4ff] transition-all duration-300 mb-10 ${
            showTitles ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-5'
          }`}
          style={{ transitionDelay: '2.0s' }}
        >
          Try Live Demo
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
          </svg>
        </a>

        {/* ── FIX: MetricTicker now receives REAL computed values ── */}
        <MetricTicker
          lotsCount={lots.length}
          totalSlots={totalSlots}
          totalRevenue={dashboard?.total_revenue}
          isLive={isLive}
        />
      </div>

      {/* Scroll indicator */}
      <div className="absolute bottom-8 left-1/2 -translate-x-1/2 z-10 flex flex-col items-center gap-2 animate-bounce">
        <span className="text-[10px] font-mono text-[rgba(255,255,255,0.2)] tracking-[0.2em]">SCROLL</span>
        <div className="w-px h-10 bg-gradient-to-b from-transparent to-[#00d4ff]" />
      </div>
    </section>
  )
}
