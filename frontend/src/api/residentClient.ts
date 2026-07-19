import { api } from './adminClient'

export interface ResidentProfileResponse {
  id: number
  user_id: number
  user_email: string
  lot_id: string | null
  lot_name: string | null
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

export interface ShareListingResponse {
  id: number
  resident_profile_id: number
  resident_name: string
  lot_id: string | null
  lot_name: string | null
  slot_index: number
  price_per_hour: number
  available_from: string | null
  available_until: string | null
  status: string
  max_advance_days: number
  registered_vehicle: string | null
  created_at: string
  updated_at: string
}

export interface ShareListingCreate {
  resident_profile_id?: number
  lot_id?: string
  slot_index?: number
  price_per_hour: number
  available_from?: string
  available_until?: string
  max_advance_days?: number
}

export async function listPermits(): Promise<ResidentProfileResponse[]> {
  const { data } = await api.get('/residential/permits')
  return data
}

export async function listShares(): Promise<ShareListingResponse[]> {
  const { data } = await api.get('/residential/shares')
  return data
}

export async function createShare(body: ShareListingCreate): Promise<ShareListingResponse> {
  const { data } = await api.post('/residential/shares', body)
  return data
}

export async function cancelShare(listingId: number): Promise<{ status: string; listing_id: number }> {
  const { data } = await api.delete(`/residential/shares/${listingId}`)
  return data
}
