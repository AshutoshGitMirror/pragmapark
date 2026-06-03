import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react'
import { api, loginUser, type User } from '../api/adminClient'

interface AuthState {
  user: User | null
  token: string | null
  loading: boolean
  error: string | null
}

interface AuthContextType extends AuthState {
  login: (email: string, password: string) => Promise<void>
  logout: () => void
  isAuthenticated: boolean
}

const AuthContext = createContext<AuthContextType | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({
    user: JSON.parse(localStorage.getItem('pragma_user') || 'null'),
    token: localStorage.getItem('pragma_token'),
    loading: false,
    error: null,
  })

  const login = useCallback(async (email: string, password: string) => {
    setState((s) => ({ ...s, loading: true, error: null }))
    try {
      const data = await loginUser(email, password)
      localStorage.setItem('pragma_token', data.access_token)
      localStorage.setItem('pragma_user', JSON.stringify(data.user))
      setState({ user: data.user, token: data.access_token, loading: false, error: null })
    } catch (err: any) {
      const msg = err.response?.data?.detail || err.message || 'Login failed'
      setState((s) => ({ ...s, loading: false, error: msg }))
      throw new Error(msg)
    }
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem('pragma_token')
    localStorage.removeItem('pragma_user')
    setState({ user: null, token: null, loading: false, error: null })
  }, [])

  useEffect(() => {
    if (state.token) {
      api.defaults.headers.common.Authorization = `Bearer ${state.token}`
    }
  }, [state.token])

  return (
    <AuthContext.Provider value={{ ...state, login, logout, isAuthenticated: !!state.token }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
