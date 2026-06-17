import { useEffect, useState, useRef, useCallback } from 'react'
import { useReveal } from '../../hooks/useScrollReveal'
import { motion } from 'framer-motion'
import { fetchDigitalTwinScenarios, runScenario } from '../../api/client'
import type { Scenario, ScenarioRunResponse } from '../../api/types'

const ICON_MAP: Record<string, string> = {
  zone_closure: '🚧',
  price_surge: '📈',
  capacity_expansion: '🏗',
  weather_disruption: '🌧',
  holiday_spike: '📆',
}

export function DigitalTwinSection() {
  const [scenarios, setScenarios] = useState<(Scenario & { icon: string })[]>([])
  const [loading, setLoading] = useState(true)
  const [fetchError, setFetchError] = useState<string | null>(null)
  const [runningIdx, setRunningIdx] = useState<number | null>(null)
  const [results, setResults] = useState<Record<string, ScenarioRunResponse>>({})
  const visible = useReveal(100)
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    setLoading(true)
    setFetchError(null)
    fetchDigitalTwinScenarios()
      .then((s) => {
        if (s && s.length) {
          setScenarios(s.map((sc) => ({
            ...sc,
            icon: ICON_MAP[sc.name] || '📋',
          })))
        } else {
          setFetchError('No scenarios returned from backend.')
        }
      })
      .catch((err) => {
        setFetchError('Digital twin API unavailable. ' + (err?.message || ''))
      })
      .finally(() => setLoading(false))
  }, [])

  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  const handleRun = useCallback(async (idx: number, name: string) => {
    setRunningIdx(idx)
    setErrorMsg(null)
    try {
      const response = await runScenario(name)
      setResults((prev) => ({ ...prev, [name]: response }))
    } catch {
      setErrorMsg(`Scenario "${name}" failed. Backend may be warming up.`)
    } finally {
      setRunningIdx(null)
    }
  }, [])

  return (
    <section className="section bg-[#0e0e18]" id="digital-twin">
      <div className="section-inner">
        <div className={`text-center mb-16 transition-all duration-700 ${visible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'}`}>
          <p className="section-label" style={{ color: '#00c785' }}>DIGITAL TWIN</p>
          <h2 className="section-headline">Simulate before you deploy.</h2>
          <p className="section-body mx-auto text-center">
            Test pricing strategies against virtual scenarios — heavy rain, city-wide events, earthquakes, holidays.
            The digital twin runs the full prediction + pricing pipeline on synthetic data before changes reach production.
          </p>
        </div>

        {loading && (
          <div className="flex justify-center py-8">
            <div className="flex items-center gap-2 text-xs font-mono text-[#64748b]">
              <span className="w-1.5 h-1.5 rounded-full bg-[#00c785] animate-pulse" />
              Loading scenarios...
            </div>
          </div>
        )}

        {fetchError && !loading && (
          <div className="max-w-lg mx-auto p-4 rounded-xl text-xs font-mono text-center"
            style={{
              background: 'rgba(245,158,11,0.08)',
              border: '1px solid rgba(245,158,11,0.2)',
              color: '#f59e0b',
            }}>
            {fetchError}
          </div>
        )}

        {!loading && !fetchError && scenarios.length === 0 && (
          <div className="max-w-lg mx-auto p-4 rounded-xl text-xs font-mono text-center text-[#64748b]"
            style={{
              background: 'rgba(255,255,255,0.03)',
              border: '1px solid rgba(255,255,255,0.06)',
            }}>
            No digital twin scenarios available.
          </div>
        )}

        {!loading && scenarios.length > 0 && (
          <div
            ref={scrollRef}
            className={`flex gap-5 overflow-x-auto pb-4 transition-all duration-700 delay-200 ${
              visible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'
            }`}
            style={{ scrollbarWidth: 'thin', scrollbarColor: 'rgba(255,255,255,0.1) transparent' }}
          >
            {scenarios.map((s, i) => {
              const result = results[s.name]
              return (
                <div
                  key={s.name}
                  className="min-w-[280px] bg-[#13131f] border border-[rgba(255,255,255,0.06)] rounded-xl p-6 shrink-0"
                >
                  <div className="text-2xl mb-3">{s.icon}</div>
                  <h3 className="text-base font-medium text-white mb-1">{s.name}</h3>
                  <p className="text-xs text-[#94a3b8] mb-4">{s.description}</p>

                  <div className="flex gap-4 mb-4 text-xs font-mono">
                    <div>
                      <span className="text-[#64748b]">Occ: </span>
                      <span style={{ color: s.occupancy_shift > 0 ? '#ffb347' : '#00d4ff' }}>
                        {s.occupancy_shift > 0 ? '+' : ''}{s.occupancy_shift}%
                      </span>
                    </div>
                    <div>
                      <span className="text-[#64748b]">Price: </span>
                      <span style={{ color: s.price_adjust > 0 ? '#ffb347' : '#00d4ff' }}>
                        {s.price_adjust > 0 ? '+' : ''}{s.price_adjust}x
                      </span>
                    </div>
                  </div>

                  <motion.button
                    onClick={() => handleRun(i, s.name)}
                    disabled={runningIdx === i}
                    whileHover={runningIdx === i ? {} : { scale: 1.03 }}
                    whileTap={runningIdx === i ? {} : { scale: 0.97 }}
                    className="w-full py-2 px-4 rounded-lg text-xs font-mono font-medium border border-[rgba(255,255,255,0.1)] text-[#94a3b8] hover:border-[#00c785] hover:text-[#00c785] transition-all disabled:opacity-40"
                  >
                    {runningIdx === i ? (
                      <span className="flex items-center justify-center gap-2">
                        <span className="w-3 h-3 rounded-full border border-[#00c785] border-t-transparent animate-spin" />
                        Simulating...
                      </span>
                    ) : result ? 'Re-run' : 'Run Simulation'}
                  </motion.button>

                  {result && result.comparisons && result.comparisons.length > 0 && (
                    <div className="mt-4 pt-4 border-t border-[rgba(255,255,255,0.04)] text-[10px] font-mono space-y-1">
                      <div className="flex justify-between">
                        <span className="text-[#64748b]">Price Impact</span>
                        <span className="text-[#94a3b8]">{result.comparisons[0].price_delta}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-[#64748b]">Occupancy Change</span>
                        <span className="text-[#94a3b8]">{result.comparisons[0].occupancy_delta}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-[#64748b]">Congestion</span>
                        <span className="text-[#94a3b8]">{result.comparisons[0].congestion}</span>
                      </div>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}

        {errorMsg && (
          <div className="mt-4 mx-auto max-w-lg p-3 rounded-lg text-xs font-mono text-center"
            style={{
              background: 'rgba(245,158,11,0.08)',
              border: '1px solid rgba(245,158,11,0.2)',
              color: '#f59e0b',
            }}>
            {errorMsg}
          </div>
        )}
      </div>
    </section>
  )
}
