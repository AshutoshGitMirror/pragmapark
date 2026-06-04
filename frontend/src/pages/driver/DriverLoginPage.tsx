import { useState } from 'react'
import { driverLogin, setDriverToken, getDriverUser } from '../../api/driverClient'

export function DriverLoginPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      const data = await driverLogin(email || 'driver@pragma.io', password || 'driver123')
      setDriverToken(data.access_token, data.user)
      window.location.hash = '/driver/find'
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  if (getDriverUser()) {
    window.location.hash = '/driver/find'
    return null
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-6"
      style={{ background: 'linear-gradient(135deg, #07070d 0%, #0a0a18 50%, #07070d 100%)' }}>
      <div className="w-full max-w-sm rounded-2xl p-8"
        style={{
          background: 'linear-gradient(135deg, #0e0e24 0%, #12122a 50%, #0e0e24 100%)',
          boxShadow: '0 1px 0 rgba(255,255,255,0.04), 0 0 0 1px rgba(255,255,255,0.04)',
        }}>
        <div className="text-center mb-8">
          <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-[#00d4ff] to-[#0088cc] flex items-center justify-center text-lg font-bold text-white mx-auto mb-3 shadow-[0_0_16px_rgba(0,212,255,0.25)]">
            P
          </div>
          <h1 className="text-lg font-semibold text-white">Driver Login</h1>
          <p className="text-xs text-[#475569] mt-1">Sign in to find & park</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="text-[11px] text-[#475569] block mb-1.5">Email</label>
            <input
              type="email" value={email} onChange={(e) => setEmail(e.target.value)}
              placeholder="driver@pragma.io"
              className="w-full rounded-lg px-3 py-2.5 text-sm bg-[rgba(255,255,255,0.03)] border border-[rgba(255,255,255,0.06)] text-white placeholder-[#3a4a6a] outline-none focus:border-[#00d4ff]/40 transition-colors"
            />
          </div>
          <div>
            <label className="text-[11px] text-[#475569] block mb-1.5">Password</label>
            <input
              type="password" value={password} onChange={(e) => setPassword(e.target.value)}
              placeholder="driver123"
              className="w-full rounded-lg px-3 py-2.5 text-sm bg-[rgba(255,255,255,0.03)] border border-[rgba(255,255,255,0.06)] text-white placeholder-[#3a4a6a] outline-none focus:border-[#00d4ff]/40 transition-colors"
            />
          </div>

          {error && <p className="text-xs text-red-400">{error}</p>}

          <button type="submit" disabled={loading}
            className="w-full rounded-lg py-2.5 text-sm font-medium text-white transition-all duration-200 disabled:opacity-50"
            style={{ background: 'linear-gradient(135deg, #00d4ff, #0088cc)' }}>
            {loading ? 'Signing in...' : 'Sign In'}
          </button>

          <p className="text-[10px] text-center text-[#475569]">
            Default: driver@pragma.io / driver123
          </p>
        </form>
      </div>
    </div>
  )
}
