/// <reference types="vite/client" />

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
  owner_id?: string
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

export interface BlockChainStatus {
  chain_length: number
  pending_transactions: number
  chain_valid: boolean
  last_block_hash: string
}

export interface DashboardData {
  total_lots: number
  total_users: number
  total_revenue: number
  total_transactions: number
  system_occupancy?: number
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

export interface PricingLot {
  lot_id: string
  base_price: number
  price_range: number[]
  currency: string
  dynamic_pricing: boolean
}

export interface Scenario {
  name: string
  description: string
  occupancy_shift: number
  price_adjust: number
  icon?: string
}

export interface ScenarioImpactItem {
  scenario: string
  description: string
  impacts: Record<string, number>
  result: Record<string, unknown>
}

export interface ScenarioComparisonItem {
  scenario: string
  occupancy_delta: string
  price_delta: string
  congestion: string
}

export interface ScenarioRunResponse {
  base_state: Record<string, unknown>
  results: ScenarioImpactItem[]
  comparisons: ScenarioComparisonItem[]
}

export interface BlockData {
  index: number
  timestamp: number
  transactions: Record<string, unknown>[]
  previous_hash: string
  nonce: number
  hash: string
}

export interface BlockListResponse {
  blocks: BlockData[]
  total: number
}

export interface ScenarioResult {
  scenario: string
  predicted_revenue_impact: number
  predicted_occupancy_change: number
  simulation_time_ms: number
}

export interface HealthCheck {
  status: string
  service: string
  version: string
  layers: number
  dependencies: {
    database: boolean
    blockchain: boolean
  }
}

export interface TransactionResponse {
  tx_hash: string
  block_index: number
  status: string
}

export interface MineBlockResponse {
  block_index: number
  hash: string
  transactions: number
  nonce: number
  timestamp: number
}

export interface PredictionItem {
  timestamp: string
  predicted_occupancy_rate: number
  actual_occupancy_rate?: number
}

export interface PricingHistoryItem {
  day: string
  hour: number
  multiplier: number
}




