<template>
  <div class="max-w-[1100px] mx-auto px-5 py-5">
    <!-- Header -->
    <div class="flex gap-3 items-center mb-4 flex-wrap">
      <h1 class="text-xl font-bold mr-auto">Infrastructure Monitor</h1>

      <button @click="refreshNow" :disabled="loading" class="btn px-3 py-1.5 disabled:opacity-50 disabled:cursor-not-allowed">
        ↺ Refresh
      </button>

      <label class="flex gap-1.5 items-center text-sm cursor-pointer select-none">
        <input type="checkbox" v-model="polling" class="cursor-pointer" />
        Auto-poll
      </label>

      <div class="flex items-center gap-1.5 text-sm text-gray-600">
        <span>Interval</span>
        <input type="number" v-model.number="pollMs" min="250" step="250"
          class="w-[90px] border border-gray-300 rounded px-2 py-1 text-sm" />
        <span>ms</span>
      </div>

      <span v-if="error" class="text-red-600 text-sm">{{ error }}</span>
      <span v-else class="text-gray-400 text-sm">Updated {{ lastFetchText }}</span>

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
      <div class="mb-5 grid grid-cols-2 sm:grid-cols-4 gap-3">
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
          <div class="summary-label">Stale Nodes</div>
          <div class="summary-value" :class="staleCount === 0 ? 'text-gray-400' : 'text-red-600'">
            {{ staleCount }}
          </div>
        </div>
      </div>

      <!-- Region cards -->
      <div class="grid gap-4" style="grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));">
        <div v-for="r in regions" :key="r.name"
          class="border rounded-xl p-4 shadow-sm bg-white transition-colors"
          :class="r.isStale ? 'border-red-300 opacity-70' : 'border-gray-200'">

          <!-- Card header -->
          <div class="flex items-start justify-between gap-3 mb-3">
            <div>
              <h2 class="text-base font-semibold leading-tight">{{ r.name }}</h2>
              <div class="flex items-center gap-2 mt-1">
                <span class="text-[11px] px-1.5 py-0.5 rounded border font-medium uppercase tracking-wide"
                  :class="r.regionType === 'urban'    ? 'border-purple-300 text-purple-700 bg-purple-50'
                        : r.regionType === 'standard' ? 'border-blue-300 text-blue-700 bg-blue-50'
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
            No site details — enable <code class="bg-gray-100 px-1 rounded not-italic">meta.sites</code> on update_state
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, reactive, ref, watch } from "vue";
import StatusBadge from "./components/StatusBadge.vue";
import ProgressBar from "./components/ProgressBar.vue";
import SiteValue   from "./components/SiteValue.vue";

// ---- State ----

const data = ref({});
const loading = ref(false);
const error = ref("");
const lastFetch = ref(null);

const polling = ref(true);
const pollMs = ref(1000);
let timer = null;
let reconnectTimer = null;

const expanded = reactive({});

// WebSocket state
let aws = null;
let fetching = false;
const wsStatus = ref("disconnected");

const exampleCommands = [
  "python -m backend.setup",
].join("\n");

function toggleSites(name) {
  expanded[name] = !expanded[name];
}

function normalizeRegion(name, raw) {
  const isNew = raw && typeof raw === "object" && ("state" in raw || "meta" in raw);
  const state = isNew ? (raw.state ?? {}) : (raw ?? {});
  const meta = isNew ? (raw.meta ?? {}) : {};
  const ts = typeof meta.timestamp === "number" ? meta.timestamp : null;
  const regionType = meta.region_type || meta.regionType || null;
  const sites = Array.isArray(meta.sites) ? meta.sites : null;

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
  return Object.entries(obj)
    .map(([name, raw]) => normalizeRegion(name, raw))
    .sort((a, b) => a.name.localeCompare(b.name));
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

const staleCount = computed(() => regions.value.filter(r => r.isStale).length);

const lastFetchText = computed(() => {
  if (!lastFetch.value) return "never";
  return new Date(lastFetch.value).toLocaleTimeString();
});

// --- WebSocket ---

function openWebsocket(address) {
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(address);
    ws.addEventListener("open", () => resolve(ws));
    ws.addEventListener("error", (e) => reject(e));
  });
}

class AsyncWebSocket {
  constructor(ws) {
    this.ws = ws;
    this.queue = [];
    this.waiters = [];
    ws.addEventListener("message", (event) => {
      const datum = JSON.parse(event.data);
      if (this.waiters.length) {
        this.waiters.shift()(datum);
      } else {
        this.queue.push(datum);
      }
    });
  }

  recv() {
    if (this.queue.length) return Promise.resolve(this.queue.shift());
    return new Promise(resolve => { this.waiters.push(resolve); });
  }

  send(msg) { this.ws.send(JSON.stringify(msg)); }
}

async function connectWs() {
  wsStatus.value = "connecting";
  try {
    const ws = await openWebsocket("ws://localhost:3042");
    aws = new AsyncWebSocket(ws);

    aws.send({ name: `Frontend-${crypto.randomUUID()}` });
    const handshake = await aws.recv();

    if (handshake.status !== "success") {
      error.value = `WS handshake failed: ${handshake.reason ?? "unknown"}`;
      wsStatus.value = "disconnected";
      reconnectTimer = setTimeout(connectWs, 2000);
      return;
    }

    wsStatus.value = "connected";
    error.value = "";

    ws.addEventListener("close", () => {
      wsStatus.value = "disconnected";
      aws = null;
      stopTimer();
      reconnectTimer = setTimeout(connectWs, 2000);
    });

    await fetchNational();
    startTimer();
  } catch (e) {
    error.value = "WebSocket error — is the capital server running?";
    wsStatus.value = "disconnected";
    reconnectTimer = setTimeout(connectWs, 2000);
  }
}

async function fetchNational() {
  if (!aws || fetching) return;
  fetching = true;
  loading.value = true;
  try {
    error.value = "";
    aws.send({ route: "api.national_infrastructure", rid: crypto.randomUUID(), body: {} });
    const response = await aws.recv();
    console.log(response)
    data.value = (response.body ?? response).state;
    lastFetch.value = Date.now();
  } catch (e) {
    error.value = e?.message ?? String(e);
  } finally {
    loading.value = false;
    fetching = false;
  }
}

function refreshNow() { fetchNational(); }

function startTimer() {
  stopTimer();
  if (!polling.value) return;
  timer = setInterval(fetchNational, Math.max(250, pollMs.value || 1000));
}

function stopTimer() {
  if (timer) clearInterval(timer);
  timer = null;
}

onMounted(() => connectWs());
onUnmounted(() => {
  stopTimer();
  if (reconnectTimer) clearTimeout(reconnectTimer);
  if (aws) aws.ws.close();
});

watch([polling, pollMs], () => startTimer());
</script>