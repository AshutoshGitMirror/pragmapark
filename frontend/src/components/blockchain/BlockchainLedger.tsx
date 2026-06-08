import { useState, useCallback, useEffect } from 'react'
import { useReveal } from '../../hooks/useScrollReveal'
import { motion } from 'framer-motion'
import { fetchBlockchainStatus, fetchBlockchainBlocks, mineBlock, addBlockchainTransaction } from '../../api/client'
import { fallbackBlockchain } from '../../api/fallbackData'
import { useApiWithFallback } from '../../hooks/useApi'
import { getErrorMessage } from '../../utils/format'
import type { BlockData } from '../../api/types'

const EVENTS = ['Session Start', 'Payment', 'Price Update', 'Overflow Reroute', 'Revenue Share', 'Validator Stake', 'IPFS Anchor']

interface DisplayBlock {
  index: number
  time: string
  txs: number
  hash: string
  event: string
}

function formatTime(ts: number): string {
  const d = new Date(ts * 1000)
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}:${String(d.getSeconds()).padStart(2, '0')}`
}

function blockEvent(block: BlockData): string {
  if (block.index === 0) return 'Genesis'
  const actions = block.transactions.map((tx) => String(tx.action || tx.type || '')).filter(Boolean)
  if (actions.length === 0) return 'Block Mined'
  // Pick the most common action
  const freq: Record<string, number> = {}
  actions.forEach((a) => { freq[a] = (freq[a] || 0) + 1 })
  const topAction = Object.entries(freq).sort((a, b) => b[1] - a[1])[0]?.[0] || ''
  const mapped: Record<string, string> = {
    session_fee: 'Session Start',
    payment: 'Payment',
    refund: 'Refund',
    prebook: 'Prebook Deposit',
    topup: 'Wallet Top-up',
    revenue_share: 'Revenue Share',
  }
  return mapped[topAction] || topAction.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
}

export function BlockchainLedger() {
  const { data: status, source, refetch } = useApiWithFallback(
    () => fetchBlockchainStatus(),
    fallbackBlockchain,
  )

  const [blocks, setBlocks] = useState<DisplayBlock[]>([])
  const [blocksLoaded, setBlocksLoaded] = useState(false)
  const [mining, setMining] = useState(false)
  const [txSubmitting, setTxSubmitting] = useState(false)
  const [showTxForm, setShowTxForm] = useState(false)
  const [txForm, setTxForm] = useState({ sender: '', receiver: '', amount: '' })
  const [error, setError] = useState<string | null>(null)
  const isLive = source === 'live'

  const visible = useReveal(100)

  // Load real blocks from backend
  useEffect(() => {
    if (!isLive || blocksLoaded) return
    fetchBlockchainBlocks()
      .then((res) => {
        const mapped = res.blocks.map((b) => ({
          index: b.index,
          time: formatTime(b.timestamp),
          txs: b.transactions.length,
          hash: b.hash.slice(0, 8) + '…' + b.hash.slice(-4),
          event: blockEvent(b),
        }))
        setBlocks(mapped)
        setBlocksLoaded(true)
      })
      .catch(() => {
        // Fallback: leave blocks empty, status still shows
        setBlocksLoaded(true)
      })
  }, [isLive, blocksLoaded])

  const handleMine = useCallback(async () => {
    setError(null)
    setMining(true)
    try {
      if (isLive) {
        const result = await mineBlock()
        setBlocks((prev) => [
          {
            index: result.block_index,
            time: formatTime(result.timestamp),
            txs: result.transactions,
            hash: result.hash.slice(0, 8) + '…' + result.hash.slice(-4),
            event: 'Block Mined',
          },
          ...prev,
        ])
        await refetch()
      } else {
        await new Promise((r) => setTimeout(r, 1500 + Math.random() * 2000))
        setBlocks((prev) => [
          {
            index: (status?.chain_length ?? prev.length) + 1,
            time: formatTime(Date.now() / 1000),
            txs: Math.floor(Math.random() * 20 + 10),
            hash: Array.from({ length: 8 }, () => Math.floor(Math.random() * 16).toString(16)).join('') + '…' + Array.from({ length: 4 }, () => Math.floor(Math.random() * 16).toString(16)).join(''),
            event: EVENTS[Math.floor(Math.random() * EVENTS.length)],
          },
          ...prev,
        ])
      }
    } catch (err: unknown) {
      setError(getErrorMessage(err, 'Failed to mine block'))
    } finally {
      setMining(false)
    }
  }, [isLive, status?.chain_length, refetch])

  const handleSubmitTx = useCallback(async (e: React.FormEvent) => {
    e.preventDefault()
    if (!txForm.sender || !txForm.receiver || !txForm.amount) return
    setError(null)
    setTxSubmitting(true)
    try {
      if (isLive) {
        await addBlockchainTransaction({
          driver_id: txForm.sender,
          lot_id: txForm.receiver,
          action: 'payment',
          price: parseFloat(txForm.amount),
        })
        setShowTxForm(false)
        setTxForm({ sender: '', receiver: '', amount: '' })
        await refetch()
      } else {
        setShowTxForm(false)
        setTxForm({ sender: '', receiver: '', amount: '' })
        await handleMine()
      }
    } catch (err: unknown) {
      setError(getErrorMessage(err, 'Failed to submit transaction'))
    } finally {
      setTxSubmitting(false)
    }
  }, [txForm, isLive, handleMine, refetch])


  return (
    <section className="section bg-[#0a0a0f]" id="blockchain">
      <div className="section-inner">
        <div className="grid grid-cols-1 lg:grid-cols-[45%_55%] gap-16 items-center">
          {/* Left column — Block chain */}
          <div className={`transition-all duration-700 delay-100 ${visible ? 'opacity-100 translate-x-0' : 'opacity-0 -translate-x-8'}`}>
            {blocks.length === 0 && blocksLoaded && isLive && (
              <div className="text-[10px] font-mono text-[#64748b] mb-4 p-3 bg-[#13131f] rounded-lg border border-[rgba(255,255,255,0.06)]">
                No blocks to display. Mine a block to create the first one.
              </div>
            )}
            {blocks.map((block: DisplayBlock, i: number) => (
              <div key={i} className="flex items-start gap-4">
                <div className="flex flex-col items-center">
                  <div
                    className={`w-3 h-3 rounded-full border-2 shrink-0 ${
                      i === 0
                        ? 'border-[#ffb347] bg-[rgba(255,179,71,0.2)]'
                        : 'border-[rgba(255,179,71,0.3)] bg-transparent'
                    }`}
                    style={i === 0 ? { boxShadow: '0 0 12px rgba(255,179,71,0.3)' } : {}}
                  />
                  {i < blocks.length - 1 && (
                    <div className="w-px h-8 bg-gradient-to-b from-[rgba(255,179,71,0.3)] to-[rgba(255,179,71,0.05)]" />
                  )}
                </div>
                <div
                  className={`flex-1 bg-[#13131f] border p-4 rounded-lg transition-all duration-500 hover:border-[rgba(255,179,71,0.3)] ${
                    i === 0 ? 'border-[rgba(255,179,71,0.3)]' : 'border-[rgba(255,255,255,0.06)]'
                  }`}
                  style={{
                    transform: visible ? 'translateY(0)' : `translateY(${i * 8}px)`,
                    opacity: visible ? 1 : 0,
                    transitionDelay: `${200 + i * 100}ms`,
                  }}
                >
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[9px] font-mono text-[#64748b] tracking-wider">
                      BLOCK #{block.index}
                    </span>
                    {i === 0 && (
                      <span className="text-[8px] font-mono text-[#ffb347] px-1.5 py-0.5 rounded bg-[rgba(255,179,71,0.1)]">
                        {isLive ? 'LIVE' : 'SIMULATION'}
                      </span>
                    )}
                  </div>
                  <div className="text-xs font-medium text-white uppercase tracking-wide mb-1">
                    {block.event}
                  </div>
                  <div className="flex items-center justify-between text-[10px] font-mono text-[#64748b]">
                    <span>{block.time}</span>
                    <span>{block.txs} TX</span>
                  </div>
                  <div className="mt-2 pt-2 border-t border-[rgba(255,255,255,0.04)] text-[8px] font-mono text-[rgba(255,255,255,0.15)] truncate">
                    {block.hash}
                  </div>
                </div>
              </div>
            ))}

            {/* ── FIX: Always show status, live or fallback ── */}
            <div className="mt-6 ml-7 text-[10px] font-mono text-[#64748b] flex gap-4">
              <span>{status.chain_length} blocks</span>
              <span>{status.pending_transactions} pending</span>
                        <span style={{ color: status.chain_valid ? '#00c785' : '#ffb347' }}>
                          {status.chain_valid ? '✓ Valid' : '⚠ Invalid'}
              </span>
              {isLive && (
                <span className="text-[#00c785]">● Live</span>
              )}
            </div>
          </div>

          {/* Right column */}
          <div className={`transition-all duration-700 ${visible ? 'opacity-100 translate-x-0' : 'opacity-0 translate-x-8'}`}>
            <div className="flex items-center gap-3 mb-4">
              <p className="section-label !mb-0" style={{ color: '#ffb347' }}>BLOCKCHAIN LEDGER</p>
              {isLive && (
                <span className="flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-[rgba(0,199,133,0.1)] border border-[rgba(0,199,133,0.2)]">
                  <span className="w-1.5 h-1.5 rounded-full bg-[#00c785] animate-pulse" />
                  <span className="text-[9px] font-mono text-[#00c785] uppercase tracking-wider">Live</span>
                </span>
              )}
            </div>
            <h2 className="section-headline">Every session. Immutable. Verifiable.</h2>
            <p className="section-body mb-6">
              Custom Proof-of-Work blockchain anchors every parking session to an unalterable ledger.
              Session data is stored on IPFS with cryptographic hashing.
            </p>

            {/* ── Interactive actions ── */}
            {error && (
              <div className="mb-4 p-3 bg-red-950/40 border border-red-500/30 text-red-200 text-xs font-mono rounded-lg">
                ⚠️ {error}
              </div>
            )}
            <div className="flex items-center gap-3 mb-6">
              <motion.button
                onClick={handleMine}
                disabled={mining}
                whileHover={mining ? {} : { scale: 1.03 }}
                whileTap={mining ? {} : { scale: 0.97 }}
                className="flex items-center gap-2 py-2 px-4 rounded-lg text-xs font-mono font-medium border border-[rgba(255,179,71,0.3)] text-[#ffb347] hover:border-[#ffb347] hover:bg-[rgba(255,179,71,0.05)] transition-all disabled:opacity-40"
              >
                {mining ? (
                  <>
                    <span className="w-3 h-3 rounded-full border border-[#ffb347] border-t-transparent animate-spin" />
                    Mining...
                  </>
                ) : (
                  <>
                    <span>⛏</span>
                    Mine Block
                  </>
                )}
              </motion.button>
              <motion.button
                onClick={() => setShowTxForm(true)}
                whileHover={{ scale: 1.03 }}
                whileTap={{ scale: 0.97 }}
                className="py-2 px-4 rounded-lg text-xs font-mono font-medium border border-[rgba(255,255,255,0.1)] text-[#94a3b8] hover:border-[#00d4ff] hover:text-[#00d4ff] transition-all"
              >
                + New Transaction
              </motion.button>
            </div>

            {/* ── Transaction form ── */}
            {showTxForm && (
              <form
                onSubmit={handleSubmitTx}
                className="bg-[#13131f] border border-[rgba(255,255,255,0.06)] rounded-lg p-4 mb-6 space-y-3"
              >
                <div className="text-[10px] font-mono text-[#ffb347] uppercase tracking-wider mb-2">New Transaction</div>
                <input
                  id="tx-sender"
                  name="sender"
                  value={txForm.sender}
                  onChange={(e) => setTxForm((f) => ({ ...f, sender: e.target.value }))}
                  placeholder="Sender address"
                  className="w-full bg-[#0a0a0f] border border-[rgba(255,255,255,0.08)] rounded px-3 py-1.5 text-xs font-mono text-[#94a3b8] placeholder-[#475569] outline-none focus:border-[#ffb347] transition-colors"
                />
                <input
                  id="tx-receiver"
                  name="receiver"
                  value={txForm.receiver}
                  onChange={(e) => setTxForm((f) => ({ ...f, receiver: e.target.value }))}
                  placeholder="Receiver address"
                  className="w-full bg-[#0a0a0f] border border-[rgba(255,255,255,0.08)] rounded px-3 py-1.5 text-xs font-mono text-[#94a3b8] placeholder-[#475569] outline-none focus:border-[#ffb347] transition-colors"
                />
                <input
                  id="tx-amount"
                  name="amount"
                  type="number"
                  value={txForm.amount}
                  onChange={(e) => setTxForm((f) => ({ ...f, amount: e.target.value }))}
                  placeholder="Amount (ETH)"
                  className="w-full bg-[#0a0a0f] border border-[rgba(255,255,255,0.08)] rounded px-3 py-1.5 text-xs font-mono text-[#94a3b8] placeholder-[#475569] outline-none focus:border-[#ffb347] transition-colors"
                />
                <div className="flex gap-2">
                  <motion.button
                    type="submit"
                    disabled={txSubmitting}
                    whileHover={txSubmitting ? {} : { scale: 1.03 }}
                    whileTap={txSubmitting ? {} : { scale: 0.97 }}
                    className="flex-1 py-1.5 rounded text-[10px] font-mono font-medium bg-[#ffb347]/10 border border-[#ffb347]/30 text-[#ffb347] hover:bg-[#ffb347]/20 transition-all disabled:opacity-40"
                  >
                    {txSubmitting ? (
                      <>
                        <span className="w-3 h-3 rounded-full border border-[#ffb347] border-t-transparent animate-spin inline-block mr-1" />
                        Submitting...
                      </>
                    ) : (
                      'Sign & Submit'
                    )}
                  </motion.button>
                  <motion.button
                    type="button"
                    disabled={txSubmitting}
                    onClick={() => setShowTxForm(false)}
                    whileHover={txSubmitting ? {} : { scale: 1.03 }}
                    whileTap={txSubmitting ? {} : { scale: 0.97 }}
                    className="py-1.5 px-3 rounded text-[10px] font-mono text-[#64748b] border border-[rgba(255,255,255,0.06)] hover:text-[#94a3b8] transition-all disabled:opacity-40"
                  >
                    Cancel
                  </motion.button>
                </div>
              </form>
            )}

            <div className="flex flex-col gap-3">
              {[
                'Genesis block + chained SHA-256 hashes',
                'IPFS content addressing for session data',
                'Ledger outbox for guaranteed delivery',
                'Idempotent payment confirmation',
              ].map((feat) => (
                <div key={feat} className="flex items-center gap-3">
                  <span className="text-[#ffb347] text-sm">✓</span>
                  <span className="text-sm text-[#94a3b8]">{feat}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
