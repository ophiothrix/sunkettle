/* Solar Hot Water — PWA Application */

const API = '/api';
let token = localStorage.getItem('solar_token');
let eventSource = null;
let historyChart = null;

// ── Helpers ──

function headers() {
  return { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` };
}

async function api(method, path, body) {
  const opts = { method, headers: headers() };
  if (body) opts.body = JSON.stringify(body);
  const res = await fetch(`${API}${path}`, opts);
  if (res.status === 401) { logout(); throw new Error('Unauthorized'); }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'Request failed');
  }
  return res.json();
}

// ── Auth ──

function showApp() {
  document.getElementById('login-screen').classList.remove('active');
  document.getElementById('app').classList.remove('hidden');
  startSSE();
  loadAlerts();
  setInterval(loadAlerts, 60000);
}

function logout() {
  token = null;
  localStorage.removeItem('solar_token');
  stopSSE();
  document.getElementById('app').classList.add('hidden');
  document.getElementById('login-screen').classList.add('active');
}

document.getElementById('login-btn').addEventListener('click', async () => {
  const pw = document.getElementById('password-input').value;
  const errEl = document.getElementById('login-error');
  errEl.classList.add('hidden');
  try {
    const data = await fetch(`${API}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password: pw }),
    }).then(r => {
      if (!r.ok) throw new Error('Invalid password');
      return r.json();
    });
    token = data.token;
    localStorage.setItem('solar_token', token);
    showApp();
  } catch (e) {
    errEl.textContent = e.message;
    errEl.classList.remove('hidden');
  }
});

document.getElementById('password-input').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') document.getElementById('login-btn').click();
});

// ── SSE (Real-time temperatures) ──

function startSSE() {
  stopSSE();
  eventSource = new EventSource(`${API}/temperatures/stream?token=${token}`);
  eventSource.onmessage = (e) => {
    const data = JSON.parse(e.data);
    updateDashboard(data);
  };
  eventSource.onerror = () => {
    // Reconnect after 5s on error
    stopSSE();
    setTimeout(startSSE, 5000);
  };
}

function stopSSE() {
  if (eventSource) { eventSource.close(); eventSource = null; }
}

function updateDashboard(data) {
  const temps = data.temperatures || {};
  setText('temp-panel', formatTemp(temps.panel));
  setText('temp-inflow', formatTemp(temps.inflow));
  setText('temp-outflow', formatTemp(temps.outflow));

  updateRelayStatus('pump', data.pump_on);
  updateRelayStatus('boiler', data.boiler_on);

  // Mode
  const isManual = data.mode === 'manual';
  document.getElementById('mode-auto').classList.toggle('active', !isManual);
  document.getElementById('mode-manual').classList.toggle('active', isManual);
  document.getElementById('pump-btn').disabled = !isManual;
  document.getElementById('boiler-btn').disabled = !isManual;

  const timeoutEl = document.getElementById('manual-timeout');
  if (isManual && data.manual_timeout_remaining != null) {
    const mins = Math.ceil(data.manual_timeout_remaining / 60);
    timeoutEl.textContent = `Auto in ${mins}m`;
    timeoutEl.classList.remove('hidden');
  } else {
    timeoutEl.classList.add('hidden');
  }
}

function formatTemp(v) {
  return v != null ? v.toFixed(1) : '--';
}

function setText(id, text) {
  document.getElementById(id).textContent = text;
}

function updateRelayStatus(name, on) {
  const el = document.getElementById(`${name}-status`);
  el.textContent = on ? 'ON' : 'OFF';
  el.classList.toggle('on', on);
}

// ── Controls ──

function applyRelayState(state) {
  updateRelayStatus('pump', state.pump_on);
  updateRelayStatus('boiler', state.boiler_on);
}

document.getElementById('pump-btn').addEventListener('click', async () => {
  const current = document.getElementById('pump-status').textContent === 'ON';
  try { applyRelayState(await api('POST', '/controls/pump', { on: !current })); } catch (e) { alert(e.message); }
});

document.getElementById('boiler-btn').addEventListener('click', async () => {
  const current = document.getElementById('boiler-status').textContent === 'ON';
  try { applyRelayState(await api('POST', '/controls/boiler', { on: !current })); } catch (e) { alert(e.message); }
});

document.getElementById('mode-auto').addEventListener('click', () => setMode('auto'));
document.getElementById('mode-manual').addEventListener('click', () => setMode('manual'));

async function setMode(mode) {
  try {
    const data = await api('POST', '/controls/mode', { mode });
    document.getElementById('mode-auto').classList.toggle('active', data.mode === 'auto');
    document.getElementById('mode-manual').classList.toggle('active', data.mode === 'manual');
    document.getElementById('pump-btn').disabled = data.mode !== 'manual';
    document.getElementById('boiler-btn').disabled = data.mode !== 'manual';
  } catch (e) { alert(e.message); }
}

// ── Alerts ──

async function loadAlerts() {
  try {
    const alerts = await api('GET', '/alerts');
    const banner = document.getElementById('alerts-banner');
    if (alerts.length === 0) {
      banner.classList.add('hidden');
      return;
    }
    banner.classList.remove('hidden');
    banner.innerHTML = alerts.map(a => `
      <div class="alert-item">
        <span>${a.message}</span>
        <button class="alert-dismiss" onclick="dismissAlert(${a.id})">&times;</button>
      </div>
    `).join('');
  } catch (_) {}
}

async function dismissAlert(id) {
  try { await api('POST', `/alerts/${id}/dismiss`); loadAlerts(); } catch (_) {}
}
// Make dismissAlert available globally for onclick handler
window.dismissAlert = dismissAlert;

// ── History ──

document.getElementById('history-date').valueAsDate = new Date();

document.getElementById('history-load').addEventListener('click', loadHistory);

async function loadHistory() {
  const date = document.getElementById('history-date').value;
  if (!date) return;

  try {
    const data = await api('GET', `/temperatures/${date}`);
    renderChart(data.readings);
  } catch (e) {
    alert(e.message);
  }
}

function renderChart(readings) {
  const ctx = document.getElementById('history-chart').getContext('2d');

  if (historyChart) historyChart.destroy();

  const labels = readings.map(r => r.time.split(' ')[1] || r.time);
  const panelData = readings.map(r => r.panel);
  const inflowData = readings.map(r => r.inflow);
  const outflowData = readings.map(r => r.outflow);

  historyChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [
        {
          label: 'Panel',
          data: panelData,
          borderColor: '#ff6b35',
          backgroundColor: 'rgba(255,107,53,0.1)',
          borderWidth: 1.5,
          pointRadius: 0,
          tension: 0.3,
        },
        {
          label: 'Inflow',
          data: inflowData,
          borderColor: '#4ecdc4',
          backgroundColor: 'rgba(78,205,196,0.1)',
          borderWidth: 1.5,
          pointRadius: 0,
          tension: 0.3,
        },
        {
          label: 'Outflow',
          data: outflowData,
          borderColor: '#45b7d1',
          backgroundColor: 'rgba(69,183,209,0.1)',
          borderWidth: 1.5,
          pointRadius: 0,
          tension: 0.3,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { intersect: false, mode: 'index' },
      plugins: {
        legend: { labels: { color: '#eee', boxWidth: 12 } },
        tooltip: {
          callbacks: {
            label: (ctx) => `${ctx.dataset.label}: ${ctx.parsed.y.toFixed(1)}°C`,
          },
        },
      },
      scales: {
        x: {
          ticks: {
            color: '#999',
            maxTicksLimit: 12,
            maxRotation: 0,
          },
          grid: { color: 'rgba(255,255,255,0.05)' },
        },
        y: {
          ticks: {
            color: '#999',
            callback: (v) => v + '°C',
          },
          grid: { color: 'rgba(255,255,255,0.05)' },
        },
      },
    },
  });
}

// ── Sensor Settings ──

const SENSOR_ROLES = ['panel', 'inflow', 'outflow'];

async function loadSensorConfig() {
  try {
    const config = await api('GET', '/sensors');
    const available = config.available;
    const assignments = config.assignments;
    const offsets = config.offsets;

    for (const role of SENSOR_ROLES) {
      const select = document.getElementById(`sensor-${role}`);
      select.innerHTML = '';

      // Add all available sensors as options
      for (const id of available) {
        const opt = document.createElement('option');
        opt.value = id;
        opt.textContent = id;
        if (id === assignments[role]) opt.selected = true;
        select.appendChild(opt);
      }

      // If current assignment isn't in available list (sensor disconnected), show it anyway
      if (assignments[role] && !available.includes(assignments[role])) {
        const opt = document.createElement('option');
        opt.value = assignments[role];
        opt.textContent = assignments[role] + ' (not detected)';
        opt.selected = true;
        select.appendChild(opt);
      }

      // Offsets
      document.getElementById(`offset-${role}`).value = offsets[role] || 0;
    }
  } catch (_) {}
}

document.getElementById('save-sensors').addEventListener('click', async () => {
  try {
    // Save assignments
    const assignments = {};
    for (const role of SENSOR_ROLES) {
      assignments[role] = document.getElementById(`sensor-${role}`).value;
    }
    await api('PUT', '/sensors/assignments', assignments);

    // Save offsets
    const offsets = {};
    for (const role of SENSOR_ROLES) {
      offsets[role] = parseFloat(document.getElementById(`offset-${role}`).value) || 0;
    }
    await api('PUT', '/sensors/offsets', offsets);

    alert('Sensor config saved');
  } catch (e) { alert(e.message); }
});

// ── Settings ──

async function loadSchedule() {
  try {
    const sched = await api('GET', '/schedule');
    document.getElementById('sched-solar-start').value = sched.solar_start;
    document.getElementById('sched-solar-end').value = sched.solar_end;
    document.getElementById('sched-boiler-start').value = sched.boiler_start;
    document.getElementById('sched-boiler-end').value = sched.boiler_end;
  } catch (_) {}
}

// ── Alert Settings ──

const ALERT_TYPES = ['sensor_failure', 'overtemp', 'pump_runtime', 'no_temp_rise'];

async function loadAlertSettings() {
  try {
    const settings = await api('GET', '/alerts/settings');
    for (const type of ALERT_TYPES) {
      document.getElementById(`alert-${type}`).checked = settings[type];
    }
  } catch (_) {}
}

document.getElementById('save-alerts').addEventListener('click', async () => {
  const body = {};
  for (const type of ALERT_TYPES) {
    body[type] = document.getElementById(`alert-${type}`).checked;
  }
  try {
    await api('PUT', '/alerts/settings', body);
    alert('Alert settings saved');
  } catch (e) { alert(e.message); }
});

document.getElementById('save-schedule').addEventListener('click', async () => {
  try {
    await api('PUT', '/schedule', {
      solar_start: parseInt(document.getElementById('sched-solar-start').value),
      solar_end: parseInt(document.getElementById('sched-solar-end').value),
      boiler_start: parseInt(document.getElementById('sched-boiler-start').value),
      boiler_end: parseInt(document.getElementById('sched-boiler-end').value),
    });
    alert('Schedule saved');
  } catch (e) { alert(e.message); }
});

async function loadSystemInfo() {
  try {
    const info = await api('GET', '/system');
    document.getElementById('system-info').innerHTML = `
      <strong>CPU Temperature:</strong> ${info.cpu_temp != null ? info.cpu_temp.toFixed(1) + '°C' : 'N/A'}<br>
      <strong>Pi Uptime:</strong> ${info.uptime_human}<br>
      <strong>Controller Uptime:</strong> ${formatDuration(info.controller_uptime)}<br>
      <strong>Last Sensor Read:</strong> ${info.last_sensor_read ? new Date(info.last_sensor_read).toLocaleTimeString() : 'Never'}<br>
      <strong>Mode:</strong> ${info.mode}<br>
      <strong>Mock Hardware:</strong> ${info.mock_hardware ? 'Yes' : 'No'}<br>
      <strong>Sensor Failures:</strong> Panel: ${info.sensor_failures.panel}, Inflow: ${info.sensor_failures.inflow}, Outflow: ${info.sensor_failures.outflow}
    `;
  } catch (_) {}
}

function formatDuration(seconds) {
  if (seconds == null) return 'unknown';
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return h > 0 ? `${h}h ${m}m` : `${m}m`;
}

document.getElementById('change-pw-btn').addEventListener('click', async () => {
  const msgEl = document.getElementById('pw-message');
  try {
    await api('POST', '/auth/change-password', {
      current_password: document.getElementById('current-pw').value,
      new_password: document.getElementById('new-pw').value,
    });
    msgEl.textContent = 'Password changed successfully';
    msgEl.className = '';
    msgEl.style.color = 'var(--on-color)';
    document.getElementById('current-pw').value = '';
    document.getElementById('new-pw').value = '';
  } catch (e) {
    msgEl.textContent = e.message;
    msgEl.className = 'error';
    msgEl.style.color = '';
  }
  msgEl.classList.remove('hidden');
});

document.getElementById('logout-btn').addEventListener('click', logout);

// ── Navigation ──

document.querySelectorAll('.nav-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const tab = btn.dataset.tab;

    document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');

    document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
    document.getElementById(`tab-${tab}`).classList.add('active');

    // Load data when switching to tabs
    if (tab === 'settings') { loadSensorConfig(); loadSchedule(); loadAlertSettings(); loadSystemInfo(); }
  });
});

// ── Service Worker ──

if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('/sw.js');
}

// ── Init ──

if (token) {
  // Verify existing token
  fetch(`${API}/temperatures/current`, { headers: headers() })
    .then(r => { if (r.ok) showApp(); else logout(); })
    .catch(() => logout());
} else {
  document.getElementById('login-screen').classList.add('active');
}
