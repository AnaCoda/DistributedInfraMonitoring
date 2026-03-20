<template>
  <span class="inline-block px-2 py-0.5 rounded border text-[11px] font-semibold uppercase tracking-wide" :class="cls">
    {{ value ?? "?" }}
  </span>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({ value: String });

const STATUS_LEVELS = [
  {
    values: ["stable", "operational"],
    cls: "border-green-400 text-green-700 bg-green-50",
  },
  {
    values: ["degraded", "semi-stable", "unstable"],
    cls: "border-yellow-400 text-yellow-700 bg-yellow-50",
  },
  {
    values: ["down", "gone"],
    cls: "border-red-400 text-red-700 bg-red-50",
  },
];

const FALLBACK_CLS = "border-gray-300 text-gray-500 bg-gray-50";

const cls = computed(() => {
  const v = (props.value ?? "").toLowerCase();
  return STATUS_LEVELS.find(level => level.values.includes(v))?.cls ?? FALLBACK_CLS;
});
</script>
