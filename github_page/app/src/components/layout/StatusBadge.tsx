import { cn } from '../../utils/cn'

interface StatusBadgeProps {
  label: string
  color: 'cyan' | 'emerald' | 'amber'
  pulse?: boolean
}

const colorMap = {
  cyan: 'bg-[#00d4ff]',
  emerald: 'bg-[#00c785]',
  amber: 'bg-[#ffb347]',
}

export function StatusBadge({ label, color, pulse }: StatusBadgeProps) {
  return (
    <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-[rgba(255,255,255,0.04)] text-xs text-[#94a3b8] font-mono">
      <div className={cn('w-1.5 h-1.5 rounded-full', colorMap[color], pulse && 'animate-pulse')} />
      {label}
    </div>
  )
}
