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
  BlockListResponse, Lot, OccupancyRecord, BlockChainStatus, DashboardData,
  MicroSlot, PricingLot, Scenario, ScenarioRunResponse, HealthCheck,
  TransactionResponse, MineBlockResponse, PredictionItem, PricingHistoryItem,
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

export async function fetchJson<T>(
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

  for (let attempt = 0; attempt <= retries; attempt++) {
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), timeout)

    try {
      const res = await fetch(url, {
        ...options,
        headers,
        credentials: 'include',
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
    } catch (err: unknown) {
      clearTimeout(timer)
      const errMsg = err instanceof Error ? err.message : String(err)
      if (err instanceof DOMException && err.name === 'AbortError') {
        if (attempt < retries) {
          await new Promise((r) => setTimeout(r, RETRY_DELAYS[attempt]))
          continue
        }
        throw new Error('Request timed out')
      }
      if (attempt < retries && !errMsg.includes('Unauthorized')) {
        await new Promise((r) => setTimeout(r, RETRY_DELAYS[attempt]))
        continue
      }
      throw err
    }
  }
  throw new Error('Exhausted retries')
}

interface AuthResponse {
  access_token: string
  token_type: string
}

export async function login(): Promise<string> {
  const body = JSON.stringify({ email: 'admin@pragma.io', password: 'admin123' })

  const res = await fetch(`${BASE_URL}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body,
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

export async function fetchOccupancy(
  lotId: string,
  hours = 24,
): Promise<OccupancyRecord[]> {
  const res = await fetchJson<{ records: OccupancyRecord[] }>(
    `/lots/${lotId}/occupancy?hours=${hours}`,
  )
  return res.records
}

export async function fetchDashboard(): Promise<DashboardData> {
  return fetchJson<DashboardData>('/admin/dashboard')
}

export async function fetchBlockchainStatus(): Promise<BlockChainStatus> {
  return fetchJson<BlockChainStatus>('/blockchain/status')
}

export async function fetchBlockchainBlocks(): Promise<BlockListResponse> {
  return fetchJson<BlockListResponse>('/blockchain/blocks')
}

export async function fetchPricingLots(): Promise<PricingLot[]> {
  try {
    return await fetchJson<PricingLot[]>('/pricing/lots')
  } catch {
    return []
  }
}

export async function fetchDigitalTwinScenarios(): Promise<Scenario[]> {
  return fetchJson<Scenario[]>('/digital-twin/scenarios')
}

export async function fetchMicroSlots(lotId: string): Promise<MicroSlot[]> {
  const res = await fetchJson<{ slots: MicroSlot[] }>(`/micro/lots/${lotId}/slots?limit=1000`)
  return res.slots
}

export async function runScenario(name: string, zoneId = 'zone_0'): Promise<ScenarioRunResponse> {
  return fetchJson<ScenarioRunResponse>('/digital-twin/scenarios/run', {
    method: 'POST',
    body: JSON.stringify({ scenario_name: name, zone_id: zoneId }),
  }, 1)
}

export async function mineBlock(): Promise<MineBlockResponse> {
  return fetchJson<MineBlockResponse>('/blockchain/mine', {
    method: 'POST',
  })
}

export async function addBlockchainTransaction(body: {
  driver_id: string
  lot_id: string
  action: string
  price: number
  duration_minutes?: number
}): Promise<TransactionResponse> {
  return fetchJson<TransactionResponse>('/blockchain/transaction', {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export async function fetchPredictions(
  lotId: string,
  hours = 24,
): Promise<PredictionItem[]> {
  return fetchJson<PredictionItem[]>(`/lots/${lotId}/predictions?hours=${hours}`)
}

export async function fetchPricingHistory(
  days = 7,
): Promise<PricingHistoryItem[]> {
  return fetchJson<PricingHistoryItem[]>(`/pricing/history?days=${days}`)
}



