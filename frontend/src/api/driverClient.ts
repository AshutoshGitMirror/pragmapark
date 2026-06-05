import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios'

const API_BASE = import.meta.env.VITE_API_URL || '/api/v1'

export const driverApi = axios.create({
  baseURL: API_BASE,
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
})

driverApi.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = sessionStorage.getItem('pragma_driver_token')
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

driverApi.interceptors.response.use(
  (res) => res,
  (err: AxiosError) => {
    if (err.response?.status === 401) {
      sessionStorage.removeItem('pragma_driver_token')
      sessionStorage.removeItem('pragma_driver_user')
      window.location.hash = '/driver/login'
    }
    return Promise.reject(err)
  },
)

export interface DriverLot {
  lot_id: string
  name: string
  address: string
  city: string
  total_slots: number
  base_price: number
  predicted_occupancy: number
  available_spots: number
  dynamic_price: number
  latitude?: number
  longitude?: number
  available_handicap: number
  available_ev: number
  available_regular: number
}

export interface DriverLotDetail {
  lot_id: string
  name: string
  address: string
  total_slots: number
  base_price: number
  latitude?: number
  longitude?: number
  predicted_occupancy: number
  current_price: number
  available_spots: number
  available_handicap: number
  available_ev: number
  available_regular: number
  recent_occupancy: { timestamp: string; occupancy_rate: number; price: number; net_flux: number }[]
}

export interface SessionHistoryItem {
  session_id: string
  lot_id: string
  lot_name: string
  start_time?: string
  end_time?: string
  duration_minutes?: number
  amount_charged?: number
  status: string
}

export interface ActiveSessionItem {
  session_id: string
  slot: number
  start_time?: string
  entry_price: number
}

export interface SessionReceipt {
  session_id: string
  lot_id: string
  driver_id: string
  start_time?: string
  end_time?: string
  duration_minutes: number
  duration_hours: number
  entry_price: number
  final_price: number
  amount_charged: number
  blockchain_ref?: string
  payment_method: string
}

export function setDriverToken(token: string, user: any) {
  sessionStorage.setItem('pragma_driver_token', token)
  sessionStorage.setItem('pragma_driver_user', JSON.stringify(user))
}

export function getDriverUser(): any {
  try {
    return JSON.parse(sessionStorage.getItem('pragma_driver_user') || 'null')
  } catch { return null }
}

export function clearDriverAuth() {
  sessionStorage.removeItem('pragma_driver_token')
  sessionStorage.removeItem('pragma_driver_user')
}

export async function driverLogin(email: string, password: string): Promise<{ access_token: string; user: any }> {
  const res = await driverApi.post('/auth/login', { email, password })
  return res.data
}

export async function fetchDriverLots(params?: { max_price?: number }): Promise<DriverLot[]> {
  const res = await driverApi.get('/driver/lots', { params })
  return res.data.lots
}

export async function fetchLotDetail(lotId: string): Promise<DriverLotDetail> {
  const res = await driverApi.get(`/driver/lots/${lotId}`)
  return res.data
}

export async function startSession(lotId: string, slot: number, payment_method = 'card'): Promise<any> {
  const res = await driverApi.post('/sessions/start', { lot_id: lotId, slot, payment_method })
  return res.data
}

export async function endSession(sessionId: string): Promise<any> {
  const res = await driverApi.post('/sessions/end', { session_id: sessionId })
  return res.data
}

export async function fetchActiveSession(): Promise<ActiveSessionItem | null> {
  try {
    const res = await driverApi.get('/sessions/active')
    const s = res.data
    return { session_id: s.session_id, slot: s.slot, start_time: s.start_time, entry_price: s.entry_price }
  } catch {
    return null
  }
}

export async function fetchSessionHistory(offset = 0, limit = 50): Promise<{ total_sessions: number; sessions: SessionHistoryItem[] }> {
  const res = await driverApi.get(`/sessions/history?offset=${offset}&limit=${limit}`)
  return res.data
}

export async function fetchSessionReceipt(sessionId: string): Promise<SessionReceipt> {
  const res = await driverApi.get(`/sessions/${sessionId}/receipt`)
  return res.data
}

export async function confirmPayment(sessionId: string, method = 'card'): Promise<any> {
  const res = await driverApi.post('/payments/confirm', { session_id: sessionId, payment_method: method, idempotency_key: `${sessionId}-${Date.now()}` })
  return res.data
}
