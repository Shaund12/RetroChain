<script setup lang="ts">
interface Props {
  label: string;
  value?: string | number;
  hint?: string;
}

defineProps<Props>();
</script>

<template>
  <div class="card-soft flex flex-col gap-1">
    <div class="text-[11px] uppercase tracking-[0.2em] text-slate-300">
      {{ label }}
    </div>
    <div class="text-lg font-semibold text-emerald-300">
      <span v-if="value !== undefined">{{ value }}</span>
      <span v-else class="opacity-60 text-xs">—</span>
    </div>
    <div v-if="hint" class="text-[11px] text-slate-300">
      {{ hint }}
    </div>
  </div>
</template>
