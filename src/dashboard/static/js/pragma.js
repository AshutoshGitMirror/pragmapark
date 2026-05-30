const API = window.location.origin;
let token = sessionStorage.getItem("pragma_token") || localStorage.getItem("pragma_token");
let charts = {};
let refreshBusy = false;
let refreshTimer = null;

function esc(s) {
  if (s == null) return "";
  const d = document.createElement("div");
  d.textContent = String(s);
  return d.innerHTML.replace(/'/g, "&#39;").replace(/"/g, "&quot;");
}

function attrEsc(s) {
  if (s == null) return "";
  return String(s).replace(/\\/g, "\\\\").replace(/"/g, "\\x22").replace(/'/g, "\\x27").replace(/</g, "\\x3C").replace(/>/g, "\\x3E").replace(/\n/g, "\\n").replace(/\r/g, "\\r");
}

async function api(path, opts = {}) {
  const headers = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 60000);
  opts.signal = controller.signal;
  try {
    const res = await fetch(`${API}${path}`, { ...opts, headers });
    clearTimeout(timer);
    if (res.status === 401) { handleLogout(); throw new Error("Session expired"); }
    if (res.status === 403) throw new Error("Access denied");
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || `Request failed (${res.status})`);
    }
    return res.json();
  } catch(e) {
    clearTimeout(timer);
    if (e.name === "AbortError") throw new Error("Request timed out");
    throw e;
  }
}

async function handleLogin(e) {
  if (e) e.preventDefault();
  const btn = document.getElementById("login-submit-btn");
  btn.disabled = true;
  btn.innerHTML = '<i class="fas fa-circle-notch fa-spin" aria-hidden="true"></i> Signing in...';
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
    errEl.textContent = e.message || "Sign in failed. Please check your credentials.";
    errEl.classList.remove("hidden");
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<i class="fas fa-right-to-bracket" aria-hidden="true"></i> Sign In';
  }
}

async function handleRegister(e) {
  if (e) e.preventDefault();
  const btn = document.getElementById("register-btn");
  btn.disabled = true;
  btn.innerHTML = '<i class="fas fa-circle-notch fa-spin" aria-hidden="true"></i> Creating...';
  const email = document.getElementById("login-email").value;
  const password = document.getElementById("login-password").value;
  const errEl = document.getElementById("login-error");
  errEl.classList.add("hidden");
  if (password.length < 6) {
    errEl.textContent = "Password must be at least 6 characters.";
    errEl.classList.remove("hidden");
    btn.disabled = false;
    btn.innerHTML = "Create Account";
    return;
  }
  try {
    const data = await api("/api/v1/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password, full_name: email.split("@")[0], organization: "" }),
    });
    token = data.access_token;
    sessionStorage.setItem("pragma_token", token);
    errEl.classList.add("hidden");
    showApp(data.user);
  } catch (e) {
    errEl.textContent = "Registration failed. " + (e.message.includes("already registered") ? "This email is already registered." : "Please try again.");
    errEl.classList.remove("hidden");
  } finally {
    btn.disabled = false;
    btn.innerHTML = "Create Account";
  }
}

function handleLogout(e) {
  if (e) e.preventDefault();
  token = null;
  currentUser = null;
  sessionStorage.removeItem("pragma_token");
  localStorage.removeItem("pragma_token");
  sessionStorage.removeItem("pragma_driver_token");
  sessionStorage.removeItem("pragma_driver_id");
  if (refreshTimer) { clearTimeout(refreshTimer); refreshTimer = null; }
  refreshBusy = false;
  if (mapInstance) { mapInstance.remove(); mapInstance = null; }
  mapMarkers = [];
  document.getElementById("app-view").classList.add("hidden");
  document.getElementById("login-view").classList.remove("hidden");
  Object.values(charts).forEach(c => { try { c.destroy(); } catch(e) { console.warn("Chart destroy:", e); } });
  charts = {};
}

function scheduleRefresh() {
  if (refreshTimer) clearTimeout(refreshTimer);
  if (refreshBusy || !currentUser) return;
  refreshTimer = setTimeout(async () => {
    if (refreshBusy || !currentUser) return;
    refreshBusy = true;
    try { await refreshDashboard(); } catch (e) { console.error("Auto-refresh failed:", e); }
    refreshBusy = false;
    if (currentUser) scheduleRefresh();
  }, 15000);
}

let currentUser = null;

function lotsUrl() {
  return currentUser?.role === "lot_owner" ? "/api/v1/lots/owner" : "/api/v1/lots";
}

function showApp(user, fromAutoLogin) {
  if (user.role === 'driver') {
    sessionStorage.setItem("pragma_driver_token", token);
    sessionStorage.setItem("pragma_driver_id", String(user.id));
    if (!fromAutoLogin) {
      window.location.href = "/app/driver";
      return;
    }
    document.getElementById("login-view").classList.remove("hidden");
    return;
  }
  currentUser = user;
  document.getElementById("login-view").classList.add("hidden");
  document.getElementById("app-view").classList.remove("hidden");
  document.getElementById("user-name").textContent = user.full_name || user.email;
  document.getElementById("user-role").textContent = user.role?.replace("_", " ") || "";
  document.getElementById("user-avatar").textContent = (user.full_name || user.email)[0].toUpperCase();
  document.getElementById("settings-name").value = user.full_name || "";
  document.getElementById("settings-org").value = user.organization || "";
  const myLotsNav = document.getElementById("nav-my-lots");
  if (myLotsNav) myLotsNav.classList.toggle("hidden", user.role !== "lot_owner" && user.role !== "admin");
  const revenueNav = document.getElementById("nav-revenue");
  if (revenueNav) revenueNav.classList.toggle("hidden", user.role !== "admin" && user.role !== "city_planner");
  switchView("dashboard");
  requestAnimationFrame(() => document.getElementById("main-content").focus());
  refreshAlerts();
  scheduleRefresh();
}

function switchView(name) {
  document.querySelectorAll(".view-section").forEach(el => el.classList.add("hidden"));
  const target = document.getElementById(`view-${name}`);
  if (target) target.classList.remove("hidden");
  document.getElementById("page-title").textContent =
      name.split("-").map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(" ");
  document.querySelectorAll(".sidebar nav a[data-view]").forEach(el => el.classList.remove("active"));
  const navLink = document.querySelector(`.sidebar nav a[data-view="${name}"]`);
  if (navLink) navLink.classList.add("active");
  if (name === "dashboard") refreshDashboard().catch(e => console.error("Dashboard refresh:", e));
  else if (name === "lots") refreshLots().catch(e => console.error("Lots refresh:", e));
  else if (name === "analytics") refreshAnalytics().catch(e => console.error("Analytics refresh:", e));
  else if (name === "revenue") refreshRevenue().catch(e => console.error("Revenue refresh:", e));
  else if (name === "map") refreshMap().catch(e => console.error("Map refresh:", e));
  else if (name === "my-lots") refreshOwnerLots().catch(e => console.error("My lots refresh:", e));
  else if (name === "alerts") refreshAlerts();
  document.getElementById("sidebar").classList.remove("mobile-open");
  document.getElementById("mobile-overlay").classList.add("hidden");
  const content = document.getElementById("main-content");
  if (content) content.setAttribute("tabindex", "-1"), content.focus();
}

function setInnerHtml(id, html) {
  document.getElementById(id).innerHTML = html;
}

function showEmptyState(id, icon, title, desc) {
  setInnerHtml(id, '<div style="text-align:center;padding:40px 16px;color:var(--text-secondary);animation:fadeUp 0.4s ease;">' +
    '<i class="fas fa-' + icon + '" style="font-size:32px;margin-bottom:12px;display:block;" aria-hidden="true"></i>' +
    '<p style="margin-bottom:4px;font-size:15px;color:var(--text-primary);">' + esc(title) + '</p>' +
    '<p style="font-size:13px;">' + esc(desc) + '</p></div>');
}

function showErrorState(id, icon, title, desc, retryFn) {
  var retryHtml = retryFn ? '<div style="margin-top:16px;"><button class="btn btn-outline btn-sm" id="retry-' + id + '"><i class="fas fa-redo" aria-hidden="true"></i> Retry</button></div>' : '';
  setInnerHtml(id, '<div style="text-align:center;padding:40px 16px;animation:fadeUp 0.4s ease;">' +
    '<i class="fas fa-' + icon + '" style="font-size:32px;margin-bottom:12px;display:block;color:var(--danger);" aria-hidden="true"></i>' +
    '<p style="margin-bottom:4px;font-size:15px;color:var(--text-primary);">' + esc(title) + '</p>' +
    '<p style="font-size:13px;color:var(--text-secondary);">' + esc(desc) + '</p>' + retryHtml + '</div>');
  if (retryFn) {
    var btn = document.getElementById('retry-' + id);
    if (btn) btn.addEventListener('click', function() { retryFn(); return false; });
  }
}

async function refreshDashboard() {
  try {
    setInnerHtml("dashboard-stats", '<div class="loading" style="text-align:center;padding:40px;color:var(--text-secondary);grid-column:1/-1;"><i class="fas fa-circle-notch fa-spin" aria-hidden="true"></i><br>Loading dashboard...</div>');
    setInnerHtml("lot-table-container", "");

    const calls = [api(lotsUrl())];
    if (currentUser?.role === "admin" || currentUser?.role === "city_planner")
      calls.push(api("/api/v1/revenue/overview?days=30"), api("/api/v1/admin/system-health").catch(() => ({ status: "unknown", layers: {} })));
    const results = await Promise.allSettled(calls);
    const lots = results[0].status === "fulfilled" ? results[0].value : [];
    const rev = results[1]?.status === "fulfilled" ? results[1].value : {};
    const health = results[2]?.status === "fulfilled" ? results[2].value : { status: "unknown", layers: {} };

    if (!lots || lots.length === 0) {
      showEmptyState("dashboard-stats", "warehouse", "No parking lots", "No lots are configured yet. Add a lot to get started.");
      renderOccChart([]);
      renderRevChart([]);
      setInnerHtml("lot-table-container", "");
      return;
    }

    const totalOcc = lots.reduce((s, l) => s + (l.current_occupancy || 0), 0);
    const avgOcc = lots.length ? (totalOcc / lots.length * 100).toFixed(1) : 0;
    const totalLots = lots.length;

    setInnerHtml("dashboard-stats", `
      <div class="stat-card">
        <div style="display:flex;justify-content:space-between;">
          <div>
            <div class="label"><i class="fas fa-warehouse" aria-hidden="true"></i> Total Lots</div>
            <div class="value">${totalLots}</div>
          </div>
          <i class="fas fa-warehouse" style="color:var(--accent)" aria-hidden="true"></i>
        </div>
        <div class="change up"><i class="fas fa-arrow-up" aria-hidden="true"></i> Active</div>
      </div>
      <div class="stat-card">
        <div style="display:flex;justify-content:space-between;">
          <div><div class="label"><i class="fas fa-parking" aria-hidden="true"></i> Avg Occupancy</div>
            <div class="value">${avgOcc}%</div>
          </div>
          <i class="fas fa-chart-bar" style="color:var(--purple)" aria-hidden="true"></i>
        </div>
        <div class="change ${avgOcc > 70 ? 'up' : 'down'}">
          <i class="fas fa-${avgOcc > 70 ? 'arrow-up' : 'arrow-down'}" aria-hidden="true"></i>
          ${avgOcc > 70 ? 'High demand' : 'Available capacity'}
        </div>
      </div>
      <div class="stat-card">
        <div style="display:flex;justify-content:space-between;">
          <div><div class="label"><i class="fas fa-dollar-sign" aria-hidden="true"></i> Total Revenue</div>
            <div class="value">$${(rev.total_revenue || 0).toLocaleString()}</div>
          </div>
          <i class="fas fa-dollar-sign" style="color:var(--success)" aria-hidden="true"></i>
        </div>
        <div class="change up"><i class="fas fa-arrow-up" aria-hidden="true"></i> ${rev.total_transactions || 0} transactions</div>
      </div>
      <div class="stat-card">
        <div style="display:flex;justify-content:space-between;">
          <div><div class="label"><i class="fas fa-heart" aria-hidden="true"></i> System Health</div>
            <div class="value" style="color:${health.status === 'healthy' ? 'var(--success)' : 'var(--warning)'}">
              ${health.status === 'healthy' ? 'Operational' : 'Degraded'}
            </div>
          </div>
          <i class="fas fa-${health.status === 'healthy' ? 'check-circle' : 'exclamation-circle'}" 
             style="color:${health.status === 'healthy' ? 'var(--success)' : 'var(--warning)'}" aria-hidden="true"></i>
        </div>
        <div class="change up">${health.layers ? Object.keys(health.layers).length : 6} layers active</div>
      </div>
    `);

    renderOccChart(lots);
    renderRevChart(rev.daily || []);
    renderLotTable(lots);
  } catch (e) {
    showErrorState("dashboard-stats", "exclamation-triangle", "Couldn't load dashboard", "Something went wrong. Try again in a moment.", refreshDashboard);
    console.error("Dashboard refresh failed:", e);
  }
}

function renderOccChart(lots) {
  const el = document.getElementById("occ-chart");
  if (!el) return;
  const ctx = el.getContext("2d");
  if (charts.occ) charts.occ.destroy();
  const labels = lots.map(l => l.name || l.lot_id);
  const data = lots.map(l => (l.current_occupancy || 0) * 100);
  const colors = data.map(v => v > 70 ? "#ff4757" : v > 40 ? "#ffc312" : "#2ed573");
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
        borderColor: "#2ed573", backgroundColor: "rgba(46,213,115,0.1)",
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
  setInnerHtml("lot-table-container", `
    <table>
      <thead><tr>
        <th>Lot</th><th>Address</th><th>Slots</th><th>Occupancy</th><th>Price</th><th>Status</th>
      </tr></thead>
      <tbody>
        ${sorted.map(l => {
          const occ = (l.current_occupancy || 0) * 100;
          const color = occ > 70 ? "#ff4757" : occ > 40 ? "#ffc312" : "#2ed573";
          const status = occ > 70 ? "High Demand" : occ > 40 ? "Moderate" : "Available";
          const badge = occ > 70 ? "badge-danger" : occ > 40 ? "badge-warning" : "badge-success";
          return `<tr>
            <td><strong>${esc(l.name || l.lot_id)}</strong></td>
            <td style="color:var(--text-secondary);font-size:13px;">${esc(l.address) || "—"}</td>
            <td>${esc(l.total_slots ?? "—")}</td>
            <td>
              <div style="display:flex;align-items:center;gap:8px;">
                <div class="occ-bar" role="meter" aria-label="Occupancy ${occ.toFixed(0)}%"><div class="fill" style="width:${occ}%;background:${color};"></div></div>
                <span style="font-size:13px;">${occ.toFixed(1)}%</span>
              </div>
            </td>
            <td>$${Number(l.current_price || 0).toFixed(2)}</td>
            <td><span class="badge ${badge}">${status}</span></td>
          </tr>`;
        }).join("")}
      </tbody>
    </table>`);
}

async function refreshLots() {
  try {
    setInnerHtml("lot-stats", '<div class="loading" style="text-align:center;padding:40px;color:var(--text-secondary);grid-column:1/-1;"><i class="fas fa-circle-notch fa-spin" aria-hidden="true"></i><br>Loading lots...</div>');
    setInnerHtml("lot-detail-table", "");
    const lots = await api(lotsUrl());
    if (!lots || lots.length === 0) {
      showEmptyState("lot-stats", "warehouse", "No parking lots", "No lots are available yet.");
      showEmptyState("lot-detail-table", "table", "No data", "Once lots are added, they will appear here.");
      return;
    }
    const avgOcc = lots.length ? (lots.reduce((s, l) => s + (l.current_occupancy || 0), 0) / lots.length * 100).toFixed(1) : 0;
    const totalRev = lots.reduce((s, l) => s + (l.base_price || 0), 0);
    setInnerHtml("lot-stats", `
      <div class="stat-card"><div class="label">Total Lots</div><div class="value">${lots.length}</div></div>
      <div class="stat-card"><div class="label">Avg Occupancy</div><div class="value">${avgOcc}%</div></div>
      <div class="stat-card"><div class="label">Total Slots</div><div class="value">${lots.reduce((s, l) => s + (l.total_slots || 0), 0)}</div></div>
      <div class="stat-card"><div class="label">Avg Base Price</div><div class="value">$${(totalRev / Math.max(lots.length, 1)).toFixed(2)}</div></div>`);
    setInnerHtml("lot-detail-table", `
      <table><thead><tr><th>Lot ID</th><th>Name</th><th>Slots</th><th>Occupancy</th><th>Price</th><th>Lat</th><th>Lng</th></tr></thead>
      <tbody>${lots.map(l => `<tr>
        <td><code style="color:var(--accent)">${esc(l.lot_id)}</code></td>
        <td>${esc(l.name)}</td>
        <td>${esc(l.total_slots)}</td>
        <td>${Number((l.current_occupancy || 0) * 100).toFixed(1)}%</td>
        <td>$${Number(l.current_price || 0).toFixed(2)}</td>
        <td style="font-size:12px;color:var(--text-secondary)">${esc(l.latitude?.toFixed(4))}</td>
        <td style="font-size:12px;color:var(--text-secondary)">${esc(l.longitude?.toFixed(4))}</td>
      </tr>`).join("")}</tbody></table>`);
  } catch (e) {
    showErrorState("lot-stats", "exclamation-triangle", "Couldn't load lots", "Something went wrong. Try again.", refreshLots);
    setInnerHtml("lot-detail-table", "");
    console.error("Lots refresh failed:", e);
  }
}

async function refreshAnalytics() {
  try {
    const lots = await api(lotsUrl());
    renderHourlyChart();
    renderLotCompareChart(lots);
    renderPerfChart();
  } catch (e) {
    console.error("Analytics refresh failed:", e);
    ["hourly-chart", "lot-compare-chart", "perf-chart"].forEach(function(id) {
      var el = document.getElementById(id);
      if (el && el.parentElement) {
        el.style.display = "none";
        if (!el.parentElement.querySelector(".analytics-error")) {
          var err = document.createElement("p");
          err.className = "analytics-error";
          err.style.cssText = "text-align:center;padding:40px;color:var(--danger);font-size:13px;";
          err.innerHTML = '<i class="fas fa-exclamation-triangle" aria-hidden="true"></i> Couldn\'t load analytics. <button class="btn btn-outline btn-sm" onclick="refreshAnalytics()" style="margin-left:8px;"><i class="fas fa-redo" aria-hidden="true"></i> Retry</button>';
          el.parentElement.appendChild(err);
        }
      }
    });
  }
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
        borderColor: "#00d4aa", backgroundColor: "rgba(0,212,170,0.1)",
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
        borderColor: "#00d4aa", backgroundColor: "rgba(0,212,170,0.15)", pointBackgroundColor: "#00d4aa",
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
      datasets: [{ data: [99.6, 97.2, 100, 95.8, 92.1, 99.9], backgroundColor: ["#ff4757", "#00d4aa", "#2ed573", "#ffc312", "#a29bfe", "#f0a500"] }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { position: "right", labels: { color: "#8892a8" } } },
    },
  });
}

async function refreshRevenue() {
  try {
    setInnerHtml("revenue-stats", '<div class="loading" style="text-align:center;padding:40px;color:var(--text-secondary);grid-column:1/-1;"><i class="fas fa-circle-notch fa-spin" aria-hidden="true"></i><br>Loading revenue...</div>');
    setInnerHtml("revenue-table", "");
    const overview = await api("/api/v1/revenue/overview?days=30");
    const lots = Array.isArray(overview?.daily) ? overview.daily : [];
    if (!lots.length) {
      showEmptyState("revenue-stats", "dollar-sign", "No revenue data", "Revenue data will appear once sessions are settled.");
      showEmptyState("revenue-table", "table", "No transactions yet", "Complete parking sessions will show here.");
      return;
    }
    const totalRev = lots.reduce((s, l) => s + (l.total_revenue || 0), 0);
    const totalTx = lots.reduce((s, l) => s + (l.total_transactions || 0), 0);
    const avgDaily = lots.reduce((s, l) => s + (l.avg_daily_revenue || 0), 0);
    setInnerHtml("revenue-stats", `
      <div class="stat-card"><div class="label">Total Revenue</div><div class="value">$${totalRev.toLocaleString()}</div></div>
      <div class="stat-card"><div class="label">Transactions</div><div class="value">${totalTx}</div></div>
      <div class="stat-card"><div class="label">Avg Daily Revenue</div><div class="value">$${avgDaily.toFixed(2)}</div></div>
      <div class="stat-card"><div class="label">Active Lots</div><div class="value">${lots.length}</div></div>`);
    setInnerHtml("revenue-table", `
      <table><thead><tr><th>Lot</th><th>Total Revenue</th><th>Transactions</th><th>Avg Daily</th></tr></thead>
      <tbody>${lots.map(l => `<tr>
        <td>${esc(l.name || l.lot_id)}</td>
        <td><strong>$${(l.total_revenue || 0).toLocaleString()}</strong></td>
        <td>${l.total_transactions || 0}</td>
        <td>$${(l.avg_daily_revenue || 0).toFixed(2)}</td>
      </tr>`).join("")}</tbody></table>`);
  } catch (e) {
    showErrorState("revenue-stats", "exclamation-triangle", "Couldn't load revenue", "Something went wrong. Try again.", refreshRevenue);
    setInnerHtml("revenue-table", "");
    console.error("Revenue refresh failed:", e);
  }
}

let mapInstance = null;
let mapMarkers = [];

const CITY_COLORS = {
  "Birmingham": "#818cf8",
  "London": "#e2b84d",
  "Manchester": "#34d399",
  "New York": "#f87171",
  "San Francisco": "#a78bfa",
  "Tokyo": "#fbbf24",
  "Dubai": "#f472b6",
  "Singapore": "#2dd4bf",
  "Mumbai": "#fb923c",
  "Berlin": "#60a5fa",
};

function cityColor(city) {
  const c = CITY_COLORS[city];
  if (c) return c;
  const keys = Object.keys(CITY_COLORS);
  const i = Math.abs((city || "").length) % keys.length;
  return CITY_COLORS[keys[i]] || "#818cf8";
}

async function refreshMap() {
  try {
    const filterEl = document.getElementById("city-filter");
    const cityFilter = filterEl ? filterEl.value : "";
    const baseUrl = lotsUrl();
    const lots = await api(baseUrl + (cityFilter ? (baseUrl.includes("?") ? "&city=" : "?city=") + encodeURIComponent(cityFilter) : ""));
    const el = document.getElementById("parking-map");
    if (!el) return;
    if (!mapInstance) {
      mapInstance = L.map("parking-map", { zoomControl: true, attributionControl: true });
      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19, attribution: "&copy; <a href='https://openstreetmap.org'>OSM</a>",
      }).addTo(mapInstance);
      setTimeout(() => mapInstance.invalidateSize(), 200);
    }
    mapMarkers.forEach(m => mapInstance.removeLayer(m));
    mapMarkers = [];
    var mapContainer = el.parentElement || el;
    var existingMsg = mapContainer.querySelector(".map-message");
    if (existingMsg) existingMsg.remove();
    if (lots.length === 0) {
      mapInstance.setView([20, 0], 2);
      var msg = document.createElement("p");
      msg.className = "map-message";
      msg.style.cssText = "text-align:center;padding:16px;color:var(--text-secondary);font-size:13px;";
      msg.innerHTML = '<i class="fas fa-map-marked-alt" aria-hidden="true"></i> No lots to show' + (cityFilter ? ' for "' + esc(cityFilter) + '"' : '') + '.';
      el.parentElement.appendChild(msg);
      return;
    }
    const bounds = [];
    lots.forEach(l => {
      const lat = l.latitude, lng = l.longitude;
      if (!lat || !lng) return;
      const occ = (l.current_occupancy || 0) * 100;
      const base = cityColor(l.city);
      const occColor = occ > 70 ? "#f87171" : occ > 40 ? "#fbbf24" : "#34d399";
      const marker = L.circleMarker([lat, lng], {
        radius: 14, fillColor: base, color: "#fff", weight: 2.5, fillOpacity: 0.85,
      }).addTo(mapInstance);
      marker.bindPopup(`
        <div style="font-family:sans-serif;min-width:200px;background:#14141e;border:1px solid rgba(255,255,255,0.08);border-radius:12px;padding:16px;color:#f0eef8;">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
            <strong style="font-size:16px;color:#e2b84d;">${esc(l.name)}</strong>
            <span style="font-size:11px;color:${base};background:${base}18;padding:2px 8px;border-radius:6px;">${esc(l.city || "")}</span>
          </div>
          <div style="font-size:12px;color:#a49fc4;margin-bottom:10px;">${esc(l.address || "")}</div>
          <div style="display:flex;gap:16px;font-size:13px;">
            <div><span style="color:#a49fc4;">Occupancy</span><br><strong style="color:${occColor};">${occ.toFixed(1)}%</strong></div>
            <div><span style="color:#a49fc4;">Price</span><br><strong style="color:#e2b84d;">$${Number(l.current_price || 0).toFixed(2)}</strong></div>
            <div><span style="color:#a49fc4;">Spots</span><br><strong>${l.total_slots || 0}</strong></div>
          </div>
          <div style="margin-top:10px;font-size:11px;color:#a49fc4;">Base $${Number(l.base_price || 0).toFixed(2)}/hr</div>
        </div>
      `, { closeButton: true, maxWidth: 320 });
      mapMarkers.push(marker);
      bounds.push([lat, lng]);
    });
    if (bounds.length === 1) {
      mapInstance.setView(bounds[0], 14);
    } else if (bounds.length > 0) {
      mapInstance.fitBounds(bounds, { padding: [40, 40] });
    }
  } catch (e) {
    var el = document.getElementById("parking-map");
    if (el) {
      var mapContainer = el.parentElement || el;
      var existingMsg = mapContainer.querySelector(".map-message");
      if (existingMsg) existingMsg.remove();
      var msg = document.createElement("p");
      msg.className = "map-message";
      msg.style.cssText = "text-align:center;padding:40px;color:var(--danger);font-size:13px;";
      msg.innerHTML = '<i class="fas fa-exclamation-triangle" aria-hidden="true"></i> Couldn\'t load map. <button class="btn btn-outline btn-sm" onclick="refreshMap()" style="margin-left:8px;"><i class="fas fa-redo" aria-hidden="true"></i> Retry</button>';
      el.parentElement.appendChild(msg);
    }
    console.error("Map refresh failed:", e);
  }
}

document.addEventListener("change", function(e) {
  if (e.target && e.target.id === "city-filter") refreshMap();
});

async function refreshOwnerLots() {
  try {
    const lots = await api("/api/v1/lots/owner");
    const container = document.getElementById("owner-lots-container");
    if (!lots.length) {
      container.innerHTML = '<p style="color:var(--text-secondary);text-align:center;padding:24px;">You don\'t own any parking lots yet.</p>';
      return;
    }
    container.innerHTML = `<div class="stats-grid">${lots.map(l => `
      <div class="stat-card" style="animation:none;">
        <div style="display:flex;justify-content:space-between;align-items:start;">
          <div>
            <div style="font-weight:600;font-size:16px;">${esc(l.name)}</div>
            <div style="font-size:12px;color:var(--text-secondary);margin:2px 0 8px;">${esc(l.city)} &middot; ${l.total_slots} spots</div>
          </div>
          <span style="background:rgba(226,184,77,0.1);color:var(--accent);padding:2px 8px;border-radius:6px;font-size:11px;">${esc(l.lot_id)}</span>
        </div>
        <div style="display:flex;gap:16px;margin-bottom:12px;">
          <div><span style="color:var(--text-secondary);font-size:11px;">Base Price</span><br><strong>$${Number(l.base_price || 0).toFixed(2)}</strong></div>
          <div><span style="color:var(--text-secondary);font-size:11px;">Price Cap</span><br><strong id="cap-${esc(l.lot_id)}">$${Number(l.price_cap || 0).toFixed(2)}</strong></div>
        </div>
        <div style="display:flex;gap:8px;align-items:center;">
          <label style="font-size:12px;color:var(--text-secondary);">Price Cap $</label>
          <input type="number" id="input-cap-${esc(l.lot_id)}" value="${esc(String(l.price_cap ?? ''))}" min="1" max="100000" step="5"
            style="width:90px;padding:6px 8px;background:rgba(255,255,255,0.03);border:1px solid var(--glass-border);border-radius:6px;color:var(--text-primary);font-size:13px;">
          <button class="btn btn-sm btn-outline" data-cap-lot="${esc(l.lot_id)}">Save</button>
        </div>
      </div>
    `).join("")}</div>`;
  } catch(e) {
    document.getElementById("owner-lots-container").innerHTML =
      '<div style="text-align:center;padding:40px;color:var(--danger);font-size:13px;">' +
      '<i class="fas fa-exclamation-triangle" style="font-size:32px;margin-bottom:12px;display:block;" aria-hidden="true"></i>' +
      '<p style="margin-bottom:4px;font-size:15px;color:var(--text-primary);">Couldn\'t load your lots</p>' +
      '<p style="color:var(--text-secondary);margin-bottom:16px;">Something went wrong. Try again.</p>' +
      '<button class="btn btn-outline btn-sm" onclick="refreshOwnerLots()"><i class="fas fa-redo" aria-hidden="true"></i> Retry</button></div>';
    console.error("Owner lots refresh failed:", e);
  }
}

document.addEventListener("click", function(e) {
  var btn = e.target.closest("[data-cap-lot]");
  if (btn) updateLotCap(btn.dataset.capLot);
});

async function updateLotCap(lotId) {
  const input = document.getElementById("input-cap-" + lotId);
  const cap = parseFloat(input.value);
  if (isNaN(cap) || cap < 1) { alert("Price cap must be a number >= 1"); return; }
  try {
    await api("/api/v1/lots/" + lotId + "/config", {
      method: "PUT",
      body: JSON.stringify({ price_cap: cap }),
    });
    document.getElementById("cap-" + lotId).textContent = "$" + cap.toFixed(2);
  } catch(e) {
    alert("Couldn't update price cap. Try again.");
  }
}

function refreshAlerts() {
  const alerts = [
    { type: "warning", msg: "Lot A3 occupancy above 85% threshold", time: "2 min ago" },
    { type: "info", msg: "ML model retrained with new weights", time: "15 min ago" },
    { type: "danger", msg: "Sensor #12 (Zone B) no data for 30 min", time: "1 hour ago" },
    { type: "success", msg: "Revenue target for Q2 exceeded by 12%", time: "3 hours ago" },
  ];
  setInnerHtml("alerts-list", alerts.map(a => {
    const icon = a.type === "danger" ? "exclamation-circle" : a.type === "warning" ? "exclamation-triangle" : a.type === "info" ? "info-circle" : "check-circle";
    const color = a.type === "danger" ? "var(--danger)" : a.type === "warning" ? "var(--warning)" : a.type === "info" ? "var(--accent)" : "var(--success)";
    return `<div style="display:flex;align-items:center;gap:12px;padding:12px 0;border-bottom:1px solid var(--glass-border);">
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
      showApp(user, true);
      return;
    } catch (e) { handleLogout(); }
  }
  document.getElementById("login-view").classList.remove("hidden");
})();
