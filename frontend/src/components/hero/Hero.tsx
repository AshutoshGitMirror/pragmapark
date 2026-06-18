import { useEffect, useState, useMemo } from 'react'
import { ThreeGlobe } from './ThreeGlobe'
import { MetricTicker } from './MetricTicker'
import { fetchLots, fetchDashboard } from '../../api/client'
import { useApi } from '../../hooks/useApi'

export function Hero() {
  const { data: lots, source: lotsSource, error: lotsError } = useApi(
    () => fetchLots(),
  )
  const { data: dashboard, source: dashSource } = useApi(
    () => fetchDashboard(),
  )

  const isLive = lotsSource === 'live' || dashSource === 'live'
  const isLoading = lotsSource === 'loading' || dashSource === 'loading'
  const hasError = lotsSource === 'error' && dashSource === 'error'

  const totalSlots = useMemo(
    () => (lots || []).reduce((a, l) => a + (l.total_slots || 0), 0),
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
        <p
          className={`font-mono text-xs tracking-[0.1em] text-muted uppercase mb-8 transition-all duration-800 ${
            showTitles ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4'
          }`}
          style={{ transitionDelay: '150ms' }}
        >
          AI · MARL · Blockchain · City-Scale Infrastructure
          {isLive && (
            <span className="ml-3 inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-[rgba(0,199,133,0.1)] border border-[rgba(0,199,133,0.2)]">
              <span className="w-1.5 h-1.5 rounded-full bg-[#00c785] animate-pulse" />
              <span className="text-[9px] font-mono text-emerald">LIVE</span>
            </span>
          )}
        </p>

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
            className={`block text-[clamp(1rem,2vw,20px)] font-mono text-muted tracking-[0.05em] uppercase mt-2 transition-all duration-800 ${
              showTitles ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-5'
            }`}
            style={{ transitionDelay: '1.5s' }}
          >
            Autonomous Parking Intelligence
          </span>
        </h1>

        <p
          className={`text-lg text-muted max-w-[560px] leading-relaxed mb-8 transition-all duration-800 ${
            showTitles ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-5'
          }`}
          style={{ transitionDelay: '1.8s' }}
        >
          Where AI prediction meets blockchain truth. Every slot. Every second. Optimized.
        </p>

        <a
          href="#/login"
          className={`inline-flex items-center gap-2 px-6 py-3 rounded-lg text-sm font-mono font-medium bg-[#00d4ff]/10 border border-cyan/30 text-cyan hover:bg-[#00d4ff]/20 hover:border-cyan transition-all duration-300 mb-10 ${
            showTitles ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-5'
          }`}
          style={{ transitionDelay: '2.0s' }}
        >
          Try Live Demo
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
          </svg>
        </a>

        {isLoading && (
          <div className="flex items-center gap-2 text-dim text-xs font-mono mb-4">
            <span className="w-1.5 h-1.5 rounded-full bg-[#00d4ff] animate-pulse" />
            Loading live data...
          </div>
        )}

        {hasError && (
          <div className="mb-4 p-3 bg-red-950/40 border border-red-500/30 text-red-200 text-xs font-mono rounded-lg max-w-md">
            Unable to connect to backend. {lotsError || ''}
          </div>
        )}

        <MetricTicker
          lotsCount={lots ? lots.length : 0}
          totalSlots={totalSlots}
          totalRevenue={dashboard?.total_revenue}
          isLive={isLive}
        />
      </div>

      <div className="absolute bottom-8 left-1/2 -translate-x-1/2 z-10 flex flex-col items-center gap-2 animate-bounce">
        <span className="text-[10px] font-mono text-[rgba(255,255,255,0.2)] tracking-[0.2em]">SCROLL</span>
        <div className="w-px h-10 bg-gradient-to-b from-transparent to-[#00d4ff]" />
      </div>
    </section>
  )
}
