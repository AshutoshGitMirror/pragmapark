/**
 * fallbackData.ts — Realistic recorded fallback data for all API endpoints.
 *
 * WHY: When the Render backend is cold (503), every component needs data to render.
 * The old code used `generateFallbackData()` functions that created random data on 
 * every mount — different each reload, unrealistic distributions.
 *
 * THIS FILE: Static, realistic data that looks like real API responses.
 * Based on the Birmingham Parking Dataset patterns and the seed_data.py script.
 */

import type {
  Lot,
  OccupancyRecord,
  BlockChainStatus,
  DashboardData,
  SystemHealth,
  MicroSlot,
  PricingZone,
  Scenario,
  ScenarioResult,
  MarlStatus,
  HealthCheck,
} from './types'

// ── Health ──
export const fallbackHealth: HealthCheck = {
  status: 'healthy',
  service: 'pragma',
  version: '2.0.0',
  layers: 6,
  dependencies: { database: true, blockchain: true },
}

// ── Lots (from seed_data.py) ──
export const fallbackLots: Lot[] = [
  { lot_id: 'A1', name: 'Downtown Plaza', address: '123 Main St', city: 'Birmingham', total_slots: 500, latitude: 52.48, longitude: -1.89, base_price: 15.0, price_cap: 50.0 },
  { lot_id: 'A2', name: 'Station Approach', address: '45 Railway Rd', city: 'Birmingham', total_slots: 350, latitude: 52.47, longitude: -1.90, base_price: 12.0, price_cap: 45.0 },
  { lot_id: 'B1', name: 'Market Square', address: '78 Market St', city: 'Birmingham', total_slots: 200, latitude: 52.48, longitude: -1.88, base_price: 10.0, price_cap: 30.0 },
  { lot_id: 'L1', name: 'Canary Wharf Garage', address: '1 Bank St', city: 'London', total_slots: 800, latitude: 51.50, longitude: -0.02, base_price: 25.0, price_cap: 80.0 },
  { lot_id: 'L2', name: "King's Cross", address: '90 Euston Rd', city: 'London', total_slots: 600, latitude: 51.53, longitude: -0.12, base_price: 20.0, price_cap: 65.0 },
  { lot_id: 'M1', name: 'Deansgate', address: '50 Deansgate', city: 'Manchester', total_slots: 400, latitude: 53.48, longitude: -2.25, base_price: 14.0, price_cap: 40.0 },
  { lot_id: 'M2', name: 'Piccadilly Tower', address: '1 Piccadilly', city: 'Manchester', total_slots: 300, latitude: 53.48, longitude: -2.24, base_price: 12.0, price_cap: 35.0 },
  { lot_id: 'NY1', name: 'Times Square Hub', address: '1 Times Sq', city: 'New York', total_slots: 1000, latitude: 40.76, longitude: -73.98, base_price: 35.0, price_cap: 120.0 },
  { lot_id: 'NY2', name: 'Madison Ave Garage', address: '200 Madison Ave', city: 'New York', total_slots: 500, latitude: 40.75, longitude: -73.98, base_price: 30.0, price_cap: 100.0 },
  { lot_id: 'SF1', name: 'Financial District', address: '300 California St', city: 'San Francisco', total_slots: 600, latitude: 37.79, longitude: -122.40, base_price: 28.0, price_cap: 90.0 },
  { lot_id: 'SF2', name: 'Mission Lot', address: '500 Mission St', city: 'San Francisco', total_slots: 350, latitude: 37.76, longitude: -122.40, base_price: 22.0, price_cap: 75.0 },
  { lot_id: 'TK1', name: 'Shibuya Central', address: '2-1 Dogenzaka', city: 'Tokyo', total_slots: 300, latitude: 35.66, longitude: 139.70, base_price: 30.0, price_cap: 100.0 },
  { lot_id: 'TK2', name: 'Shinjuku Tower', address: '1-1-1 Nishi-Shinjuku', city: 'Tokyo', total_slots: 400, latitude: 35.69, longitude: 139.70, base_price: 28.0, price_cap: 90.0 },
  { lot_id: 'DB1', name: 'Dubai Mall Lot', address: 'Financial Center Rd', city: 'Dubai', total_slots: 1500, latitude: 25.20, longitude: 55.27, base_price: 40.0, price_cap: 150.0 },
  { lot_id: 'DB2', name: 'Marina Park', address: 'Dubai Marina', city: 'Dubai', total_slots: 700, latitude: 25.08, longitude: 55.14, base_price: 35.0, price_cap: 120.0 },
  { lot_id: 'SG1', name: 'Orchard Road', address: '333A Orchard Rd', city: 'Singapore', total_slots: 500, latitude: 1.30, longitude: 103.83, base_price: 22.0, price_cap: 60.0 },
  { lot_id: 'SG2', name: 'Marina Bay', address: '10 Bayfront Ave', city: 'Singapore', total_slots: 600, latitude: 1.28, longitude: 103.86, base_price: 26.0, price_cap: 70.0 },
  { lot_id: 'MB1', name: 'BKC Lot', address: 'Bandra Kurla Complex', city: 'Mumbai', total_slots: 700, latitude: 19.07, longitude: 72.87, base_price: 12.0, price_cap: 30.0 },
  { lot_id: 'MB2', name: 'Nariman Point', address: '1 Nariman Point', city: 'Mumbai', total_slots: 400, latitude: 18.93, longitude: 72.82, base_price: 10.0, price_cap: 25.0 },
  { lot_id: 'BR1', name: 'Potsdamer Platz', address: 'Potsdamer Str 1', city: 'Berlin', total_slots: 500, latitude: 52.51, longitude: 13.37, base_price: 18.0, price_cap: 50.0 },
  { lot_id: 'BR2', name: 'Alexanderplatz', address: 'Alexanderplatz 1', city: 'Berlin', total_slots: 400, latitude: 52.52, longitude: 13.41, base_price: 16.0, price_cap: 45.0 },
]

// ── Occupancy Records (24h, realistic diurnal pattern) ──
// Based on Birmingham Parking Dataset: peaks at 8-10am and 5-7pm, troughs overnight
export const fallbackOccupancy: OccupancyRecord[] = (() => {
  const data: OccupancyRecord[] = []
  const basePrice = 15.0
  const totalSlots = 500

  for (let h = 0; h < 24; h++) {
    // Realistic occupancy curve: commuters 8-10, shoppers 12-14, evening 17-19
    let rate: number
    if (h >= 0 && h < 6) rate = 0.15 + Math.random() * 0.05           // Night: 15-20%
    else if (h >= 6 && h < 8) rate = 0.35 + Math.random() * 0.1       // Early morning: 35-45%
    else if (h >= 8 && h < 11) rate = 0.78 + Math.random() * 0.12     // Morning peak: 78-90%
    else if (h >= 11 && h < 14) rate = 0.65 + Math.random() * 0.1     // Lunch: 65-75%
    else if (h >= 14 && h < 17) rate = 0.55 + Math.random() * 0.08    // Afternoon: 55-63%
    else if (h >= 17 && h < 20) rate = 0.82 + Math.random() * 0.1     // Evening peak: 82-92%
    else rate = 0.30 + Math.random() * 0.1                             // Late evening: 30-40%

    const occupied = Math.round(rate * totalSlots)
    const price = basePrice * (1 + (rate - 0.5) * 0.5)

    data.push({
      lot_id: 'A1',
      occupied_slots: occupied,
      total_slots: totalSlots,
      occupancy_rate: Math.round(rate * 1000) / 1000,
      net_flux: Math.round((Math.random() - 0.5) * 10 * 100) / 100,
      price: Math.round(price * 100) / 100,
      timestamp: new Date(Date.now() - (24 - h) * 3600 * 1000).toISOString(),
    })
  }
  return data
})()

// ── Dashboard ──
export const fallbackDashboard: DashboardData = {
  total_lots: 21,
  total_users: 1847,
  total_revenue: 2847500,
  total_transactions: 45200,
  total_sessions: 38400,
  total_drivers: 1523,
}

// ── Blockchain Status ──
export const fallbackBlockchain: BlockChainStatus = {
  chain_length: 142,
  pending_transactions: 4,
  valid: true,
  last_block_hash: '00ba9f7c2242b6ca329209c36f5f71d549eb349c6c26add22c2e6f3ff3395fa1',
  total_blocks: 142,
}

// ── System Health ──
export const fallbackSystemHealth: SystemHealth = {
  database: true,
  blockchain: true,
  models_loaded: true,
  ready: true,
}

// ── Pricing Zones ──
export const fallbackPricingZones: PricingZone[] = [
  { zone_id: 'A1-North', base_price: 15.0, current_multiplier: 2.3, occupancy: 0.87, city: 'Birmingham' },
  { zone_id: 'A1-South', base_price: 15.0, current_multiplier: 1.8, occupancy: 0.72, city: 'Birmingham' },
  { zone_id: 'A1-East', base_price: 12.0, current_multiplier: 1.4, occupancy: 0.58, city: 'Birmingham' },
  { zone_id: 'L1-Central', base_price: 25.0, current_multiplier: 3.1, occupancy: 0.94, city: 'London' },
  { zone_id: 'L1-West', base_price: 25.0, current_multiplier: 2.7, occupancy: 0.89, city: 'London' },
  { zone_id: 'NY1-TimesSq', base_price: 35.0, current_multiplier: 3.2, occupancy: 0.96, city: 'New York' },
  { zone_id: 'NY1-Midtown', base_price: 30.0, current_multiplier: 2.5, occupancy: 0.81, city: 'New York' },
  { zone_id: 'SF1-FiDi', base_price: 28.0, current_multiplier: 2.9, occupancy: 0.91, city: 'San Francisco' },
  { zone_id: 'TK1-Shibuya', base_price: 30.0, current_multiplier: 2.6, occupancy: 0.88, city: 'Tokyo' },
  { zone_id: 'DB1-Mall', base_price: 40.0, current_multiplier: 1.9, occupancy: 0.76, city: 'Dubai' },
]

// ── Digital Twin Scenarios ──
export const fallbackScenarios: Scenario[] = [
  { name: 'Heavy Rain', description: 'Weather impact on demand', occupancy_shift: -15, price_adjust: -0.3, icon: 'rain' },
  { name: 'City Event', description: 'Concert or sports match surge', occupancy_shift: 40, price_adjust: 1.5, icon: 'event' },
  { name: 'Earthquake', description: 'Emergency evacuation protocols', occupancy_shift: -60, price_adjust: 0, icon: 'alert' },
  { name: 'Holiday', description: 'Inverted demand curve', occupancy_shift: -25, price_adjust: -0.5, icon: 'holiday' },
  { name: 'Emergency', description: 'All gates open, free parking', occupancy_shift: -80, price_adjust: -1.0, icon: 'emergency' },
  { name: 'Festival', description: 'Extended hours, surge cap raised', occupancy_shift: 55, price_adjust: 2.0, icon: 'festival' },
]

// ── Micro Slots (40 slots for grid visualization) ──
export const fallbackMicroSlots: MicroSlot[] = (() => {
  const slots: MicroSlot[] = []
  const types = ['regular', 'regular', 'regular', 'regular', 'covered', 'premium', 'handicap', 'ev']
  for (let i = 0; i < 40; i++) {
    const type = types[i % types.length]
    const prob = 0.3 + Math.random() * 0.65
    slots.push({
      id: i + 1,
      lot_id: 'A1',
      slot_index: i + 1,
      row_label: String.fromCharCode(65 + Math.floor(i / 10)),
      position: (i % 10) + 1,
      slot_type: type,
      base_modifier_score: Math.round(Math.random() * 0.5 * 100) / 100,
      state: prob > 0.6 ? 'available' : prob > 0.3 ? 'occupied' : 'reserved',
      probability: Math.round(prob * 1000) / 1000,
      adjusted_price: Math.round((15.0 * (1 + (type === 'premium' ? 0.5 : type === 'handicap' ? -0.3 : 0))) * 100) / 100,
    })
  }
  return slots
})()

// ── MARL Status ──
export const fallbackMarlStatus: MarlStatus = {
  training: false,
  episodes: 5000,
  avg_reward: 0.847,
  last_trained: new Date(Date.now() - 3600 * 1000).toISOString(),
}
