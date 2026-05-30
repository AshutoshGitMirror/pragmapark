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
  valid: boolean
  last_block_hash: string
  total_blocks: number
}

export interface BlockPool {
  pool_id: string
  total_spots: number
  available_spots: number
  total_revenue: number
}

export interface DashboardData {
  total_lots: number
  total_users: number
  total_revenue: number
  total_transactions: number
  total_sessions: number
  total_drivers: number
}

export interface SystemHealth {
  database: boolean
  blockchain: boolean
  models_loaded: boolean
  ready: boolean
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
  adjusted_price?: number
}

export interface PricingZone {
  zone_id: string
  base_price: number
  current_multiplier: number
  occupancy: number
  city: string
}

export interface Scenario {
  name: string
  description: string
  occupancy_shift: number
  price_adjust: number
  icon?: string
}

export interface ScenarioResult {
  scenario: string
  predicted_revenue_impact: number
  predicted_occupancy_change: number
  simulation_time_ms: number
}

export interface MarlStatus {
  training: boolean
  episodes: number
  avg_reward: number
  last_trained: string
}

export interface SessionStart {
  session_id: string
  lot_id: string
  driver_id: string
  slot: number
  start_time: string
  entry_price: number
  status: string
  layers: {
    iot: any
    ml: any
    blockchain: any
    rl: any
    digital_twin: any
    actuator: any
  }
  blockchain_ref: string
}

export interface PaymentConfirm {
  tx_hash: string
  amount: number
  status: string
  timestamp: string
  blockchain_ref: string
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

export interface ApiResponse<T> {
  data: T
  source: 'live' | 'cache' | 'warming'
  latency_ms?: number
}
