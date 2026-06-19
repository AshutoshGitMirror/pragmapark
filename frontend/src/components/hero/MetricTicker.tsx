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
  const { ref, visible } = useReveal(2200)

  const pills = [
    { label: 'Lots Managed', value: formatNumber(lotsCount) },
    { label: 'Total Slots', value: formatNumber(totalSlots) },
    {
      label: 'Total Revenue',
      value: totalRevenue != null ? formatCurrency(totalRevenue) : '—',
    },
    {
      label: 'Network',
      value: isLive ? 'Live' : 'Demo',
      accent: isLive ? 'text-green-400' : 'text-amber-400',
    },
  ]

  return (
    <div
      ref={ref}
      className={`mx-auto mt-16 grid max-w-5xl grid-cols-2 gap-px overflow-hidden rounded-2xl border border-white/10 bg-white/5 md:grid-cols-4 transition-all duration-1000 ${
        visible ? 'translate-y-0 opacity-100' : 'translate-y-8 opacity-0'
      }`}
    >
      {pills.map((p) => (
        <div
          key={p.label}
          className="flex flex-col items-center justify-center px-6 py-8"
        >
          <span
            className={`font-fraunces text-3xl font-bold tracking-tight ${
              p.accent ?? 'text-amber-300'
            }`}
          >
            {p.value}
          </span>
          <span className="mt-1 text-sm font-medium tracking-wide text-white/60">
            {p.label}
          </span>
        </div>
      ))}
    </div>
  )
}
