import axios, { AxiosInstance, InternalAxiosRequestConfig } from 'axios';

const api: AxiosInstance = axios.create({
  baseURL: '/api/v1',
  timeout: 60000,
  headers: { 'Content-Type': 'application/json' },
  withCredentials: true,
});

api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  return config;
});

api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      window.dispatchEvent(new CustomEvent('pragma:unauthorized'));
    }
    return Promise.reject(err);
  },
);

export async function fetchCurrentUser() {
  const res = await api.get('/auth/me');
  return res.data;
}

export async function login(email: string, password: string) {
  const res = await api.post('/auth/login', { email, password });
  return res.data;
}

export async function register(data: { email: string; password: string; full_name?: string; organization?: string }) {
  const res = await api.post('/auth/register', data);
  return res.data;
}

export async function logout() {
  try { await api.post('/auth/logout'); } catch {}
}

export async function fetchDashboard(): Promise<{ stats: Record<string, any>; lots: any[]; alerts: any[] }> {
  const [statsRes, lotsRes, alertsRes] = await Promise.all([
    api.get('/admin/dashboard').catch(() => ({ data: {} })),
    api.get('/lots'),
    api.get('/lots', { params: { alerts: true } }).catch(() => ({ data: [] })),
  ]);
  return {
    stats: statsRes.data,
    lots: lotsRes.data.lots || lotsRes.data,
    alerts: Array.isArray(alertsRes.data) ? alertsRes.data : [],
  };
}

export async function fetchLots(city?: string) {
  const params: Record<string, string> = {};
  if (city) params.city = city;
  const res = await api.get('/lots', { params });
  return res.data.lots || res.data;
}

export async function fetchLotDetail(lotId: string) {
  const res = await api.get(`/driver/lots/${lotId}`);
  return res.data;
}

export async function fetchOccupancy(lotId: string, hours = 24) {
  const res = await api.get(`/lots/${lotId}/occupancy?hours=${hours}`);
  return res.data.records || res.data;
}

export async function fetchRevenue() {
  const res = await api.get('/revenue');
  return res.data;
}

export async function fetchSlotGrid(lotId: string) {
  const res = await api.get(`/micro/lots/${lotId}/slots`);
  return res.data;
}

export async function fetchAlerts() {
  const res = await api.get('/lots', { params: { alerts: true } }).catch(() => ({ data: [] }));
  return Array.isArray(res.data) ? res.data : [];
}

export async function fetchHealth() {
  const res = await api.get('/health', { timeout: 10000 });
  return res.data;
}

export async function fetchSimulationStatus() {
  const res = await api.get('/simulation/status');
  return res.data;
}

export async function setSimulationSpeed(speedup: number) {
  const res = await api.post('/simulation/speed', { speedup });
  return res.data;
}

export async function updateProfile(data: { full_name?: string; organization?: string }) {
  const res = await api.put('/auth/profile', data);
  return res.data;
}

export async function fetchSlotsByLot(lotId: string) {
  const res = await api.get(`/micro/lots/${lotId}/slots`);
  return res.data.slots || res.data;
}

export async function updateLotConfig(lotId: string, data: { base_price?: number; total_slots?: number }) {
  const res = await api.put(`/lots/${lotId}`, data);
  return res.data;
}

export default api;
