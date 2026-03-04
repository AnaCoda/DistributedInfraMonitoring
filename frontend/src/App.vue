<template>
  <div>
    <h1>Infrastructure Monitor</h1>

    <p v-if="error" style="color: red">{{ error }}</p>
    <p v-else-if="loading">Loading...</p>

    <div v-else>
      <h2>National View</h2>

      <div v-if="Object.keys(national).length === 0">
        No regions reporting yet.
      </div>

      <div v-for="(state, region) in national" :key="region" style="margin-bottom: 16px; padding: 12px; border: 1px solid #ccc;">
        <h3>{{ region }}</h3>
        <ul>
          <li><b>power:</b> {{ state.power }}</li>
          <li><b>medical_capacity:</b> {{ state.medical_capacity }}%</li>
          <li><b>transport:</b> {{ state.transport }}</li>
          <li><b>water_capacity:</b> {{ state.water_capacity }}%</li>
          <li><b>fuel_storage:</b> {{ state.fuel_storage }}%</li>
        </ul>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'

const national = ref({})
const loading = ref(true)
const error = ref('')
let timer = null

async function fetchNational() {
  try {
    error.value = ''
    const res = await fetch('/api/national_infrastructure')
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    national.value = await res.json()
  } catch (e) {
    error.value = e?.message ?? String(e)
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await fetchNational()
  timer = setInterval(fetchNational, 1000) // refresh every second
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>