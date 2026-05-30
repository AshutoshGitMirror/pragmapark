export function formatCurrency(n: number): string {
  return '$' + n.toFixed(2)
}

export function formatPercent(n: number): string {
  return (n * 100).toFixed(1) + '%'
}

export function formatNumber(n: number): string {
  if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M'
  if (n >= 1000) return (n / 1000).toFixed(1) + 'K'
  return n.toFixed(0)
}

export function formatLatency(ms: number): string {
  return ms < 1000 ? ms + 'ms' : (ms / 1000).toFixed(1) + 's'
}
