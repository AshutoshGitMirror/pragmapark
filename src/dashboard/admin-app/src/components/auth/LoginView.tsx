import { useState, FormEvent } from 'react'

interface LoginViewProps {
  onLogin: (email: string, password: string) => Promise<void>;
  onRegister: () => void;
}

export default function LoginView({ onLogin, onRegister }: LoginViewProps) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault(); setError(''); setBusy(true)
    try { await onLogin(email, password) }
    catch (err: any) { setError(err.response?.data?.detail || err.message || 'Login failed') }
    finally { setBusy(false) }
  }

  return (
    <div
      className="p-11 rounded-[20px] w-[400px] max-w-[90vw]"
      style={{
        background: 'rgba(255,255,255,0.06)',
        backdropFilter: 'blur(24px)',
        WebkitBackdropFilter: 'blur(24px)',
        border: '1px solid rgba(255,255,255,0.06)',
        boxShadow: '0 16px 48px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.06)',
      }}
    >
      <div className="flex items-center gap-2.5 mb-2">
        <i className="fas fa-parking text-[28px]" style={{ color: '#e2b84d' }} />
        <h2 className="text-[22px] font-semibold">Pragma</h2>
      </div>
      <p className="text-sm mb-7" style={{ color: '#a49fc4' }}>Smart Parking Management Platform</p>
      {error && (
        <div className="p-2 mb-4 text-[13px] rounded-lg" role="alert" style={{ background: 'rgba(239,68,68,0.1)', color: '#f87171' }}>
          {error}
        </div>
      )}
      <form onSubmit={handleSubmit}>
        <div className="mb-[18px]">
          <label className="block text-[13px] mb-1.5" style={{ color: '#a49fc4' }}>Email</label>
          <input
            type="email" value={email} onChange={(e) => setEmail(e.target.value)}
            className="w-full px-3.5 py-3 rounded-xl text-sm outline-none transition-all duration-200"
            style={{
              background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)',
              color: '#f0eef8',
            }}
            onFocus={(e) => { e.target.style.borderColor = 'rgba(226,184,77,0.3)'; e.target.style.background = 'rgba(255,255,255,0.05)' }}
            onBlur={(e) => { e.target.style.borderColor = 'rgba(255,255,255,0.06)'; e.target.style.background = 'rgba(255,255,255,0.03)' }}
            placeholder="you@company.com" required
          />
        </div>
        <div className="mb-[18px]">
          <label className="block text-[13px] mb-1.5" style={{ color: '#a49fc4' }}>Password</label>
          <input
            type="password" value={password} onChange={(e) => setPassword(e.target.value)}
            className="w-full px-3.5 py-3 rounded-xl text-sm outline-none transition-all duration-200"
            style={{
              background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)',
              color: '#f0eef8',
            }}
            onFocus={(e) => { e.target.style.borderColor = 'rgba(226,184,77,0.3)'; e.target.style.background = 'rgba(255,255,255,0.05)' }}
            onBlur={(e) => { e.target.style.borderColor = 'rgba(255,255,255,0.06)'; e.target.style.background = 'rgba(255,255,255,0.03)' }}
            placeholder="Enter password" required
          />
        </div>
        <button
          type="submit" disabled={busy}
          className="w-full flex items-center justify-center gap-2 py-3 rounded-xl text-sm font-semibold cursor-pointer transition-all duration-200 border-none"
          style={{
            background: 'linear-gradient(135deg, #e2b84d, #c9a33e)',
            color: '#0b0b12',
          }}
          onMouseEnter={(e) => { if (!busy) e.currentTarget.style.filter = 'brightness(1.12)' }}
          onMouseLeave={(e) => { if (!busy) e.currentTarget.style.filter = '' }}
        >
          {busy ? <i className="fas fa-circle-notch fa-spin" /> : <i className="fas fa-right-to-bracket" />}
          Sign In
        </button>
      </form>
      <p className="text-center mt-3">
        <button
          onClick={onRegister}
          className="px-3.5 py-1.5 rounded-lg text-xs cursor-pointer transition-all duration-200"
          style={{
            background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)',
            color: '#f0eef8',
          }}
          onMouseEnter={(e) => { e.currentTarget.style.borderColor = 'rgba(226,184,77,0.3)'; e.currentTarget.style.color = '#e2b84d' }}
          onMouseLeave={(e) => { e.currentTarget.style.borderColor = 'rgba(255,255,255,0.06)'; e.currentTarget.style.color = '#f0eef8' }}
        >
          Create Account
        </button>
      </p>
    </div>
  )
}
