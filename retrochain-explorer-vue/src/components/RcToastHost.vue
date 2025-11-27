<script setup lang="ts">
import { onMounted, onUnmounted, ref } from "vue";

interface Toast {
  id: number;
  message: string;
}

const toasts = ref<Toast[]>([]);

function handle(ev: Event) {
  const custom = ev as CustomEvent<string>;
  toasts.value.push({
    id: Date.now() + Math.random(),
    message: custom.detail
  });
  setTimeout(() => {
    toasts.value.shift();
  }, 3000);
}

onMounted(() => {
  window.addEventListener("rc-toast", handle as any);
});
onUnmounted(() => {
  window.removeEventListener("rc-toast", handle as any);
});
</script>

<template>
  <div class="fixed bottom-4 right-4 flex flex-col gap-2 z-50">
    <div
      v-for="toast in toasts"
      :key="toast.id"
      class="px-3 py-2 rounded-lg bg-slate-900/95 border border-emerald-400/60 text-xs shadow-lg max-w-xs"
    >
      {{ toast.message }}
    </div>
  </div>
</template>
