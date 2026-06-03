export interface User {
  id: number; email: string; full_name: string; role: string; organization: string;
}

export interface AuthResponse {
  access_token: string; token_type: string; user: User;
}

export interface DashboardStats {
  total_lots: number; total_slots: number; active_sessions: number;
  total_revenue: number; total_users: number; avg_occupancy: number;
  revenue_today: number; pending_alerts: number;
}

export interface Lot {
  id: number; lot_id: string; name: string; address: string; city: string;
  total_slots: number; base_price: number; dynamic_price: number;
  available_spots: number; predicted_occupancy: number; latitude: number; longitude: number;
}

export interface LotDetail extends Lot {
  recent_occupancy: OccupancyRecord[];
  config: Record<string, any>;
}

export interface OccupancyRecord {
  timestamp: string; occupancy_rate: number; available: number;
}

export interface RevenueData {
  total_revenue: number; total_transactions: number; avg_daily: number;
  active_lots: number; lots: RevenueLot[];
}

export interface RevenueLot {
  lot_id: string; name: string; revenue: number; transactions: number; avg_daily: number;
}

export interface Alert {
  id: number; lot_id: string; lot_name: string; message: string; title?: string;
  severity: string; created_at: string; timestamp?: string; acknowledged: boolean;
  description?: string; detail?: string;
}

export type WeekDay = 'monday'|'tuesday'|'wednesday'|'thursday'|'friday'|'saturday'|'sunday'

export interface MicroSlot {
  id: number; lot_id: number; slot_index: number; row_label: string;
  position: number; state: string; slot_type: string; probability: number;
  base_price: number; current_price: number;
  day_of_week?: string; start_time?: string; end_time?: string; is_reserved?: boolean;
}

export interface SlotGridData {
  lot_id?: string;
  slots: MicroSlot[]; total_slots?: number; available?: number;
  reserved?: number; prebooked?: number; occupied?: number;
}

export interface SystemHealth {
  database: string; cache: string; ml_models: string;
  blockchain: string; last_check: string;
}

export interface SimulationStatus {
  speedup: number; is_fast_forwarding: boolean; real_time: string;
  snapshot_exists: boolean;
}

export interface HealthCheck {
  status: string; service: string; version: string;
  models: { rf: boolean; xgb: boolean; meta: boolean };
  blockchain: { chain_length: number; valid: boolean };
}
