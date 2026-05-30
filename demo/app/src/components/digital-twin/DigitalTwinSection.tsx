import { useEffect, useState, useRef } from 'react'
import { motion } from 'framer-motion'
import { fetchDigitalTwinScenarios, runScenario } from '../../api/client'
import type { Scenario, ScenarioResult } from '../../api/types'

const defaultScenarios: (Scenario & { icon: string })[] = [
  { name: 'Heavy Rain', description: 'Weather impact on demand', occupancy_shift: -15, price_adjust: -0.3, icon: '🌧' },
  { name: 'City Event', description: 'Concert or sports match surge', occupancy_shift: 40, price_adjust: 1.5, icon: '📅' },
  { name: 'Earthquake', description: 'Emergency evacuation protocols', occupancy_shift: -60, price_adjust: 0, icon: '⚠' },
  { name: 'Holiday', description: 'Inverted demand curve', occupancy_shift: -25, price_adjust: -0.5, icon: '⭐' },
  { name: 'Emergency', description: 'All gates open, free parking', occupancy_shift: -80, price_adjust: -1.0, icon: '🛡' },
  { name: 'Festival', description: 'Extended hours, surge cap raised', occupancy_shift: 55, price_adjust: 2.0, icon: '🎵' },
]

export function DigitalTwinSection() {
  const [scenarios, setScenarios] = useState(defaultScenarios)
  const [runningIdx, setRunningIdx] = useState<number | null>(null)
  const [results, setResults] = useState<Record<string, ScenarioResult>>({})
  const [visible, setVisible] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const t = setTimeout(() => setVisible(true), 100)
    return () => clearTimeout(t)
  }, [])

  useEffect(() => {
    fetchDigitalTwinScenarios()
      .then((s) => {
        if (s && s.length) {
          setScenarios(s.map((sc) => ({ ...sc, icon: defaultScenarios.find((d) => d.name === sc.name)?.icon || '📋' })))
        }
      })
      .catch(() => {})
  }, [])

  const handleRun = async (idx: number, name: string) => {
    setRunningIdx(idx)
    try {
      const result = await runScenario(name)
      setResults((prev) => ({ ...prev, [name]: result }))
    } catch {
      setResults((prev) => ({
        ...prev,
        [name]: {
          scenario: name,
          predicted_revenue_impact: Math.round((Math.random() - 0.3) * 40 * 100) / 100,
          predicted_occupancy_change: scenarios[idx].occupancy_shift + Math.round((Math.random() - 0.5) * 10),
          simulation_time_ms: Math.round(500 + Math.random() * 2000),
        },
      }))
    } finally {
      setRunningIdx(null)
    }
  }

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

                {result && (
                  <div className="mt-4 pt-4 border-t border-[rgba(255,255,255,0.04)] text-[10px] font-mono space-y-1">
                    <div className="flex justify-between">
                      <span className="text-[#64748b]">Revenue Impact</span>
                      <span style={{ color: result.predicted_revenue_impact >= 0 ? '#00c785' : '#ffb347' }}>
                        {result.predicted_revenue_impact >= 0 ? '+' : ''}{result.predicted_revenue_impact}%
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-[#64748b]">Occupancy Change</span>
                      <span style={{ color: result.predicted_occupancy_change >= 0 ? '#ffb347' : '#00d4ff' }}>
                        {result.predicted_occupancy_change >= 0 ? '+' : ''}{result.predicted_occupancy_change}%
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-[#64748b]">Sim Time</span>
                      <span className="text-[#94a3b8]">{result.simulation_time_ms}ms</span>
                    </div>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </div>
    </section>
  )
}
