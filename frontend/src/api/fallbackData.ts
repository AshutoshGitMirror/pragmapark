import type {
  Lot, OccupancyRecord, BlockChainStatus, DashboardData,
  MicroSlot, PricingLot, Scenario, ScenarioResult, HealthCheck,
} from './types'

const FIXED_TS = '2026-06-01T12:00:00.000Z'

export const fallbackHealth: HealthCheck = {
  status: 'healthy',
  service: 'pragma',
  version: '2.0.0',
  layers: 6,
  dependencies: { database: true, blockchain: true },
}

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

const BASE_TS = new Date(FIXED_TS).getTime()

function occHour(h: number): { rate: number; occupied: number; price: number; flux: number } {
  const rates: Record<string, number> = {
    '0': 0.175, '1': 0.180, '2': 0.165, '3': 0.170, '4': 0.185, '5': 0.190,
    '6': 0.400, '7': 0.420,
    '8': 0.840, '9': 0.860, '10': 0.820,
    '11': 0.700, '12': 0.690, '13': 0.680,
    '14': 0.580, '15': 0.590, '16': 0.600,
    '17': 0.870, '18': 0.880, '19': 0.850,
    '20': 0.350, '21': 0.340, '22': 0.330, '23': 0.320,
  }
  const rate = rates[String(h)] ?? 0.5
  const occupied = Math.round(rate * 500)
  const price = Math.round(15.0 * (1 + (rate - 0.5) * 0.5) * 100) / 100
  const flux = Math.round((Math.sin(h * Math.PI / 6) * 3) * 100) / 100
  return { rate, occupied, price, flux }
}

export const fallbackOccupancy: OccupancyRecord[] = Array.from({ length: 24 }, (_, h) => {
  const o = occHour(h)
  return {
    lot_id: 'A1',
    occupied_slots: o.occupied,
    total_slots: 500,
    occupancy_rate: o.rate,
    net_flux: o.flux,
    price: o.price,
    timestamp: new Date(BASE_TS - (24 - h) * 3600 * 1000).toISOString(),
  }
})

export const fallbackDashboard: DashboardData = {
  total_lots: 21,
  total_users: 1847,
  total_revenue: 2847500,
  total_transactions: 45200,
}

export const fallbackBlockchain: BlockChainStatus = {
  chain_length: 142,
  pending_transactions: 4,
  chain_valid: true,
  last_block_hash: '00ba9f7c2242b6ca329209c36f5f71d549eb349c6c26add22c2e6f3ff3395fa1',
}

export const fallbackPricingLots: PricingLot[] = [
  { lot_id: 'A1-North', base_price: 15.0, price_range: [6.0, 50.0], currency: 'USD', dynamic_pricing: true },
  { lot_id: 'A1-South', base_price: 15.0, price_range: [6.0, 50.0], currency: 'USD', dynamic_pricing: true },
  { lot_id: 'A1-East', base_price: 12.0, price_range: [5.0, 40.0], currency: 'USD', dynamic_pricing: true },
  { lot_id: 'L1-Central', base_price: 25.0, price_range: [10.0, 75.0], currency: 'USD', dynamic_pricing: true },
  { lot_id: 'L1-West', base_price: 25.0, price_range: [10.0, 75.0], currency: 'USD', dynamic_pricing: true },
  { lot_id: 'NY1-TimesSq', base_price: 35.0, price_range: [15.0, 100.0], currency: 'USD', dynamic_pricing: true },
  { lot_id: 'NY1-Midtown', base_price: 30.0, price_range: [12.0, 90.0], currency: 'USD', dynamic_pricing: true },
  { lot_id: 'SF1-FiDi', base_price: 28.0, price_range: [12.0, 85.0], currency: 'USD', dynamic_pricing: true },
  { lot_id: 'TK1-Shibuya', base_price: 30.0, price_range: [30.0, 80.0], currency: 'JPY', dynamic_pricing: true },
  { lot_id: 'DB1-Mall', base_price: 40.0, price_range: [20.0, 100.0], currency: 'USD', dynamic_pricing: true },
]

const _slotTypes = ['regular', 'regular', 'regular', 'regular', 'covered', 'premium', 'handicap', 'ev']
export const fallbackMicroSlots: MicroSlot[] = Array.from({ length: 40 }, (_, i) => {
  const type = _slotTypes[i % _slotTypes.length]
  const stateIdx = i % 3
  const state = stateIdx === 0 ? 'available' : stateIdx === 1 ? 'occupied' : 'reserved'
  return {
    id: i + 1,
    lot_id: 'A1',
    slot_index: i + 1,
    row_label: String.fromCharCode(65 + Math.floor(i / 10)),
    position: (i % 10) + 1,
    slot_type: type,
    base_modifier_score: Math.round((i % 5) / 10 * 100) / 100,
    state,
    probability: Math.round((0.3 + (i % 7) / 10) * 1000) / 1000,
  }
})
