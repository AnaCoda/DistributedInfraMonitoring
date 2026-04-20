<template>
  <div class="max-w-[1100px] mx-auto px-5 py-5">
    <!-- Header -->
    <div class="flex gap-3 items-center mb-4 flex-wrap">
      <h1 class="text-xl font-bold mr-auto">Infrastructure Monitor</h1>

      <button
        @click="refreshNowAll"
        :disabled="loading"
        class="btn px-3 py-1.5 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        ↺ Refresh
      </button>

      <span v-if="error" class="text-red-600 text-sm">{{ error }}</span>
      <span v-else class="text-gray-400 text-sm">Updated {{ lastFetchText }}</span>
      <span v-if="endpointLabel" class="text-gray-400 text-xs">via {{ endpointLabel }}</span>
      <span v-if="capital" class="text-gray-400 text-xs">capital {{ capital }}</span>
      <span v-if="leader" class="text-gray-400 text-xs">leader {{ leader }}</span>

      <!-- WS status badge -->
      <span
        class="flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full border font-medium"
        :class="wsStatus === 'connected'
          ? 'border-green-500 text-green-700'
          : wsStatus === 'connecting'
            ? 'border-yellow-400 text-yellow-600'
            : 'border-gray-300 text-gray-400'"
      >
        <span
          class="w-1.5 h-1.5 rounded-full"
          :class="wsStatus === 'connected'
            ? 'bg-green-500'
            : wsStatus === 'connecting'
              ? 'bg-yellow-400 animate-pulse'
              : 'bg-gray-300'"
        />
        {{ wsStatus }}
      </span>

      <div class="flex items-center bg-gray-100 rounded-lg p-1 ml-2">
        <button
          @click="viewMode = 'grid'"
          class="px-3 py-1 text-xs font-bold rounded-md transition-all"
          :class="viewMode === 'grid' ? 'bg-white shadow-sm text-gray-800' : 'text-gray-500 hover:text-gray-700'"
        >
          Grid
        </button>
        <button
          @click="viewMode = 'map'"
          class="px-3 py-1 text-xs font-bold rounded-md transition-all"
          :class="viewMode === 'map' ? 'bg-white shadow-sm text-gray-800' : 'text-gray-500 hover:text-gray-700'"
        >
          Map
        </button>
      </div>
    </div>

    <div class="pb-6 flex flex-row gap-3 flex-wrap">
      <div
        class="p-1 pl-2 border-gray-500 border rounded-full flex justify-center items-center gap-2 flex-row"
        v-for="value in connectedEndpoints"
        :key="value"
      >
        <div class="w-4 h-4 border bg-green-400 rounded-full"></div>
        <div>{{ value }}</div>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading && regions.length === 0" class="text-sm text-gray-400">Loading…</div>

    <!-- Empty state -->
    <div
      v-else-if="regions.length === 0"
      class="p-4 border border-dashed border-gray-300 rounded-lg text-sm text-gray-600"
    >
      No regions reporting yet.
    </div>

    <div v-else>
      <!-- National summary -->
      <div class="mb-5 grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-6 gap-3">
        <div class="summary-card">
          <div class="summary-label">Regions</div>
          <div class="summary-value text-gray-800">{{ regions.length }}</div>
        </div>
        <div class="summary-card">
          <div class="summary-label">Power Stable</div>
          <div
            class="summary-value"
            :class="nationalPower === regions.length ? 'text-green-700' : 'text-yellow-600'"
          >
            {{ nationalPower }}/{{ regions.length }}
          </div>
        </div>
        <div class="summary-card">
          <div class="summary-label">Avg Medical</div>
          <div
            class="summary-value"
            :class="nationalMedical >= 70 ? 'text-green-700' : nationalMedical >= 30 ? 'text-yellow-600' : 'text-red-600'"
          >
            {{ nationalMedical }}%
          </div>
        </div>
        <div class="summary-card">
          <div class="summary-label">Avg Water</div>
          <div
            class="summary-value"
            :class="nationalWater >= 70 ? 'text-green-700' : nationalWater >= 30 ? 'text-yellow-600' : 'text-red-600'"
          >
            {{ nationalWater }}%
          </div>
        </div>
        <div class="summary-card">
          <div class="summary-label">Avg Fuel</div>
          <div
            class="summary-value"
            :class="nationalFuel >= 70 ? 'text-green-700' : nationalFuel >= 30 ? 'text-yellow-600' : 'text-red-600'"
          >
            {{ nationalFuel }}%
          </div>
        </div>
        <div class="summary-card">
          <div class="summary-label">Stale Nodes</div>
          <div class="summary-value" :class="staleCount === 0 ? 'text-gray-400' : 'text-red-600'">
            {{ staleCount }}
          </div>
        </div>
      </div>

      <!-- Region visualization -->
      <div v-if="viewMode === 'grid'">
        <!-- Region cards -->
        <div
          class="grid gap-4 items-start"
          style="grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));"
        >
          <div
            v-for="r in regions"
            :key="r.name"
            class="border rounded-xl p-4 shadow-sm bg-white transition-colors"
            :class="r.isCapital
              ? 'border-slate-400 bg-slate-50 shadow-md'
              : r.isStale
                ? 'border-red-300 opacity-70'
                : 'border-gray-200'"
          >
            <!-- Card header -->
            <div class="flex items-start justify-between gap-3 mb-3">
              <div>
                <h2 class="text-base font-semibold leading-tight">{{ r.name }}</h2>
                <div class="flex items-center gap-2 mt-1 flex-wrap">
                  <span
                    class="text-[11px] px-1.5 py-0.5 rounded border font-medium uppercase tracking-wide"
                    :class="r.regionType === 'urban'
                      ? 'border-purple-300 text-purple-700 bg-purple-50'
                      : r.regionType === 'standard'
                        ? 'border-blue-300 text-blue-700 bg-blue-50'
                        : r.isCapital
                          ? 'border-slate-700 text-white bg-slate-700'
                          : 'border-gray-300 text-gray-500'"
                  >
                    {{ r.isCapital ? "capital" : (r.regionType || "unknown") }}
                  </span>

                  <span
                    v-if="r.name === leader"
                    class="text-[11px] px-1.5 py-0.5 rounded border border-green-300 text-green-700 bg-green-50 font-medium uppercase tracking-wide"
                  >
                    leader
                  </span>

                  <span v-if="r.sites" class="text-[11px] text-gray-400">{{ r.sites.length }} sites</span>
                </div>
              </div>

              <div class="shrink-0 text-right text-xs">
                <span
                  v-if="r.isStale"
                  class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full border border-red-400 text-red-600 bg-red-50 font-semibold uppercase"
                >
                  ⚠ Stale
                </span>
                <span v-else class="text-gray-400">{{ r.lastSeenText }}</span>
              </div>
            </div>

            <hr class="border-gray-100 mb-3" />

            <!-- Status rows -->
            <div class="space-y-2">
              <div class="flex items-center text-sm">
                <span class="label-col">Power</span>
                <StatusBadge :value="r.state.power" />
              </div>
              <div class="flex items-center text-sm">
                <span class="label-col">Transport</span>
                <StatusBadge :value="r.state.transport" />
              </div>
              <div class="flex items-center text-sm gap-3">
                <span class="label-col">Medical</span>
                <ProgressBar :value="r.state.medical_capacity" />
              </div>
              <div class="flex items-center text-sm gap-3">
                <span class="label-col">Water</span>
                <ProgressBar :value="r.state.water_capacity" />
              </div>
              <div class="flex items-center text-sm gap-3">
                <span class="label-col">Fuel</span>
                <ProgressBar :value="r.state.fuel_storage" />
              </div>
            </div>

            <!-- Sites toggle -->
            <div v-if="r.sites && r.sites.length" class="mt-3">
              <button
                @click="toggleSites(r.name)"
                class="btn w-full flex justify-between items-center px-3 py-1.5 text-xs"
              >
                <span>Site details</span>
                <span class="flex items-center gap-1.5">
                  <span class="bg-gray-100 rounded px-1.5 py-0.5">{{ r.sites.length }}</span>
                  {{ expanded[r.name] ? '▲' : '▼' }}
                </span>
              </button>

              <div v-if="expanded[r.name]" class="mt-2 rounded-lg overflow-hidden border border-gray-200">
                <table class="w-full text-xs">
                  <thead class="bg-gray-50 text-gray-400 uppercase tracking-wide">
                    <tr>
                      <th class="th-cell">Site</th>
                      <th class="th-cell">Type</th>
                      <th class="th-cell text-right">Value</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr
                      v-for="s in r.sites"
                      :key="s.name + s.resource_type"
                      class="border-t border-gray-100 hover:bg-gray-50"
                    >
                      <td class="td-cell font-mono text-gray-600">{{ s.name }}</td>
                      <td class="td-cell text-gray-500">{{ s.resource_type }}</td>
                      <td class="td-cell text-right">
                        <SiteValue :value="s.resource_value" />
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            <div v-else class="mt-2.5 text-[11px] text-gray-400 italic">
              No site details
            </div>
          </div>
        </div>
      </div>
      <div v-else>
        <MapView :regions="regions" :heartbeats="heartbeats" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, reactive, ref } from "vue";
import StatusBadge from "./components/StatusBadge.vue";
import ProgressBar from "./components/ProgressBar.vue";
import SiteValue from "./components/SiteValue.vue";
import MapView from "./components/MapView.vue";

// ---- State ----

const data = ref({});
const heartbeats = ref({});
const loading = ref(true);
const error = ref("");
const lastFetch = ref(null);
const connectedEndpoint = ref("");
const leader = ref("");
const capital = ref("");
const connectedEndpoints = ref([]);
const activeSocket = ref(null);

let reconnectTimer = null;

const expanded = reactive({});
const wsStatus = ref("disconnected");
const viewMode = ref("grid");

function isValidWsUrl(url) {
  try {
    const u = new URL(url);
    return (u.protocol === "ws:" || u.protocol === "wss:") && Boolean(u.hostname);
  } catch {
    return false;
  }
}

/** Default: live capital replicas (TLS). Override with VITE_WS_ENDPOINTS. */
const wsCandidates = (() => {
  const raw = (import.meta.env.VITE_WS_ENDPOINTS || "").trim();
  const liveCapitalDefaults = [
    "wss://rm-1.warsys.click",
    "wss://rm-2.warsys.click",
    "wss://rm-3.warsys.click",
    "wss://carstairs-r1.warsys.click",
    "wss://carstairs-r2.warsys.click",
    "wss://carstairs-r3.warsys.click",
    "wss://hospital-1.warsys.click",
  ];
  const parsed = raw
    ? raw.split(",").map(v => v.trim()).filter(Boolean)
    : liveCapitalDefaults;
  return [...new Set(parsed.filter(isValidWsUrl))];
})();

/** Deployed capitals use `query.capital`. Override with VITE_WS_REFRESH_ROUTE if needed. */
const refreshRoute = (import.meta.env.VITE_WS_REFRESH_ROUTE || "query.capital").trim();

function toggleSites(name) {
  expanded[name] = !expanded[name];
}

function parseRegionType(raw) {
  if (!raw) return null;
  return raw.toLowerCase().replace(/regionnode$|node$/, "").trim() || null;
}

function normalizeRegion(name, raw, hb) {
  const isNew = raw && typeof raw === "object" && ("state" in raw || "meta" in raw);
  const state = isNew ? (raw.state ?? {}) : (raw ?? {});
  const meta = isNew ? (raw.meta ?? {}) : {};
  const regionType = parseRegionType(meta.region_type || meta.regionType || null);
  const sites = Array.isArray(meta.sites) ? meta.sites : null;

  const hbEntry = hb?.[name];
  const lastContact = hbEntry?.last_contact ? new Date(hbEntry.last_contact).getTime() / 1000 : null;
  const ts = lastContact;

  const now = Date.now() / 1000;
  const age = ts ? (now - ts) : null;
  const isStale = age !== null ? age > 5 : false;

  const lastSeenText =
    age === null ? "no heartbeat" :
      age < 1 ? "just now" :
        `${age.toFixed(1)}s ago`;

  const isCapital = capital.value === name;

  return { name, state, regionType, sites, ts, isStale, lastSeenText, isCapital };
}

const regions = computed(() => {
  const obj = data.value || {};
  const hb = heartbeats.value || {};
  return Object.entries(obj)
    .map(([name, raw]) => normalizeRegion(name, raw, hb))
    .sort((a, b) => {
      if (a.isCapital) return -1;
      if (b.isCapital) return 1;
      return a.name.localeCompare(b.name);
    });
});

const nationalPower = computed(() =>
  regions.value.filter(r => {
    const v = (r.state.power ?? "").toLowerCase();
    return v === "stable";
  }).length
);

const nationalMedical = computed(() => {
  const vals = regions.value.map(r => Number(r.state.medical_capacity)).filter(v => !Number.isNaN(v));
  if (!vals.length) return 0;
  return Math.round(vals.reduce((a, b) => a + b, 0) / vals.length);
});

const nationalWater = computed(() => {
  const vals = regions.value.map(r => Number(r.state.water_capacity)).filter(v => !Number.isNaN(v));
  if (!vals.length) return 0;
  return Math.round(vals.reduce((a, b) => a + b, 0) / vals.length);
});

const nationalFuel = computed(() => {
  const vals = regions.value.map(r => Number(r.state.fuel_storage)).filter(v => !Number.isNaN(v));
  if (!vals.length) return 0;
  return Math.round(vals.reduce((a, b) => a + b, 0) / vals.length);
});

const staleCount = computed(() => regions.value.filter(r => r.isStale).length);

const lastFetchText = computed(() => {
  if (!lastFetch.value) return "never";
  return new Date(lastFetch.value).toLocaleTimeString();
});

const endpointLabel = computed(() => {
  if (!connectedEndpoint.value) return "";
  return connectedEndpoint.value.replace(/^wss?:\/\//, "");
});

// ---- State update handler ----

function typeMatches(resourceType, needles) {
  const t = (resourceType ?? "").toLowerCase();
  return needles.some(n => t.includes(n.toLowerCase()));
}

function inferStringMetric(sites, typeNeedles) {
  const s = sites.find(x => typeMatches(x.resource_type, typeNeedles));
  if (!s) return "unknown";
  const v = s.resource_value;
  return typeof v === "string" && v.length ? v : "unknown";
}

function maxNumericByNeedles(sites, typeNeedles) {
  let best = null;
  for (const s of sites) {
    if (!typeMatches(s.resource_type, typeNeedles)) continue;
    const n = Number(s.resource_value);
    if (!Number.isNaN(n)) best = best === null ? n : Math.max(best, n);
  }
  return best;
}

/**
 * Maps live `query.capital` body (regions → infrastructure → sites) into the dashboard shape.
 */
function applyCapitalQuery(body) {
  const regions = body?.regions;
  if (!regions || typeof regions !== "object") return;

  const capitalName = body.name ?? "";
  const nextState = {};
  const nextHb = {};

  for (const [regionKey, regRaw] of Object.entries(regions)) {
    const rname = regRaw?.name ?? regionKey;
    const infra = regRaw?.infrastructure ?? {};
    const sites = [];

    for (const [siteKey, siteRaw] of Object.entries(infra)) {
      const n = siteRaw?.name ?? siteKey;
      const rt = siteRaw?.resource_type ?? "Unknown";
      const rv = siteRaw?.value ?? siteRaw?.resource_value ?? null;
      sites.push({ name: n, resource_type: rt, resource_value: rv });
    }

    const medical = maxNumericByNeedles(sites, ["hospital"]);
    const water = maxNumericByNeedles(sites, ["water"]);
    const fuel = maxNumericByNeedles(sites, ["fuel", "depot"]);

    nextState[rname] = {
      state: {
        power: inferStringMetric(sites, ["powerplant", "power"]),
        transport: inferStringMetric(sites, ["railroad", "rail", "transport"]),
        medical_capacity: medical ?? 0,
        water_capacity: water ?? 0,
        fuel_storage: fuel ?? 0,
      },
      meta: {
        region_type: "StandardRegionNode",
        sites,
      },
    };

    // Key by region name so normalizeRegion() finds hb[name].
    nextHb[rname] = {
      name: rname,
      last_contact: new Date().toISOString(),
      is_leader: true,
    };
  }

  data.value = nextState;
  heartbeats.value = nextHb;
  leader.value = capitalName;
  capital.value = capitalName;
  lastFetch.value = Date.now();
  loading.value = false;
  error.value = "";
}

function applyStateUpdate(body) {
  const root = body.__state ?? body ?? {};
  data.value = root.state ?? body.state ?? {};
  heartbeats.value = root.heartbeat ?? body.heartbeats ?? {};
  leader.value = body.leader ?? "";
  capital.value = body.capital ?? body.leader ?? "";
  lastFetch.value = Date.now();
  loading.value = false;
  error.value = "";
}

const WS_LOG = "[InfraMonitor WS]";

/** Shapes `query.capital` bodies for console (full sites per region, not only region names). */
function summarizeCapitalResponseBody(body) {
  const regions = body?.regions;
  if (!regions || typeof regions !== "object" || Array.isArray(regions)) return body;
  const out = {};
  for (const [regionKey, reg] of Object.entries(regions)) {
    const infra = reg?.infrastructure ?? {};
    out[regionKey] = {
      name: reg?.name ?? regionKey,
      sites: Object.entries(infra).map(([siteKey, site]) => ({
        name: site?.name ?? siteKey,
        resource_type: site?.resource_type,
        value: site?.value ?? site?.resource_value,
      })),
    };
  }
  return { name: body.name, regions: out };
}

function handleWsMessage(raw) {
  let msg;
  try {
    msg = JSON.parse(raw);
  } catch {
    console.warn(WS_LOG, "non-JSON message", raw?.slice?.(0, 200) ?? raw);
    return;
  }
  const body = msg.body;
  const preview =
    body && typeof body === "object" && body.regions && typeof body.regions === "object" && !Array.isArray(body.regions)
      ? summarizeCapitalResponseBody(body)
      : body;
  console.info(WS_LOG, "←", msg.route, msg.rid ? `(rid ${String(msg.rid).slice(0, 8)}…)` : "", preview);
  if (msg.route === "push.state_update" || msg.route === "push.replica_state_update") {
    applyStateUpdate(msg.body ?? {});
    return;
  }
  if (msg.route === "__response") {
    const b = msg.body ?? {};
    if (b.regions && typeof b.regions === "object" && !Array.isArray(b.regions)) {
      applyCapitalQuery(b);
    } else {
      applyStateUpdate(b);
    }
  }
}

function packRpc(route, body = {}) {
  return {
    route,
    rid: crypto.randomUUID(),
    fireforget: false,
    body,
  };
}

const WS_OPEN_TIMEOUT_MS = 8000;

/** If "1"/"true", each candidate is tried again as wss://same-host-and-path (TLS). */
const tryWssAlternate =
  import.meta.env.VITE_WS_TRY_WSS === "1" || import.meta.env.VITE_WS_TRY_WSS === "true";

const lastConnectDiag = ref("");

function scheduleReconnect(ms) {
  if (reconnectTimer) clearTimeout(reconnectTimer);
  reconnectTimer = setTimeout(connectWs, ms);
}

function alternateTlsUrl(endpoint) {
  try {
    const u = new URL(endpoint);
    const host = u.host;
    const path = `${u.pathname}${u.search}`;
    return u.protocol === "ws:" ? `wss://${host}${path}` : `ws://${host}${path}`;
  } catch {
    return null;
  }
}

function endpointsToTry(primary) {
  const list = [primary];
  if (tryWssAlternate) {
    const alt = alternateTlsUrl(primary);
    if (alt && alt !== primary) list.push(alt);
  }
  return list;
}

/**
 * Wait until open, or fail with close code / timeout (browser "error" gives no details).
 */
function waitUntilOpen(ws, ms) {
  return new Promise((resolve, reject) => {
    if (ws.readyState === WebSocket.OPEN) {
      resolve();
      return;
    }
    const timer = setTimeout(() => {
      cleanup();
      reject(new Error(`open timed out after ${ms}ms`));
    }, ms);
    const onOpen = () => {
      cleanup();
      resolve();
    };
    const onClose = ev => {
      cleanup();
      const detail = `closed before open (code ${ev.code}${ev.reason ? ` ${ev.reason}` : ""})`;
      reject(new Error(detail));
    };
    const onError = () => {
      cleanup();
      reject(new Error("error event (often TCP blocked, wrong port, or TLS mismatch — see UI hint)"));
    };
    function cleanup() {
      clearTimeout(timer);
      ws.removeEventListener("open", onOpen);
      ws.removeEventListener("close", onClose);
      ws.removeEventListener("error", onError);
    }
    ws.addEventListener("open", onOpen, { once: true });
    ws.addEventListener("close", onClose, { once: true });
    ws.addEventListener("error", onError, { once: true });
  });
}

async function tryOpenCapitalSocket(endpoint) {
  let ws = null;
  try {
    console.info(WS_LOG, "connecting", endpoint);
    ws = new WebSocket(endpoint);
    await waitUntilOpen(ws, WS_OPEN_TIMEOUT_MS);
    console.info(WS_LOG, "socket open", { url: ws.url, readyState: ws.readyState });

    ws.send(JSON.stringify({ name: `Frontend-${crypto.randomUUID()}` }));
    const handshake = await new Promise((resolve, reject) => {
      const t = setTimeout(() => reject(new Error("Handshake timed out")), WS_OPEN_TIMEOUT_MS);
      ws.addEventListener(
        "message",
        e => {
          clearTimeout(t);
          resolve(JSON.parse(e.data));
        },
        { once: true }
      );
    });
    console.info(WS_LOG, "handshake", handshake);

    if (handshake.status !== "success") {
      console.warn(WS_LOG, "handshake rejected", handshake);
      ws.close();
      return null;
    }

    ws.addEventListener("message", event => handleWsMessage(event.data));

    ws.addEventListener("close", ev => {
      console.info(WS_LOG, "close", { code: ev.code, reason: ev.reason || "(none)", wasClean: ev.wasClean });
      if (import.meta.env.DEV) {
        delete window.__infraMonitorWS;
      }
      if (activeSocket.value === ws) {
        activeSocket.value = null;
        connectedEndpoint.value = "";
        connectedEndpoints.value = [];
        wsStatus.value = "disconnected";
        scheduleReconnect(2500);
      }
    });

    activeSocket.value = ws;
    connectedEndpoint.value = endpoint;
    connectedEndpoints.value = [endpoint.replace(/^wss?:\/\//, "")];
    wsStatus.value = "connected";
    error.value = "";

    if (import.meta.env.DEV) {
      window.__infraMonitorWS = ws;
      console.info(WS_LOG, "live socket on window.__infraMonitorWS (dev only)", ws);
    }

    refreshNow(ws);
    return ws;
  } catch (e) {
    console.warn(WS_LOG, "connect failed", endpoint, e?.message || e);
    lastConnectDiag.value = `${endpoint}: ${e?.message || e}`;
    if (ws) {
      try {
        ws.close();
      } catch {
        // ignore
      }
    }
    return null;
  }
}

async function connectWs() {
  if (reconnectTimer) {
    clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }

  if (activeSocket.value && activeSocket.value.readyState === WebSocket.OPEN) {
    return;
  }

  if (!wsCandidates.length) {
    error.value = "No WebSocket endpoints configured (check VITE_WS_ENDPOINTS).";
    wsStatus.value = "disconnected";
    loading.value = false;
    scheduleReconnect(5000);
    return;
  }

  wsStatus.value = "connecting";

  for (const endpoint of wsCandidates) {
    for (const ep of endpointsToTry(endpoint)) {
      const ws = await tryOpenCapitalSocket(ep);
      if (ws) return;
    }
  }

  const hint =
    "No endpoint accepted the connection. Confirm DNS, TLS (wss), and that WebSockets are allowed from this network. " +
    "For local capital without TLS, set VITE_WS_ENDPOINTS to ws://127.0.0.1:… (see example below).";
  error.value = `WebSocket: no capital reachable. ${hint} Last: ${lastConnectDiag.value || "unknown"}`;
  wsStatus.value = "disconnected";
  loading.value = false;
  scheduleReconnect(3000);
}

function refreshNow(ws) {
  if (!ws || ws.readyState !== WebSocket.OPEN) return;
  const payload = packRpc(refreshRoute, {});
  console.info(WS_LOG, "→", payload.route, `(rid ${String(payload.rid).slice(0, 8)}…)`);
  ws.send(JSON.stringify(payload));
}

function refreshNowAll() {
  refreshNow(activeSocket.value);
}

onMounted(() => connectWs());
onUnmounted(() => {
  if (reconnectTimer) clearTimeout(reconnectTimer);
  reconnectTimer = null;
  const ws = activeSocket.value;
  activeSocket.value = null;
  if (import.meta.env.DEV) {
    delete window.__infraMonitorWS;
  }
  if (ws) {
    try {
      ws.close();
    } catch {
      // ignore
    }
  }
});
</script>