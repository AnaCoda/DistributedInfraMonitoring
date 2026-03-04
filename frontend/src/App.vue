<template>
  <div style="max-width: 980px; margin: 0 auto; padding: 20px;">
    <h1>Infrastructure Monitor</h1>

    <div style="display: flex; gap: 12px; align-items: center; margin-bottom: 12px;">
      <button @click="refreshNow" :disabled="loading" style="padding: 8px 12px;">
        Refresh
      </button>

      <label style="display: flex; gap: 8px; align-items: center;">
        Poll
        <input type="checkbox" v-model="polling" />
      </label>

      <label style="display: flex; gap: 8px; align-items: center;">
        Interval (ms)
        <input type="number" v-model.number="pollMs" min="250" step="250" style="width: 110px;" />
      </label>

      <span v-if="error" style="color: #b00020;">{{ error }}</span>
      <span v-else style="opacity: 0.7;">Last fetch: {{ lastFetchText }}</span>
    </div>

    <div v-if="loading && regions.length === 0">Loading...</div>

    <div v-else-if="regions.length === 0" style="padding: 14px; border: 1px dashed #aaa;">
      No regions reporting yet. Start nodes like:
      <pre style="margin-top: 10px; background: #f6f6f6; padding: 10px; overflow-x: auto;"><code>python -m capital.server
python -m regional.node --name Alberta --type standard
python -m regional.node --name Calgary --type urban --interval 1.5</code></pre>
    </div>

    <div v-else style="display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 14px;">
      <div
        v-for="r in regions"
        :key="r.name"
        style="border: 1px solid #ddd; border-radius: 10px; padding: 14px;"
      >
        <div style="display: flex; justify-content: space-between; align-items: baseline; gap: 10px;">
          <div>
            <h2 style="margin: 0;">{{ r.name }}</h2>
            <div style="opacity: 0.75; font-size: 13px;">
              Type: {{ r.regionType || "unknown" }}
            </div>
          </div>

          <div style="text-align: right;">
            <div
              v-if="r.isStale"
              style="display: inline-block; padding: 3px 8px; border-radius: 999px; border: 1px solid #b00020; color: #b00020; font-size: 12px;"
              title="Node heartbeat is old"
            >
              STALE
            </div>
            <div v-else style="opacity: 0.7; font-size: 12px;" title="Heartbeat freshness">
              {{ r.lastSeenText }}
            </div>
          </div>
        </div>

        <hr style="margin: 12px 0; border: none; border-top: 1px solid #eee;" />

        <ul style="margin: 0; padding-left: 18px;">
          <li><b>power:</b> {{ r.state.power ?? "?" }}</li>
          <li><b>medical_capacity:</b> {{ formatPct(r.state.medical_capacity) }}</li>
          <li><b>transport:</b> {{ r.state.transport ?? "?" }}</li>
          <li><b>water_capacity:</b> {{ formatPct(r.state.water_capacity) }}</li>
          <li><b>fuel_storage:</b> {{ formatPct(r.state.fuel_storage) }}</li>
        </ul>

        <div v-if="r.sites && r.sites.length" style="margin-top: 12px;">
          <button @click="toggleSites(r.name)" style="padding: 6px 10px;">
            {{ expanded[r.name] ? "Hide" : "Show" }} sites ({{ r.sites.length }})
          </button>

          <div v-if="expanded[r.name]" style="margin-top: 10px;">
            <table style="width: 100%; border-collapse: collapse; font-size: 13px;">
              <thead>
                <tr style="text-align: left;">
                  <th style="border-bottom: 1px solid #eee; padding: 6px 4px;">Site</th>
                  <th style="border-bottom: 1px solid #eee; padding: 6px 4px;">Type</th>
                  <th style="border-bottom: 1px solid #eee; padding: 6px 4px;">Value</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="s in r.sites" :key="s.name + s.resource_type">
                  <td style="border-bottom: 1px solid #f2f2f2; padding: 6px 4px;">{{ s.name }}</td>
                  <td style="border-bottom: 1px solid #f2f2f2; padding: 6px 4px;">{{ s.resource_type }}</td>
                  <td style="border-bottom: 1px solid #f2f2f2; padding: 6px 4px;">{{ s.resource_value }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <div v-else style="margin-top: 10px; opacity: 0.65; font-size: 12px;">
          (No site details — enable <code>meta.sites</code> in capital update_state to display.)
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'

const data = ref({})
const loading = ref(false)
const error = ref('')
const lastFetch = ref(null)

const polling = ref(true)
const pollMs = ref(1000)
let timer = null

const expanded = reactive({})

function toggleSites(name) {
  expanded[name] = !expanded[name]
}

function formatPct(v) {
  if (v === undefined || v === null || Number.isNaN(Number(v))) return '?'
  return `${Number(v)}%`
}

function normalizeRegion(name, raw) {
  // raw can be either:
  // 1) old: state dict directly
  // 2) new: { state: {...}, meta: {...} }
  const isNew = raw && typeof raw === 'object' && ('state' in raw || 'meta' in raw)

  const state = isNew ? (raw.state ?? {}) : (raw ?? {})
  const meta = isNew ? (raw.meta ?? {}) : {}

  const ts = typeof meta.timestamp === 'number' ? meta.timestamp : null
  const regionType = meta.region_type || meta.regionType || null
  const sites = Array.isArray(meta.sites) ? meta.sites : null

  const now = Date.now() / 1000
  const age = ts ? (now - ts) : null
  const isStale = age !== null ? age > 5 : false

  const lastSeenText =
    age === null ? 'no heartbeat timestamp' :
    age < 1 ? 'just now' :
    `${age.toFixed(1)}s ago`

  return { name, state, regionType, sites, ts, isStale, lastSeenText }
}

const regions = computed(() => {
  const obj = data.value || {}
  return Object.entries(obj)
    .map(([name, raw]) => normalizeRegion(name, raw))
    .sort((a, b) => a.name.localeCompare(b.name))
})

const lastFetchText = computed(() => {
  if (!lastFetch.value) return 'never'
  return new Date(lastFetch.value).toLocaleTimeString()
})

async function fetchNational() {
  loading.value = true
  try {
    error.value = ''
    const res = await fetch('/api/national_infrastructure')
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    data.value = await res.json()
    lastFetch.value = Date.now()
  } catch (e) {
    error.value = e?.message ?? String(e)
  } finally {
    loading.value = false
  }
}

function refreshNow() {
  fetchNational()
}

function startTimer() {
  stopTimer()
  if (!polling.value) return
  timer = setInterval(fetchNational, Math.max(250, pollMs.value || 1000))
}

function stopTimer() {
  if (timer) clearInterval(timer)
  timer = null
}

onMounted(async () => {
  await fetchNational()
  startTimer()
})

onUnmounted(() => stopTimer())

watch([polling, pollMs], () => startTimer())
</script>