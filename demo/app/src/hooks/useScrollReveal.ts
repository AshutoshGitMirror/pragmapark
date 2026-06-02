import { useState, useEffect, useRef } from 'react'

export function useReveal(delay = 100) {
  const [visible, setVisible] = useState(false)
  const timerRef = useRef<ReturnType<typeof setTimeout>>()

  useEffect(() => {
    timerRef.current = setTimeout(() => setVisible(true), delay)
    return () => { if (timerRef.current) clearTimeout(timerRef.current) }
  }, [delay])

  return visible
}


