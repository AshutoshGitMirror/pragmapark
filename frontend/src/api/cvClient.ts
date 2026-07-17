/**
 * cvClient.ts — client for the LOCAL CV agent (Phase 2 Live Vision).
 *
 * The CV agent runs on its own port (default 8777) and is NEVER exposed
 * from Render. It runs on the operator's machine next to the camera, so we
 * point directly at http://localhost:8777 (no TLS -> mixed-content exempt).
 *
 * The MJPEG live feed is consumed directly by an <img> tag (see
 * LiveVisionPage) via getMjpegUrl(); polling endpoints here fetch
 * occupancy / slots / calibration state.
 */

const CV_BASE = import.meta.env.VITE_CV_AGENT_URL || 'http://localhost:8777'

export interface SlotReading {
  slot_id: number
  occupied: boolean
  confidence: number
}

export interface OccupancyResponse {
  lot_id: string
  frame_size: [number, number]
  camera_available: boolean
  occupancy: SlotReading[]
}

export interface StatusResponse {
  ok: boolean
  backend: string
  model: string
  lots: string[]
  camera: { available: boolean; frame_size: [number, number] }
}

export interface SlotDef {
  slot_id: number
  polygon: [number, number][]
}

const FETCH_TIMEOUT = 8000

async function cvFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${CV_BASE}${path}`
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), FETCH_TIMEOUT)
  try {
    const res = await fetch(url, {
      ...options,
      headers: { 'Content-Type': 'application/json', ...(options?.headers as Record<string, string>) },
      signal: controller.signal,
    })
    if (!res.ok) {
      const text = await res.text().catch(() => '')
      throw new Error(`CV agent ${res.status}: ${text.slice(0, 200)}`)
    }
    return res.json() as Promise<T>
  } finally {
    clearTimeout(timer)
  }
}

export function getMjpegUrl(): string {
  // Cache-busting so the <img> reconnects cleanly on reload.
  return `${CV_BASE}/camera/mjpeg?t=${Date.now()}`
}

export function getFrameUrl(): string {
  return `${CV_BASE}/camera/frame?t=${Date.now()}`
}

export async function fetchCvStatus(): Promise<StatusResponse> {
  return cvFetch<StatusResponse>('/status')
}

export async function fetchCvLots(): Promise<string[]> {
  const data = await cvFetch<{ lots: string[] }>('/lots')
  return data.lots
}

export async function fetchCvSlots(lotId: string): Promise<SlotDef[]> {
  const data = await cvFetch<{ lot_id: string; slots: SlotDef[] }>(`/slots/${encodeURIComponent(lotId)}`)
  return data.slots
}

export async function fetchCvOccupancy(lotId: string): Promise<OccupancyResponse> {
  return cvFetch<OccupancyResponse>(`/camera/occupancy/${encodeURIComponent(lotId)}`)
}

export async function suggestGrid(
  width: number,
  height: number,
  rows: number,
  cols: number,
  margin = 0.05,
): Promise<SlotDef[]> {
  const data = await cvFetch<{ slots: SlotDef[] }>('/calibrate/grid-suggest', {
    method: 'POST',
    body: JSON.stringify({ width, height, rows, cols, margin }),
  })
  return data.slots
}

export async function saveCalibration(lotId: string, slots: SlotDef[]): Promise<{ saved: number; lot_id: string }> {
  return cvFetch<{ saved: number; lot_id: string }>('/calibrate/save', {
    method: 'POST',
    body: JSON.stringify({ lot_id: lotId, slots }),
  })
}
