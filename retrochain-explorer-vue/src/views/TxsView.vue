<script setup lang="ts">
import { onMounted } from "vue";
import { useTxs } from "@/composables/useTxs";
import { useRouter } from "vue-router";

const { txs, loading, error, searchRecent } = useTxs();
const router = useRouter();

onMounted(async () => {
  await searchRecent(50);
});
</script>

<template>
  <div class="card">
    <div class="flex items-center justify-between mb-3">
      <div>
        <h1 class="text-sm font-semibold text-slate-100">Transactions</h1>
        <p class="text-xs text-slate-400">
          Last 50 RetroChain transactions via gRPC Tx service.
        </p>
      </div>
      <button class="btn text-xs" @click="searchRecent(50)">
        Refresh
      </button>
    </div>

    <div v-if="loading" class="text-xs text-slate-400 mb-2">
      Loading transactions…
    </div>
    <div v-if="error" class="text-xs text-rose-300 mb-2">
      {{ error }}
    </div>

    <table class="table">
      <thead>
        <tr class="text-xs text-slate-300">
          <th>Hash</th>
          <th>Height</th>
          <th>Code</th>
          <th>Gas</th>
          <th>Time</th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="t in txs"
          :key="t.hash"
          class="cursor-pointer"
          @click="router.push({ name: 'tx-detail', params: { hash: t.hash } })"
        >
          <td class="font-mono text-[11px]">
            {{ t.hash.slice(0, 18) }}…
          </td>
          <td class="font-mono text-[11px]">{{ t.height }}</td>
          <td class="text-xs">
            <span
              class="badge"
              :class="t.code === 0 ? 'border-emerald-400/60' : 'border-rose-400/60 text-rose-200'"
            >
              {{ t.code ?? 0 }}
            </span>
          </td>
          <td class="text-[11px] text-slate-300">
            {{ t.gasUsed || '—' }} / {{ t.gasWanted || '—' }}
          </td>
          <td class="text-[11px] text-slate-300">
            {{ t.timestamp || '—' }}
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
