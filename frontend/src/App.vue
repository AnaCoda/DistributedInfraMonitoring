<template>
  <div class="max-w-[1100px] mx-auto px-5 py-5">
    <!-- Header -->
    <div class="flex gap-3 items-center mb-4 flex-wrap">
      <h1 class="text-xl font-bold mr-auto">Infrastructure Monitor</h1>

      <button @click="refreshNow" :disabled="loading" class="btn px-3 py-1.5 disabled:opacity-50 disabled:cursor-not-allowed">
        ↺ Refresh
      </button>

      <span v-if="error" class="text-red-600 text-sm">{{ error }}</span>
      <span v-else class="text-gray-400 text-sm">Updated {{ lastFetchText }}</span>
      <span v-if="endpointLabel" class="text-gray-400 text-xs">via {{ endpointLabel }}</span>

      <!-- WS status badge -->
      <span class="flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full border font-medium"
        :class="wsStatus === 'connected'   ? 'border-green-500 text-green-700'
              : wsStatus === 'connecting'  ? 'border-yellow-400 text-yellow-600'
              :                             'border-gray-300 text-gray-400'">
        <span class="w-1.5 h-1.5 rounded-full"
          :class="wsStatus === 'connected'  ? 'bg-green-500'
                : wsStatus === 'connecting' ? 'bg-yellow-400 animate-pulse'
                :                            'bg-gray-300'" />
        {{ wsStatus }}
      </span>
    </div>

    <!-- Loading -->
    <div v-if="loading && regions.length === 0" class="text-sm text-gray-400">Loading…</div>

    <!-- Empty state -->
    <div v-else-if="regions.length === 0" class="p-4 border border-dashed border-gray-300 rounded-lg text-sm text-gray-600">
      No regions reporting yet. Start nodes like:
      <pre class="mt-2 bg-gray-50 border border-gray-200 rounded p-3 text-xs overflow-x-auto">{{ exampleCommands }}</pre>
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
          <div class="summary-value" :class="nationalPower === regions.length ? 'text-green-700' : 'text-yellow-600'">
            {{ nationalPower }}/{{ regions.length }}
          </div>
        </div>
        <div class="summary-card">
          <div class="summary-label">Avg Medical</div>
          <div class="summary-value" :class="nationalMedical >= 70 ? 'text-green-700' : nationalMedical >= 30 ? 'text-yellow-600' : 'text-red-600'">
            {{ nationalMedical }}%
          </div>
        </div>
        <div class="summary-card">
          <div class="summary-label">Avg Water</div>
          <div class="summary-value" :class="nationalWater >= 70 ? 'text-green-700' : nationalWater >= 30 ? 'text-yellow-600' : 'text-red-600'">
            {{ nationalWater }}%
          </div>
        </div>
        <div class="summary-card">
          <div class="summary-label">Avg Fuel</div>
          <div class="summary-value" :class="nationalFuel >= 70 ? 'text-green-700' : nationalFuel >= 30 ? 'text-yellow-600' : 'text-red-600'">
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

      <!-- Region cards -->
      <div class="grid gap-4 items-start" style="grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));">
        <div v-for="r in regions" :key="r.name"
          class="border rounded-xl p-4 shadow-sm bg-white transition-colors"
          :class="r.isStale ? 'border-red-300 opacity-70'
                : r.regionType === 'capital' ? 'border-slate-400 bg-slate-50 shadow-md'
                : 'border-gray-200'">

          <!-- Card header -->
          <div class="flex items-start justify-between gap-3 mb-3">
            <div>
              <h2 class="text-base font-semibold leading-tight">{{ r.name }}</h2>
              <div class="flex items-center gap-2 mt-1">
                <span class="text-[11px] px-1.5 py-0.5 rounded border font-medium uppercase tracking-wide"
                  :class="r.regionType === 'urban'    ? 'border-purple-300 text-purple-700 bg-purple-50'
                        : r.regionType === 'standard' ? 'border-blue-300 text-blue-700 bg-blue-50'
                        : r.regionType === 'capital'  ? 'border-slate-700 text-white bg-slate-700'
                        :                              'border-gray-300 text-gray-500'">
                  {{ r.regionType || "unknown" }}
                </span>
                <span v-if="r.sites" class="text-[11px] text-gray-400">{{ r.sites.length }} sites</span>
              </div>
            </div>

            <div class="shrink-0 text-right text-xs">
              <span v-if="r.isStale"
                class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full border border-red-400 text-red-600 bg-red-50 font-semibold uppercase">
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
            <button @click="toggleSites(r.name)" class="btn w-full flex justify-between items-center px-3 py-1.5 text-xs">
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
                  <tr v-for="s in r.sites" :key="s.name + s.resource_type" class="border-t border-gray-100 hover:bg-gray-50">
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
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, reactive, ref } from "vue";
import StatusBadge from "./components/StatusBadge.vue";
import ProgressBar from "./components/ProgressBar.vue";
import SiteValue   from "./components/SiteValue.vue";

// ---- State ----

const data = ref({});
const heartbeats = ref({});
const loading = ref(true);
const error = ref("");
const lastFetch = ref(null);
const connectedEndpoint = ref("");

let reconnectTimer = null;
let ws = null;

const expanded = reactive({});
const wsStatus = ref("disconnected");

const wsCandidates = (() => {
  const raw = (import.meta.env.VITE_WS_ENDPOINTS || "").trim();
  const defaults = [
    "ws://localhost:4001",
    "ws://localhost:4002",
    "ws://localhost:4003",
  ];

  const parsed = raw
    ? raw.split(",").map(v => v.trim()).filter(Boolean)
    : defaults;

  return [...new Set(parsed.filter(url => /^ws:\/\/localhost:4\d{3}$/i.test(url)))];
})();

const exampleCommands = [
  "python -m backend.setup",
].join("\n");

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

  return { name, state, regionType, sites, ts, isStale, lastSeenText };
}

const regions = computed(() => {
  const obj = data.value || {};
  const hb = heartbeats.value || {};
  return Object.entries(obj)
    .map(([name, raw]) => normalizeRegion(name, raw, hb))
    .sort((a, b) => {
      if (a.regionType === "capital") return -1;
      if (b.regionType === "capital") return 1;
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
  return connectedEndpoint.value.replace(/^ws:\/\//, "");
});

// ---- State update handler ----

function applyStateUpdate(body) {
  data.value = body.state ?? {};
  heartbeats.value = body.heartbeats ?? {};
  lastFetch.value = Date.now();
  loading.value = false;
  error.value = "";
}

// ---- WebSocket ----

async function connectWs() {
  wsStatus.value = "connecting";
  if (reconnectTimer) {
    clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }

  for (const endpoint of wsCandidates) {
    try {
      ws = new WebSocket(endpoint);

      await new Promise((resolve, reject) => {
        ws.addEventListener("open", resolve, { once: true });
        ws.addEventListener("error", reject, { once: true });
      });

      // Handshake
      ws.send(JSON.stringify({ name: `Frontend-${crypto.randomUUID()}` }));
      const handshake = await new Promise(resolve => {
        ws.addEventListener("message", e => resolve(JSON.parse(e.data)), { once: true });
      });

      if (handshake.status !== "success") {
        ws.close();
        ws = null;
        continue;
      }

      wsStatus.value = "connected";
      connectedEndpoint.value = endpoint;
      error.value = "";
      refreshNow();

      ws.addEventListener("close", () => {
        wsStatus.value = "disconnected";
        connectedEndpoint.value = "";
        ws = null;
        reconnectTimer = setTimeout(connectWs, 2000);
      });

      // React to server-pushed state and explicit request responses
      ws.addEventListener("message", (event) => {
        const msg = JSON.parse(event.data);
        if (msg.route === "push.state_update" || msg.route === "push.replica_state_update") {
          applyStateUpdate(msg.body ?? {});
        } else if (msg.route === "__response" && msg.body?.state) {
          applyStateUpdate(msg.body);
        }
      });

      return;
    } catch (_e) {
      if (ws) {
        try {
          ws.close();
        } catch (_closeErr) {
          //  continue trying other endpoints.
        }
      }
      ws = null;
    }
  }

  error.value = "WebSocket error: no replica reachable";
  wsStatus.value = "disconnected";
  connectedEndpoint.value = "";
  reconnectTimer = setTimeout(connectWs, 2000);
}

function refreshNow() {
  if (!ws || ws.readyState !== WebSocket.OPEN) return;
  ws.send(JSON.stringify({
    route: "api.national_infrastructure",
    rid: crypto.randomUUID(),
    body: {}
  }));
}

onMounted(() => connectWs());
onUnmounted(() => {
  if (reconnectTimer) clearTimeout(reconnectTimer);
  if (ws) ws.close();
});
</script>