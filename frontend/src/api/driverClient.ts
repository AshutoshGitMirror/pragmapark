import axios, { AxiosError } from 'axios'

const API_BASE = import.meta.env.VITE_API_URL || '/api/v1'

export const driverApi = axios.create({
  baseURL: API_BASE,
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
  withCredentials: true,
})

/* ─── Shared response types ─── */

export interface SessionStartResponse {
  session_id: string
  lot_id: string
  slot: number
  entry_price: number
  status: string
  start_time: string
  layers_activated?: string[]
}

export interface SessionEndResponse {
  session_id: string
  status: string
  amount_charged: number
  total_cost?: number
  deposit_refund?: number
  duration_hours?: number
  entry_price?: number
  current_rate?: number
  blockchain_ref?: string
}

export interface PaymentConfirmResponse {
  status: string
  already_paid?: boolean
  amount_charged?: number
  transaction_id?: string
}

export interface PrebookSlotResponse {
  prebook_id: string
  status: string
  slot_index: number
  assigned_slot_index?: number
  slot_label?: string
  price_at_booking?: number
  probability?: number
  expires_at?: string
  booking_fee?: number
  deposit?: number
}

export interface PrebookConfirmResponse {
  status: string
  session_id?: string
  message?: string
}

export interface PrebookCancelResponse {
  status: string
  refund_amount?: number
  message?: string
}

driverApi.interceptors.response.use(
  (res) => res,
  (err: AxiosError) => {
    if (err.response?.status === 401) {
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
  status?: string
  amount_charged?: number
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

export async function fetchDriverLots(params?: { max_price?: number; slot_type?: string }): Promise<DriverLot[]> {
  const res = await driverApi.get('/driver/lots', { params })
  return res.data.lots
}

export async function fetchLotDetail(lotId: string): Promise<DriverLotDetail> {
  const res = await driverApi.get(`/driver/lots/${lotId}`)
  return res.data
}

export async function startSession(lotId: string, slot: number, payment_method = 'card'): Promise<SessionStartResponse> {
  const res = await driverApi.post('/sessions/start', { lot_id: lotId, slot, payment_method })
  return res.data
}

export async function endSession(sessionId: string): Promise<SessionEndResponse> {
  const res = await driverApi.post('/sessions/end', { session_id: sessionId })
  return res.data
}

export async function fetchActiveSession(): Promise<ActiveSessionItem | null> {
  try {
    const res = await driverApi.get('/sessions/active')
    const s = res.data
    return {
      session_id: s.session_id,
      slot: s.slot,
      start_time: s.start_time,
      entry_price: s.entry_price,
      status: s.status,
      amount_charged: s.amount_charged,
    }
  } catch (err) {
    // 404 means no active session — return null (UI shows empty state)
    // 500 means server error — still return null, but log so we can diagnose
    if (err instanceof AxiosError && err.response?.status === 404) {
      return null
    }
    console.error('Failed to check active session:', err)
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

export async function confirmPayment(sessionId: string, method = 'card'): Promise<PaymentConfirmResponse> {
  // Idempotency key is the session_id alone — deterministic.
  // If the first POST succeeds but the response is lost, the retry with the same
  // key lets the backend return already_paid=True instead of charging again.
  const res = await driverApi.post('/payments/confirm', { session_id: sessionId, payment_method: method, idempotency_key: sessionId })
  return res.data
}

export interface PrebookItem {
  prebook_id: string
  lot_id: string
  lot_name: string
  driver_id: string
  slot_index: number
  slot_label: string
  target_time: string
  expires_at: string
  probability_given: number | null
  price_at_booking: number | null
  status: string
  booking_fee: number | null
  deposit: number | null
  deposit_refunded: boolean
  created_at: string
}

export async function fetchPrebooks(): Promise<PrebookItem[]> {
  const res = await driverApi.get('/micro/prebooks/list')
  return res.data.prebooks
}

export async function prebookSlot(lotId: string, slot: number, targetTime: string): Promise<PrebookSlotResponse> {
  const res = await driverApi.post('/micro/prebook', {
    lot_id: lotId,
    slots: [{ slot_index: slot }],
    target_time: targetTime,
  })
  return res.data
}

export async function confirmPrebook(prebookId: string): Promise<PrebookConfirmResponse> {
  const res = await driverApi.post('/micro/confirm', { prebook_id: prebookId })
  return res.data
}

export async function cancelPrebook(prebookId: string): Promise<PrebookCancelResponse> {
  const res = await driverApi.post('/micro/cancel', { prebook_id: prebookId })
  return res.data
}


export interface TopupResponse {
  balance: number
  amount_added: number
  message: string
}

export interface WalletTransaction {
  tx_hash: string
  action: string
  amount: number
  status: string
  lot_id?: string
  timestamp: string
  session_id?: string
}

export async function topupWallet(amount: number): Promise<TopupResponse> {
  const res = await driverApi.post('/wallet/topup', { amount })
  return res.data
}

export async function fetchWalletTransactions(): Promise<WalletTransaction[]> {
  const res = await driverApi.get('/wallet/transactions')
  return res.data
}

