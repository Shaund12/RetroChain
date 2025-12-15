<script setup lang="ts">
import { onMounted, ref, computed } from "vue";
import { useRoute } from "vue-router";
import { useTxs } from "@/composables/useTxs";
import dayjs from "dayjs";
import { formatCoins } from "@/utils/format";

const { getTx } = useTxs();
const route = useRoute();
const hash = String(route.params.hash);

const loading = ref(false);
const error = ref<string | null>(null);
const tx = ref<any | null>(null);
const viewMode = ref<"pretty" | "raw">("pretty");

const messages = computed(() => {
  return tx.value?.tx?.body?.messages || [];
});

const getMessageType = (msg: any) => {
  const type = msg["@type"] || msg.type || "";
  return type.split(".").pop() || type;
};

const formatAmount = (amount: any) => formatCoins(amount, { minDecimals: 2, maxDecimals: 6, showZerosForIntegers: true });

const isSuccess = computed(() => {
  return tx.value?.tx_response?.code === 0;
});

const feeString = computed(() => formatCoins(tx.value?.tx?.auth_info?.fee?.amount || [], { minDecimals: 2, maxDecimals: 6, showZerosForIntegers: true }));

const memo = computed(() => tx.value?.tx?.body?.memo || "");

const signers = computed(() => tx.value?.tx?.auth_info?.signer_infos || tx.value?.tx?.auth_info?.signerInfos || []);

const copyToClipboard = async (text: string) => {
  try {
    await navigator.clipboard?.writeText?.(text);
    // no toast system wired here; silent success
  } catch {}
};

const downloadJson = (obj: any, filename = "tx.json") => {
  const blob = new Blob([JSON.stringify(obj, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
};

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
  <div class="space-y-3">
    <!-- Status Banner -->
    <div 
      v-if="tx"
      class="card relative overflow-hidden"
      :class="isSuccess ? 'border-emerald-500/50' : 'border-rose-500/50'"
    >
      <div class="absolute inset-0 opacity-10"
           :class="isSuccess ? 'bg-gradient-to-r from-emerald-500 to-cyan-500' : 'bg-gradient-to-r from-rose-500 to-orange-500'"
      ></div>
      <div class="relative flex items-center gap-4">
        <div 
          class="w-16 h-16 rounded-2xl flex items-center justify-center text-3xl font-bold backdrop-blur-sm"
          :class="isSuccess ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/50' : 'bg-rose-500/20 text-rose-400 border border-rose-500/50'"
        >
          {{ isSuccess ? "OK" : "X" }}
        </div>
        <div class="flex-1">
          <div class="text-lg font-bold" :class="isSuccess ? 'text-emerald-300' : 'text-rose-300'">
            Transaction {{ isSuccess ? "Successful" : "Failed" }}
          </div>
          <div class="text-sm text-slate-400 mt-1 flex items-center gap-2">
            <span>{{ dayjs(tx.tx_response?.timestamp).format("YYYY-MM-DD HH:mm:ss") }}</span>
            <span class="text-xs">|</span>
            <span class="text-xs">{{ dayjs(tx.tx_response?.timestamp).fromNow() }}</span>
          </div>
        </div>
        <div v-if="isSuccess" class="text-right">
          <div class="text-xs text-slate-400 uppercase tracking-wider">Status Code</div>
          <div class="text-2xl font-bold text-emerald-400">0</div>
        </div>
      </div>
    </div>

    <div class="grid gap-3 grid-cols-1 md:grid-cols-3">
      <!-- Overview -->
      <div class="card md:col-span-2">
        <h1 class="text-sm font-semibold mb-3 text-slate-100">
          Transaction Details
        </h1>
        <div class="mb-3 flex items-center gap-2">
          <button class="btn text-xs sm:text-[12px]" :class="viewMode==='pretty' ? 'border-emerald-400/70 bg-emerald-500/10' : ''" @click="viewMode='pretty'">Pretty</button>
          <button class="btn text-xs sm:text-[12px]" :class="viewMode==='raw' ? 'border-indigo-400/70 bg-indigo-500/10' : ''" @click="viewMode='raw'">Raw JSON</button>
          <button class="btn text-xs sm:text-[12px]" @click="copyToClipboard(JSON.stringify(tx, null, 2))">Copy JSON</button>
          <button class="btn text-xs sm:text-[12px]" @click="downloadJson(tx)">Download</button>
        </div>

        <div v-if="loading" class="text-xs text-slate-400">
          Loading transaction…
        </div>
        <div v-if="error" class="text-xs text-rose-300">
          {{ error }}
        </div>

        <div v-if="tx && viewMode==='pretty'" class="space-y-3">
          <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 text-xs">
            <div>
              <div class="text-[11px] uppercase tracking-wider text-slate-400 mb-1">
                Transaction Hash
              </div>
              <div class="flex items-center gap-2 whitespace-nowrap">
                <code class="text-[11px] break-words sm:break-all text-slate-200 truncate max-w-[240px] sm:max-w-none">{{ hash }}</code>
                <button class="btn text-[10px] sm:text-[11px]" @click="copyToClipboard(hash)">Copy</button>
              </div>
            </div>
            <div>
              <div class="text-[11px] uppercase tracking-wider text-slate-400 mb-1">
                Block Height
              </div>
              <div class="text-slate-200">{{ tx.tx_response?.height ?? '—' }}</div>
            </div>
            <div>
              <div class="text-[11px] uppercase tracking-wider text-slate-400 mb-1">
                Status Code
              </div>
              <span
                class="badge"
                :class="isSuccess ? 'border-emerald-400/60 text-emerald-200' : 'border-rose-400/60 text-rose-200'"
              >
                {{ tx.tx_response?.code ?? 0 }}
              </span>
            </div>
            <div>
              <div class="text-[11px] uppercase tracking-wider text-slate-400 mb-1">
                Gas (Used / Wanted)
              </div>
              <div class="text-slate-200">
                {{ tx.tx_response?.gas_used ?? '—' }} / {{ tx.tx_response?.gas_wanted ?? '—' }}
              </div>
            </div>
            <div>
              <div class="text-[11px] uppercase tracking-wider text-slate-400 mb-1">
                Fee
              </div>
              <div class="text-slate-200">{{ feeString }}</div>
            </div>
            <div>
              <div class="text-[11px] uppercase tracking-wider text-slate-400 mb-1">
                Memo
              </div>
              <div class="text-slate-300 break-words sm:break-all">{{ memo || '—' }}</div>
            </div>
          </div>

          <!-- Messages -->
          <div class="border-t border-slate-800 pt-3">
            <div class="text-sm font-semibold text-slate-100 mb-2">
              Messages ({{ messages.length }})
            </div>
            <div class="space-y-2">
              <div
                v-for="(msg, idx) in messages"
                :key="idx"
                class="p-3 bg-slate-900/60 rounded-lg border border-slate-700"
              >
                <div class="flex items-center gap-2 mb-2">
                  <span class="badge text-xs border-cyan-400/60 text-cyan-200">
                    {{ getMessageType(msg) }}
                  </span>
                  <button class="btn text-[10px] sm:text-[11px]" @click="copyToClipboard(JSON.stringify(msg, null, 2))">Copy JSON</button>
                </div>
                <div class="text-xs text-slate-300 space-y-1">
                  <div v-if="msg.from_address || msg.fromAddress">
                    <span class="text-slate-400">From:</span>
                    <code class="ml-1 text-[10px] break-words sm:break-all">{{ msg.from_address || msg.fromAddress }}</code>
                  </div>
                  <div v-if="msg.to_address || msg.toAddress">
                    <span class="text-slate-400">To:</span>
                    <code class="ml-1 text-[10px] break-words sm:break-all">{{ msg.to_address || msg.toAddress }}</code>
                  </div>
                  <div v-if="msg.amount">
                    <span class="text-slate-400">Amount:</span>
                    <span class="ml-1">{{ formatAmount(msg.amount) }}</span>
                  </div>
                  <div v-if="msg.validator_address || msg.validatorAddress">
                    <span class="text-slate-400">Validator:</span>
                    <code class="ml-1 text-[10px] break-words sm:break-all">{{ msg.validator_address || msg.validatorAddress }}</code>
                  </div>
                  <div v-if="msg.delegator_address || msg.delegatorAddress">
                    <span class="text-slate-400">Delegator:</span>
                    <code class="ml-1 text-[10px] break-words sm:break-all">{{ msg.delegator_address || msg.delegatorAddress }}</code>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- Events/Logs -->
          <div v-if="tx.tx_response?.logs?.length" class="border-t border-slate-800 pt-3">
            <div class="text-sm font-semibold text-slate-100 mb-2">
              Events & Logs
            </div>
            <pre
              class="p-3 rounded bg-slate-900/80 overflow-x-auto max-h-64 text-xs"
            >{{ JSON.stringify(tx.tx_response.logs, null, 2) }}</pre>
          </div>
        </div>

        <!-- Raw JSON full view -->
        <div v-else-if="tx && viewMode==='raw'" class="text-xs">
          <pre class="p-2 rounded bg-slate-900/80 overflow-auto max-h-[60vh]">{{ JSON.stringify(tx, null, 2) }}</pre>
        </div>
      </div>

      <!-- Raw JSON -->
      <div class="card">
        <h2 class="text-sm font-semibold mb-2 text-slate-100">
          Raw Transaction
        </h2>
        <div v-if="tx" class="text-xs">
          <pre
            class="p-2 rounded bg-slate-900/80 overflow-auto max-h-[50vh]"
          >{{ JSON.stringify(tx, null, 2) }}</pre>
        </div>
        <div v-else-if="loading" class="text-xs text-slate-400">
          Loading...
        </div>
        <div v-else class="text-xs text-slate-400">
          No data
        </div>
      </div>
    </div>
  </div>
</template>
