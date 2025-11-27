<script setup lang="ts">
import { onMounted, computed } from "vue";
import { useBlocks } from "@/composables/useBlocks";
import { useRouter } from "vue-router";

const router = useRouter();
const { blocks, loading, error, fetchLatest } = useBlocks();

onMounted(async () => {
  await fetchLatest(50);
});

const latestHeight = computed(() =>
  blocks.value.length ? blocks.value[0].height : null
);
</script>

<template>
  <div class="card flex flex-col gap-3">
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-sm font-semibold text-slate-100">Blocks</h1>
        <p class="text-xs text-slate-400">
          Latest RetroChain blocks from your local devnet. Click a row for full
          block details.
        </p>
      </div>
      <div class="flex items-center gap-2">
        <div
          v-if="latestHeight"
          class="badge text-[11px] border-emerald-400/60 text-emerald-200"
        >
          Latest: <span class="font-mono ml-1">#{{ latestHeight }}</span>
        </div>
        <button class="btn text-xs" @click="fetchLatest(50)">
          Refresh
        </button>
      </div>
    </div>

    <div v-if="loading" class="text-xs text-slate-400">
      Loading blocks…
    </div>
    <div v-if="error" class="text-xs text-rose-300">
      {{ error }}
    </div>

    <div v-if="!loading && !error && blocks.length === 0" class="text-xs text-slate-400">
      No blocks found yet. Make sure
      <code>ignite chain serve</code>
      is running and the REST API is reachable at
      <code>http://localhost:1317</code>.
    </div>

    <div v-if="blocks.length" class="overflow-x-auto">
      <table class="table">
        <thead>
          <tr class="text-xs text-slate-300">
            <th style="width: 80px">Height</th>
            <th>Hash</th>
            <th style="width: 80px">Txs</th>
            <th style="width: 180px">Time</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="b in blocks"
            :key="b.height"
            class="cursor-pointer"
            @click="
              router.push({
                name: 'block-detail',
                params: { height: b.height }
              })
            "
          >
            <td class="font-mono text-[11px]">{{ b.height }}</td>
            <td class="font-mono text-[11px]">
              {{ b.hash ? b.hash.slice(0, 24) + "…" : "—" }}
            </td>
            <td class="text-xs">
              <span class="badge">
                {{ b.txs }} tx
              </span>
            </td>
            <td class="text-xs text-slate-300">
              {{ b.time || "—" }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
