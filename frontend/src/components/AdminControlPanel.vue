<template>
  <section class="mb-5 rounded-xl border border-amber-300 bg-amber-50 p-4">
    <div class="flex items-start justify-between gap-3 mb-3 flex-wrap">
      <div>
        <h2 class="text-sm font-semibold text-amber-900">Demo Controls</h2>
      </div>
      <div class="flex items-center gap-2">
        <span class="text-[11px] px-2 py-0.5 rounded-full border"
          :class="disabled ? 'border-gray-300 text-gray-500 bg-gray-100' : 'border-amber-300 text-amber-800 bg-amber-100'">
          {{ disabled ? 'No active replica connection' : 'Ready' }}
        </span>
        <button
          type="button"
          class="btn px-2.5 py-1 text-xs"
          @click="isCollapsed = !isCollapsed"
        >
          {{ isCollapsed ? 'Expand' : 'Collapse' }}
        </button>
      </div>
    </div>

    <div v-if="!isCollapsed" class="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      <label class="text-xs text-gray-600">
        Target
        <select v-model="targetId" class="mt-1 w-full rounded border border-gray-300 bg-white px-2 py-1.5 text-sm">
          <option v-for="target in nodeTargets" :key="target" :value="target">{{ target }}</option>
        </select>
      </label>

      <label class="text-xs text-gray-600">
        Outage Timer (seconds)
        <input
          v-model.number="durationSec"
          type="number"
          min="1"
          max="600"
          class="mt-1 w-full rounded border border-gray-300 bg-white px-2 py-1.5 text-sm"
        >
      </label>
    </div>

    <div v-if="!isCollapsed" class="mt-3 flex items-center gap-3 flex-wrap">
      <button
        class="btn px-3 py-1.5"
        :disabled="disabled || !targetId || commandStatus.state === 'sending'"
        @click="submit"
      >
        {{ commandStatus.state === 'sending' ? 'Sending…' : 'Send Command' }}
      </button>

      <span class="text-xs" :class="statusClass">{{ statusText }}</span>
    </div>
  </section>
</template>

<script setup>
import { computed, ref, watch } from "vue";

const props = defineProps({
  nodeTargets: {
    type: Array,
    default: () => [],
  },
  commandStatus: {
    type: Object,
    default: () => ({ state: "idle", message: "" }),
  },
  disabled: {
    type: Boolean,
    default: false,
  },
});

const emit = defineEmits(["submit"]);

const isCollapsed = ref(true);
const targetId = ref("");
const durationSec = ref(15);

watch(() => props.nodeTargets, (next) => {
  if (!next.length) {
    targetId.value = "";
    return;
  }
  if (!next.includes(targetId.value)) {
    targetId.value = next[0];
  }
}, { immediate: true });

const statusText = computed(() => {
  if (props.commandStatus.state === "sending") return "Sending command...";
  if (props.commandStatus.state === "success") return props.commandStatus.message || "Command accepted.";
  if (props.commandStatus.state === "error") return props.commandStatus.message || "Command failed.";
  return "";
});

const statusClass = computed(() => {
  if (props.commandStatus.state === "success") return "text-green-700";
  if (props.commandStatus.state === "error") return "text-red-600";
  if (props.commandStatus.state === "sending") return "text-yellow-700";
  return "text-gray-500";
});

function submit() {
  if (!targetId.value) return;
  const duration = Number(durationSec.value);
  if (!Number.isFinite(duration) || duration <= 0) return;

  emit("submit", {
    target_id: targetId.value,
    duration_sec: Math.round(duration),
    requested_at: new Date().toISOString(),
    requested_by: "frontend-admin",
  });
}
</script>
