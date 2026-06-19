import { createContext, useContext, useState, type ReactNode } from 'react'

interface WarmupContextValue {
  backendReady: boolean
  setBackendReady: (v: boolean) => void
}

const WarmupContext = createContext<WarmupContextValue>({
  backendReady: false,
  setBackendReady: () => {},
})

export function useWarmupContext() {
  return useContext(WarmupContext)
}

export function WarmupProvider({ children }: { children: ReactNode }) {
  const [backendReady, setBackendReady] = useState(false)
  return (
    <WarmupContext.Provider value={{ backendReady, setBackendReady }}>
      {children}
    </WarmupContext.Provider>
  )
}
