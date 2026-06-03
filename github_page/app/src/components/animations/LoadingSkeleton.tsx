import { motion } from 'framer-motion'

interface Props {
  lines?: number
  height?: number
  className?: string
}

export function LoadingSkeleton({ lines = 3, height = 120, className }: Props) {
  return (
    <div className={`flex flex-col gap-3 ${className ?? ''}`}>
      {Array.from({ length: lines }).map((_, i) => (
        <motion.div
          key={i}
          className="rounded bg-gradient-to-r from-[rgba(255,255,255,0.04)] via-[rgba(255,255,255,0.08)] to-[rgba(255,255,255,0.04)] bg-[length:200%_100%]"
          style={{ height: i === lines - 1 ? height * 0.5 : height / lines }}
          animate={{ backgroundPosition: ['200% 0', '-200% 0'] }}
          transition={{ duration: 1.5, repeat: Infinity, ease: 'linear', delay: i * 0.1 }}
        />
      ))}
    </div>
  )
}

export function ChartSkeleton() {
  return (
    <div className="h-[300px] flex items-center justify-center">
      <LoadingSkeleton lines={4} height={200} className="w-full max-w-[90%]" />
    </div>
  )
}
