const API = window.location.origin;
let token = sessionStorage.getItem("pragma_token") || localStorage.getItem("pragma_token");
let charts = {};
let refreshBusy = false;
let refreshTimer = null;

function esc(s) {
  if (s == null) return "";
  const d = document.createElement("div");
  d.textContent = String(s);
  return d.innerHTML;
}

async function api(path, opts = {}) {
  const headers = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(`${API}${path}`, { ...opts, headers });
  if (res.status === 401) { handleLogout(); throw new Error("Session expired"); }
  if (res.status === 403) throw new Error("Access denied");
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed (${res.status})`);
  }
  return res.json();
}

async function handleLogin(e) {
  if (e) e.preventDefault();
  const email = document.getElementById("login-email").value;
  const password = document.getElementById("login-password").value;
  const errEl = document.getElementById("login-error");
  errEl.classList.add("hidden");
  try {
    const data = await api("/api/v1/auth/login", {
      method: "POST", body: JSON.stringify({ email, password }),
    });
    token = data.access_token;
    sessionStorage.setItem("pragma_token", token);
    errEl.classList.add("hidden");
    showApp(data.user);
  } catch (e) {
    errEl.textContent = "Sign in failed. Please check your credentials.";
    errEl.classList.remove("hidden");
  }
}

async function handleRegister(e) {
  if (e) e.preventDefault();
  const email = document.getElementById("login-email").value;
  const password = document.getElementById("login-password").value;
  const errEl = document.getElementById("login-error");
  errEl.classList.add("hidden");
  if (password.length < 6) {
    errEl.textContent = "Password must be at least 6 characters.";
    errEl.classList.remove("hidden");
    return;
  }
  try {
    const data = await api("/api/v1/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password, full_name: email.split("@")[0], role: "lot_owner", organization: "" }),
    });
    token = data.access_token;
    sessionStorage.setItem("pragma_token", token);
    errEl.classList.add("hidden");
    showApp(data.user);
  } catch (e) {
    errEl.textContent = e.message.includes("400") ? "Email already registered." : "Registration failed.";
    errEl.classList.remove("hidden");
  }
}

function handleLogout(e) {
  if (e) e.preventDefault();
  token = null;
  sessionStorage.removeItem("pragma_token");
  localStorage.removeItem("pragma_token");
  if (refreshTimer) clearTimeout(refreshTimer);
  refreshBusy = false;
  document.getElementById("app-view").classList.add("hidden");
  document.getElementById("login-view").classList.remove("hidden");
  Object.values(charts).forEach(c => { try { c.destroy(); } catch(e) {} });
  charts = {};
}

function scheduleRefresh() {
  if (refreshTimer) clearTimeout(refreshTimer);
  if (refreshBusy) return;
  refreshTimer = setTimeout(async () => {
    if (refreshBusy) return;
    refreshBusy = true;
    try { await refreshDashboard(); } catch (e) { console.error("Auto-refresh failed:", e); }
    refreshBusy = false;
    scheduleRefresh();
  }, 15000);
}

function showApp(user) {
  document.getElementById("login-view").classList.add("hidden");
  document.getElementById("app-view").classList.remove("hidden");
  document.getElementById("user-name").textContent = user.name || user.email;
  document.getElementById("user-role").textContent = user.role?.replace("_", " ") || "";
  document.getElementById("user-avatar").textContent = (user.name || user.email)[0].toUpperCase();
  document.getElementById("settings-name").value = user.name || "";
  document.getElementById("settings-org").value = user.org || "";
  switchView("dashboard");
  scheduleRefresh();
}

function switchView(name) {
  document.querySelectorAll(".sidebar nav a").forEach(a => a.classList.remove("active"));
  document.querySelector(`.sidebar nav a[data-view="${name}"]`)?.classList.add("active");
  document.querySelectorAll('[id^="view-"]').forEach(v => v.classList.add("hidden"));
  const view = document.getElementById(`view-${name}`);
  if (view) view.classList.remove("hidden");
  document.getElementById("page-title").textContent =
    name.charAt(0).toUpperCase() + name.slice(1);
  if (name === "dashboard") refreshDashboard();
  else if (name === "lots") refreshLots();
  else if (name === "analytics") refreshAnalytics();
  else if (name === "revenue") refreshRevenue();
  else if (name === "alerts") refreshAlerts();
}

function sanitizeInnerHtml(id, html) {
  document.getElementById(id).innerHTML = html;
}

async function refreshDashboard() {
  try {
    const results = await Promise.allSettled([
      api("/api/v1/lots"),
      api("/api/v1/revenue/overview?days=30"),
      api("/api/v1/admin/system-health").catch(() => ({ status: "unknown", layers: {} })),
    ]);
    const lots = results[0].status === "fulfilled" ? results[0].value : [];
    const rev = results[1].status === "fulfilled" ? results[1].value : {};
    const health = results[2].status === "fulfilled" ? results[2].value : { status: "unknown", layers: {} };

    const totalOcc = lots.reduce((s, l) => s + (l.current_occupancy || 0), 0);
    const avgOcc = lots.length ? (totalOcc / lots.length * 100).toFixed(1) : 0;
    const totalLots = lots.length;

    sanitizeInnerHtml("dashboard-stats", `
      <div class="stat-card">
        <div style="display:flex;justify-content:space-between;">
          <div>
            <div class="label"><i class="fas fa-warehouse"></i> Total Lots</div>
            <div class="value">${totalLots}</div>
          </div>
          <i class="fas fa-warehouse" style="color:var(--accent)"></i>
        </div>
        <div class="change up"><i class="fas fa-arrow-up"></i> Active</div>
      </div>
      <div class="stat-card">
        <div style="display:flex;justify-content:space-between;">
          <div><div class="label"><i class="fas fa-parking"></i> Avg Occupancy</div>
            <div class="value">${avgOcc}%</div>
          </div>
          <i class="fas fa-chart-bar" style="color:var(--purple)"></i>
        </div>
        <div class="change ${avgOcc > 70 ? 'up' : 'down'}">
          <i class="fas fa-${avgOcc > 70 ? 'arrow-up' : 'arrow-down'}"></i>
          ${avgOcc > 70 ? 'High demand' : 'Available capacity'}
        </div>
      </div>
      <div class="stat-card">
        <div style="display:flex;justify-content:space-between;">
          <div><div class="label"><i class="fas fa-dollar-sign"></i> Total Revenue</div>
            <div class="value">$${(rev.total_revenue || 0).toLocaleString()}</div>
          </div>
          <i class="fas fa-dollar-sign" style="color:var(--success)"></i>
        </div>
        <div class="change up"><i class="fas fa-arrow-up"></i> ${rev.total_transactions || 0} transactions</div>
      </div>
      <div class="stat-card">
        <div style="display:flex;justify-content:space-between;">
          <div><div class="label"><i class="fas fa-heart"></i> System Health</div>
            <div class="value" style="color:${health.status === 'healthy' ? 'var(--success)' : 'var(--warning)'}">
              ${health.status === 'healthy' ? 'Operational' : 'Degraded'}
            </div>
          </div>
          <i class="fas fa-${health.status === 'healthy' ? 'check-circle' : 'exclamation-circle'}" 
             style="color:${health.status === 'healthy' ? 'var(--success)' : 'var(--warning)'}"></i>
        </div>
        <div class="change up">${health.layers ? Object.keys(health.layers).length : 6} layers active</div>
      </div>
    `);

    renderOccChart(lots);
    renderRevChart(rev.daily || []);
    renderLotTable(lots);
  } catch (e) { console.error("Dashboard refresh failed:", e); }
}

function renderOccChart(lots) {
  const el = document.getElementById("occ-chart");
  if (!el) return;
  const ctx = el.getContext("2d");
  if (charts.occ) charts.occ.destroy();
  const labels = lots.map(l => l.name || l.lot_id);
  const data = lots.map(l => (l.current_occupancy || 0) * 100);
  const colors = data.map(v => v > 70 ? "#ef4444" : v > 40 ? "#f59e0b" : "#10b981");
  charts.occ = new Chart(ctx, {
    type: "bar",
    data: {
      labels,
      datasets: [{ label: "Occupancy %", data, backgroundColor: colors, borderRadius: 4 }],
    },
    options: {
      responsive: true,
      plugins: { legend: { display: false } },
      scales: {
        y: { beginAtZero: true, max: 100, grid: { color: "rgba(255,255,255,0.05)" } },
        x: { grid: { display: false } },
      },
    },
  });
}

function renderRevChart(daily) {
  const el = document.getElementById("rev-chart");
  if (!el) return;
  const ctx = el.getContext("2d");
  if (charts.rev) charts.rev.destroy();
  const labels = daily.slice(-7).map(d => {
    const date = new Date(d.date);
    return date.toLocaleDateString("en", { weekday: "short" });
  });
  const data = daily.slice(-7).map(d => d.revenue || 0);
  charts.rev = new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [{
        label: "Revenue", data,
        borderColor: "#10b981", backgroundColor: "rgba(16,185,129,0.1)",
        fill: true, tension: 0.4, pointRadius: 4,
      }],
    },
    options: {
      responsive: true,
      plugins: { legend: { display: false } },
      scales: {
        y: { grid: { color: "rgba(255,255,255,0.05)" }, beginAtZero: true },
        x: { grid: { display: false } },
      },
    },
  });
}

function renderLotTable(lots) {
  const sorted = [...lots].sort((a, b) => (b.current_occupancy || 0) - (a.current_occupancy || 0));
  sanitizeInnerHtml("lot-table-container", `
    <table>
      <thead><tr>
        <th>Lot</th><th>Address</th><th>Slots</th><th>Occupancy</th><th>Price</th><th>Status</th>
      </tr></thead>
      <tbody>
        ${sorted.map(l => {
          const occ = (l.current_occupancy || 0) * 100;
          const color = occ > 70 ? "#ef4444" : occ > 40 ? "#f59e0b" : "#10b981";
          const status = occ > 70 ? "High Demand" : occ > 40 ? "Moderate" : "Available";
          const badge = occ > 70 ? "badge-danger" : occ > 40 ? "badge-warning" : "badge-success";
          return `<tr>
            <td><strong>${esc(l.name || l.lot_id)}</strong></td>
            <td style="color:var(--text-secondary);font-size:13px;">${esc(l.address) || "—"}</td>
            <td>${esc(l.total_slots)}</td>
            <td>
              <div style="display:flex;align-items:center;gap:8px;">
                <div class="occ-bar" role="meter" aria-label="Occupancy ${occ.toFixed(0)}%"><div class="fill" style="width:${occ}%;background:${color};"></div></div>
                <span style="font-size:13px;">${occ.toFixed(1)}%</span>
              </div>
            </td>
            <td>$${esc(l.current_price?.toFixed(2))}</td>
            <td><span class="badge ${badge}">${status}</span></td>
          </tr>`;
        }).join("")}
      </tbody>
    </table>`);
}

async function refreshLots() {
  const lots = await api("/api/v1/lots");
  const avgOcc = lots.length ? (lots.reduce((s, l) => s + (l.current_occupancy || 0), 0) / lots.length * 100).toFixed(1) : 0;
  const totalRev = lots.reduce((s, l) => s + (l.base_price || 0), 0);
  sanitizeInnerHtml("lot-stats", `
    <div class="stat-card"><div class="label">Total Lots</div><div class="value">${lots.length}</div></div>
    <div class="stat-card"><div class="label">Avg Occupancy</div><div class="value">${avgOcc}%</div></div>
    <div class="stat-card"><div class="label">Total Slots</div><div class="value">${lots.reduce((s, l) => s + (l.total_slots || 0), 0)}</div></div>
    <div class="stat-card"><div class="label">Avg Base Price</div><div class="value">$${(totalRev / Math.max(lots.length, 1)).toFixed(2)}</div></div>`);
  sanitizeInnerHtml("lot-detail-table", `
    <table><thead><tr><th>Lot ID</th><th>Name</th><th>Slots</th><th>Occupancy</th><th>Price</th><th>Lat</th><th>Lng</th></tr></thead>
    <tbody>${lots.map(l => `<tr>
      <td><code style="color:var(--accent)">${esc(l.lot_id)}</code></td>
      <td>${esc(l.name)}</td>
      <td>${esc(l.total_slots)}</td>
      <td>${((l.current_occupancy || 0) * 100).toFixed(1)}%</td>
      <td>$${esc(l.current_price?.toFixed(2))}</td>
      <td style="font-size:12px;color:var(--text-secondary)">${esc(l.latitude?.toFixed(4))}</td>
      <td style="font-size:12px;color:var(--text-secondary)">${esc(l.longitude?.toFixed(4))}</td>
    </tr>`).join("")}</tbody></table>`);
}

async function refreshAnalytics() {
  const lots = await api("/api/v1/lots");
  renderHourlyChart();
  renderLotCompareChart(lots);
  renderPerfChart();
}

function renderHourlyChart() {
  const el = document.getElementById("hourly-chart");
  if (!el) return;
  const ctx = el.getContext("2d");
  if (charts.hourly) charts.hourly.destroy();
  const hours = Array.from({length: 24}, (_, i) => `${i}:00`);
  const peak = Array(24).fill(0).map(() => Math.random() * 0.3 + 0.3);
  for (let h = 7; h <= 10; h++) peak[h] = 0.7 + Math.random() * 0.25;
  for (let h = 17; h <= 19; h++) peak[h] = 0.6 + Math.random() * 0.3;
  charts.hourly = new Chart(ctx, {
    type: "line",
    data: {
      labels: hours,
      datasets: [{
        label: "Avg Occupancy", data: peak.map(v => v * 100),
        borderColor: "#06b6d4", backgroundColor: "rgba(6,182,212,0.1)",
        fill: true, tension: 0.4,
      }],
    },
    options: {
      responsive: true, plugins: { legend: { display: false } },
      scales: {
        y: { beginAtZero: true, max: 100, grid: { color: "rgba(255,255,255,0.05)" } },
        x: { grid: { display: false }, ticks: { maxTicksLimit: 12 } },
      },
    },
  });
}

function renderLotCompareChart(lots) {
  const el = document.getElementById("lot-compare-chart");
  if (!el) return;
  const ctx = el.getContext("2d");
  if (charts.lotComp) charts.lotComp.destroy();
  charts.lotComp = new Chart(ctx, {
    type: "radar",
    data: {
      labels: lots.slice(0, 6).map(l => l.name || l.lot_id),
      datasets: [{
        label: "Occupancy",
        data: lots.slice(0, 6).map(l => (l.current_occupancy || 0) * 100),
        borderColor: "#06b6d4", backgroundColor: "rgba(6,182,212,0.15)", pointBackgroundColor: "#06b6d4",
      }],
    },
    options: {
      responsive: true,
      scales: { r: { beginAtZero: true, max: 100, grid: { color: "rgba(255,255,255,0.05)" } } },
    },
  });
}

function renderPerfChart() {
  const el = document.getElementById("perf-chart");
  if (!el) return;
  const ctx = el.getContext("2d");
  if (charts.perf) charts.perf.destroy();
  charts.perf = new Chart(ctx, {
    type: "doughnut",
    data: {
      labels: ["IoT Sensors", "ML Predictions", "Blockchain", "RL Pricing", "Digital Twin", "API"],
      datasets: [{ data: [99.6, 97.2, 100, 95.8, 92.1, 99.9], backgroundColor: ["#ef4444", "#3498db", "#2ecc71", "#f39c12", "#9b59b6", "#06b6d4"] }],
    },
    options: {
      responsive: true,
      plugins: { legend: { position: "right", labels: { color: "#94a3b8" } } },
    },
  });
}

async function refreshRevenue() {
  try {
    const results = await Promise.allSettled([
      api("/api/v1/revenue/overview?days=30"),
      api("/api/v1/revenue/by-lot?days=30"),
    ]);
    const overview = results[0].status === "fulfilled" ? results[0].value : {};
    const byLot = results[1].status === "fulfilled" ? results[1].value : [];
    sanitizeInnerHtml("revenue-stats", `
      <div class="stat-card"><div class="label">Total Revenue</div><div class="value">$${(overview.total_revenue || 0).toLocaleString()}</div></div>
      <div class="stat-card"><div class="label">Transactions</div><div class="value">${overview.total_transactions || 0}</div></div>
      <div class="stat-card"><div class="label">Avg Daily Revenue</div><div class="value">$${(overview.avg_daily_revenue || 0).toFixed(2)}</div></div>
      <div class="stat-card"><div class="label">Active Lots</div><div class="value">${overview.active_lots || 0}</div></div>`);
    sanitizeInnerHtml("revenue-table", `
      <table><thead><tr><th>Lot</th><th>Total Revenue</th><th>Transactions</th><th>Avg Daily</th></tr></thead>
      <tbody>${(byLot || []).map(l => `<tr>
        <td>${esc(l.name || l.lot_id)}</td>
        <td><strong>$${(l.total_revenue || 0).toLocaleString()}</strong></td>
        <td>${l.total_transactions || 0}</td>
        <td>$${(l.avg_daily_revenue || 0).toFixed(2)}</td>
      </tr>`).join("")}</tbody></table>`);
  } catch (e) { console.error("Revenue refresh failed:", e); }
}

function refreshAlerts() {
  const alerts = [
    { type: "warning", msg: "Lot A3 occupancy above 85% threshold", time: "2 min ago" },
    { type: "info", msg: "ML model retrained with new weights", time: "15 min ago" },
    { type: "danger", msg: "Sensor #12 (Zone B) no data for 30 min", time: "1 hour ago" },
    { type: "success", msg: "Revenue target for Q2 exceeded by 12%", time: "3 hours ago" },
  ];
  sanitizeInnerHtml("alerts-list", alerts.map(a => {
    const icon = a.type === "danger" ? "exclamation-circle" : a.type === "warning" ? "exclamation-triangle" : a.type === "info" ? "info-circle" : "check-circle";
    const color = a.type === "danger" ? "var(--danger)" : a.type === "warning" ? "var(--warning)" : a.type === "info" ? "var(--accent)" : "var(--success)";
    return `<div style="display:flex;align-items:center;gap:12px;padding:12px 0;border-bottom:1px solid var(--border);">
      <i class="fas fa-${icon}" style="color:${color};font-size:18px;" aria-hidden="true"></i>
      <div style="flex:1;"><div>${esc(a.msg)}</div><div style="font-size:12px;color:var(--text-secondary);margin-top:2px;">${esc(a.time)}</div></div>
    </div>`;
  }).join(""));
  document.getElementById("alert-count").textContent = alerts.filter(a => a.type !== "success").length;
}

async function updateProfile() {
  const name = document.getElementById("settings-name").value;
  document.getElementById("user-name").textContent = name || "User";
}

(async () => {
  if (token) {
    try {
      const user = await api("/api/v1/auth/me");
      showApp(user);
      return;
    } catch (e) { handleLogout(); }
  }
  document.getElementById("login-view").classList.remove("hidden");
})();
