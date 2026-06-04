import { useState, type FormEvent } from 'react'
import { useAuth } from '../../context/AuthContext'

const MailIcon = () => (
  <svg className="w-4 h-4 text-[#64748b]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M21.75 6.75v10.5a2.25 2.25 0 01-2.25 2.25h-15a2.25 2.25 0 01-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0019.5 4.5h-15a2.25 2.25 0 00-2.25 2.25m19.5 0v.243a2.25 2.25 0 01-1.07 1.916l-7.5 4.615a2.25 2.25 0 01-2.36 0L3.32 8.91a2.25 2.25 0 01-1.07-1.916V6.75" />
  </svg>
)

const LockIcon = () => (
  <svg className="w-4 h-4 text-[#64748b]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z" />
  </svg>
)

export function LoginPage() {
  const { login, loading, error } = useAuth()
  const [email, setEmail] = useState('admin@pragma.io')
  const [password, setPassword] = useState('admin123')
  const [localError, setLocalError] = useState<string | null>(null)

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setLocalError(null)
    try {
      await login(email, password)
    } catch (err: any) {
      setLocalError(err.message)
    }
  }

  return (
    <div className="relative min-h-screen bg-[#0a0a0f] flex items-center justify-center p-4 overflow-hidden">
      {/* subtle dot-grid texture */}
      <div
        className="absolute inset-0 opacity-[0.03]"
        style={{ backgroundImage: 'radial-gradient(circle, #00d4ff 1px, transparent 1px)', backgroundSize: '28px 28px' }}
      />
      {/* ambient glow */}
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 w-[420px] h-[420px] bg-[#00d4ff]/5 rounded-full blur-[120px]" />
      <div className="absolute bottom-1/4 left-1/2 -translate-x-1/2 w-[320px] h-[320px] bg-[#00c785]/5 rounded-full blur-[100px]" />

      <div className="relative w-full max-w-sm">
        <div className="text-center mb-10">
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-[rgba(0,212,255,0.08)] border border-[rgba(0,212,255,0.2)] text-[#00d4ff] text-[11px] font-mono tracking-wider mb-6">
            <span className="w-1.5 h-1.5 rounded-full bg-[#00d4ff] animate-pulse" />
            ADMIN ACCESS
          </div>
          <h1 className="text-3xl font-light tracking-tight text-white">Sign in to Pragma</h1>
          <p className="text-sm text-[#64748b] mt-2">Smart Parking Management Platform</p>
        </div>

        <form
          onSubmit={handleSubmit}
          className="bg-[#0e0e1a] border border-[rgba(255,255,255,0.06)] rounded-2xl p-8 space-y-5 shadow-[0_0_60px_rgba(0,212,255,0.04)]"
        >
          <div>
            <label htmlFor="login-email" className="block text-sm text-white/70 mb-1.5 font-medium">
              Email
            </label>
            <div className="relative">
              <span className="absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none">
                <MailIcon />
              </span>
              <input
                id="login-email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full bg-[#0a0a0f] border border-white/8 rounded-xl pl-10 pr-3.5 py-2.5 text-sm text-white placeholder-[#64748b]/60 focus:outline-none focus:border-[#00d4ff]/40 focus:shadow-[0_0_20px_rgba(0,212,255,0.06)] transition-all duration-300"
                placeholder="you@example.com"
                required
              />
            </div>
          </div>

          <div>
            <label htmlFor="login-password" className="block text-sm text-white/70 mb-1.5 font-medium">
              Password
            </label>
            <div className="relative">
              <span className="absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none">
                <LockIcon />
              </span>
              <input
                id="login-password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full bg-[#0a0a0f] border border-white/8 rounded-xl pl-10 pr-3.5 py-2.5 text-sm text-white placeholder-[#64748b]/60 focus:outline-none focus:border-[#00d4ff]/40 focus:shadow-[0_0_20px_rgba(0,212,255,0.06)] transition-all duration-300"
                placeholder="Enter your password"
                required
              />
            </div>
          </div>

          {(localError || error) && (
            <div className="flex items-center gap-2 bg-red-500/8 border border-red-500/20 rounded-xl px-4 py-2.5">
              <svg className="w-4 h-4 text-red-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
              </svg>
              <p id="login-error" className="text-red-400 text-sm">{localError || error}</p>
            </div>
          )}

          <button
            id="login-submit-btn"
            type="submit"
            disabled={loading}
            className="w-full bg-[#00d4ff] hover:bg-[#00e5ff] text-[#0a0a0f] font-semibold rounded-xl py-2.5 text-sm transition-all duration-300 disabled:opacity-40 disabled:cursor-not-allowed shadow-[0_0_30px_rgba(0,212,255,0.15)] hover:shadow-[0_0_40px_rgba(0,212,255,0.3)]"
          >
            {loading ? 'Signing in...' : 'Sign In'}
          </button>
        </form>

        <div className="mt-6 text-center">
          <div className="w-px h-6 bg-gradient-to-b from-transparent to-[#00d4ff]/30 mx-auto" />
        </div>
      </div>
    </div>
  )
}
