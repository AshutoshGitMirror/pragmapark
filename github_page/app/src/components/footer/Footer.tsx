import { useReveal } from '../../hooks/useScrollReveal'

export function Footer() {
  const visible = useReveal(100)

  return (
    <footer className="bg-black border-t border-[rgba(255,255,255,0.04)] py-16">
      <div
        className={`max-w-6xl mx-auto px-6 transition-all duration-700 ${visible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'}`}
      >
        <div className="grid grid-cols-1 md:grid-cols-3 gap-10 mb-12">
          <div>
            <p className="text-xl font-[300] text-white tracking-[-0.02em] mb-2">PRAGMA</p>
            <p className="text-xs font-mono text-[#64748b] leading-relaxed max-w-[260px]">
              Autonomous parking intelligence for the cities of tomorrow.
              AI prediction. Blockchain truth. Every slot optimized.
            </p>
          </div>
          <div>
            <p className="text-[9px] font-mono text-[#64748b] tracking-[0.15em] uppercase mb-4">Vision</p>
            <p className="text-xs font-mono text-[#94a3b8] leading-relaxed">
              Reduce urban cruising by <span className="text-white">80%</span> across 50 cities by 2030.
              Every parking transaction on a verifiable ledger.
              Every pricing decision optimized by multi-agent RL.
            </p>
          </div>
          <div className="text-right md:text-left">
            <p className="text-[9px] font-mono text-[#64748b] tracking-[0.15em] uppercase mb-4">Stack</p>
            <div className="flex flex-wrap gap-2 justify-end md:justify-start">
              {['Python', 'PyTorch', 'FastAPI', 'React', 'Web3', 'IPFS'].map((s) => (
                <span
                  key={s}
                  className="text-[9px] font-mono text-[#64748b] px-2 py-1 rounded border border-[rgba(255,255,255,0.06)]"
                >
                  {s}
                </span>
              ))}
            </div>
          </div>
        </div>

        <div className="pt-8 border-t border-[rgba(255,255,255,0.04)] flex flex-col md:flex-row items-center justify-between gap-4">
          <p className="text-[10px] font-mono text-[#475569]">
            &copy; {new Date().getFullYear()} Pragma Systems — Autonomous Mobility Division
          </p>
          <div className="flex items-center gap-2 text-[#475569]">
            <span className="w-1.5 h-1.5 rounded-full bg-[rgba(255,255,255,0.1)]" />
            <span className="text-[10px] font-mono">System Status: Operational</span>
          </div>
          <div className="flex gap-4">
            {['GitHub', 'Docs', 'API', 'Status'].map((l) => (
              <a
                key={l}
                href="#"
                className="text-[10px] font-mono text-[#475569] hover:text-[#00d4ff] transition-colors"
              >
                {l}
              </a>
            ))}
          </div>
        </div>
      </div>
    </footer>
  )
}
