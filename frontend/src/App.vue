<template>
  <div class="max-w-[980px] mx-auto p-5">
    <h1 class="text-2xl font-bold mb-4">Infrastructure Monitor</h1>

    <div class="flex gap-3 items-center mb-3 flex-wrap">
      <button @click="refreshNow" :disabled="loading"
        class="btn px-3 py-2 disabled:opacity-50 disabled:cursor-not-allowed">
        Refresh
      </button>

      <label class="flex gap-2 items-center text-sm">
        Poll
        <input type="checkbox" v-model="polling" class="cursor-pointer" />
      </label>

      <label class="flex gap-2 items-center text-sm">
        Interval (ms)
        <input type="number" v-model.number="pollMs" min="250" step="250"
          class="w-[110px] border border-gray-300 rounded px-2 py-1 text-sm" />
      </label>

      <span v-if="error" class="text-red-700 text-sm">{{ error }}</span>
      <span v-else class="opacity-70 text-sm">Last fetch: {{ lastFetchText }}</span>

      <span
        class="ml-auto text-xs px-2 py-0.5 rounded-full border font-medium"
        :class="wsStatus === 'connected'
          ? 'border-green-600 text-green-700'
          : wsStatus === 'connecting'
            ? 'border-yellow-500 text-yellow-600'
            : 'border-gray-400 text-gray-500'"
      >{{ wsStatus }}</span>
    </div>

    <div v-if="loading && regions.length === 0" class="text-sm opacity-70">Loading...</div>

    <div v-else-if="regions.length === 0" class="p-3.5 border border-dashed border-gray-400 rounded text-sm">
      No regions reporting yet. Start nodes like:
      <pre class="mt-2.5 bg-gray-100 p-2.5 overflow-x-auto rounded text-xs"><code>{{ exampleCommands }}</code></pre>
    </div>

    <div v-else class="grid gap-3.5" style="grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));">
      <div v-for="r in regions" :key="r.name" class="border border-gray-200 rounded-[10px] p-3.5 shadow-sm">
        <div class="flex justify-between items-baseline gap-2.5">
          <div>
            <h2 class="text-lg font-semibold m-0 leading-tight">{{ r.name }}</h2>
            <div class="opacity-75 text-[13px] mt-0.5">
              Type: {{ r.regionType || "unknown" }}
            </div>
          </div>

          <div class="text-right shrink-0">
            <div v-if="r.isStale"
              class="inline-block px-2 py-0.5 rounded-full border border-red-700 text-red-700 text-xs"
              title="Node heartbeat is old">
              STALE
            </div>
            <div v-else class="opacity-70 text-xs" title="Heartbeat freshness">
              {{ r.lastSeenText }}
            </div>
          </div>
        </div>

        <hr class="my-3 border-0 border-t border-gray-100" />

        <ul class="m-0 pl-[18px] space-y-0.5 text-sm">
          <li><b>power:</b> {{ r.state.power ?? "?" }}</li>
          <li><b>medical_capacity:</b> {{ formatPct(r.state.medical_capacity) }}</li>
          <li><b>transport:</b> {{ r.state.transport ?? "?" }}</li>
          <li><b>water_capacity:</b> {{ formatPct(r.state.water_capacity) }}</li>
          <li><b>fuel_storage:</b> {{ formatPct(r.state.fuel_storage) }}</li>
        </ul>

        <div v-if="r.sites && r.sites.length" class="mt-3">
          <button @click="toggleSites(r.name)" class="btn px-2.5 py-1.5">
            {{ expanded[r.name] ? "Hide" : "Show" }} sites ({{ r.sites.length }})
          </button>

          <div v-if="expanded[r.name]" class="mt-2.5">
            <table class="w-full border-collapse text-[13px]">
              <thead>
                <tr class="text-left">
                  <th class="th-cell">Site</th>
                  <th class="th-cell">Type</th>
                  <th class="th-cell">Value</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="s in r.sites" :key="s.name + s.resource_type">
                  <td class="td-cell">{{ s.name }}</td>
                  <td class="td-cell">{{ s.resource_type }}</td>
                  <td class="td-cell">{{ s.resource_value }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <div v-else class="mt-2.5 opacity-65 text-xs">
          (No site details — enable <code class="bg-gray-100 px-1 rounded">meta.sites</code> in capital update_state to
          display.)
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, reactive, ref, watch } from "vue";

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
  "python -m capital.server",
  "python -m regional.node --name Alberta --type standard",
  "python -m regional.node --name Calgary --type urban --interval 1.5",
].join("\n");

function toggleSites(name) {
  expanded[name] = !expanded[name];
}

function formatPct(v) {
  if (v === undefined || v === null || Number.isNaN(Number(v))) return "?";
  return `${Number(v)}%`;
}

function normalizeRegion(name, raw) {
  // raw can be either:
  // 1) old: state dict directly
  // 2) new: { state: {...}, meta: {...} }
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
    age === null ? "no heartbeat timestamp" :
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
    if (this.queue.length) {
      return Promise.resolve(this.queue.shift());
    }
    return new Promise(resolve => {
      this.waiters.push(resolve);
    });
  }

  send(msg) {
    this.ws.send(JSON.stringify(msg));
  }
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
    aws.send({
      route: "api.national_infrastructure",
      rid: crypto.randomUUID(),
      body: {}
    });
    const response = await aws.recv();
    data.value = response.body ?? response;
    lastFetch.value = Date.now();
  } catch (e) {
    error.value = e?.message ?? String(e);
  } finally {
    loading.value = false;
    fetching = false;
  }
}

function refreshNow() {
  fetchNational();
}

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