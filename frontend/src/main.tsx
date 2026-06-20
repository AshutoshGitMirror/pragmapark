// Safeguard: framer-motion may pass non-numeric threshold values to IntersectionObserver
// on some React 18 / browser combinations. This wrapper prevents the crash from
// bubbling up into the React error boundary.
const OrigObserver = window.IntersectionObserver
window.IntersectionObserver = function (
  callback: IntersectionObserverCallback,
  options?: IntersectionObserverInit
) {
  try {
    return new OrigObserver(callback, options)
  } catch {
    return { observe: () => {}, unobserve: () => {}, disconnect: () => {} } as unknown as IntersectionObserver
  }
} as any
window.IntersectionObserver.prototype = OrigObserver.prototype
Object.assign(window.IntersectionObserver, OrigObserver)

import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { HashRouter } from 'react-router-dom'
import App from './App'
import './styles/globals.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <HashRouter>
      <App />
    </HashRouter>
  </StrictMode>
)
