import { useState, useEffect } from 'react'
import { fetchWalletTransactions, type WalletTransaction } from '../../api/driverClient'

function ActionBadge({ action }: { action: string }) {
  let color = '#94a3b8' // default gray
  if (action === 'deposit') color = '#00c785' // green
  else if (action === 'booking_fee') color = '#ef4444' // red
  else if (action === 'refund') color = '#f59e0b' // orange
  else if (action === 'session_fee') color = '#3b82f6' // blue

  return (
    <span className="text-[9px] font-mono font-medium px-2 py-0.5 rounded uppercase tracking-wider" style={{ background: `${color}15`, color }}>
      {action.replace('_', ' ')}
    </span>
  )
}

function StatusBadge({ status }: { status: string }) {
  const color = status === 'completed' || status === 'settled' ? '#00c785' : '#f59e0b'
  return (
    <span className="text-[9px] font-mono font-medium px-1.5 py-0.5 rounded uppercase" style={{ background: `${color}15`, color }}>
      {status}
    </span>
  )
}

export function TransactionsPage() {
  const [transactions, setTransactions] = useState<WalletTransaction[]>([])
  const [loading, setLoading] = useState(true)

  const load = async () => {
    try {
      const txs = await fetchWalletTransactions()
      setTransactions(txs || [])
    } catch { /* silent */ }
    setLoading(false)
  }

  useEffect(() => { load() }, [])

  const nav = (hash: string) => { window.location.hash = hash }

  return (
    <div className="space-y-4 pt-2">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold text-white">Transactions</h1>
          <p className="text-xs text-[#475569] mt-0.5">Your wallet history</p>
        </div>
        <button
          onClick={() => nav('/driver/dashboard')}
          className="text-xs font-semibold px-3 py-1.5 rounded-lg bg-[#1b1b38] text-white border border-white/5 hover:bg-[#25254c] active:scale-95 transition-all"
        >
          Back to Dashboard
        </button>
      </div>

      {loading ? (
        <div className="text-[#5a6a8a] text-sm animate-pulse text-center py-12">Loading transactions...</div>
      ) : transactions.length === 0 ? (
        <div className="rounded-xl p-10 text-center"
          style={{
            background: 'linear-gradient(135deg, #0e0e24 0%, #12122a 50%, #0e0e24 100%)',
            boxShadow: '0 1px 0 rgba(255,255,255,0.04), 0 0 0 1px rgba(255,255,255,0.04)',
          }}>
          <p className="text-sm text-[#475569]">No transactions recorded yet</p>
        </div>
      ) : (
        <div className="space-y-2">
          {transactions.map((tx) => {
            const isAddition = tx.action === 'deposit' || tx.action === 'refund'
            const prefix = isAddition ? '+' : '-'
            const amountColor = isAddition ? 'text-[#00c785]' : 'text-white'

            return (
              <div key={tx.tx_hash}
                className="rounded-xl p-4 flex flex-col md:flex-row md:items-center justify-between gap-3"
                style={{
                  background: 'linear-gradient(135deg, #0e0e24 0%, #12122a 50%, #0e0e24 100%)',
                  boxShadow: '0 1px 0 rgba(255,255,255,0.04), 0 0 0 1px rgba(255,255,255,0.04)',
                }}>
                <div className="space-y-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <ActionBadge action={tx.action} />
                    <StatusBadge status={tx.status} />
                  </div>
                  <p className="text-[10px] text-[#475569] font-mono leading-none pt-1">
                    TX: <span className="text-[#64748b]">{tx.tx_hash.length > 20 ? `${tx.tx_hash.slice(0, 24)}...` : tx.tx_hash}</span>
                  </p>
                  <div className="flex gap-2 text-[10px] text-[#475569] flex-wrap">
                    {tx.lot_id && <span>Lot: {tx.lot_id}</span>}
                    {tx.session_id && <span>Session: {tx.session_id.slice(0, 8)}...</span>}
                  </div>
                </div>

                <div className="flex items-end md:items-end flex-col justify-between">
                  <p className={`text-sm font-bold font-mono ${amountColor}`}>
                    {prefix}${tx.amount.toFixed(2)}
                  </p>
                  <p className="text-[9px] text-[#475569] mt-0.5">
                    {new Date(tx.timestamp).toLocaleString()}
                  </p>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
