/* Chhaya dashboard - live client logic */

const DEVICE_LABELS = {
    sensor_node:   { label: "SensorNode",   icon: "S", color: "#00ffc8" },
    camera_stream: { label: "CameraStream", icon: "C", color: "#4f8bff" },
    smart_switch:  { label: "SmartSwitch",  icon: "W", color: "#ff5dcd" },
    unknown:       { label: "Unknown",      icon: "?", color: "#8693b8" },
};

const PROFILE_DESCRIPTIONS = {
    sensor_node:   "Environmental sensor",
    camera_stream: "Security camera",
    smart_switch:  "Smart switch",
};

// Per-device rolling history (60 seconds) for the chart
const HISTORY = 60;
const series = new Map();   // src_ip -> array of {t, v}
const startTs = Date.now();
let chart = null;
const chartCtx = document.getElementById("traffic-chart").getContext("2d");

const deviceList = document.getElementById("device-list");
const alertList  = document.getElementById("alert-list");
const eventLog  = document.getElementById("event-log");
const sysStatus = document.getElementById("system-status");
const uptimeEl  = document.getElementById("uptime");
const deviceCountEl = document.getElementById("device-count");
const alertCountEl = document.getElementById("alert-count");
const graphLegend = document.getElementById("graph-legend");
const lastUpdateEl = document.getElementById("last-update");

let deviceCount = 0;
let alertCount = 0;

// =================================================================
// Chart
// =================================================================
function initChart() {
    const datasets = [];
    for (const ip of Object.keys(DEVICE_LABELS)) {
        const meta = DEVICE_LABELS[ip];
        series.set(ip, []);
        datasets.push({
            label: meta.label,
            data: [],
            borderColor: meta.color,
            backgroundColor: meta.color + "20",
            borderWidth: 2,
            tension: 0.3,
            pointRadius: 0,
            fill: false,
        });
    }
    return new Chart(chartCtx, {
        type: "line",
        data: { labels: [], datasets },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: { duration: 0 },
            interaction: { mode: "index", intersect: false },
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: "#0a0e1a",
                    borderColor: "#2c3a59",
                    borderWidth: 1,
                    titleColor: "#00ffc8",
                    bodyColor: "#d8e4ff",
                },
            },
            scales: {
                x: {
                    ticks: { color: "#586380", font: { family: "monospace", size: 10 } },
                    grid: { color: "rgba(255,255,255,0.04)" },
                },
                y: {
                    beginAtZero: true,
                    ticks: { color: "#586380", font: { family: "monospace", size: 10 } },
                    grid: { color: "rgba(255,255,255,0.04)" },
                    title: {
                        display: true,
                        text: "packets / min",
                        color: "#8693b8",
                        font: { family: "monospace", size: 11 },
                    },
                },
            },
        },
    });
}

function refreshLegend() {
    graphLegend.innerHTML = "";
    for (const [ip, meta] of Object.entries(DEVICE_LABELS)) {
        const span = document.createElement("span");
        span.innerHTML = `<span class="legend-dot" style="background:${meta.color}"></span>${meta.label}`;
        graphLegend.appendChild(span);
    }
}

function pushChartPoint(ts, ppmByIp) {
    const t = new Date(ts * 1000).toLocaleTimeString("en-GB");
    chart.data.labels.push(t);
    if (chart.data.labels.length > HISTORY) {
        chart.data.labels.shift();
    }
    for (let i = 0; i < chart.data.datasets.length; i++) {
        const ip = Object.keys(DEVICE_LABELS)[i];
        const v = ppmByIp[ip] || 0;
        chart.data.datasets[i].data.push(v);
        if (chart.data.datasets[i].data.length > HISTORY) {
            chart.data.datasets[i].data.shift();
        }
    }
    chart.update("none");
}

// =================================================================
// Device cards
// =================================================================
function renderDevices(devices) {
    // devices: dict from API keyed by source_ip
    const ips = Object.keys(devices);
    if (ips.length === 0) {
        deviceList.innerHTML = '<div class="empty">awaiting traffic...</div>';
        deviceCount = 0;
        deviceCountEl.textContent = "0";
        return;
    }
    deviceCount = ips.length;
    deviceCountEl.textContent = String(ips.length);

    // Build cards in deterministic order
    const html = ips.sort().map(ip => {
        const d = devices[ip];
        const feat = d.features || {};
        const pred = d.prediction || {};
        const label = pred.label || "unknown";
        const conf = pred.confidence || 0;
        const meta = DEVICE_LABELS[label] || DEVICE_LABELS.unknown;
        const confPct = (conf * 100).toFixed(1);
        const statusClass = d.status || "idle";
        const statusText = (d.status || "idle").toUpperCase();
        return `
        <div class="device-card ${statusClass}">
            <div class="device-head">
                <div class="device-name">
                    <span class="device-icon" style="color:${meta.color};background:${meta.color}18">${meta.icon}</span>
                    <span style="color:${meta.color}">${meta.label}</span>
                    <span class="device-ip">${ip}</span>
                </div>
                <span class="device-status status-${statusClass}">${statusText}</span>
            </div>
            <div class="confidence-bar">
                <div class="confidence-fill" style="width:${Math.min(100, confPct)}%"></div>
            </div>
            <div class="device-features">
                <span class="k">avg size</span><span class="v">${(feat.avg_packet_size || 0).toFixed(1)} bytes</span>
                <span class="k">interval</span><span class="v">${(feat.inter_packet_interval_ms || 0).toFixed(1)} ms</span>
                <span class="k">packets/min</span><span class="v">${(feat.packets_per_minute || 0).toFixed(1)}</span>
                <span class="k">burstiness</span><span class="v">${(feat.burstiness || 0).toFixed(3)}</span>
            </div>
        </div>`;
    }).join("");
    deviceList.innerHTML = html;
}

function renderAlerts(alerts) {
    if (!alerts || alerts.length === 0) {
        alertList.innerHTML = '<div class="empty">no alerts</div>';
        alertCount = 0;
        alertCountEl.textContent = "0";
        return;
    }
    alertCount = alerts.length;
    alertCountEl.textContent = String(alerts.length);
    alertList.innerHTML = alerts.map(a => {
        const ts = new Date(a.timestamp * 1000).toLocaleTimeString("en-GB");
        const reviewed = a.reviewed ? "reviewed" : "";
        const reviewedTag = a.reviewed ? '<span class="alert-meta">REVIEWED</span>' : "";
        return `
        <div class="alert-item ${a.type} ${reviewed}">
            <div class="alert-body">
                <div class="alert-type">${a.type} - ${a.severity}</div>
                <div class="alert-message">${escapeHtml(a.message)}</div>
                <div class="alert-meta">${ts} | ${a.source_ip} | ${a.alert_id} ${reviewedTag}</div>
            </div>
            <div class="alert-actions">
                <button class="btn-review" data-alert="${a.alert_id}" ${a.reviewed ? "disabled" : ""}>
                    ${a.reviewed ? "Reviewed" : "Mark reviewed"}
                </button>
            </div>
        </div>`;
    }).join("");
    alertList.querySelectorAll(".btn-review").forEach(btn => {
        if (btn.disabled) return;
        btn.addEventListener("click", () => {
            const id = btn.dataset.alert;
            fetch(`/api/alerts/${id}/review`, { method: "POST" })
              .then(r => r.json())
              .then(d => {
                  if (d.ok) {
                      btn.disabled = true;
                      btn.textContent = "Reviewed";
                      btn.closest(".alert-item").classList.add("reviewed");
                      logEvent("info", "alert", `Marked ${id} as reviewed`);
                  }
              });
        });
    });
}

function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, c => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[c]));
}

// =================================================================
// System log
// =================================================================
function logEvent(level, category, msg) {
    const ts = new Date().toLocaleTimeString("en-GB");
    const entry = document.createElement("div");
    entry.className = `entry ${level}`;
    entry.innerHTML = `<span class="ts">${ts}</span><span class="lvl">${category}</span><span class="msg">${escapeHtml(msg)}</span>`;
    eventLog.insertBefore(entry, eventLog.firstChild);
    while (eventLog.children.length > 80) {
        eventLog.removeChild(eventLog.lastChild);
    }
}

// =================================================================
// Socket.IO
// =================================================================
const socket = io();

socket.on("connect", () => {
    sysStatus.classList.add("capturing");
    sysStatus.querySelector(".label").textContent = "live";
    logEvent("info", "system", "Connected to Chhaya");
});

socket.on("disconnect", () => {
    sysStatus.classList.remove("capturing");
    sysStatus.querySelector(".label").textContent = "disconnected";
    logEvent("warning", "system", "Disconnected");
});

socket.on("snapshot", (data) => {
    renderDevices(data.devices);
    renderAlerts(data.recent_alerts);
    sysStatus.querySelector(".label").textContent = data.system_status || "live";
    lastUpdateEl.textContent = "Updated " + new Date().toLocaleTimeString("en-GB");
});

socket.on("prediction", (p) => {
    lastUpdateEl.textContent = "Updated " + new Date().toLocaleTimeString("en-GB");
    scheduleRefresh();
});

socket.on("status", (p) => {
    logEvent("device", "status", `${p.source_ip} -> ${p.status}`);
});

socket.on("alert", (a) => {
    logEvent(a.type === "spoofing" ? "critical" : "warning", a.type, a.message);
    scheduleRefresh();
});

socket.on("alert_reviewed", () => {
    // Reload via snapshot
    fetch("/api/state").then(r => r.json()).then(d => {
        renderDevices(d.devices);
        renderAlerts(d.recent_alerts);
    });
});

// =================================================================
// Demo controls
// =================================================================
function bindToggle(btnId, endpoint, extraBody) {
    const btn = document.getElementById(btnId);
    btn.addEventListener("click", () => {
        const on = btn.dataset.state === "off";
        const body = Object.assign({ enabled: on }, extraBody ? extraBody() : {});
        fetch(endpoint, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
        }).then(r => r.json()).then(d => {
            if (d.ok) {
                btn.dataset.state = on ? "on" : "off";
                btn.classList.toggle("on", on);
                btn.querySelector(".text").textContent = on ? "ON" : "OFF";
                logEvent(on ? "warning" : "info", "control",
                    `${btnId.replace("-toggle", "")} ${on ? "enabled" : "disabled"}`);
            }
        });
    });
}

bindToggle("rogue-toggle", "/api/sim/rogue");
bindToggle("spoofer-toggle", "/api/sim/spoofer", () => ({
    target: document.getElementById("spoofer-target").value,
}));

// =================================================================
// Boot
// =================================================================
let lastDevicesJson = "";
let lastAlertsJson = "";

// Re-render device cards + alerts from /api/state and feed the chart.
// Called by the 3-second poll and immediately on prediction/alert events,
// so a newly connected device appears without a page reload.
async function refreshState() {
    try {
        const r = await fetch("/api/state");
        const data = await r.json();
        const dj = JSON.stringify(data.devices);
        if (dj !== lastDevicesJson) {
            lastDevicesJson = dj;
            renderDevices(data.devices);
        }
        const aj = JSON.stringify(data.recent_alerts);
        if (aj !== lastAlertsJson) {
            lastAlertsJson = aj;
            renderAlerts(data.recent_alerts);
        }
        const ppm = {};
        for (const [ip, d] of Object.entries(data.devices)) {
            if (d.features) {
                // Normalize ip to label key for the chart series
                const label = d.prediction && d.prediction.label;
                if (label && DEVICE_LABELS[label]) {
                    ppm[label] = d.features.packets_per_minute;
                }
            }
        }
        pushChartPoint(Date.now() / 1000, ppm);
    } catch (e) { /* ignore */ }
}

// Throttled: at most one refresh per second even if events fire rapidly.
let lastRefresh = 0;
let refreshTimer = null;
function scheduleRefresh() {
    const now = Date.now();
    if (now - lastRefresh >= 1000) {
        lastRefresh = now;
        refreshState();
    } else if (!refreshTimer) {
        refreshTimer = setTimeout(() => {
            refreshTimer = null;
            lastRefresh = Date.now();
            refreshState();
        }, 600);
    }
}

async function boot() {
    chart = initChart();
    refreshLegend();
    // Fetch initial state
    await refreshState();
    // Poll continuously (devices + alerts + chart stay live)
    setInterval(refreshState, 3000);

    // Uptime counter
    setInterval(() => {
        const sec = Math.floor((Date.now() - startTs) / 1000);
        const m = String(Math.floor(sec / 60)).padStart(2, "0");
        const s = String(sec % 60).padStart(2, "0");
        uptimeEl.textContent = `${m}:${s}`;
    }, 1000);
}

boot();
