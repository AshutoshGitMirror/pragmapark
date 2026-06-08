import { useState } from 'react'
import { useAuth } from '../../context/AuthContext'
import { getErrorMessage } from '../../utils/format'

const GOLD = '#f0c040'
const GOLD_DIM = 'rgba(240,192,64,0.12)'

export function DriverLoginPage() {
  const { login, user } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      await login(email || 'driver@pragma.io', password || 'driver123')
      window.location.hash = '/driver/dashboard'
    } catch (err: unknown) {
      setError(getErrorMessage(err, 'Login failed'))
    } finally {
      setLoading(false)
    }
  }

  if (user && user.role === 'driver') {
    window.location.hash = '/driver/dashboard'
    return null
  }

  return (
    <div className="relative min-h-screen flex items-center justify-center p-4 overflow-hidden"
      style={{ background: '#04040a' }}>
      {/* CRT grid */}
      <div className="absolute inset-0 opacity-[0.025]"
        style={{
          backgroundImage: `
            linear-gradient(rgba(240,192,64,0.5) 1px, transparent 1px),
            linear-gradient(90deg, rgba(240,192,64,0.5) 1px, transparent 1px)
          `,
          backgroundSize: '48px 48px',
        }} />
      {/* Ambient glows */}
      <div className="absolute top-1/3 left-1/2 -translate-x-1/2 w-[500px] h-[500px] rounded-full blur-[140px] opacity-30"
        style={{ background: 'radial-gradient(circle, rgba(240,192,64,0.06), transparent)' }} />
      <div className="absolute bottom-1/4 left-1/3 w-[300px] h-[300px] rounded-full blur-[100px] opacity-20"
        style={{ background: 'radial-gradient(circle, rgba(64,212,240,0.04), transparent)' }} />

      <div className="relative w-full max-w-sm">
        {/* Brand */}
        <div className="text-center mb-10">
          <div className="font-display text-[42px] font-black italic leading-none mb-2"
            style={{ color: GOLD, letterSpacing: '-2px' }}>
            Pragma<span style={{ color: '#5a6a8a' }}>.</span>
          </div>
          <div className="flex items-center gap-2 justify-center mb-6">
            <span className="w-px h-3" style={{ background: `linear-gradient(to bottom, ${GOLD}, transparent)` }} />
            <span className="text-[9px] font-mono tracking-[3px] uppercase text-[#9a97b0]">Driver Portal</span>
            <span className="w-px h-3" style={{ background: `linear-gradient(to bottom, transparent, ${GOLD})` }} />
          </div>
          <h1 className="font-heading text-xl font-semibold text-white">Find & Park</h1>
          <p className="font-mono text-[11px] text-[#9a97b0] mt-1">Smart Parking for the City</p>
        </div>

        <form
          onSubmit={handleSubmit}
          className="rounded-2xl p-8 space-y-5 backdrop-blur-sm"
          style={{
            background: 'linear-gradient(135deg, rgba(14,14,28,0.9), rgba(10,10,24,0.9))',
            border: '1px solid rgba(255,255,255,0.06)',
            boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
          }}>
          <div>
            <label className="block text-[10px] font-mono uppercase tracking-wider text-[#9a97b0] mb-1.5">Email</label>
            <input
              type="email" value={email} onChange={(e) => setEmail(e.target.value)}
              placeholder="driver@pragma.io"
              className="w-full rounded-xl px-3.5 py-2.5 text-sm text-white placeholder-[#5a6a8a] font-mono transition-all duration-300"
              style={{
                background: 'rgba(0,0,0,0.3)',
                border: '1px solid rgba(255,255,255,0.06)',
              }}
            />
          </div>
          <div>
            <label className="block text-[10px] font-mono uppercase tracking-wider text-[#9a97b0] mb-1.5">Password</label>
            <input
              type="password" value={password} onChange={(e) => setPassword(e.target.value)}
              placeholder="Enter password"
              className="w-full rounded-xl px-3.5 py-2.5 text-sm text-white placeholder-[#5a6a8a] font-mono transition-all duration-300"
              style={{
                background: 'rgba(0,0,0,0.3)',
                border: '1px solid rgba(255,255,255,0.06)',
              }}
            />
          </div>

          {error && (
            <div className="flex items-center gap-2 rounded-xl px-4 py-2.5"
              style={{
                background: 'rgba(240,64,96,0.08)',
                border: '1px solid rgba(240,64,96,0.2)',
              }}>
              <span className="text-[#f04060] text-xs">⚠</span>
              <p className="text-[#f04060] text-xs font-mono">{error}</p>
            </div>
          )}

          <button type="submit" disabled={loading}
            className="cta-btn w-full justify-center text-xs"
            style={{
              background: GOLD,
              color: '#04040a',
              padding: '12px 32px',
              boxShadow: `0 0 24px ${GOLD_DIM}`,
            }}>
            {loading ? 'Signing in...' : 'Sign In'}
          </button>

          <p className="text-[9px] text-center text-[#5a6a8a] font-mono">
            Default: driver@pragma.io / driver123
          </p>
        </form>

        <div className="mt-6 text-center">
          <p className="text-[8px] font-mono text-[#3a3a5a] tracking-[3px] uppercase">
            AI · MARL · Blockchain · City-Scale
          </p>
        </div>
      </div>
    </div>
  )
}
