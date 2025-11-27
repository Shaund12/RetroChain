<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRoute } from "vue-router";
import { useTxs } from "@/composables/useTxs";

const { getTx } = useTxs();
const route = useRoute();
const hash = String(route.params.hash);

const loading = ref(false);
const error = ref<string | null>(null);
const tx = ref<any | null>(null);

onMounted(async () => {
  loading.value = true;
  error.value = null;
  try {
    const res = await getTx(hash);
    tx.value = res;
  } catch (e: any) {
    error.value = e?.message ?? String(e);
  } finally {
    loading.value = false;
  }
});
</script>

<template>
  <div class="grid gap-3 grid-cols-1 lg:grid-cols-2">
    <div class="card">
      <h1 class="text-sm font-semibold mb-2 text-slate-100">
        Transaction
        <span class="font-mono text-[11px] break-all">{{ hash }}</span>
      </h1>

      <div v-if="loading" class="text-xs text-slate-400">
        Loading transaction…
      </div>
      <div v-if="error" class="text-xs text-rose-300">
        {{ error }}
      </div>

      <div v-if="tx" class="text-xs text-slate-200 space-y-1">
        <div>
          <span class="font-semibold text-slate-300">Height:</span>
          <span>{{ tx.tx_response?.height ?? '—' }}</span>
        </div>
        <div>
          <span class="font-semibold text-slate-300">Code:</span>
          <span>{{ tx.tx_response?.code ?? 0 }}</span>
        </div>
        <div>
          <span class="font-semibold text-slate-300">Gas wanted:</span>
          <span>{{ tx.tx_response?.gas_wanted ?? '—' }}</span>
        </div>
        <div>
          <span class="font-semibold text-slate-300">Gas used:</span>
          <span>{{ tx.tx_response?.gas_used ?? '—' }}</span>
        </div>
        <div>
          <span class="font-semibold text-slate-300">Time:</span>
          <span>{{ tx.tx_response?.timestamp ?? '—' }}</span>
        </div>
        <div class="mt-2">
          <span class="font-semibold text-slate-300">Logs:</span>
          <pre
            class="mt-1 p-2 rounded bg-slate-900/80 overflow-x-auto max-h-64"
          >{{ JSON.stringify(tx.tx_response?.logs ?? [], null, 2) }}</pre>
        </div>
      </div>
    </div>

    <div class="card">
      <h2 class="text-sm font-semibold mb-2 text-slate-100">
        Raw transaction
      </h2>
      <div v-if="tx" class="text-xs">
        <pre
          class="p-2 rounded bg-slate-900/80 overflow-x-auto max-h-[420px]"
        >{{ JSON.stringify(tx, null, 2) }}</pre>
      </div>
      <div v-else class="text-xs text-slate-400">
        No tx data loaded yet.
      </div>
    </div>
  </div>
</template>
