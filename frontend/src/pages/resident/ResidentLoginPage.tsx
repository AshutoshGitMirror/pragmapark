import { useState, useEffect } from 'react'
import { fetchCurrentUser } from '../../api/adminClient'
import { useAuth } from '../../context/AuthContext'
import { getErrorMessage } from '../../utils/format'

const VIOLET = '#a855f7'
const VIOLET_DIM = 'rgba(168,85,247,0.12)'

export default function ResidentLoginPage() {
  const { login, user, logout } = useAuth()
  const [email, setEmail] = useState('resident@pragma.io')
  const [password, setPassword] = useState('resident123')
  const [loading, setLoading] = useState(false)
  const [loadingSlow, setLoadingSlow] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!loading) { setLoadingSlow(false); return }
    const t = setTimeout(() => setLoadingSlow(true), 15000)
    return () => clearTimeout(t)
  }, [loading])

  const [existingUser, setExistingUser] = useState<{ email: string; role: string } | null>(null)

  // Server-verified redirect: never trust stale AuthContext cache
  useEffect(() => {
    let cancelled = false
    fetchCurrentUser()
      .then((u) => {
        if (!cancelled) {
          if (u.role === 'resident') {
            window.location.hash = '/resident/dashboard'
          } else {
            setExistingUser({ email: u.email, role: u.role })
          }
        }
      })
      .catch(() => { /* session expired — stay on login */ })
    return () => { cancelled = true }
  }, [user])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      await login(email || 'resident@pragma.io', password || 'resident123')
      // redirect handled by useEffect on user change — no race
    } catch (err: unknown) {
      setError(getErrorMessage(err, 'Login failed'))
    } finally {
      setLoading(false)
    }
  }

  if (user && user.role === 'resident') return null

  return (
    <div className="relative min-h-screen flex items-center justify-center p-4 overflow-hidden"
      style={{ background: 'linear-gradient(135deg, #0c0712 0%, #120a1c 50%, #0c0712 100%)' }}>
      <div className="absolute top-1/3 left-1/2 -translate-x-1/2 w-[500px] h-[500px] rounded-full blur-[140px] opacity-30"
        style={{ background: 'radial-gradient(circle, rgba(168,85,247,0.10), transparent)' }} />

      <div className="relative w-full max-w-sm">
        <div className="text-center mb-10">
          <div className="font-display text-[42px] font-black italic leading-none mb-2"
            style={{ color: VIOLET, letterSpacing: '-2px' }}>
            Pragma<span style={{ color: '#5a6a8a' }}>.</span>
          </div>
          <div className="flex items-center gap-2 justify-center mb-6">
            <span className="w-px h-3" style={{ background: `linear-gradient(to bottom, ${VIOLET}, transparent)` }} />
            <span className="text-[9px] font-mono tracking-[3px] uppercase text-muted-alt">Resident Portal</span>
            <span className="w-px h-3" style={{ background: `linear-gradient(to bottom, transparent, ${VIOLET})` }} />
          </div>
          <h1 className="font-heading text-xl font-semibold text-white">Share Your Home Slot</h1>
          <p className="font-mono text-[11px] text-muted-alt mt-1">Turn idle parking into city supply</p>
        </div>

        {existingUser && (
          <div className="rounded-2xl p-6 space-y-3 backdrop-blur-sm text-center"
            style={{
              background: 'linear-gradient(135deg, rgba(18,10,28,0.9), rgba(12,7,18,0.9))',
              border: '1px solid rgba(168,85,247,0.2)',
            }}>
            <p className="text-xs font-mono" style={{ color: VIOLET }}>
              You are signed in as <strong>{existingUser.email}</strong> ({existingUser.role})
            </p>
            <div className="flex gap-3 justify-center">
              <button onClick={() => { logout().then(() => setExistingUser(null)).catch(() => setExistingUser(null)) }}
                className="px-4 py-2 rounded-lg text-xs font-mono font-semibold text-white"
                style={{ background: '#ff4757' }}>
                Sign Out &amp; Switch Account
              </button>
              <button onClick={() => window.location.hash = '/driver/login'}
                className="px-4 py-2 rounded-lg text-xs font-mono font-semibold"
                style={{ color: '#7a8aaa', border: '1px solid rgba(255,255,255,0.08)' }}>
                Go to Driver Portal
              </button>
            </div>
          </div>
        )}
        {!existingUser && (
          <>
            <form
              onSubmit={handleSubmit}
              className="rounded-2xl p-8 space-y-5 backdrop-blur-sm"
              style={{
                background: 'linear-gradient(135deg, rgba(18,10,28,0.9), rgba(12,7,18,0.9))',
                border: '1px solid rgba(255,255,255,0.06)',
                boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
              }}>
              <div>
                <label className="block text-[10px] font-mono uppercase tracking-wider text-muted-alt mb-1.5">Email</label>
                <input
                  type="email" value={email} onChange={(e) => setEmail(e.target.value)}
                  placeholder="resident@pragma.io"
                  className="w-full rounded-xl px-3.5 py-2.5 text-sm text-white placeholder-[#5a6a8a] font-mono transition-all duration-300"
                  style={{
                    background: 'rgba(0,0,0,0.3)',
                    border: '1px solid rgba(255,255,255,0.06)',
                  }}
                />
              </div>
              <div>
                <label className="block text-[10px] font-mono uppercase tracking-wider text-muted-alt mb-1.5">Password</label>
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
                  <span className="text-rose text-xs">⚠</span>
                  <p className="text-rose text-xs font-mono">{error}</p>
                </div>
              )}

              <button type="submit" disabled={loading}
                className="w-full justify-center text-xs"
                style={{
                  background: VIOLET,
                  color: '#0c0712',
                  padding: '12px 32px',
                  boxShadow: `0 0 24px ${VIOLET_DIM}`,
                }}>
                {loading ? 'Signing in...' : 'Sign In'}
              </button>

              {loadingSlow && (
                <p className="text-[10px] font-mono animate-pulse text-center" style={{ color: VIOLET }}>
                  Login is taking longer than expected. Please wait...
                </p>
              )}

              <p className="text-[9px] text-center text-subtle font-mono">
                Default: resident@pragma.io / resident123
              </p>
            </form>

            <div className="mt-6 text-center">
              <p className="text-[8px] font-mono text-[#3a3a5a] tracking-[3px] uppercase">
                AI · MARL · Blockchain · City-Scale
              </p>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
