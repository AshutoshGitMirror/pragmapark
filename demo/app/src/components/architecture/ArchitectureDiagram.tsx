import { useEffect, useState } from 'react'

const layers = [
  {
    name: 'User Layer',
    items: ['Mobile App', 'Admin Dashboard', 'API Gateway'],
    color: '#00d4ff',
  },
  {
    name: 'Prediction Layer',
    items: ['Random Forest', 'XGBoost Ensemble', 'Temporal Encoding', 'Feature Pipeline'],
    color: '#00c785',
  },
  {
    name: 'Pricing Layer',
    items: ['QMIX Agents', 'Surge Detection', 'Zone Manager', 'Reward Model'],
    color: '#ffb347',
  },
  {
    name: 'Blockchain Layer',
    items: ['PoW Chain', 'IPFS Store', 'Ledger Outbox', 'Verifier'],
    color: '#00d4ff',
  },
  {
    name: 'IoT Layer',
    items: ['Camera Nodes', 'Sensor Grid', 'License Plate OCR', 'Event Bus'],
    color: '#94a3b8',
  },
]

export function ArchitectureDiagram() {
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    const t = setTimeout(() => setVisible(true), 100)
    return () => clearTimeout(t)
  }, [])

  return (
    <section className="section bg-[#0e0e18]" id="architecture">
      <div className="section-inner">
        <div className={`text-center mb-16 transition-all duration-700 ${visible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'}`}>
          <p className="section-label" style={{ color: '#00d4ff' }}>SYSTEM ARCHITECTURE</p>
          <h2 className="section-headline">Five layers of intelligence.</h2>
          <p className="section-body mx-auto text-center">
            From IoT camera to immutable ledger — every component is designed for failure isolation,
            horizontal scaling, and sub-second feedback loops.
          </p>
        </div>

        <div className={`max-w-5xl mx-auto transition-all duration-700 delay-200 ${visible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'}`}>
          {layers.map((layer, li) => (
            <div key={layer.name} className="relative">
              {li > 0 && (
                <div className="flex justify-center">
                  <div className="w-px h-6 bg-gradient-to-b from-transparent to-[rgba(255,255,255,0.06)]" />
                </div>
              )}
              <div
                className="flex items-stretch gap-4 transition-all duration-500"
                style={{
                  opacity: visible ? 1 : 0,
                  transform: visible ? 'translateY(0)' : 'translateY(20px)',
                  transitionDelay: `${300 + li * 100}ms`,
                }}
              >
                <div className="w-32 shrink-0 flex flex-col justify-center">
                  <p className="text-xs font-mono tracking-[0.1em]" style={{ color: layer.color }}>
                    {layer.name}
                  </p>
                </div>
                <div className="flex-1 bg-[#13131f] rounded-lg border border-[rgba(255,255,255,0.06)] p-4">
                  <div className="flex flex-wrap gap-2">
                    {layer.items.map((item) => (
                      <span
                        key={item}
                        className="text-xs font-mono text-[#94a3b8] px-3 py-1.5 rounded-md"
                        style={{
                          background: `${layer.color}08`,
                          border: `1px solid ${layer.color}15`,
                        }}
                      >
                        {item}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          ))}

          <div className="flex justify-center mt-10">
            <div className="flex items-center gap-6 text-xs font-mono text-[#64748b]">
              <span className="flex items-center gap-2">
                <span className="w-8 h-px bg-[#00d4ff]" /> 10 Gbps Internal
              </span>
              <span className="flex items-center gap-2">
                <span className="w-8 h-px bg-[#ffb347]" /> Event Bus
              </span>
              <span className="flex items-center gap-2">
                <span className="w-8 h-px bg-[#00c785]" /> gRPC Stream
              </span>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
