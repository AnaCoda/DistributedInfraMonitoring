<template>
  <div class="relative w-full h-[650px] border border-gray-200 rounded-2xl overflow-hidden shadow-2xl bg-slate-50">
    <div ref="mapEl" class="w-full h-full"></div>

    <div
      v-if="hoveredRegion && !hoveredSite && !hoveredReplica"
      class="absolute bottom-6 right-6 z-[1000] w-[340px] bg-white/95 backdrop-blur-md rounded-2xl shadow-2xl border border-white/20 p-5 transition-all duration-300 animate-in fade-in slide-in-from-bottom-4"
    >
      <div class="flex justify-between items-start mb-4">
        <div>
          <h3 class="text-xl font-bold text-slate-800 tracking-tight">{{ hoveredRegion.name }}</h3>
          <div class="flex gap-2 mt-1.5">
            <span
              class="text-[10px] px-2 py-0.5 rounded-full border font-black uppercase tracking-widest"
              :class="hoveredRegion.isCapital ? 'bg-amber-500 text-white border-amber-500 shadow-sm' : 'bg-slate-100 text-slate-600 border-slate-200'"
            >
              {{ hoveredRegion.isCapital ? "capital" : "region" }}
            </span>
            <span class="text-[11px] text-slate-400 font-medium">{{ hoveredRegion.sites?.length || 0 }} Infrastructure Sites</span>
          </div>
        </div>
      </div>

      <div class="grid grid-cols-2 gap-3 mb-4">
        <div class="bg-slate-50 p-2 rounded-xl border border-slate-100">
          <p class="text-[10px] font-bold text-slate-400 uppercase mb-1">Power</p>
          <StatusBadge :value="hoveredRegion.state.power" />
        </div>
        <div class="bg-slate-50 p-2 rounded-xl border border-slate-100">
          <p class="text-[10px] font-bold text-slate-400 uppercase mb-1">Transport</p>
          <StatusBadge :value="hoveredRegion.state.transport" />
        </div>
      </div>

      <div class="space-y-3">
        <div v-for="res in ['medical_capacity', 'water_capacity', 'fuel_storage']" :key="res" class="space-y-1">
          <div class="flex justify-between items-center text-[10px] font-bold text-slate-500 uppercase">
            <span>{{ res.replace('_', ' ') }}</span>
          </div>
          <ProgressBar :value="hoveredRegion.state[res]" />
        </div>
      </div>
    </div>

    <div
      v-if="hoveredReplica"
      class="absolute bottom-6 right-6 z-[1000] w-[300px] bg-slate-900/95 backdrop-blur-md rounded-2xl shadow-2xl border border-slate-700 p-4 text-white transition-all duration-300"
    >
      <div class="flex justify-between items-start mb-3">
        <div>
          <h3 class="text-base font-bold text-white">{{ hoveredReplica.id }}</h3>
          <p class="text-[10px] text-slate-400 font-bold uppercase tracking-widest">{{ hoveredReplica.regionName }} REPLICA</p>
        </div>
        <div v-if="hoveredReplica.is_leader" class="bg-amber-500 text-[10px] px-2 py-0.5 rounded-full font-black uppercase shadow-lg shadow-amber-500/20">
          LEADER
        </div>
      </div>

      <div class="space-y-2 text-[11px]">
        <div class="flex items-center justify-between bg-white/5 p-2.5 rounded-xl border border-white/10">
          <span class="text-slate-400 font-medium">Status</span>
          <span :class="hoveredReplica.status === 'up' ? 'text-emerald-400' : 'text-rose-400'" class="font-bold uppercase">
            {{ hoveredReplica.status ?? 'unknown' }}
          </span>
        </div>

        <div class="flex items-center justify-between bg-white/5 p-2.5 rounded-xl border border-white/10">
          <span class="text-slate-400 font-medium">Version</span>
          <span class="font-bold text-white">{{ hoveredReplica.version ?? "—" }}</span>
        </div>

        <div class="flex items-center justify-between bg-white/5 p-2.5 rounded-xl border border-white/10">
          <span class="text-slate-400 font-medium">Last Seen</span>
          <span class="font-bold text-white">{{ formatLastSeen(hoveredReplica.last_seen) }}</span>
        </div>
      </div>

      <p class="mt-3 text-[10px] text-slate-500 italic text-center">Physical Node ID: {{ hoveredReplica.id }}</p>
    </div>

    <div
      v-if="hoveredSite"
      class="absolute bottom-6 right-6 z-[1000] w-[280px] bg-white rounded-2xl shadow-2xl border border-slate-100 p-5 transition-all duration-300"
    >
      <div class="flex items-center gap-3 mb-4">
        <div class="p-2 bg-slate-50 rounded-xl border border-slate-100 shadow-sm" v-html="getSiteIcon(hoveredSite.resource_type, 'w-6 h-6 text-slate-700')"></div>
        <div>
          <h3 class="text-base font-bold text-slate-800">{{ hoveredSite.name }}</h3>
          <p class="text-[10px] text-slate-400 font-bold uppercase tracking-widest">{{ hoveredSite.resource_type }}</p>
        </div>
      </div>

      <div class="space-y-4">
        <div class="space-y-1.5">
          <div class="flex justify-between text-[10px] font-black text-slate-500 uppercase tracking-wider">
            <span>Operational Capacity</span>
          </div>
          <ProgressBar :value="siteDisplayValue(hoveredSite)" />
        </div>

        <div class="flex items-center justify-between text-[11px] bg-slate-50 p-2.5 rounded-xl border border-slate-100">
          <span class="text-slate-500 font-medium">Infrastructure State</span>
          <span class="flex items-center gap-2 font-bold" :class="isBadSite(hoveredSite) ? 'text-rose-600' : 'text-emerald-600'">
            <span class="w-1.5 h-1.5 rounded-full" :class="isBadSite(hoveredSite) ? 'bg-rose-500' : 'bg-emerald-500'"></span>
            {{ String(hoveredSite.resource_value).toUpperCase() }}
          </span>
        </div>
      </div>
    </div>

    <div class="absolute top-4 right-4 z-[1000] bg-white/90 backdrop-blur-md p-3 rounded-2xl border border-slate-200 shadow-xl flex flex-col gap-2">
      <p class="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-1">Legend</p>
      <div class="flex items-center gap-3 text-[10px] font-bold text-slate-600">
        <div class="w-3 h-3 rounded-full bg-slate-800 shadow-sm shadow-slate-400"></div>
        <span>CAPITAL REPLICA</span>
      </div>
      <div class="flex items-center gap-3 text-[10px] font-bold text-slate-600">
        <div class="w-3 h-3 rounded-full bg-blue-500 shadow-sm shadow-blue-300"></div>
        <span>REGION REPLICA</span>
      </div>
      <div class="flex items-center gap-3 text-[10px] font-bold text-slate-600">
        <div class="w-3 h-3 rounded-full bg-amber-500 shadow-lg shadow-amber-300 border-2 border-white"></div>
        <span>CURRENT LEADER</span>
      </div>
      <div class="flex items-center gap-3 text-[10px] font-bold text-slate-600">
        <div class="w-3 h-3 rounded-full border-2 border-dashed border-slate-400"></div>
        <span>LOGICAL BOUNDARY</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { nextTick, onMounted, onUnmounted, ref, watch } from "vue";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import StatusBadge from "./StatusBadge.vue";
import ProgressBar from "./ProgressBar.vue";
import {
  getRegionCoords,
  getReplicaCoords,
  getSiteCoords,
} from "../config/mapLayout.js";

const props = defineProps({
  regions: { type: Array, required: true },
  heartbeats: { type: Object, required: true },
});

const mapEl = ref(null);
const hoveredRegion = ref(null);
const hoveredReplica = ref(null);
const hoveredSite = ref(null);
const currentZoom = ref(4);

let map = null;
const layers = new Map();

const ICONS = {
  Powerplant: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M13 2 3 14h9l-1 8 10-12h-9l1-8z"/></svg>`,
  Hospital: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 14c1.49 0 2.5-1.01 2.5-2.5s-1.01-2.5-2.5-2.5h-1V5c0-1.1-.9-2-2-2H8c-1.1 0-2 .9-2 2v4H5c-1.49 0-2.5 1.01-2.5 2.5S3.51 14 5 14h1v7c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2v-7h1Z"/><path d="M12 7v10"/><path d="M8 12h8"/></svg>`,
  Railroad: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="16" height="16" x="4" y="4" rx="2"/><path d="m9 22 3-3 3 3"/><path d="M9 2h6"/><path d="M12 22V2"/><path d="M5 12h14"/><path d="M5 8h14"/><path d="M5 16h14"/></svg>`,
  "Fuel Depot": `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m12 2 6.6 6.6A11 11 0 0 1 12 22a11 11 0 0 1-6.6-13.4L12 2Z"/></svg>`,
  "Water Treatment Plant": `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22a7 7 0 0 0 7-7c0-2-1-3.9-3-5.5s-3.5-4-4-6.5c-.5 2.5-2 4.9-4 6.5C6 11.1 5 13 5 15a7 7 0 0 0 7 7Z"/></svg>`,
};

function getSiteIcon(type, className) {
  const svg = ICONS[type] || ICONS.Powerplant;
  return svg.replace("<svg", `<svg class="${className}"`);
}

function isBadSite(site) {
  const v = site.resource_value;
  return v === "down" || v === "unstable" || (typeof v === "number" && v < 30);
}

function siteDisplayValue(site) {
  const v = site.resource_value;
  if (v === "stable") return 100;
  if (v === "unstable") return 50;
  if (v === "down") return 0;
  return Number(v) || 0;
}

function getSiteColorHex(site) {
  const v = site.resource_value;
  if (v === "down" || (typeof v === "number" && v < 30)) return "#f43f5e";
  if (v === "unstable" || (typeof v === "number" && v < 70)) return "#f59e0b";
  return "#10b981";
}

function getSiteIconStyled(type, colorHex) {
  const svg = ICONS[type] || ICONS.Powerplant;
  return svg.replace('stroke="currentColor"', `stroke="${colorHex}"`);
}

function formatLastSeen(lastSeen) {
  if (!lastSeen) return "—";
  const ts = new Date(lastSeen).getTime();
  if (Number.isNaN(ts)) return "—";
  const delta = Math.max(0, (Date.now() - ts) / 1000);
  if (delta < 1) return "just now";
  return `${delta.toFixed(1)}s ago`;
}

function deterministicReplicaCoords(center, idx, total) {
  if (total <= 1) return center;
  const angle = (idx / total) * 2 * Math.PI;
  const jitter = 0.18;
  return [
    center[0] + Math.cos(angle) * jitter,
    center[1] + Math.sin(angle) * jitter,
  ];
}

function deterministicSiteCoords(center, idx, total) {
  const angle = (idx / Math.max(total, 1)) * 2 * Math.PI;
  const dist = 0.32;
  return [
    center[0] + Math.cos(angle) * dist,
    center[1] + Math.sin(angle) * dist,
  ];
}

function updateMapLayers() {
  if (!map) return;

  layers.forEach((l) => map.removeLayer(l));
  layers.clear();

  const replicasByRegion = {};
  for (const region of props.regions) {
    replicasByRegion[region.name] = region.replicas ?? [];
  }

  props.regions.forEach((region) => {
    const coords = getRegionCoords(region.name);
    const group = L.layerGroup();

    const isBad =
      region.state.power === "unstable" ||
      Number(region.state.medical_capacity) < 30;

    const boundary = L.circle(coords, {
      radius: 12000,
      color: isBad ? "#f43f5e" : "#94a3b8",
      weight: 1.5,
      dashArray: "8, 8",
      fillOpacity: 0.03,
      fillColor: isBad ? "#f43f5e" : "#94a3b8",
    }).addTo(group);

    boundary.on("mouseover", () => {
      hoveredRegion.value = region;
    });
    boundary.on("mouseout", () => {
      hoveredRegion.value = null;
    });

    const replicas = replicasByRegion[region.name] || [];
    const leaderReplica = replicas.find((r) => r.is_leader);

    if (leaderReplica) {
      const leaderCenterMarker = L.circleMarker(coords, {
        radius: region.isCapital ? 9 : 7,
        fillColor: "#f59e0b",
        color: "#fff",
        weight: 3,
        fillOpacity: 1,
        className: "leader-glow",
      }).addTo(group);

      leaderCenterMarker.on("mouseover", (e) => {
        L.DomEvent.stopPropagation(e);
        hoveredReplica.value = {
          ...leaderReplica,
          regionName: region.name,
          isCapital: region.isCapital,
          centerMarker: true,
        };
      });

      leaderCenterMarker.on("mouseout", () => {
        hoveredReplica.value = null;
      });
    }

    replicas.forEach((rep, idx) => {
      const explicit = getReplicaCoords(region.name, rep.id, null);
      const repCoords =
        explicit ?? deterministicReplicaCoords(coords, idx, replicas.length);

      const isCapital = region.isCapital;
      const baseColor = isCapital ? "#1e293b" : "#3b82f6";

      const replicaMarker = L.circleMarker(repCoords, {
        radius: isCapital ? 11 : 8,
        fillColor: rep.is_leader ? "#f59e0b" : baseColor,
        color: rep.is_leader ? "#d97706" : "#fff",
        weight: 3,
        fillOpacity: 1,
        className: rep.is_leader ? "leader-glow" : "",
      }).addTo(group);

      replicaMarker.on("mouseover", (e) => {
        L.DomEvent.stopPropagation(e);
        hoveredReplica.value = {
          ...rep,
          regionName: region.name,
          isCapital,
        };
      });

      replicaMarker.on("mouseout", () => {
        hoveredReplica.value = null;
      });
    });

    if (region.sites?.length) {
      region.sites.forEach((site, index) => {
        const explicit = getSiteCoords(region.name, site.name);
        const siteCoords =
          explicit ?? deterministicSiteCoords(coords, index, region.sites.length);

        const colorHex = getSiteColorHex(site);
        let marker;

        if (currentZoom.value < 10) {
          marker = L.circleMarker(siteCoords, {
            radius: 4,
            fillColor: colorHex,
            color: "#fff",
            weight: 1.5,
            fillOpacity: 0.9,
          }).addTo(group);
        } else {
          const iconHtml = getSiteIconStyled(site.resource_type, colorHex);
          const siteIcon = L.divIcon({
            className: "infra-icon",
            html: `<div style="padding:4px;background:white;border:1px solid #e2e8f0;border-radius:8px;box-shadow:0 1px 3px rgba(0,0,0,.12);width:28px;height:28px;display:flex;align-items:center;justify-content:center;">${iconHtml}</div>`,
            iconSize: [28, 28],
            iconAnchor: [14, 14],
          });
          marker = L.marker(siteCoords, { icon: siteIcon }).addTo(group);
        }

        marker.on("mouseover", (e) => {
          L.DomEvent.stopPropagation(e);
          hoveredSite.value = { ...site, regionName: region.name };
        });

        marker.on("mouseout", () => {
          hoveredSite.value = null;
        });
      });
    }

    group.addTo(map);
    layers.set(region.name, group);
  });
}

async function initMap() {
  await nextTick();

  if (!mapEl.value) return;

  if (map) {
    map.invalidateSize();
    updateMapLayers();
    return;
  }

  map = L.map(mapEl.value, {
    zoomControl: false,
    attributionControl: false,
  }).setView([51.5, -114.0], 8);

  L.tileLayer("https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png", {
    maxZoom: 19,
  }).addTo(map);

  L.control.zoom({ position: "topleft" }).addTo(map);

  map.on("zoomend", () => {
    currentZoom.value = map.getZoom();
    updateMapLayers();
  });

  updateMapLayers();
}

watch(
  () => [props.regions, props.heartbeats],
  () => {
    if (map) updateMapLayers();
  },
  { deep: true }
);

onMounted(() => {
  initMap();
});

onUnmounted(() => {
  if (map) {
    map.remove();
    map = null;
  }
});
</script>

<style scoped>
#map { z-index: 1; border-radius: inherit; }
:deep(.leaflet-tile-pane) { filter: saturate(0.8) contrast(1.05) brightness(1.02); }
:deep(.infra-icon) { background: none; border: none; }
:deep(.leader-glow) { filter: drop-shadow(0 0 6px #f59e0b); }
.animate-in { animation: animate-in 0.3s ease-out; }
@keyframes animate-in {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>