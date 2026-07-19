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
      const requestUrl = err.config?.url || ''
      const currentHash = window.location.hash || '#/'
      const isSessionProbe = requestUrl.includes('/auth/me')
      const isPublicRoute = currentHash === '#/' || currentHash === '' || currentHash.includes('/login') || currentHash.includes('/driver/login')
      if (!isSessionProbe && !isPublicRoute) {
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
  is_resident_only?: boolean
}

export interface ResidentPermit {
  id: number
  user_id: number
  user_email: string
  lot_id: string
  lot_name: string
  slot_index: number
  permit_type: string
  start_date: string
  end_date: string
  monthly_rate: number
  auto_renew: boolean
  is_active: boolean
  registered_vehicle: string | null
  created_at: string
  updated_at: string
}

export interface ShareListingInfo {
  id: number
  resident_profile_id: number
  resident_name: string
  lot_id: string
  lot_name: string
  slot_index: number
  price_per_hour: number
  available_from: string
  available_until: string
  status: string
  max_advance_days: number
  registered_vehicle: string | null
  created_at: string
  updated_at: string
}

export interface ShareBookingInfo {
  id: number
  share_listing_id: number
  slot_id: number
  driver_name: string
  lot_name: string
  slot_index: number
  start_time: string
  end_time: string
  total_cost: number
  platform_fee: number
  owner_payout: number
  status: string
  vehicle_id: string | null
  blockchain_ref: string | null
  created_at: string
}

export interface ResidentialMapSlot {
  slot_id: number
  lot_id: string | null
  slot_index: number
  latitude: number
  longitude: number
  spatial_id: string
  is_shared: boolean
  has_permit: boolean
  permit_type: string | null
  price_per_hour: number | null
  available_from: string | null
  available_until: string | null
  resident_name: string | null
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
  const res = await api.get(`/micro/lots/${lotId}/slots?limit=1000`)
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

/* ─── Resident Management ─── */

export async function fetchResidentPermits(): Promise<ResidentPermit[]> {
  const res = await api.get('/residential/permits')
  return res.data
}

export async function createResidentPermit(data: {
  lot_id: string
  slot_index: number
  permit_type?: string
  start_date: string
  end_date: string
  monthly_rate?: number
  registered_vehicle?: string
}): Promise<ResidentPermit> {
  const res = await api.post('/residential/permits', data)
  return res.data
}

export async function deactivatePermit(permitId: number): Promise<ResidentPermit> {
  const res = await api.post(`/residential/permits/${permitId}/deactivate`)
  return res.data
}

export async function fetchPermitSlots(lotId: string): Promise<{ slot_index: number; permit_type: string; is_active: boolean; registered_vehicle: string | null }[]> {
  const res = await api.get(`/residential/permits/${lotId}/slots`)
  return res.data
}

export async function cancelShareListingAdmin(listingId: number): Promise<{ status: string }> {
  const res = await api.delete(`/residential/shares/${listingId}`)
  return res.data
}

export async function settleShareBooking(bookingId: number): Promise<{ status: string; platform_fee?: number; owner_payout?: number; blockchain_ref?: string }> {
  const res = await api.post(`/residential/shares/booking/${bookingId}/settle`)
  return res.data
}

export async function fetchResidentialMap(): Promise<ResidentialMapSlot[]> {
  const res = await api.get('/residential/map')
  return res.data
}
