import { useState, useEffect } from 'react'

interface LayerNode {
  id: number
  name: string
  color: string
  glowColor: string
  subtitle: string
  telemetry: Record<string, string | number>
}

const LAYERS: LayerNode[] = [
  {
    id: 1,
    name: 'IoT Sensor Fusion',
    color: '#00ff66',
    glowColor: 'rgba(0, 255, 102, 0.4)',
    subtitle: 'Dual-sensor real-time validation',
    telemetry: {
      'Ultrasonic Confidence': '92%',
      'Vision Confidence': '88%',
      'Consensus Decision': 'Occupied',
      'Net Event Flux': '+1.4/min',
      'Environment Noise': '2.1dB'
    }
  },
  {
    id: 2,
    name: 'ML Forecasts',
    color: '#00f0ff',
    glowColor: 'rgba(0, 240, 255, 0.4)',
    subtitle: 'RidgeCV + XGBoost 15m predictions',
    telemetry: {
      'Active Models': 'RidgeCV, XGB, RF',
      'Feature Set Count': '19 Engineered',
      'Hour-Squared Weight': '0.428',
      'Cyclical Day Match': '94.1%',
      'Forecast Horizon': '15 minutes'
    }
  },
  {
    id: 3,
    name: 'Blockchain Ledger',
    color: '#ffaa00',
    glowColor: 'rgba(255, 170, 0, 0.4)',
    subtitle: 'PoW transaction execution',
    telemetry: {
      'Last Block Mined': '0x8f2a...1e40',
      'Pending Pool Size': '3 Txs',
      'Staking Validators': '12 Nodes',
      'Revenue Contract Share': '60/40 Split',
      'IPFS Storage CID': 'QmYwAP3...c4e'
    }
  },
  {
    id: 4,
    name: 'RL Price Agent',
    color: '#f43f5e',
    glowColor: 'rgba(244, 63, 94, 0.4)',
    subtitle: 'NumPy DQN Tariff Optimizations',
    telemetry: {
      'Agent Framework': 'NumPy DQN MLP',
      'Epsilon Value': '0.12 (Decayed)',
      'Chosen Q-Value': '14.86',
      'Optimized Rate': '$2.50/hour',
      'Convergence Error': '0.0012'
    }
  },
  {
    id: 5,
    name: 'Digital Twin Simulation',
    color: '#a855f7',
    glowColor: 'rgba(168, 85, 247, 0.4)',
    subtitle: 'CVAE-WGAN counterfactual scenarios',
    telemetry: {
      'Scenario Set': '5 Running',
      'Generative Samples': '256/sec',
      'STID Corr Index': '0.78',
      'Reconstruction Loss': '0.014',
      'Adversarial Critic Score': '0.94'
    }
  },
  {
    id: 6,
    name: 'Actuator Control',
    color: '#94a3b8',
    glowColor: 'rgba(148, 163, 184, 0.4)',
    subtitle: 'Physical state dispatching',
    telemetry: {
      'Smart Barrier': 'CLOSED (Secure)',
      'Pricing Board': '$2.50/hr LCD',
      'Congestion Light': 'RED (High Load)',
      'gRPC Signal Latency': '14ms',
      'Health Status': 'Normal (100%)'
    }
  }
]

export function CircularNexus() {
  const [activeLayer, setActiveLayer] = useState<number>(1)
  const [pulseActive, setPulseActive] = useState<boolean>(false)
  const [pulseLayer, setPulseLayer] = useState<number>(0)

  useEffect(() => {
    if (pulseActive) {
      const interval = setInterval(() => {
        setPulseLayer((prev) => {
          if (prev >= 6) {
            setPulseActive(false)
            return 0;
          }
          return prev + 1
        })
      }, 700)
      return () => clearInterval(interval)
    }
  }, [pulseActive])

  const triggerPulse = () => {
    if (pulseActive) return
    setPulseActive(true)
    setPulseLayer(1)
  }

  // Radial angles for 6 nodes (in degrees, starting from top)
  const getCoordinates = (index: number) => {
    const angle = (index * 60 - 90) * (Math.PI / 180)
    const radius = 140 // radius of the nexus circle
    return {
      x: 180 + radius * Math.cos(angle),
      y: 180 + radius * Math.sin(angle)
    }
  }

  const activeData = LAYERS.find(l => l.id === (pulseActive ? pulseLayer : activeLayer)) || LAYERS[0]

  return (
    <div className="w-full bg-[#07070e] border border-[rgba(0,255,102,0.1)] rounded-lg p-6 relative overflow-hidden crt-grid">
      <div className="absolute top-2 left-2 flex items-center gap-1.5 px-2 py-0.5 rounded bg-[#00ff66]/10 border border-[#00ff66]/20">
        <span className="w-1.5 h-1.5 rounded-full bg-[#00ff66] animate-pulse" />
        <span className="text-[9px] font-mono text-emerald">AUTONOMOUS SYSTEM NEXUS</span>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[45%_55%] gap-8 items-center mt-4">
        {/* Radial SVG Visualization */}
        <div className="flex justify-center items-center">
          <div className="relative w-[360px] h-[360px] select-none">
            {/* SVG connections & paths */}
            <svg className="absolute inset-0 w-full h-full pointer-events-none">
              {/* Main Ring */}
              <circle cx="180" cy="180" r="140" fill="none" stroke="rgba(0, 255, 102, 0.05)" strokeWidth="4" />
              
              {/* Circular flow path */}
              <path
                d="M 180,40 A 140,140 0 1,1 179.9,40"
                fill="none"
                stroke="rgba(0, 240, 255, 0.08)"
                strokeWidth="2"
                strokeDasharray="6 4"
              />

              {/* Pulsing signal between nodes */}
              {pulseActive && (
                <circle
                  cx={getCoordinates(pulseLayer - 1).x}
                  cy={getCoordinates(pulseLayer - 1).y}
                  r="8"
                  fill={LAYERS[pulseLayer - 1]?.color || '#00ff66'}
                  className="animate-ping"
                  style={{ opacity: 0.8 }}
                />
              )}
            </svg>

            {/* Central HUD Core */}
            <div 
              className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-48 h-48 rounded-full bg-[#030307] border border-[rgba(0,255,102,0.15)] flex flex-col items-center justify-center p-4 text-center shadow-[inset_0_0_20px_rgba(0,255,102,0.05)] transition-all duration-300"
              style={{ borderColor: activeData.color + '40' }}
            >
              <span className="text-[10px] text-white/40 uppercase tracking-widest font-mono">Layer {activeData.id}</span>
              <h4 className="text-xs font-bold font-mono tracking-tight mt-1 text-white truncate max-w-full" style={{ textShadow: `0 0 6px ${activeData.color}40`, color: activeData.color }}>
                {activeData.name}
              </h4>
              <p className="text-[9px] text-[#8fa0b5] mt-1 line-clamp-2 leading-tight px-1">
                {activeData.subtitle}
              </p>
              
              {/* Pulse trigger inside HUD */}
              <button
                onClick={triggerPulse}
                disabled={pulseActive}
                className={`mt-4 px-3 py-1 rounded text-[9px] font-mono border transition-all duration-150 ${
                  pulseActive
                    ? 'border-white/10 text-white/30 bg-white/5 cursor-not-allowed'
                    : 'border-[#00ff66]/30 text-emerald bg-[#00ff66]/5 hover:bg-[#00ff66]/15 hover:border-[#00ff66]'
                }`}
              >
                {pulseActive ? 'PROPAGATING...' : 'TRIGGER FLOW'}
              </button>
            </div>

            {/* Layer Stations (Nodes) */}
            {LAYERS.map((layer, index) => {
              const { x, y } = getCoordinates(index)
              const isActive = (pulseActive ? pulseLayer === layer.id : activeLayer === layer.id)
              return (
                <button
                  key={layer.id}
                  onClick={() => !pulseActive && setActiveLayer(layer.id)}
                  className="absolute -translate-x-1/2 -translate-y-1/2 w-10 h-10 rounded-full flex items-center justify-center border transition-all duration-300 focus:outline-none z-10"
                  style={{
                    left: `${x}px`,
                    top: `${y}px`,
                    backgroundColor: isActive ? layer.color + '15' : '#030307',
                    borderColor: isActive ? layer.color : 'rgba(255,255,255,0.08)',
                    boxShadow: isActive ? `0 0 12px ${layer.glowColor}` : 'none'
                  }}
                  title={layer.name}
                >
                  <span 
                    className="text-xs font-bold font-mono"
                    style={{ color: isActive ? layer.color : '#4e5f73' }}
                  >
                    L{layer.id}
                  </span>
                </button>
              )
            })}
          </div>
        </div>

        {/* HUD Telemetry Details */}
        <div className="flex flex-col h-full justify-between">
          <div>
            <div className="flex justify-between items-start border-b border-white/[0.06] pb-3">
              <div>
                <span className="text-[10px] font-mono text-[#8fa0b5] uppercase">Layer Register Telemetry</span>
                <h3 className="text-base font-bold font-mono text-white mt-1 flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full" style={{ backgroundColor: activeData.color }} />
                  {activeData.name}
                </h3>
              </div>
              <span className="text-xs font-mono text-white/30 uppercase mt-1">
                Reg_0{activeData.id} // OK
              </span>
            </div>

            <div className="mt-4 space-y-2">
              {Object.entries(activeData.telemetry).map(([key, val]) => (
                <div key={key} className="flex justify-between items-center text-xs font-mono py-1.5 border-b border-white/[0.02]">
                  <span className="text-[#8fa0b5]">{key}:</span>
                  <span className="font-semibold text-white tracking-wide">{val}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="mt-6 p-3 rounded bg-[#030307] border border-white/[0.04] text-[10px] font-mono text-[#4e5f73] leading-relaxed">
            <span className="text-emerald mr-1">&gt;</span> 
            {pulseActive 
              ? `Real-time flow packet running. Layer ${pulseLayer} processing event data stream.` 
              : `System standing by. Click any station or trigger flow loop to trace event cascade.`}
          </div>
        </div>
      </div>
    </div>
  )
}
