<script setup lang="ts">
import { onMounted } from "vue";
import { useChainInfo } from "@/composables/useChainInfo";
import { useBlocks } from "@/composables/useBlocks";
import { useTxs } from "@/composables/useTxs";
import RcStatCard from "@/components/RcStatCard.vue";
import { useRouter } from "vue-router";
import dayjs from "dayjs";

const router = useRouter();
const { info, loading: loadingInfo, refresh } = useChainInfo();
const { blocks, loading: loadingBlocks, fetchLatest } = useBlocks();
const { txs, loading: loadingTxs, searchRecent } = useTxs();

onMounted(async () => {
  await Promise.all([refresh(), fetchLatest(10), searchRecent(10)]);
});

const formatTime = (value?: string | null) =>
  value ? dayjs(value).fromNow?.() ?? value : "—";
</script>

<template>
  <div class="grid grid-1-3 gap-4">
    <section class="flex flex-col gap-3">
      <div class="card-soft">
        <div class="flex flex-wrap items-baseline gap-2 mb-1">
          <h1 class="text-xl font-semibold text-slate-50">
            RetroChain Arcade Explorer
          </h1>
          <span class="badge text-emerald-200 border-emerald-500/40">
            devnet
          </span>
        </div>
        <p class="text-sm text-slate-300 mb-3">
          Custom Cosmos-SDK app chain for arcade-style gaming. This dashboard
          shows chain health, latest blocks and transactions on your local node.
        </p>
        <div class="flex flex-wrap gap-2 text-[11px] text-slate-400">
          <span class="badge">
            REST: <code>http://localhost:1317</code>
          </span>
          <span class="badge">
            Node: <code>http://localhost:26657</code>
          </span>
          <span class="badge">Token: RETRO / uretro</span>
        </div>
      </div>

      <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <RcStatCard
          label="Latest block"
          :value="loadingInfo ? '…' : info.latestBlockHeight ?? '—'"
          :hint="
            loadingInfo
              ? 'Querying /blocks/latest…'
              : info.latestBlockTime
              ? `at ${info.latestBlockTime}`
              : undefined
          "
        />
        <RcStatCard
          label="Chain ID"
          :value="loadingInfo ? '…' : info.chainId ?? 'retrochain-arcade-1'"
          hint="Configured via config.yml"
        />
        <RcStatCard
          label="Recent txs"
          :value="loadingTxs ? '…' : txs.length"
          hint="Last 10 transactions"
        />
      </div>

      <div class="card">
        <div class="flex items-center justify-between mb-2">
          <h2 class="text-sm font-semibold text-slate-100">Latest blocks</h2>
          <button class="btn text-xs" @click="router.push({ name: 'blocks' })">
            View all blocks
          </button>
        </div>
        <div v-if="loadingBlocks" class="text-xs text-slate-400">
          Loading latest blocks…
        </div>
        <table v-else class="table">
          <thead>
            <tr class="text-slate-300 text-xs">
              <th>Height</th>
              <th>Hash</th>
              <th>Txs</th>
              <th>Time</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="b in blocks"
              :key="b.height"
              class="cursor-pointer"
              @click="router.push({ name: 'block-detail', params: { height: b.height } })"
            >
              <td class="font-mono text-[11px]">{{ b.height }}</td>
              <td class="font-mono text-[11px]">
                {{ b.hash.slice(0, 10) }}…
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
    </section>

    <section class="flex flex-col gap-3">
      <div class="card">
        <div class="flex items-center justify-between mb-2">
          <h2 class="text-sm font-semibold text-slate-100">
            Recent transactions
          </h2>
          <button class="btn text-xs" @click="router.push({ name: 'txs' })">
            View all txs
          </button>
        </div>
        <div v-if="loadingTxs" class="text-xs text-slate-400">
          Loading recent transactions…
        </div>
        <table v-else class="table">
          <thead>
            <tr class="text-slate-300 text-xs">
              <th>Hash</th>
              <th>Height</th>
              <th>Code</th>
              <th>Gas</th>
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
                {{ t.hash.slice(0, 10) }}…
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
            </tr>
          </tbody>
        </table>
      </div>

      <div class="card text-xs text-slate-300 leading-relaxed">
        <h3 class="text-sm font-semibold mb-1 text-slate-100">
          How to use this explorer
        </h3>
        <ol class="list-decimal list-inside space-y-1">
          <li>Keep <code>ignite chain serve</code> running for RetroChain.</li>
          <li>
            Ensure REST API is exposed at
            <code>http://localhost:1317</code>
            (default).
          </li>
          <li>
            Start this UI with
            <code>npm install && npm run dev</code>
            inside
            <code>vue/</code>.
          </li>
          <li>
            Hit the faucet endpoint or use CLI to generate traffic and watch
            blocks / txs update.
          </li>
        </ol>
      </div>
    </section>
  </div>
</template>
