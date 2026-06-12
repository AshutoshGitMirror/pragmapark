import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react'
import { loginUser, fetchCurrentUser, logoutUser, type User } from '../api/adminClient'
import { getErrorMessage } from '../utils/format'

interface AuthState {
  user: User | null
  loading: boolean
  error: string | null
}

interface AuthContextType extends AuthState {
  login: (email: string, password: string) => Promise<void>
  logout: () => Promise<void>
  isAuthenticated: boolean
}

const AuthContext = createContext<AuthContextType | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({
    user: null,
    loading: true,
    error: null,
  })

  // On mount, check if we have a valid session cookie by calling /auth/me
  useEffect(() => {
    let cancelled = false
    fetchCurrentUser()
      .then((user) => {
        if (!cancelled) {
          setState({ user, loading: false, error: null })
        }
      })
      .catch(() => {
        if (!cancelled) {
          setState({ user: null, loading: false, error: null })
        }
      })
    return () => { cancelled = true }
  }, [])

  const login = useCallback(async (email: string, password: string) => {
    setState((s) => ({ ...s, loading: true, error: null }))
    try {
      const data = await loginUser(email, password)
      setState({ user: data.user, loading: false, error: null })
    } catch (err: unknown) {
      const msg = getErrorMessage(err, 'Login failed')
      setState((s) => ({ ...s, loading: false, error: msg }))
      throw new Error(msg)
    }
  }, [])

  const logout = useCallback(async () => {
    try {
      await logoutUser()
    } catch (err) {
      console.error('Logout API call failed, clearing local state anyway', err)
    }
    setState({ user: null, loading: false, error: null })
  }, [])
  
  // Set auth header from cookie-based session if user is loaded
  useEffect(() => {
    if (state.user) {
      // We rely on the HttpOnly cookie — no explicit Bearer header needed.
      // But if there's an existing token in cookies, the server reads it.
      // Keep axios default clean; withCredentials handles cookie delivery.
    }
  }, [state.user])

  return (
    <AuthContext.Provider value={{ ...state, login, logout, isAuthenticated: !!state.user }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
