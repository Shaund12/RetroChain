<script setup lang="ts">
import { onMounted, ref, computed, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useBlocks } from "@/composables/useBlocks";
import { useToast } from "@/composables/useToast";

const route = useRoute();
const router = useRouter();
const { fetchByHeight } = useBlocks();
const { notify } = useToast();

const loading = ref(false);
const error = ref<string | null>(null);
const block = ref<any | null>(null);
const commit = ref<any | null>(null);

const height = ref<number>(Number(route.params.height || 0));

// Derived header fields
const header = computed(() => block.value?.header ?? {});
const txCount = computed(() => block.value?.data?.txs?.length ?? 0);
const blockHash = computed(() => commit.value?.hash ?? "—");
const proposer = computed(() => header.value.proposer_address ?? "—");
const time = computed(() => header.value.time ?? "—");

// Navigation helpers
const goToHeight = (h: number) => {
  if (h <= 0 || loading.value) return;
  router.push({ name: "block-detail", params: { height: h } });
};

const loadBlock = async () => {
  if (!height.value || Number.isNaN(height.value)) {
    error.value = "Invalid block height.";
    return;
  }

  loading.value = true;
  error.value = null;
  block.value = null;
  commit.value = null;

  try {
    const res = await fetchByHeight(height.value);
    block.value = res.block;
    commit.value = res.block_id;
  } catch (e: any) {
    const msg = e?.message ?? String(e);
    error.value = msg;
    notify(`Failed to load block #${height.value}: ${msg}`);
  } finally {
    loading.value = false;
  }
};

onMounted(loadBlock);

// React when route param changes but component instance stays
watch(
  () => route.params.height,
  (val) => {
    height.value = Number(val || 0);
    loadBlock();
  }
);
</script>

<template>
  <div class="grid gap-3 grid-cols-1 lg:grid-cols-2">
    <!-- Summary / meta card -->
    <div class="card">
      <div class="flex items-center justify-between mb-2">
        <div>
          <h1 class="text-sm font-semibold text-slate-100">
            Block #{{ height }}
          </h1>
          <p class="text-xs text-slate-400">
            RetroChain block details (REST).
          </p>
        </div>

        <div class="flex items-center gap-2">
          <button
            class="btn text-xs"
            :disabled="height <= 1 || loading"
            @click="goToHeight(height - 1)"
          >
            ← Prev
          </button>
          <button
            class="btn text-xs"
            :disabled="loading"
            @click="goToHeight(height + 1)"
          >
            Next →
          </button>
        </div>
      </div>

      <div v-if="loading" class="text-xs text-slate-400 mb-2">
        Loading block from node…
      </div>

      <div v-if="error" class="mb-2 text-xs text-rose-300">
        {{ error }}
      </div>

      <div
        v-if="block"
        class="mt-2 text-xs text-slate-200 space-y-2 border-t border-slate-800 pt-2"
      >
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-2">
          <div>
            <div class="text-[11px] uppercase tracking-[0.18em] text-slate-400">
              Block hash
            </div>
            <code class="text-[11px] break-all">{{ blockHash }}</code>
          </div>
          <div>
            <div class="text-[11px] uppercase tracking-[0.18em] text-slate-400">
              Time
            </div>
            <div>{{ time }}</div>
          </div>
          <div>
            <div class="text-[11px] uppercase tracking-[0.18em] text-slate-400">
              Proposer
            </div>
            <code class="text-[11px] break-all">{{ proposer }}</code>
          </div>
          <div>
            <div class="text-[11px] uppercase tracking-[0.18em] text-slate-400">
              Tx count
            </div>
            <div>
              <span class="badge">{{ txCount }} tx</span>
            </div>
          </div>
        </div>

        <div class="mt-3 grid grid-cols-1 sm:grid-cols-2 gap-2">
          <div>
            <div class="text-[11px] uppercase tracking-[0.18em] text-slate-400">
              Chain ID
            </div>
            <div>{{ header.chain_id || "—" }}</div>
          </div>
          <div>
            <div class="text-[11px] uppercase tracking-[0.18em] text-slate-400">
              App hash
            </div>
            <code class="text-[11px] break-all">
              {{ header.app_hash || "—" }}
            </code>
          </div>
          <div>
            <div class="text-[11px] uppercase tracking-[0.18em] text-slate-400">
              Last block ID hash
            </div>
            <code class="text-[11px] break-all">
              {{ header.last_block_id?.hash || "—" }}
            </code>
          </div>
          <div>
            <div class="text-[11px] uppercase tracking-[0.18em] text-slate-400">
              Version
            </div>
            <div>
              {{ header.version?.block || "—" }} /
              {{ header.version?.app || "—" }}
            </div>
          </div>
        </div>

        <div class="mt-3">
          <div class="text-[11px] uppercase tracking-[0.18em] text-slate-400">
            Header JSON
          </div>
          <pre
            class="mt-1 p-2 rounded bg-slate-900/80 overflow-x-auto max-h-72"
          >{{ JSON.stringify(header, null, 2) }}</pre>
        </div>
      </div>

      <div v-else-if="!loading && !error" class="text-xs text-slate-400 mt-2">
        No block data yet for this height.
      </div>
    </div>

    <!-- Raw block JSON -->
    <div class="card">
      <h2 class="text-sm font-semibold mb-2 text-slate-100">Raw block</h2>
      <div v-if="block" class="text-xs">
        <pre
          class="p-2 rounded bg-slate-900/80 overflow-x-auto max-h-[420px]"
        >{{ JSON.stringify(block, null, 2) }}</pre>
      </div>
      <div v-else-if="loading" class="text-xs text-slate-400">
        Fetching raw block…
      </div>
      <div v-else class="text-xs text-slate-400">
        No block data yet.
      </div>
    </div>
  </div>
</template>
