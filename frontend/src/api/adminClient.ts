import axios, { AxiosError } from 'axios'

const API_BASE = import.meta.env.VITE_API_URL || '/api/v1'

export const api = axios.create({
  baseURL: API_BASE,
  timeout: 60000,
  headers: { 'Content-Type': 'application/json' },
  withCredentials: true,
})

api.interceptors.response.use(
  (res) => res,
  (err: AxiosError) => {
    if (err.response?.status === 401) {
      if (!window.location.hash.includes('/login')) {
        window.location.hash = '/login'
      }
    }
    return Promise.reject(err)
  },
)

export interface User {
  id: string
  email: string
  full_name: string
  role: string
  organization: string
}

export interface Lot {
  lot_id: string
  name: string
  address: string
  city: string
  total_slots: number
  latitude: number
  longitude: number
  base_price: number
  price_cap: number
  current_occupancy?: number
  owner_id?: string
  status?: string
}

export interface LotDetail extends Lot {
  current_occupancy: number
  available_slots: number
  revenue_today: number
  transactions_today: number
  occupancy_history: OccupancyRecord[]
}

export interface OccupancyRecord {
  lot_id: string
  occupied_slots: number
  total_slots: number
  occupancy_rate: number
  net_flux: number
  price: number
  timestamp: string
}

export interface RevenueOverview {
  total_revenue: number
  total_transactions: number
  period_revenue: number
  period_transactions: number
  daily_revenue: { date: string; revenue: number; transactions: number }[]
  revenue_by_lot: { lot_id: string; name: string; revenue: number; transactions: number }[]
}

export interface SystemHealth {
  status: string
  layers: Record<string, string>
  uptime?: string
  version?: string
}

export interface DashboardData {
  total_lots: number
  total_slots: number
  avg_occupancy: number
  total_revenue: number
  total_transactions: number
  system_health: SystemHealth
  occupancy_trend: { hour: number; rate: number }[]
  revenue_7d: { date: string; revenue: number }[]
  lots: Lot[]
  alerts: Alert[]
}

export interface Alert {
  id: number
  type: string
  severity: string
  message: string
  lot_id?: string
  created_at: string
  resolved: boolean
}

export interface MicroSlot {
  id: number
  lot_id: string
  slot_index: number
  row_label: string
  position: number
  slot_type: string
  base_modifier_score: number
  state?: string
  probability?: number
}

export interface AnalyticsData {
  hourly_occupancy: { hour: number; rate: number; lot_id?: string }[]
  lot_comparison: { lot_id: string; name: string; occupancy: number; revenue: number; efficiency: number }[]
  system_performance: { metric: string; value: number; unit: string; status: string }[]
}

export async function loginUser(email: string, password: string): Promise<{ access_token: string; user: User }> {
  const res = await api.post('/auth/login', { email, password })
  return res.data
}

export async function fetchCurrentUser(): Promise<User> {
  const res = await api.get('/auth/me')
  return res.data
}

export async function logoutUser(): Promise<void> {
  await api.post('/auth/logout')
}

export async function fetchDashboard(): Promise<DashboardData> {
  const res = await api.get('/admin/dashboard')
  return res.data
}

export async function fetchLots(): Promise<Lot[]> {
  const res = await api.get('/lots')
  return res.data
}

export async function fetchLotDetail(lotId: string): Promise<LotDetail> {
  const res = await api.get(`/lots/${lotId}`)
  return res.data
}

export async function fetchOccupancy(lotId: string, hours = 24): Promise<OccupancyRecord[]> {
  const res = await api.get(`/lots/${lotId}/occupancy?hours=${hours}`)
  return res.data.records || res.data
}

export async function fetchRevenue(days = 30): Promise<RevenueOverview> {
  const res = await api.get(`/revenue/overview?days=${days}`)
  return res.data
}

export async function fetchAnalytics(): Promise<AnalyticsData> {
  const res = await api.get('/admin/analytics')
  return res.data
}

export async function fetchAlerts(): Promise<Alert[]> {
  const res = await api.get('/admin/alerts')
  return res.data
}

export async function fetchHealth(): Promise<SystemHealth> {
  const res = await api.get('/admin/system-health')
  return res.data
}

export async function fetchMicroSlots(lotId: string): Promise<MicroSlot[]> {
  const res = await api.get(`/micro/lots/${lotId}/slots`)
  return res.data.slots || res.data
}

export async function createLot(data: Partial<Lot>): Promise<Lot> {
  const res = await api.post('/lots', data)
  return res.data
}

export async function updateLot(lotId: string, data: Partial<Lot>): Promise<Lot> {
  const res = await api.put(`/lots/${lotId}`, data)
  return res.data
}

export async function deleteLot(lotId: string): Promise<void> {
  await api.delete(`/lots/${lotId}`)
}
