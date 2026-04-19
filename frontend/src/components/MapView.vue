<template>
  <div class="relative w-full h-[600px] border border-gray-200 rounded-xl overflow-hidden shadow-inner bg-gray-50">
    <div id="map" class="w-full h-full"></div>

    <!-- Floating Info Card (shown on hover) -->
    <div
      v-if="hoveredRegion && !hoveredSite"
      class="absolute bottom-6 right-6 z-[1000] w-[320px] bg-white rounded-xl shadow-2xl border border-gray-100 p-4 transition-all duration-200"
    >
      <div class="flex justify-between items-start mb-3">
        <div>
          <h3 class="text-lg font-bold text-gray-800">{{ hoveredRegion.name }}</h3>
          <div class="flex gap-2 mt-1">
            <span
              class="text-[10px] px-1.5 py-0.5 rounded border font-bold uppercase tracking-wider"
              :class="hoveredRegion.isCapital ? 'bg-slate-800 text-white border-slate-800' : 'bg-purple-50 text-purple-700 border-purple-200'"
            >
              {{ hoveredRegion.isCapital ? 'CAPITAL' : 'REGION' }}
            </span>
            <span class="text-[11px] text-gray-400">{{ hoveredRegion.sites?.length || 0 }} sites</span>
          </div>
        </div>
        <div class="text-[10px] text-gray-400 font-medium uppercase">{{ hoveredRegion.lastSeenText }}</div>
      </div>

      <hr class="border-gray-50 mb-3" />

      <div class="space-y-2.5">
        <div class="flex items-center text-sm">
          <span class="w-20 text-gray-500 font-medium">Power</span>
          <StatusBadge :value="hoveredRegion.state.power" />
        </div>
        <div class="flex items-center text-sm">
          <span class="w-20 text-gray-500 font-medium">Transport</span>
          <StatusBadge :value="hoveredRegion.state.transport" />
        </div>
        <div class="flex items-center text-sm gap-3">
          <span class="w-20 text-gray-500 font-medium">Medical</span>
          <ProgressBar :value="hoveredRegion.state.medical_capacity" />
        </div>
        <div class="flex items-center text-sm gap-3">
          <span class="w-20 text-gray-500 font-medium">Water</span>
          <ProgressBar :value="hoveredRegion.state.water_capacity" />
        </div>
        <div class="flex items-center text-sm gap-3">
          <span class="w-20 text-gray-500 font-medium">Fuel</span>
          <ProgressBar :value="hoveredRegion.state.fuel_storage" />
        </div>
      </div>
      <div v-if="!hoveredRegion.sites?.length" class="mt-3 text-[11px] text-gray-400 italic">No site details</div>
    </div>

    <!-- Site Info Card (shown on hover over shape) -->
    <div
      v-if="hoveredSite"
      class="absolute bottom-6 right-6 z-[1000] w-[280px] bg-white rounded-xl shadow-2xl border border-gray-100 p-4 transition-all duration-200"
    >
      <div class="flex justify-between items-start mb-2">
        <div>
          <h3 class="text-base font-bold text-gray-800">{{ hoveredSite.name }}</h3>
          <p class="text-[10px] text-gray-400 font-bold uppercase tracking-wide">{{ hoveredSite.regionName }}</p>
        </div>
        <div class="text-[10px] px-1.5 py-0.5 rounded border border-blue-200 bg-blue-50 text-blue-700 font-bold uppercase">SITE</div>
      </div>
      
      <hr class="border-gray-50 mb-3" />

      <div class="space-y-3">
        <div class="flex flex-col gap-1">
          <div class="flex justify-between text-[11px] font-bold text-gray-500 uppercase">
            <span>{{ hoveredSite.resource_type }} Level</span>
          </div>
          <ProgressBar :value="hoveredSite.resource_value" />
        </div>
        
        <div class="flex items-center justify-between text-xs bg-gray-50 p-2 rounded-lg">
          <span class="text-gray-500">Node Status</span>
          <span class="flex items-center gap-1.5 font-bold" :class="hoveredSite.resource_value < 30 ? 'text-red-600' : 'text-green-600'">
            <span class="w-1.5 h-1.5 rounded-full" :class="hoveredSite.resource_value < 30 ? 'bg-red-500' : 'bg-green-500'"></span>
            {{ hoveredSite.resource_value < 30 ? 'CRITICAL' : 'ACTIVE' }}
          </span>
        </div>
      </div>
    </div>

    <!-- Map Overlay Legend -->
    <div class="absolute top-4 right-4 z-[1000] bg-white/90 backdrop-blur-sm p-2 rounded-lg border border-gray-200 text-[10px] font-semibold text-gray-600 shadow-sm flex flex-col gap-1">
      <div class="flex items-center gap-2">
        <div class="w-2 h-2 rounded-full border border-dashed border-gray-600"></div>
        <span>REGION BOUNDARY</span>
      </div>
      <div class="flex items-center gap-2">
        <div class="w-2 h-2 rounded-full bg-blue-400"></div>
        <span>STABLE SITE</span>
      </div>
      <div class="flex items-center gap-2">
        <div class="w-0 h-0 border-l-[4px] border-l-transparent border-r-[4px] border-r-transparent border-b-[6px] border-b-gray-400"></div>
        <span>AUXILIARY SITE</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, onUnmounted, ref, watch } from 'vue';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import StatusBadge from './StatusBadge.vue';
import ProgressBar from './ProgressBar.vue';

const props = defineProps({
  regions: {
    type: Array,
    required: true
  }
});

const hoveredRegion = ref(null);
const hoveredSite = ref(null);
let map = null;
const regionLayers = new Map();

// Hardcoded coordinates for demonstration
const regionCoords = {
  "Capital": [45.4215, -75.6972],
  "Alberta": [53.5461, -113.4938],
  "British Columbia": [49.2827, -123.1207],
  "Manitoba": [49.8951, -97.1384],
  "Quebec": [46.8139, -71.2080],
  "Atlantic": [44.6488, -63.5752],
  "Ontario": [43.6532, -79.3832]
};

function initMap() {
  // Center on Canada
  map = L.map('map', {
    zoomControl: false,
    attributionControl: false
  }).setView([56.1304, -106.3468], 4);

  L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
    maxZoom: 19,
  }).addTo(map);

  L.control.zoom({
    position: 'topleft'
  }).addTo(map);

  updateMapLayers();
}

function updateMapLayers() {
  if (!map) return;

  // Clear existing layers
  regionLayers.forEach(layer => map.removeLayer(layer));
  regionLayers.clear();

  props.regions.forEach(region => {
    const coords = regionCoords[region.name] || [50 + Math.random() * 5, -100 + Math.random() * 10];
    const group = L.layerGroup();

    // 1. Region Boundary (Dashed Circle)
    const isBad = region.isStale || region.state.medical_capacity < 30 || region.state.power === 'UNSTABLE';
    const boundary = L.circle(coords, {
      radius: 150000, // 150km
      color: isBad ? '#ef4444' : '#333',
      weight: isBad ? 2 : 1.5,
      dashArray: '5, 5',
      fillOpacity: isBad ? 0.1 : 0.05,
      fillColor: isBad ? '#ef4444' : '#333'
    }).addTo(group);

    boundary.on('mouseover', () => {
      hoveredRegion.value = region;
    });
    boundary.on('mouseout', () => {
      hoveredRegion.value = null;
    });

    // 2. Sites (Markers)
    if (region.sites) {
      region.sites.forEach((site, index) => {
        // Offset sites slightly from center for visualization
        const angle = (index / region.sites.length) * 2 * Math.PI;
        const dist = 0.5 + Math.random() * 0.5;
        const siteCoords = [
          coords[0] + Math.cos(angle) * dist,
          coords[1] + Math.sin(angle) * dist
        ];

        if (index % 2 === 0) {
          // Circle Marker
          const marker = L.circleMarker(siteCoords, {
            radius: 6,
            fillColor: region.isStale ? '#ef4444' : (region.name === 'Capital' ? '#475569' : (site.resource_value < 30 ? '#ef4444' : '#60a5fa')),
            color: '#fff',
            weight: 2,
            fillOpacity: 0.8
          }).addTo(group);

          marker.on('mouseover', (e) => {
            L.DomEvent.stopPropagation(e);
            hoveredSite.value = { ...site, regionName: region.name };
          });
          marker.on('mouseout', () => {
            hoveredSite.value = null;
          });
        } else {
          // Triangle Marker (Custom SVG)
          const isSiteBad = site.resource_value < 30 || region.isStale;
          const triangleIcon = L.divIcon({
            className: 'custom-div-icon',
            html: `<div style="width: 0; height: 0; border-left: 6px solid transparent; border-right: 6px solid transparent; border-bottom: 10px solid ${isSiteBad ? '#ef4444' : (region.name === 'Capital' ? '#475569' : '#94a3b8')};"></div>`,
            iconSize: [12, 12],
            iconAnchor: [6, 10]
          });
          const marker = L.marker(siteCoords, { icon: triangleIcon }).addTo(group);

          marker.on('mouseover', (e) => {
            L.DomEvent.stopPropagation(e);
            hoveredSite.value = { ...site, regionName: region.name };
          });
          marker.on('mouseout', () => {
            hoveredSite.value = null;
          });
        }
      });
    }

    group.addTo(map);
    regionLayers.set(region.name, group);
  });
}

watch(() => props.regions, updateMapLayers, { deep: true });

onMounted(() => {
  initMap();
});

onUnmounted(() => {
  if (map) {
    map.remove();
  }
});
</script>

<style scoped>
#map {
  z-index: 1;
}

:deep(.leaflet-tile-pane) {
  filter: grayscale(0.2) contrast(1.1);
}

:deep(.custom-div-icon) {
  background: none;
  border: none;
}
</style>
