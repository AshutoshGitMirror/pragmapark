import { useEffect, useState } from 'react'
import { useReveal } from '../../hooks/useScrollReveal'

const testimonials = [
  {
    quote: 'Digital twin simulations cut our planning cycles from weeks to hours. We simulated "city-wide concert" scenarios and adjusted pricing before the event even went live.',
    name: 'Sarah Chen',
    title: 'CTO, Birmingham Mobility Authority',
    initial: 'SC',
  },
  {
    quote: 'The multi-agent pricing system paid for itself in three months. Revenue is up 34% and complaints about pricing are actually down — it just feels fair when it\'s dynamic.',
    name: 'James Okonkwo',
    title: 'VP Operations, ParkSmart EU',
    initial: 'JO',
  },
  {
    quote: 'We were skeptical about blockchain for parking. After the audit trail saved us in a dispute with the city council, we\'re all in. Immutable logs are a game-changer.',
    name: 'Elena Vasquez',
    title: 'Head of Infrastructure, Smart City Munich',
    initial: 'EV',
  },
  {
    quote: 'Vision Zero is real. Our drivers spend 40% less time circling blocks. The micro-slot probability model is eerily accurate — even in heavy rain.',
    name: 'Marcus Johansson',
    title: 'Fleet Manager, CityCab Nordic',
    initial: 'MJ',
  },
]

export function TestimonialsSection() {
  const visible = useReveal(100)
  const [active, setActive] = useState(0)

  useEffect(() => {
    const interval = setInterval(() => {
      setActive((prev) => (prev + 1) % testimonials.length)
    }, 6000)
    return () => clearInterval(interval)
  }, [])

  const t = testimonials[active]

  return (
    <section className="section bg-[#0e0e18]" id="testimonials">
      <div className="section-inner">
        <div className={`max-w-3xl mx-auto text-center transition-all duration-700 ${visible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'}`}>
          <p className="section-label justify-center" style={{ color: '#ffb347' }}>TRUSTED BY CITIES</p>
          <h2 className="section-headline">What operators say.</h2>
        </div>

        <div className={`max-w-2xl mx-auto mt-16 transition-all duration-500 ${visible ? 'opacity-100' : 'opacity-0'}`}>
          <div className="relative min-h-[220px]">
            {testimonials.map((item, i) => (
              <div
                key={i}
                className="absolute inset-0 transition-all duration-700 ease-in-out"
                style={{
                  opacity: i === active ? 1 : 0,
                  transform: `translateY(${i === active ? 0 : '12px'}) scale(${i === active ? 1 : 0.97})`,
                  pointerEvents: i === active ? 'auto' : 'none',
                }}
              >
                <div className="bg-[#13131f] rounded-xl border border-[rgba(255,179,71,0.1)] p-8 relative">
                  <div className="text-5xl text-[rgba(255,179,71,0.15)] absolute top-4 left-6 leading-none font-serif">
                    &ldquo;
                  </div>
                  <blockquote className="text-base text-[#94a3b8] leading-relaxed mb-6 relative z-10 pt-4">
                    {item.quote}
                  </blockquote>
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-full bg-gradient-to-br from-[rgba(255,179,71,0.3)] to-transparent flex items-center justify-center text-xs font-mono text-[#ffb347] border border-[rgba(255,179,71,0.2)]">
                      {item.initial}
                    </div>
                    <div className="text-left">
                      <p className="text-sm font-medium text-white">{item.name}</p>
                      <p className="text-[10px] font-mono text-[#64748b]">{item.title}</p>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>

          <div className="flex justify-center gap-2 mt-8">
            {testimonials.map((_, i) => (
              <button
                key={i}
                onClick={() => setActive(i)}
                className={`w-2 h-2 rounded-full transition-all duration-300 ${
                  i === active ? 'bg-[#ffb347] w-6' : 'bg-[rgba(255,179,71,0.2)]'
                }`}
              />
            ))}
          </div>
        </div>
      </div>
    </section>
  )
}
