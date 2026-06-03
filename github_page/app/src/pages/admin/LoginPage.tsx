import { useState, type FormEvent } from 'react'
import { useAuth } from '../../context/AuthContext'

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
    <div className="min-h-screen bg-[#0a0a0f] flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-10">
          <h1 className="text-3xl font-light tracking-wider text-cyan-400">Pragma</h1>
          <p className="text-sm text-muted mt-2">Smart Parking Management Platform</p>
        </div>
        <form onSubmit={handleSubmit} className="bg-[#13131f] border border-white/5 rounded-xl p-8 space-y-5">
          <div>
            <label className="block text-xs text-dim uppercase tracking-widest mb-1.5">Email</label>
            <input
              id="login-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full bg-[#0a0a0f] border border-white/10 rounded-lg px-3.5 py-2.5 text-sm text-white placeholder-dim/50 focus:outline-none focus:border-cyan-500/50 transition-colors"
              placeholder="admin@pragma.io"
              required
            />
          </div>
          <div>
            <label className="block text-xs text-dim uppercase tracking-widest mb-1.5">Password</label>
            <input
              id="login-password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full bg-[#0a0a0f] border border-white/10 rounded-lg px-3.5 py-2.5 text-sm text-white placeholder-dim/50 focus:outline-none focus:border-cyan-500/50 transition-colors"
              placeholder="••••••••"
              required
            />
          </div>
          {(localError || error) && (
            <p id="login-error" className="text-red-400 text-xs">{localError || error}</p>
          )}
          <button
            id="login-submit-btn"
            type="submit"
            disabled={loading}
            className="w-full bg-cyan-500 hover:bg-cyan-400 text-black font-medium rounded-lg py-2.5 text-sm transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? 'Signing in...' : 'Sign In'}
          </button>
        </form>
      </div>
    </div>
  )
}
