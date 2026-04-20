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
const viewMode = ref("grid");

let reconnectTimer = null;

const expanded = reactive({});
const wsStatus = ref("disconnected");
const hasEverLoaded = ref(false);

const wsCandidates = (() => {
  const raw = (import.meta.env.VITE_WS_ENDPOINTS || "").trim();
  const defaults = [
    "wss://rm-1.warsys.click",
    "wss://rm-2.warsys.click",
    "wss://rm-3.warsys.click",
  ];

  const parsed = raw
    ? raw.split(",").map(v => v.trim()).filter(Boolean)
    : defaults;

  return [...new Set(parsed)];
})();

/** Deployed capitals use this route now. */
const refreshRoute = (import.meta.env.VITE_WS_REFRESH_ROUTE || "api.national_infrastructure").trim();

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

function applyStateUpdate(body) {
  const root = body?.__state ?? body ?? {};
  const nextData = root?.state ?? body?.state ?? {};
  const nextHeartbeats = root?.heartbeat ?? body?.heartbeats ?? {};

  data.value = nextData;
  heartbeats.value = nextHeartbeats;
  leader.value = body?.leader ?? "";
  capital.value = body?.capital ?? body?.leader ?? "";
  lastFetch.value = Date.now();
  loading.value = false;
  hasEverLoaded.value = true;
  error.value = "";
}

// ---- WebSocket ----

function cleanupSocket() {
  const ws = activeSocket.value;
  activeSocket.value = null;
  if (ws) {
    try {
      ws.close();
    } catch {
      // ignore
    }
  }
}

function scheduleReconnect(delay = 2000) {
  if (reconnectTimer) clearTimeout(reconnectTimer);
  reconnectTimer = setTimeout(connectWs, delay);
}

function refreshNow(ws = activeSocket.value) {
  if (!ws || ws.readyState !== WebSocket.OPEN) return;

  ws.send(JSON.stringify({
    route: refreshRoute,
    rid: crypto.randomUUID(),
    fireforget: false,
    body: {}
  }));
}

function refreshNowAll() {
  refreshNow(activeSocket.value);
}

async function tryConnect(endpoint) {
  return new Promise((resolve) => {
    let settled = false;
    const ws = new WebSocket(endpoint);

    const fail = (msg = "") => {
      if (settled) return;
      settled = true;
      try { ws.close(); } catch {}
      resolve(null);
    };

    const timeout = setTimeout(() => fail("timeout"), 3000);

    ws.addEventListener("open", () => {
      try {
        ws.send(JSON.stringify({ name: `Frontend-${crypto.randomUUID()}` }));
      } catch {
        clearTimeout(timeout);
        fail("handshake-send-failed");
      }
    });

    ws.addEventListener("message", (event) => {
      try {
        const msg = JSON.parse(event.data);

        // Handshake response
        if (!settled && msg?.status) {
          if (msg.status !== "success") {
            clearTimeout(timeout);
            fail("handshake-failed");
            return;
          }

          settled = true;
          clearTimeout(timeout);

          activeSocket.value = ws;
          wsStatus.value = "connected";
          connectedEndpoint.value = endpoint;
          connectedEndpoints.value = [endpoint];
          error.value = "";

          refreshNow(ws);

          resolve(ws);
          return;
        }

        // Normal routed response
        if (msg?.route === "__response") {
          applyStateUpdate(msg.body ?? {});
          return;
        }

        if (msg?.route === "push.state_update" || msg?.route === "push.replica_state_update") {
          applyStateUpdate(msg.body ?? {});
        }
      } catch {
        // ignore malformed messages
      }
    });

    ws.addEventListener("close", () => {
      if (!settled) {
        clearTimeout(timeout);
        fail("closed-before-handshake");
        return;
      }

      if (activeSocket.value === ws) {
        activeSocket.value = null;
        connectedEndpoints.value = [];
        connectedEndpoint.value = "";
        wsStatus.value = "disconnected";

        if (hasEverLoaded.value) {
          error.value = "Connection lost. Reconnecting…";
        }

        scheduleReconnect(2000);
      }
    });

    ws.addEventListener("error", () => {
      if (!settled) {
        clearTimeout(timeout);
        fail("ws-error");
      }
    });
  });
}

async function connectWs() {
  if (activeSocket.value && activeSocket.value.readyState === WebSocket.OPEN) {
    return;
  }

  if (!wsCandidates.length) {
    error.value = "No WebSocket endpoints configured.";
    wsStatus.value = "disconnected";
    loading.value = false;
    scheduleReconnect(5000);
    return;
  }

  wsStatus.value = "connecting";

  for (const endpoint of wsCandidates) {
    const ws = await tryConnect(endpoint);
    if (ws) {
      return;
    }
  }

  if (!hasEverLoaded.value) {
    error.value = "WebSocket error: no replica reachable";
    loading.value = false;
  } else {
    error.value = "All replicas unreachable. Reconnecting…";
  }

  wsStatus.value = "disconnected";
  scheduleReconnect(2000);
}

onMounted(() => {
  connectWs();
});

onUnmounted(() => {
  if (reconnectTimer) clearTimeout(reconnectTimer);
  reconnectTimer = null;
  cleanupSocket();
});
</script>