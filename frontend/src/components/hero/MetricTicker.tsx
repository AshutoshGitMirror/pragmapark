import { cn } from '../../utils/cn'
import { useReveal } from '../../hooks/useScrollReveal'
import { formatNumber, formatCurrency } from '../../utils/format'

interface MetricTickerProps {
  lotsCount?: number
  totalSlots?: number
  totalRevenue?: number
  isLive?: boolean
}

export function MetricTicker({
  lotsCount = 0,
  totalSlots = 0,
  totalRevenue,
  isLive = false,
}: MetricTickerProps) {
  const visible = useReveal(2200)

  const pills = [
    { label: isLive && totalRevenue ? formatCurrency(totalRevenue) : `${lotsCount} Lots`, color: 'cyan' as const, pulse: isLive },
    { label: `${lotsCount} Lots Active`, color: 'emerald' as const, pulse: false },
    { label: `${formatNumber(totalSlots)}+ Slots`, color: 'amber' as const, pulse: false },
    { label: isLive ? 'Backend Connected' : 'Connecting...', color: 'emerald' as const, pulse: isLive },
  ]

  return (
    <div
      className={cn(
        'flex flex-wrap justify-center gap-3 px-4 transition-all duration-700',
        visible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4',
      )}
    >
      {pills.map((pill) => (
        <div
          key={pill.label}
          className="inline-flex items-center gap-2 px-5 py-2.5 rounded-full bg-[rgba(255,255,255,0.04)] text-xs text-[#94a3b8] font-mono"
        >
          <div
            className={cn(
              'w-1.5 h-1.5 rounded-full',
              pill.color === 'cyan' && 'bg-[#00d4ff]',
              pill.color === 'emerald' && 'bg-[#00c785]',
              pill.color === 'amber' && 'bg-[#ffb347]',
              pill.pulse && 'animate-pulse',
            )}
          />
          {pill.label}
        </div>
      ))}
    </div>
  )
}
