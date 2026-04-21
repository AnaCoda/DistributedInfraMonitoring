<template>
  <div class="max-w-[1200px] mx-auto px-5 py-5">
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
      <span v-if="capitalNamespace" class="text-gray-400 text-xs">capital {{ capitalNamespace }}</span>
      <span v-if="capitalLeaderReplica" class="text-gray-400 text-xs">leader {{ capitalLeaderReplica }}</span>

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

    <div v-if="capitalReplicas.length" class="mb-4 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
      <div class="text-[11px] font-semibold uppercase tracking-wide text-slate-500 mb-2">
        Capital Replica Set
      </div>

      <div class="flex flex-wrap gap-2 items-center">
        <div
          v-for="rep in capitalReplicas"
          :key="rep.id"
          class="flex items-center gap-2 rounded-full border px-3 py-1 text-xs"
          :class="rep.is_leader
            ? 'border-amber-400 bg-amber-50 text-amber-700'
            : rep.status === 'up'
              ? 'border-slate-300 bg-white text-slate-700'
              : 'border-red-300 bg-red-50 text-red-600'"
        >
          <span
            class="inline-block w-2.5 h-2.5 rounded-full"
            :class="rep.is_leader
              ? 'bg-amber-500'
              : rep.status === 'up'
                ? 'bg-green-500'
                : 'bg-red-500'"
          ></span>

          <span class="font-mono">{{ rep.id }}</span>
          <span v-if="rep.is_leader" class="font-semibold">(leader)</span>
          <span class="text-[10px] opacity-70">v{{ rep.version ?? "—" }}</span>
        </div>
      </div>
    </div>

    <div v-if="regionReplicaSets.length" class="mb-4 space-y-3">
      <div
        v-for="group in regionReplicaSets"
        :key="group.name"
        class="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2"
      >
        <div class="text-[11px] font-semibold uppercase tracking-wide text-slate-500 mb-2">
          Region Replica Set — {{ group.name }}
        </div>

        <div class="flex flex-wrap gap-2 items-center">
          <div
            v-for="rep in group.replicas"
            :key="rep.id"
            class="flex items-center gap-2 rounded-full border px-3 py-1 text-xs"
            :class="rep.is_leader
              ? 'border-amber-400 bg-amber-50 text-amber-700'
              : rep.status === 'up'
                ? 'border-slate-300 bg-white text-slate-700'
                : 'border-red-300 bg-red-50 text-red-600'"
          >
            <span
              class="inline-block w-2.5 h-2.5 rounded-full"
              :class="rep.is_leader
                ? 'bg-amber-500'
                : rep.status === 'up'
                  ? 'bg-green-500'
                  : 'bg-red-500'"
            ></span>

            <span class="font-mono">{{ rep.id }}</span>
            <span v-if="rep.is_leader" class="font-semibold">(leader)</span>
            <span class="text-[10px] opacity-70">v{{ rep.version ?? "—" }}</span>
          </div>
        </div>
      </div>
    </div>

    <div class="pb-4 flex flex-row gap-3 flex-wrap">
      <div
        v-for="node in connectedNodes"
        :key="node.id"
        class="p-1 pl-2 border rounded-full flex justify-center items-center gap-2 flex-row"
        :class="node.status === 'up' ? 'border-green-400' : 'border-red-400 opacity-70'"
      >
        <div
          class="w-4 h-4 border rounded-full"
          :class="node.status === 'up' ? 'bg-green-400' : 'bg-red-400'"
        ></div>
        <div class="text-xs">
          <span class="font-medium">{{ node.id }}</span>
          <span v-if="node.is_leader" class="ml-1 text-amber-600 font-semibold">(leader)</span>
        </div>
      </div>
    </div>

    <div v-if="loading && displayRegions.length === 0" class="text-sm text-gray-400">Loading…</div>

    <div
      v-else-if="displayRegions.length === 0"
      class="p-4 border border-dashed border-gray-300 rounded-lg text-sm text-gray-600"
    >
      No regions reporting yet.
    </div>

    <div v-else>
      <div class="mb-5 grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-6 gap-3">
        <div class="summary-card">
          <div class="summary-label">Regions</div>
          <div class="summary-value text-gray-800">{{ displayRegions.length }}</div>
        </div>
        <div class="summary-card">
          <div class="summary-label">Power Stable</div>
          <div
            class="summary-value"
            :class="nationalPower === operationalRegions.length ? 'text-green-700' : 'text-yellow-600'"
          >
            {{ nationalPower }}/{{ operationalRegions.length }}
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
          <div class="summary-label">Stale Replicas</div>
          <div class="summary-value" :class="staleReplicaCount === 0 ? 'text-gray-400' : 'text-red-600'">
            {{ staleReplicaCount }}
          </div>
        </div>
      </div>

      <div v-if="viewMode === 'grid'">
        <div
          class="grid gap-4 items-start"
          style="grid-template-columns: repeat(auto-fit, minmax(340px, 1fr));"
        >
          <div
            v-for="r in displayRegions"
            :key="r.name"
            class="border rounded-xl p-4 shadow-sm bg-white transition-colors"
            :class="r.isCapital ? 'border-slate-400 bg-slate-50 shadow-md' : 'border-gray-200'"
          >
            <div class="flex items-start justify-between gap-3 mb-3">
              <div>
                <h2 class="text-base font-semibold leading-tight">{{ r.name }}</h2>
                <div class="flex items-center gap-2 mt-1 flex-wrap">
                  <span
                    class="text-[11px] px-1.5 py-0.5 rounded border font-medium uppercase tracking-wide"
                    :class="r.isCapital
                      ? 'border-slate-700 text-white bg-slate-700'
                      : 'border-blue-300 text-blue-700 bg-blue-50'"
                  >
                    {{ r.isCapital ? "capital" : "region" }}
                  </span>

                  <span
                    v-if="r.leaderReplica"
                    class="text-[11px] px-1.5 py-0.5 rounded border border-green-300 text-green-700 bg-green-50 font-medium uppercase tracking-wide"
                  >
                    leader {{ r.leaderReplica }}
                  </span>

                  <span v-if="r.sites" class="text-[11px] text-gray-400">{{ r.sites.length }} sites</span>
                </div>
              </div>

              <div class="shrink-0 text-right text-xs">
                <span v-if="r.lastSeenText" class="text-gray-400">{{ r.lastSeenText }}</span>
              </div>
            </div>

            <hr class="border-gray-100 mb-3" />

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

            <div class="mt-4 rounded-lg border border-gray-200 overflow-hidden">
              <div class="px-3 py-2 bg-gray-50 text-xs font-semibold text-gray-600 uppercase tracking-wide">
                Replicas
              </div>
              <table class="w-full text-xs">
                <thead class="bg-white text-gray-400 uppercase tracking-wide">
                  <tr>
                    <th class="th-cell">Replica</th>
                    <th class="th-cell">Status</th>
                    <th class="th-cell">Version</th>
                    <th class="th-cell">Seen</th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="rep in r.replicas"
                    :key="rep.id"
                    class="border-t border-gray-100"
                  >
                    <td class="td-cell font-mono">
                      {{ rep.id }}
                      <span v-if="rep.is_leader" class="ml-1 text-amber-600 font-semibold">(L)</span>
                    </td>
                    <td class="td-cell">
                      <span :class="rep.status === 'up' ? 'text-green-700' : 'text-red-600'">
                        {{ rep.status }}
                      </span>
                    </td>
                    <td class="td-cell">{{ rep.version ?? "—" }}</td>
                    <td class="td-cell">{{ formatLastSeen(rep.last_seen) }}</td>
                  </tr>
                </tbody>
              </table>
            </div>

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

              <div v-if="expanded[r.name]" class="mt-2 space-y-2">
                <div class="rounded-lg overflow-hidden border border-gray-200">
                  <table class="w-full text-xs">
                    <thead class="bg-gray-50 text-gray-400 uppercase tracking-wide">
                      <tr>
                        <th class="th-cell">Site</th>
                        <th class="th-cell">Type</th>
                        <th class="th-cell text-right">Value</th>
                        <th class="th-cell text-right">Set</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr
                        v-for="s in r.sites"
                        :key="s.name + s.resource_type"
                        class="border-t border-gray-100 hover:bg-gray-50"
                        :class="s.node_status === 'down' ? 'bg-red-50/50' : ''"
                      >
                        <td class="td-cell font-mono text-gray-600">{{ s.name }}</td>
                        <td class="td-cell text-gray-500">{{ s.resource_type }}</td>
                        <td class="td-cell text-right">
                          <SiteValue :value="s.resource_value" />
                        </td>
                        <td class="td-cell text-right">
                          <template v-if="canControlInfra(s.name)">
                            <div class="flex flex-wrap gap-1 justify-end max-w-[180px] ml-auto">
                              <button
                                v-for="preset in getInfraPresetsForSite(s)"
                                :key="`${s.name}-${preset.value}`"
                                class="btn px-2 py-1 text-[10px] text-center whitespace-nowrap min-w-[44px]"
                                @click="setInfraValue(s.name, preset.value)"
                              >
                                {{ preset.label }}
                              </button>
                            </div>
                          </template>

                          <span v-else class="text-[10px] text-gray-400 italic">no control</span>
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
            </div>

            <div v-else class="mt-2.5 text-[11px] text-gray-400 italic">
              No site details
            </div>
          </div>
        </div>
      </div>

      <div v-else>
        <MapView :regions="displayRegions" :heartbeats="replicaHeartbeatMap" />
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

const capitalState = ref(null);
const clusterState = ref(null);
const infraStatusMap = ref(new Map());

const loading = ref(true);
const error = ref("");
const lastFetch = ref(null);
const connectedEndpoint = ref("");
const connectedEndpoints = ref([]);
const activeSocket = ref(null);

let reconnectTimer = null;
let clusterPollTimer = null;
let capitalPollTimer = null;

const expanded = reactive({});
const wsStatus = ref("disconnected");
const viewMode = ref("grid");

const wsCandidates = [
  "wss://rm-1.fly.dev",
  "wss://rm-2.fly.dev",
];

const WS_LOG = "[InfraMonitor WS]";
const WS_OPEN_TIMEOUT_MS = 8000;
const CLUSTER_POLL_MS = 3000;
const CAPITAL_POLL_MS = 6000;

function toggleSites(name) {
  expanded[name] = !expanded[name];
}

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

function getInfraPresetsForSite(site) {
  const clusterSite = getControllableInfra(site.name);
  const effectiveType = clusterSite?.infra_type ?? site.resource_type ?? "";
  const t = effectiveType.toLowerCase();

  if (t.includes("power")) {
    return [
      { label: "D", value: "down" },
      { label: "UN", value: "unstable" },
      { label: "ST", value: "stable" },
    ];
  }

  if (t.includes("rail") || t.includes("transport")) {
    return [
      { label: "D", value: "down" },
      { label: "DE", value: "degraded" },
      { label: "OP", value: "operational" },
    ];
  }

  return [
    { label: "0", value: 0 },
    { label: "25", value: 25 },
    { label: "50", value: 50 },
    { label: "100", value: 100 },
  ];
}

function scheduleReconnect(ms) {
  if (reconnectTimer) clearTimeout(reconnectTimer);
  reconnectTimer = setTimeout(connectWs, ms);
}

function clearPollTimers() {
  if (clusterPollTimer) clearInterval(clusterPollTimer);
  if (capitalPollTimer) clearInterval(capitalPollTimer);
  clusterPollTimer = null;
  capitalPollTimer = null;
}

function startPollTimers() {
  clearPollTimers();

  clusterPollTimer = setInterval(async () => {
    if (document.hidden) return;
    if (wsStatus.value !== "connected") return;

    try {
      const ok = await refreshClusterWithFallback();
      if (ok) {
        await refreshInfraStatuses();
      }
      lastFetch.value = Date.now();
    } catch (e) {
      console.warn("[InfraMonitor WS] background cluster poll failed", e?.message || e);
    }
  }, CLUSTER_POLL_MS);

  capitalPollTimer = setInterval(() => {
    if (document.hidden) return;
    if (wsStatus.value !== "connected") return;

    const ws = activeSocket.value;
    if (!ws || ws.readyState !== WebSocket.OPEN) return;

    try {
      refreshNow(ws, "query.capital");
    } catch (e) {
      console.warn("[InfraMonitor WS] background capital poll failed", e?.message || e);
    }
  }, CAPITAL_POLL_MS);
}

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
      reject(new Error(`closed before open (code ${ev.code}${ev.reason ? ` ${ev.reason}` : ""})`));
    };
    const onError = () => {
      cleanup();
      reject(new Error("connection error (network/TLS/port)"));
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

function packRpc(route, body = {}) {
  return {
    route,
    rid: crypto.randomUUID(),
    fireforget: false,
    body,
  };
}

async function tryOpenCapitalSocket(endpoint) {
  let ws = null;
  try {
    console.info(WS_LOG, "connecting", endpoint);
    ws = new WebSocket(endpoint);
    await waitUntilOpen(ws, WS_OPEN_TIMEOUT_MS);

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

    if (handshake.status !== "success") {
      ws.close();
      return null;
    }

    ws.addEventListener("message", event => handleWsMessage(event.data));
    ws.addEventListener("close", ev => {
      console.info(WS_LOG, "close", { code: ev.code, reason: ev.reason || "(none)", wasClean: ev.wasClean });
      if (activeSocket.value === ws) {
        activeSocket.value = null;
        connectedEndpoint.value = "";
        connectedEndpoints.value = [];
        wsStatus.value = "disconnected";
        clearPollTimers();
        scheduleReconnect(2500);
      }
    });

    activeSocket.value = ws;
    connectedEndpoint.value = endpoint;
    wsStatus.value = "connected";
    error.value = "";
    startPollTimers();

    refreshNowAll();
    return ws;
  } catch (e) {
    console.warn(WS_LOG, "connect failed", endpoint, e?.message || e);
    if (ws) {
      try { ws.close(); } catch {}
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
    error.value = "No WebSocket endpoints configured.";
    wsStatus.value = "disconnected";
    loading.value = false;
    scheduleReconnect(5000);
    return;
  }

  wsStatus.value = "connecting";

  for (const endpoint of wsCandidates) {
    const ws = await tryOpenCapitalSocket(endpoint);
    if (ws) return;
  }

  error.value = "WebSocket: no capital reachable.";
  wsStatus.value = "disconnected";
  loading.value = false;
  scheduleReconnect(3000);
}

function applyCapitalQuery(body) {
  capitalState.value = body;
}

function applyClusterQuery(body) {
  clusterState.value = body;

  const connected = [];
  Object.values(body.capitals ?? {}).flat().forEach(x => connected.push(x));
  Object.values(body.regions ?? {}).forEach(regionBody => {
    connected.push(...(regionBody?.replicas ?? []));
  });
  (body.infrastructure ?? []).forEach(x => connected.push(x));

  connectedEndpoints.value = connected;
}

function handleWsMessage(raw) {
  let msg;
  try {
    msg = JSON.parse(raw);
  } catch {
    return;
  }

  if (msg.route !== "__response") return;

  const body = msg.body ?? {};

  if (body.capitals || body.infrastructure || body.capital_leader_replica) {
    applyClusterQuery(body);
  } else if (body.regions && body.name) {
    applyCapitalQuery(body);
  } else if (body.status === "fail") {
    console.warn("[InfraMonitor WS] request failed", body);
    if (!capitalState.value && !clusterState.value) {
      error.value = body.reason || "Request failed";
    }
  }

  lastFetch.value = Date.now();
  loading.value = false;
}

function refreshNow(ws, route) {
  if (!ws || ws.readyState !== WebSocket.OPEN) return;
  const payload = packRpc(route, {});
  console.info(WS_LOG, "→", payload.route);
  ws.send(JSON.stringify(payload));
}

async function queryRouteFromEndpoint(endpoint, route, body = {}) {
  let ws = null;

  try {
    ws = new WebSocket(endpoint);
    await waitUntilOpen(ws, WS_OPEN_TIMEOUT_MS);

    ws.send(JSON.stringify({ name: `Frontend-Probe-${crypto.randomUUID()}` }));

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

    if (handshake.status !== "success") {
      throw new Error(`Handshake rejected by ${endpoint}`);
    }

    const payload = packRpc(route, body);
    ws.send(JSON.stringify(payload));

    const response = await new Promise((resolve, reject) => {
      const t = setTimeout(() => reject(new Error(`${route} timed out`)), WS_OPEN_TIMEOUT_MS);
      ws.addEventListener(
        "message",
        e => {
          clearTimeout(t);
          resolve(JSON.parse(e.data));
        },
        { once: true }
      );
    });

    const out = response?.body ?? {};
    if (out?.status === "fail") {
      throw new Error(out.reason || `${route} failed`);
    }

    return out;
  } finally {
    if (ws) {
      try { ws.close(); } catch {}
    }
  }
}

async function rpcDirectToEndpoint(endpoint, route, body = {}) {
  let ws = null;

  try {
    ws = new WebSocket(endpoint);
    await waitUntilOpen(ws, WS_OPEN_TIMEOUT_MS);

    ws.send(JSON.stringify({ name: `Frontend-Direct-${crypto.randomUUID()}` }));

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

    if (handshake.status !== "success") {
      throw new Error(`Handshake rejected by ${endpoint}`);
    }

    const payload = packRpc(route, body);

    console.log("[InfraMonitor WS] rpcDirectToEndpoint payload", {
      endpoint,
      route,
      body,
      payload,
    });
    console.log("[InfraMonitor WS] rpcDirectToEndpoint raw", JSON.stringify(payload));

    ws.send(JSON.stringify(payload));

    const response = await new Promise((resolve, reject) => {
      const t = setTimeout(() => reject(new Error(`${route} timed out`)), 5000);
      ws.addEventListener(
        "message",
        e => {
          clearTimeout(t);
          resolve(JSON.parse(e.data));
        },
        { once: true }
      );
    });

    const out = response?.body ?? {};
    if (out?.status === "fail") {
      throw new Error(out.reason || `${route} failed`);
    }

    return out;
  } finally {
    if (ws) {
      try { ws.close(); } catch {}
    }
  }
}

async function refreshInfraStatuses() {
  const next = new Map();

  const infraList = clusterState.value?.infrastructure ?? [];
  for (const infra of infraList) {
    if (!infra?.id) continue;

    const endpoint = infraEndpointForTarget(infra.id);

    try {
      const body = await queryRouteFromEndpoint(endpoint, "query.node_status", {});
      next.set(infra.id, body);
    } catch {
      next.set(infra.id, {
        id: infra.id,
        kind: "infra",
        logical_name: infra.logical_name,
        infra_type: infra.infra_type,
        status: "down",
        resource_value: null,
        last_seen_unix: null,
        last_seen: null,
      });
    }
  }

  infraStatusMap.value = next;
}

async function discoverCapitalLeaderEndpoint() {
  const electionResults = [];

  for (const endpoint of wsCandidates) {
    try {
      const body = await queryRouteFromEndpoint(endpoint, "election.state", {});
      electionResults.push({ endpoint, body });
    } catch (e) {
      console.warn("[InfraMonitor WS] election.state failed on", endpoint, e?.message || e);
    }
  }

  const leaderEntry = electionResults.find(x => x.body?.is_leader === true);
  if (leaderEntry) return leaderEntry.endpoint;

  const explicitLeaderName = electionResults
    .map(x => x.body?.leader)
    .find(Boolean);

  if (explicitLeaderName) {
    const guessed = wsCandidates.find(ep => ep.includes(explicitLeaderName));
    if (guessed) return guessed;
  }

  return connectedEndpoint.value || wsCandidates[0] || null;
}

async function refreshClusterWithFallback() {
  const leaderEndpoint = await discoverCapitalLeaderEndpoint();
  const ordered = [
    ...(leaderEndpoint ? [leaderEndpoint] : []),
    ...wsCandidates.filter(x => x !== leaderEndpoint),
  ];

  for (const endpoint of ordered) {
    try {
      const body = await queryRouteFromEndpoint(endpoint, "query.cluster", {});
      applyClusterQuery(body);
      return true;
    } catch (e) {
      console.warn("[InfraMonitor WS] query.cluster failed on", endpoint, e?.message || e);
    }
  }

  return false;
}

async function refreshNowAll() {
  const ws = activeSocket.value;
  if (!ws || ws.readyState !== WebSocket.OPEN) return;

  loading.value = true;
  error.value = "";

  refreshNow(ws, "query.capital");

  const ok = await refreshClusterWithFallback();

  if (ok) {
    await refreshInfraStatuses();
  } else if (!capitalState.value) {
    error.value = "Unable to load cluster topology from any capital replica.";
  }

  loading.value = false;
}

async function setInfraValue(target, value) {
  try {
    loading.value = true;

    const endpoint = infraEndpointForTarget(target);
    console.log("[InfraMonitor WS] setInfraValue direct", { target, value, endpoint });

    await rpcDirectToEndpoint(endpoint, "control.infra.set_state", { value });
    await refreshNowAll();
    await refreshInfraStatuses();
  } catch (e) {
    error.value = e?.message || String(e);
  } finally {
    loading.value = false;
  }
}

const capitalNamespace = computed(() => clusterState.value?.capital_namespace ?? capitalState.value?.name ?? "");
const capitalLeaderReplica = computed(() => clusterState.value?.capital_leader_replica ?? "");

const controllableInfraMap = computed(() => {
  const out = new Map();
  for (const site of clusterState.value?.infrastructure ?? []) {
    if (site?.id) out.set(site.id, site);
  }
  return out;
});

function getControllableInfra(siteName) {
  return controllableInfraMap.value.get(siteName) ?? null;
}

function canControlInfra(siteName) {
  return !!getControllableInfra(siteName);
}

function infraEndpointForTarget(target) {
  return `wss://${target}.fly.dev`;
}

const capitalReplicas = computed(() => {
  const caps = clusterState.value?.capitals ?? {};
  const live = caps[capitalNamespace.value];
  if (live?.length) return live;
  return [];
});

const regionReplicaSets = computed(() => {
  const regionGroups = clusterState.value?.regions ?? {};

  return Object.entries(regionGroups)
    .map(([name, regionBody]) => ({
      name,
      replicas: regionBody?.replicas ?? [],
      leaderReplica: regionBody?.leader_replica ?? null,
      status: regionBody?.status ?? "unknown",
    }))
    .sort((a, b) => a.name.localeCompare(b.name));
});

const replicaGroups = computed(() => {
  const groups = {};
  const capitals = clusterState.value?.capitals ?? {};
  const regionGroups = clusterState.value?.regions ?? {};

  for (const [logicalName, reps] of Object.entries(capitals)) {
    groups[logicalName] = reps;
  }

  for (const [logicalName, regionBody] of Object.entries(regionGroups)) {
    groups[logicalName] = regionBody?.replicas ?? [];
  }

  return groups;
});

const replicaHeartbeatMap = computed(() => {
  const out = {};
  for (const reps of Object.values(replicaGroups.value)) {
    for (const rep of reps) {
      out[rep.id] = {
        name: rep.logical_name,
        is_leader: !!rep.is_leader,
        last_contact: rep.last_seen,
        status: rep.status,
        version: rep.version,
      };
    }
  }
  return out;
});

function formatLastSeen(lastSeen) {
  if (!lastSeen) return "—";
  const ts = new Date(lastSeen).getTime();
  if (Number.isNaN(ts)) return "—";
  const delta = Math.max(0, (Date.now() - ts) / 1000);
  if (delta < 1) return "just now";
  return `${delta.toFixed(1)}s ago`;
}

const regions = computed(() => {
  const capitalBody = capitalState.value ?? {};
  const capitalRegions = capitalBody.regions ?? {};
  const clusterCaps = clusterState.value?.capitals ?? {};
  const clusterRegs = clusterState.value?.regions ?? {};

  const logicalNames = new Set([
    ...Object.keys(clusterCaps),
    ...Object.keys(clusterRegs),
    ...Object.keys(capitalRegions),
  ]);

  return [...logicalNames].map((logicalName) => {
    const regRaw = capitalRegions[logicalName] ?? null;
    const infra = regRaw?.infrastructure ?? {};
    const sites = [];

    for (const [siteKey, siteRaw] of Object.entries(infra)) {
      const n = siteRaw?.name ?? siteKey;
      const clusterInfra = getControllableInfra(n);
      const directInfra = infraStatusMap.value.get(n) ?? null;

      const rt =
        directInfra?.infra_type ??
        clusterInfra?.infra_type ??
        siteRaw?.resource_type ??
        "Unknown";

      let rv =
        siteRaw?.value ??
        siteRaw?.resource_value ??
        null;

      if (directInfra?.status === "down") {
        rv = "down";
      } else if (directInfra?.resource_value !== undefined && directInfra?.resource_value !== null) {
        rv = directInfra.resource_value;
      }

      sites.push({
        name: n,
        resource_type: rt,
        resource_value: rv,
        node_status: directInfra?.status ?? clusterInfra?.status ?? "unknown",
        last_seen: directInfra?.last_seen ?? null,
      });
    }

    const medical = maxNumericByNeedles(sites, ["hospital"]);
    const water = maxNumericByNeedles(sites, ["water"]);
    const fuel = maxNumericByNeedles(sites, ["fuel", "depot"]);

    const replicas = replicaGroups.value[logicalName] ?? [];
    const leaderReplica = replicas.find(r => r.is_leader)?.id ?? null;

    const newestSeenTs = replicas
      .map(r => r.last_seen ? new Date(r.last_seen).getTime() : null)
      .filter(v => v !== null);

    const newestSeen = newestSeenTs.length
      ? new Date(Math.max(...newestSeenTs)).toISOString()
      : null;

    return {
      name: logicalName,
      isCapital: logicalName === capitalNamespace.value,
      leaderReplica,
      replicas,
      lastSeenText: formatLastSeen(newestSeen),
      sites,
      state: {
        power: inferStringMetric(sites, ["powerplant", "power"]),
        transport: inferStringMetric(sites, ["railroad", "rail", "transport"]),
        medical_capacity: medical ?? 0,
        water_capacity: water ?? 0,
        fuel_storage: fuel ?? 0,
      },
    };
  }).sort((a, b) => a.name.localeCompare(b.name));
});

const displayRegions = computed(() =>
  regions.value.filter(r => !r.isCapital)
);

const operationalRegions = computed(() =>
  regions.value.filter(r => !r.isCapital)
);

const connectedNodes = computed(() => {
  const out = [];
  const caps = clusterState.value?.capitals ?? {};
  const regs = clusterState.value?.regions ?? {};
  const infra = clusterState.value?.infrastructure ?? [];

  for (const reps of Object.values(caps)) {
    out.push(...reps);
  }

  for (const regionBody of Object.values(regs)) {
    out.push(...(regionBody?.replicas ?? []));
  }

  out.push(...infra);
  return out;
});

const nationalPower = computed(() =>
  operationalRegions.value.filter(r => (r.state.power ?? "").toLowerCase() === "stable").length
);

const nationalMedical = computed(() => {
  const vals = operationalRegions.value.map(r => Number(r.state.medical_capacity)).filter(v => !Number.isNaN(v));
  if (!vals.length) return 0;
  return Math.round(vals.reduce((a, b) => a + b, 0) / vals.length);
});

const nationalWater = computed(() => {
  const vals = operationalRegions.value.map(r => Number(r.state.water_capacity)).filter(v => !Number.isNaN(v));
  if (!vals.length) return 0;
  return Math.round(vals.reduce((a, b) => a + b, 0) / vals.length);
});

const nationalFuel = computed(() => {
  const vals = operationalRegions.value.map(r => Number(r.state.fuel_storage)).filter(v => !Number.isNaN(v));
  if (!vals.length) return 0;
  return Math.round(vals.reduce((a, b) => a + b, 0) / vals.length);
});

const staleReplicaCount = computed(() =>
  connectedNodes.value.filter(n => n.status !== "up").length
);

const lastFetchText = computed(() => {
  if (!lastFetch.value) return "never";
  return new Date(lastFetch.value).toLocaleTimeString();
});

const endpointLabel = computed(() => {
  if (!connectedEndpoint.value) return "";
  return connectedEndpoint.value.replace(/^wss?:\/\//, "");
});

onMounted(() => connectWs());

onUnmounted(() => {
  if (reconnectTimer) clearTimeout(reconnectTimer);
  reconnectTimer = null;
  clearPollTimers();
  const ws = activeSocket.value;
  activeSocket.value = null;
  if (ws) {
    try { ws.close(); } catch {}
  }
});
</script>