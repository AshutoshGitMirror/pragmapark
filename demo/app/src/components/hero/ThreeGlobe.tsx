import { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'

// ── Constants ───────────────────────────────────────────────────────────
const COUNT = 800                    // Reduced from 2000 — still looks dense, much faster
const MAX_EDGES_PER_NODE = 5         // Limit edges to prevent O(n²) explosion
const EDGE_THRESHOLD = 0.35          // Distance threshold for edge connection
const ROTATION_SPEED = 0.001         // Slower, smoother rotation
const MOUSE_INFLUENCE = 0.15         // Reduced mouse influence

export function ThreeGlobe() {
  const ref = useRef<HTMLCanvasElement>(null)
  const mouseRef = useRef({ x: 0, y: 0 })
  const [isVisible, setIsVisible] = useState(true)
  const isVisibleRef = useRef(true)

  // IntersectionObserver: pause rendering when scrolled off-screen
  useEffect(() => {
    const canvas = ref.current
    if (!canvas) return

    const observer = new IntersectionObserver(
      ([entry]) => {
        setIsVisible(entry.isIntersecting)
        isVisibleRef.current = entry.isIntersecting
      },
      { threshold: 0.05 } // 5% visibility triggers
    )
    observer.observe(canvas)
    return () => observer.disconnect()
  }, [])

  useEffect(() => {
    const canvas = ref.current
    if (!canvas) return

    const scene = new THREE.Scene()
    const camera = new THREE.PerspectiveCamera(
      45,
      canvas.clientWidth / canvas.clientHeight,
      0.1,
      1000
    )
    camera.position.z = 4

    const renderer = new THREE.WebGLRenderer({
      canvas,
      alpha: true,
      antialias: false, // ← Disabled: major GPU saving. Canvas CSS handles smoothing.
      powerPreference: 'low-power', // ← Hint for mobile/integrated GPUs
    })

    // ── FIX: Cap pixel ratio more aggressively ──
    // On a 1080p display with dpr=2, we render 3840x2160 — huge waste.
    // Cap at 1.5 for crisp-but-efficient rendering.
    const dpr = Math.min(window.devicePixelRatio || 1, 1.5)
    renderer.setPixelRatio(dpr)
    renderer.setSize(canvas.clientWidth, canvas.clientHeight, false)

    // ── Particle positions (spherical distribution) ──
    const positions = new Float32Array(COUNT * 3)
    const colors = new Float32Array(COUNT * 3)
    const sizes = new Float32Array(COUNT)

    for (let i = 0; i < COUNT; i++) {
      const theta = Math.random() * Math.PI * 2
      const phi = Math.acos(2 * Math.random() - 1)
      const r = 1.4 + Math.random() * 0.3
      positions[i * 3] = r * Math.sin(phi) * Math.cos(theta)
      positions[i * 3 + 1] = r * Math.cos(phi)
      positions[i * 3 + 2] = r * Math.sin(phi) * Math.sin(theta)
      const c = new THREE.Color().setHSL(0.55, 0.8, 0.3 + Math.random() * 0.4)
      colors[i * 3] = c.r
      colors[i * 3 + 1] = c.g
      colors[i * 3 + 2] = c.b
      sizes[i] = 0.01 + Math.random() * 0.02
    }

    const geo = new THREE.BufferGeometry()
    geo.setAttribute('position', new THREE.BufferAttribute(positions, 3))
    geo.setAttribute('color', new THREE.BufferAttribute(colors, 3))
    geo.setAttribute('size', new THREE.BufferAttribute(sizes, 1))

    const mat = new THREE.PointsMaterial({
      size: 0.025,
      vertexColors: true,
      transparent: true,
      opacity: 0.8,
      blending: THREE.AdditiveBlending,
      sizeAttenuation: true,
      depthWrite: false, // ← Prevents z-fighting, faster rendering
    })
    const points = new THREE.Points(geo, mat)
    scene.add(points)

    // ── FIX: O(n) edge generation instead of O(n²) ──
    // Instead of checking every pair (2M checks), use spatial bucketing.
    // Divide sphere into grid cells, only check neighbors in adjacent cells.
    const edgePositions: number[] = []
    const grid = new Map<string, number[]>() // cellKey -> [particle indices]
    const cellSize = EDGE_THRESHOLD

    // Place particles into grid cells
    for (let i = 0; i < COUNT; i++) {
      const x = positions[i * 3]
      const y = positions[i * 3 + 1]
      const z = positions[i * 3 + 2]
      const cx = Math.floor(x / cellSize)
      const cy = Math.floor(y / cellSize)
      const cz = Math.floor(z / cellSize)
      const key = `${cx},${cy},${cz}`
      if (!grid.has(key)) grid.set(key, [])
      grid.get(key)!.push(i)
    }

    // Check neighbors only in same + adjacent cells
    const neighborOffsets = []
    for (let dx = -1; dx <= 1; dx++)
      for (let dy = -1; dy <= 1; dy++)
        for (let dz = -1; dz <= 1; dz++)
          neighborOffsets.push([dx, dy, dz])

    for (let i = 0; i < COUNT; i++) {
      let edgeCount = 0
      const x = positions[i * 3]
      const y = positions[i * 3 + 1]
      const z = positions[i * 3 + 2]
      const cx = Math.floor(x / cellSize)
      const cy = Math.floor(y / cellSize)
      const cz = Math.floor(z / cellSize)

      for (const [dx, dy, dz] of neighborOffsets) {
        if (edgeCount >= MAX_EDGES_PER_NODE) break
        const key = `${cx + dx},${cy + dy},${cz + dz}`
        const cell = grid.get(key)
        if (!cell) continue

        for (const j of cell) {
          if (j <= i) continue // avoid duplicates
          if (edgeCount >= MAX_EDGES_PER_NODE) break
          const dx_ = positions[i * 3] - positions[j * 3]
          const dy_ = positions[i * 3 + 1] - positions[j * 3 + 1]
          const dz_ = positions[i * 3 + 2] - positions[j * 3 + 2]
          if (dx_ * dx_ + dy_ * dy_ + dz_ * dz_ < EDGE_THRESHOLD * EDGE_THRESHOLD) {
            edgePositions.push(
              positions[i * 3], positions[i * 3 + 1], positions[i * 3 + 2],
              positions[j * 3], positions[j * 3 + 1], positions[j * 3 + 2],
            )
            edgeCount++
          }
        }
      }
    }

    const edgeGeo = new THREE.BufferGeometry()
    edgeGeo.setAttribute('position', new THREE.Float32BufferAttribute(edgePositions, 3))
    const edgeMat = new THREE.LineBasicMaterial({
      color: new THREE.Color('#00d4ff'),
      transparent: true,
      opacity: 0.06,
    })
    const lines = new THREE.LineSegments(edgeGeo, edgeMat)
    scene.add(lines)

    // ── Mouse tracking ──
    const handleMove = (e: MouseEvent) => {
      mouseRef.current.x = (e.clientX / window.innerWidth - 0.5) * MOUSE_INFLUENCE
      mouseRef.current.y = (e.clientY / window.innerHeight - 0.5) * MOUSE_INFLUENCE
    }
    window.addEventListener('mousemove', handleMove)

    // ── FIX: Visibility-aware animation loop ──
    let rafId: number
    let angle = 0

    function animate() {
      rafId = requestAnimationFrame(animate)

      // Skip frames when not visible (scrolled away or tab hidden)
      if (!isVisibleRef.current || document.hidden) return

      angle += ROTATION_SPEED
      points.rotation.y = angle + mouseRef.current.x
      points.rotation.x = Math.sin(angle * 0.5) * 0.1 + mouseRef.current.y * 0.3
      lines.rotation.copy(points.rotation)
      renderer.render(scene, camera)
    }
    animate()

    // ── FIX: Page Visibility API ──
    // When user switches tabs, isVisibleRef stays true (we're still on page)
    // but document.hidden pauses the loop. When they come back, we resume.
    // No extra listener needed — checked inside animate().

    // ── Resize handler ──
    const handleResize = () => {
      const w = canvas.clientWidth
      const h = canvas.clientHeight
      if (w === 0 || h === 0) return // prevent zero-size crash
      camera.aspect = w / h
      camera.updateProjectionMatrix()
      renderer.setSize(w, h, false) // false = don't update canvas style
    }
    window.addEventListener('resize', handleResize)

    return () => {
      cancelAnimationFrame(rafId)
      window.removeEventListener('mousemove', handleMove)
      window.removeEventListener('resize', handleResize)
      renderer.dispose()
      geo.dispose()
      mat.dispose()
      edgeGeo.dispose()
      edgeMat.dispose()
    }
  }, [])

  return (
    <canvas
      ref={ref}
      className="absolute inset-0 w-full h-full"
      // ── FIX: Remove opacity:0.6 CSS ──
      // Opacity forces GPU compositing layer for the ENTIRE canvas.
      // Instead, control opacity via the Three.js material opacity.
      style={{ display: 'block' }}
    />
  )
}
