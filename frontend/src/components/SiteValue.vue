<template>
  <span class="font-semibold" :class="cls">{{ display }}</span>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({ value: [String, Number] });

// Just check if num for now
const isPercent = computed(() => {
  const v = props.value;
  return v !== "" && v !== null && v !== undefined && !isNaN(Number(v));
});

const display = computed(() => isPercent.value ? `${Number(props.value)}%` : (props.value ?? "?"));

const cls = computed(() => {
  if (isPercent.value) {
    const n = Number(props.value);
    return n >= 70 ? "text-green-700" : n >= 30 ? "text-yellow-600" : "text-red-600";
  }
  const v = (props.value ?? "").toString().toLowerCase();
  if (v === "stable" || v === "operational") return "text-green-700";
  if (v === "degraded" || v === "unstable")  return "text-yellow-600";
  if (v === "down"     || v === "gone")      return "text-red-600";
  return "text-gray-500";
});
</script>
