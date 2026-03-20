<template>
  <div class="flex items-center gap-2 flex-1 min-w-0">
    <div class="flex-1 h-1.5 bg-gray-200 rounded-full overflow-hidden">
      <div v-if="valid" class="h-full rounded-full transition-all duration-500" :class="barColor" :style="{ width: `${pct}%` }" />
    </div>
    <span class="w-[34px] text-right text-xs font-mono" :class="textColor">{{ label }}</span>
  </div>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({ value: [Number, String] });

const num   = computed(() => Number(props.value));
const valid = computed(() => !Number.isNaN(num.value));
const pct   = computed(() => valid.value ? Math.max(0, Math.min(100, num.value)) : 0);
const label = computed(() => valid.value ? `${pct.value}%` : "?");

const barColor  = computed(() => pct.value >= 70 ? "bg-green-500" : pct.value >= 30 ? "bg-yellow-400" : "bg-red-500");
const textColor = computed(() => pct.value >= 70 ? "text-green-700" : pct.value >= 30 ? "text-yellow-600" : "text-red-600");
</script>
