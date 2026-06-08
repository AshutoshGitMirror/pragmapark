export function formatCurrency(n: number): string {
  return '$' + n.toFixed(2)
}

export function formatNumber(n: number): string {
  if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M'
  if (n >= 1000) return (n / 1000).toFixed(1) + 'K'
  return n.toFixed(0)
}

export function formatLatency(ms: number): string {
  return ms < 1000 ? ms + 'ms' : (ms / 1000).toFixed(1) + 's'
}

/** Safely extract a human-readable error message from an unknown caught value. */
export function getErrorMessage(err: unknown, fallback = 'An unexpected error occurred'): string {
  if (typeof err === 'string') return err
  if (err && typeof err === 'object') {
    // Axios-style error with response detail
    const axiosErr = err as { response?: { data?: { detail?: string } }; message?: string }
    if (axiosErr.response?.data?.detail) return axiosErr.response.data.detail
    if (axiosErr.message) return axiosErr.message
  }
  if (err instanceof Error) return err.message
  return fallback
}
