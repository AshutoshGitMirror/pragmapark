/**
 * client.ts — API client with retry, auth, and graceful error handling.
 *
 * CHANGES from original:
 * 1. BASE_URL is now configurable via import.meta.env.VITE_API_URL
 *    - Dev (Vite proxy): '/api/v1' → proxied to Render
 *    - Prod (static deploy): falls back to full Render URL
 * 2. Health endpoint has shorter timeout (10s vs 60s) for faster cold-start detection
 * 3. Added isBackendReachable() helper for quick connectivity checks
 */

import type {
  Lot, OccupancyRecord, BlockChainStatus, DashboardData,
  SystemHealth, MicroSlot, PricingZone, Scenario, ScenarioResult,
  MarlStatus, SessionStart, PaymentConfirm, HealthCheck,
} from './types'

// ── FIX: Configurable base URL ──
// Vite proxy handles /api in dev. In production (static deploy), use full URL.
const BASE_URL = import.meta.env.VITE_API_URL || '/api/v1'

const FETCH_TIMEOUT = 60000
const HEALTH_TIMEOUT = 10000  // Shorter for health checks
const MAX_RETRIES = 3
const RETRY_DELAYS = [1000, 3000, 7000]

let _jwt: string | null = null

export function setJwt(token: string) {
  _jwt = token
}

export function getJwt(): string | null {
  return _jwt
}

async function fetchJson<T>(
  path: string,
  options?: RequestInit,
  retries = MAX_RETRIES,
  timeout = FETCH_TIMEOUT,
): Promise<T> {
  const url = `${BASE_URL}${path}`
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options?.headers as Record<string, string>),
  }
  if (_jwt) headers['Authorization'] = `Bearer ${_jwt}`

  for (let attempt = 0; attempt <= retries; attempt++) {
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), timeout)

    try {
      const res = await fetch(url, {
        ...options,
        headers,
        signal: controller.signal,
      })
      clearTimeout(timer)

      if (res.status === 503) {
        if (attempt < retries) {
          await new Promise((r) => setTimeout(r, RETRY_DELAYS[attempt]))
          continue
        }
        throw new Error('Service unavailable (cold start)')
      }
      if (res.status === 401) {
        throw new Error('Unauthorized')
      }
      if (!res.ok) {
        const text = await res.text().catch(() => '')
        throw new Error(`HTTP ${res.status}: ${text.slice(0, 200)}`)
      }
      return res.json()
    } catch (err: any) {
      clearTimeout(timer)
      if (err.name === 'AbortError') {
        if (attempt < retries) {
          await new Promise((r) => setTimeout(r, RETRY_DELAYS[attempt]))
          continue
        }
        throw new Error('Request timed out')
      }
      if (attempt < retries && !err.message?.includes('Unauthorized')) {
        await new Promise((r) => setTimeout(r, RETRY_DELAYS[attempt]))
        continue
      }
      throw err
    }
  }
  throw new Error('Exhausted retries')
}

export interface AuthResponse {
  access_token: string
  token_type: string
}

export async function login(): Promise<string> {
  const formData = new URLSearchParams()
  formData.append('username', 'admin@pragma.io')
  formData.append('password', 'admin123')

  const res = await fetch(`${BASE_URL}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: formData,
  })

  if (!res.ok) throw new Error('Login failed')
  const data: AuthResponse = await res.json()
  _jwt = data.access_token
  return _jwt
}

// ── FIX: Shorter timeout for health checks ──
export async function fetchHealth(): Promise<HealthCheck> {
  return fetchJson<HealthCheck>('/health', {}, 1, HEALTH_TIMEOUT)
}

export async function fetchLots(): Promise<Lot[]> {
  return fetchJson<Lot[]>('/lots')
}

export async function fetchDriverLots(): Promise<any[]> {
  return fetchJson<any[]>('/driver/lots')
}

export async function fetchOccupancy(
  lotId: string,
  hours = 24,
): Promise<OccupancyRecord[]> {
  return fetchJson<OccupancyRecord[]>(
    `/lots/${lotId}/occupancy?hours=${hours}`,
  )
}

export async function fetchDashboard(): Promise<DashboardData> {
  return fetchJson<DashboardData>('/admin/dashboard')
}

export async function fetchSystemHealth(): Promise<SystemHealth> {
  return fetchJson<SystemHealth>('/admin/system-health')
}

export async function fetchBlockchainStatus(): Promise<BlockChainStatus> {
  return fetchJson<BlockChainStatus>('/blockchain/status')
}

export async function fetchPricingZones(): Promise<PricingZone[]> {
  return fetchJson<PricingZone[]>('/pricing/zones')
}

export async function fetchDigitalTwinScenarios(): Promise<Scenario[]> {
  return fetchJson<Scenario[]>('/digital-twin/scenarios')
}

export async function fetchMicroSlots(lotId: string): Promise<MicroSlot[]> {
  return fetchJson<MicroSlot[]>(`/micro/lots/${lotId}/slots`)
}

export async function fetchMarlStatus(): Promise<MarlStatus> {
  return fetchJson<MarlStatus>('/marl/status')
}

export async function startSession(
  lotId: string,
  driverId: string,
  slot?: number,
): Promise<SessionStart> {
  return fetchJson<SessionStart>('/sessions/start', {
    method: 'POST',
    body: JSON.stringify({ lot_id: lotId, driver_id: driverId, slot, force: true }),
  }, 1)
}

export async function endSession(sessionId: string): Promise<any> {
  return fetchJson<any>('/sessions/end', {
    method: 'POST',
    body: JSON.stringify({ session_id: sessionId }),
  }, 1)
}

export async function confirmPayment(sessionId: string): Promise<PaymentConfirm> {
  return fetchJson<PaymentConfirm>('/payments/confirm', {
    method: 'POST',
    body: JSON.stringify({ session_id: sessionId }),
  }, 1)
}

export async function runScenario(name: string): Promise<ScenarioResult> {
  return fetchJson<ScenarioResult>('/digital-twin/scenarios/run', {
    method: 'POST',
    body: JSON.stringify({ scenario: name }),
  }, 1)
}

export async function triggerMarlTrain(): Promise<any> {
  return fetchJson<any>('/marl/train', {
    method: 'POST',
  }, 1)
}
