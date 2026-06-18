import { useState, useEffect, type FormEvent } from 'react'
import { fetchCurrentUser } from '../../api/adminClient'
import { useAuth } from '../../context/AuthContext'
import { getErrorMessage } from '../../utils/format'

const GOLD = '#f0c040'
const GOLD_DIM = 'rgba(240,192,64,0.12)'

const MailIcon = () => (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M21.75 6.75v10.5a2.25 2.25 0 01-2.25 2.25h-15a2.25 2.25 0 01-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0019.5 4.5h-15a2.25 2.25 0 00-2.25 2.25m19.5 0v.243a2.25 2.25 0 01-1.07 1.916l-7.5 4.615a2.25 2.25 0 01-2.36 0L3.32 8.91a2.25 2.25 0 01-1.07-1.916V6.75" />
  </svg>
)

const LockIcon = () => (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z" />
  </svg>
)

export function LoginPage() {
  const { login, loading, error, user } = useAuth()
  const [email, setEmail] = useState('admin@pragma.io')
  const [password, setPassword] = useState('admin123')
  const [localError, setLocalError] = useState<string | null>(null)

  // Server-verified redirect: never trust stale AuthContext cache
  useEffect(() => {
    let cancelled = false
    fetchCurrentUser()
      .then((u) => {
        if (!cancelled) {
          if (u.role !== 'driver') {
            window.location.hash = '/app/dashboard'
          } else {
            window.location.hash = '/driver/dashboard'
          }
        }
      })
      .catch(() => { /* session expired — stay on login */ })
    return () => { cancelled = true }
  }, [user])

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setLocalError(null)
    try {
      await login(email, password)
      // redirect handled by useEffect on user change — no race
    } catch (err: unknown) {
      setLocalError(getErrorMessage(err))
    }
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
      {/* Ambient radial glows */}
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
            <span className="text-[9px] font-mono tracking-[3px] uppercase text-muted-alt">Admin Access</span>
            <span className="w-px h-3" style={{ background: `linear-gradient(to bottom, transparent, ${GOLD})` }} />
          </div>
          <h1 className="font-heading text-xl font-semibold text-white">Sign in</h1>
          <p className="font-mono text-[11px] text-muted-alt mt-1">Smart Parking Management</p>
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
            <label htmlFor="login-email" className="block text-[10px] font-mono uppercase tracking-wider text-muted-alt mb-1.5">
              Email
            </label>
            <div className="relative">
              <span className="absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none" style={{ color: '#5a6a8a' }}>
                <MailIcon />
              </span>
              <input
                id="login-email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full rounded-xl pl-10 pr-3.5 py-2.5 text-sm text-white placeholder-[#5a6a8a] font-mono transition-all duration-300"
                style={{
                  background: 'rgba(0,0,0,0.3)',
                  border: '1px solid rgba(255,255,255,0.06)',
                }}
                placeholder="you@pragma.io"
                required
              />
            </div>
          </div>

          <div>
            <label htmlFor="login-password" className="block text-[10px] font-mono uppercase tracking-wider text-muted-alt mb-1.5">
              Password
            </label>
            <div className="relative">
              <span className="absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none" style={{ color: '#5a6a8a' }}>
                <LockIcon />
              </span>
              <input
                id="login-password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full rounded-xl pl-10 pr-3.5 py-2.5 text-sm text-white placeholder-[#5a6a8a] font-mono transition-all duration-300"
                style={{
                  background: 'rgba(0,0,0,0.3)',
                  border: '1px solid rgba(255,255,255,0.06)',
                }}
                placeholder="Enter password"
                required
              />
            </div>
          </div>

          {(localError || error) && (
            <div className="flex items-center gap-2 rounded-xl px-4 py-2.5"
              style={{
                background: 'rgba(240,64,96,0.08)',
                border: '1px solid rgba(240,64,96,0.2)',
              }}>
              <span className="text-rose text-xs">⚠</span>
              <p id="login-error" className="text-rose text-xs font-mono">{localError || error}</p>
            </div>
          )}

          <button
            id="login-submit-btn"
            type="submit"
            disabled={loading}
            className="w-full justify-center text-xs"
            style={{
              background: GOLD,
              color: '#04040a',
              padding: '12px 32px',
              boxShadow: `0 0 24px ${GOLD_DIM}`,
            }}
          >
            {loading ? 'Signing in...' : 'Sign In'}
          </button>
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
