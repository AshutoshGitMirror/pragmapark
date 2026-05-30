import { useEffect, useRef } from 'react'

export function useScrollReveal(
  selector = '.reveal',
  options = { threshold: 0.1, rootMargin: '0px 0px -40px 0px' },
) {
  const observerRef = useRef<IntersectionObserver>()

  useEffect(() => {
    const els = document.querySelectorAll(selector)
    if (!els.length) return

    observerRef.current = new IntersectionObserver((entries) => {
      entries.forEach((e) => {
        if (e.isIntersecting) {
          e.target.classList.add('visible')
          observerRef.current?.unobserve(e.target)
        }
      })
    }, options)

    els.forEach((el) => observerRef.current?.observe(el))

    return () => observerRef.current?.disconnect()
  }, [selector])
}
