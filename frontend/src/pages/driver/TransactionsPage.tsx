import { useState, useEffect } from 'react'
import { fetchWalletTransactions, type WalletTransaction } from '../../api/driverClient'

const ROSE = '#f04060'
const ROSE_DIM = 'rgba(240,64,96,0.10)'

function ActionBadge({ action }: { action: string }) {
  let color = '#94a3b8'
  if (action === 'deposit') color = '#00c785'
  else if (action === 'booking_fee') color = '#ef4444'
  else if (action === 'refund') color = '#f59e0b'
  else if (action === 'session_fee') color = '#3b82f6'

  return (
    <span className="text-[8px] font-mono font-semibold px-2 py-0.5 rounded uppercase tracking-wider"
      style={{ background: `${color}15`, color }}>
      {action.replace('_', ' ')}
    </span>
  )
}

function StatusBadge({ status }: { status: string }) {
  const color = status === 'completed' || status === 'settled' ? '#00c785' : '#f59e0b'
  return (
    <span className="text-[8px] font-mono font-semibold px-1.5 py-0.5 rounded uppercase"
      style={{ background: `${color}15`, color }}>
      {status}
    </span>
  )
}

export function TransactionsPage() {
  const [transactions, setTransactions] = useState<WalletTransaction[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      const txs = await fetchWalletTransactions()
      setTransactions(txs || [])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load transactions')
    }
    setLoading(false)
  }

  useEffect(() => { load() }, [])

  const nav = (hash: string) => { window.location.hash = hash }

  return (
    <div className="space-y-5 pt-2">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <p className="text-[9px] font-mono tracking-[3px] uppercase mb-1" style={{ color: '#9a97b0' }}>
            Wallet Activity
          </p>
          <h1 className="text-lg font-heading font-semibold text-white">Transactions</h1>
        </div>
        <button onClick={() => nav('/driver/dashboard')}
          className="text-[10px] font-mono font-semibold px-3 py-1.5 rounded-lg transition-all active:scale-95"
          style={{
            background: ROSE_DIM,
            color: ROSE,
            border: `1px solid ${ROSE}20`,
          }}>
          Dashboard
        </button>
      </div>

      {error && (
        <div className="rounded-xl py-3 px-4 text-xs font-mono text-center flex items-center justify-center gap-2"
          style={{ background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.2)', color: '#f59e0b' }}>
          <span>⚠</span> {error}
          <button onClick={load} className="underline hover:no-underline">Retry</button>
        </div>
      )}

      {loading ? (
        <div className="text-[#5a6a8a] font-mono text-[11px] animate-pulse text-center py-16">Loading transactions...</div>
      ) : !error && transactions.length === 0 ? (
        <div className="rounded-xl p-12 text-center" style={{
          background: 'linear-gradient(135deg, #0e0e24 0%, #12122a 50%, #0e0e24 100%)',
          boxShadow: '0 1px 0 rgba(255,255,255,0.04), 0 0 0 1px rgba(255,255,255,0.04)',
        }}>
          <svg className="w-8 h-8 mx-auto mb-3" viewBox="0 0 24 24" fill="none" stroke="#5a6a8a" strokeWidth={1.2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v12m-3-2.818l.879.659c1.171.879 3.07.879 4.242 0 1.172-.879 1.172-2.303 0-3.182C13.536 12.219 12.768 12 12 12c-.725 0-1.45-.22-2.003-.659-1.106-.879-1.106-2.303 0-3.182s2.9-.879 4.006 0l.415.33M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <p className="text-sm text-[#5a6a8a] font-mono">No transactions yet</p>
        </div>
      ) : (
        <div className="space-y-2">
          {transactions.map((tx) => {
            const isAddition = tx.action === 'deposit' || tx.action === 'refund'
            const prefix = isAddition ? '+' : '-'

            return (
              <div key={tx.tx_hash}
                className="rounded-xl p-4 transition-all duration-200"
                style={{
                  background: 'linear-gradient(135deg, #0e0e24 0%, #12122a 50%, #0e0e24 100%)',
                  boxShadow: '0 1px 0 rgba(255,255,255,0.04), 0 0 0 1px rgba(255,255,255,0.04)',
                }}>
                <div className="flex items-start justify-between gap-3">
                  <div className="space-y-1.5 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <ActionBadge action={tx.action} />
                      <StatusBadge status={tx.status} />
                    </div>
                    <p className="text-[9px] font-mono text-[#5a6a8a] truncate">
                      TX: {tx.tx_hash.length > 20 ? `${tx.tx_hash.slice(0, 24)}...` : tx.tx_hash}
                    </p>
                    <div className="flex gap-2 text-[9px] text-[#5a6a8a] font-mono flex-wrap">
                      {tx.lot_id && <span>Lot: {tx.lot_id}</span>}
                      {tx.session_id && <span>Session: {tx.session_id.slice(0, 8)}...</span>}
                    </div>
                  </div>

                  <div className="text-right shrink-0">
                    <p className={`font-display text-lg font-bold ${isAddition ? 'text-[#00c785]' : 'text-white'}`}>
                      {prefix}${tx.amount.toFixed(2)}
                    </p>
                    <p className="text-[8px] font-mono text-[#5a6a8a] mt-0.5">
                      {new Date(tx.timestamp).toLocaleDateString()}
                    </p>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
