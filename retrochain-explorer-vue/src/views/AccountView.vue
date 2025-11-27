<script setup lang="ts">
import { onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useAccount } from "@/composables/useAccount";
import { useToast } from "@/composables/useToast";

const route = useRoute();
const router = useRouter();
const { balances, bech32Address, loading, error, load } = useAccount();
const { notify } = useToast();

const addressInput = ref<string>((route.params.address as string) || "");

const submit = async () => {
  if (!addressInput.value) {
    notify("Enter a RetroChain address first.");
    return;
  }
  router.replace({ name: "account", params: { address: addressInput.value } });
  await load(addressInput.value);
};

onMounted(async () => {
  if (addressInput.value) {
    await load(addressInput.value);
  }
});

watch(error, (val) => {
  if (val) notify(val);
});
</script>

<template>
  <div class="grid gap-3 grid-cols-1 lg:grid-cols-2">
    <div class="card">
      <h1 class="text-sm font-semibold mb-2 text-slate-100">
        Account explorer
      </h1>
      <p class="text-xs text-slate-400 mb-3">
        Look up balances for any RetroChain account address (bech32).
      </p>

      <form class="flex flex-col gap-2 max-w-xl" @submit.prevent="submit">
        <label class="text-xs text-slate-300">
          Address
          <input
            v-model="addressInput"
            type="text"
            placeholder="cosmos1..."
            class="mt-1 w-full px-2 py-1.5 rounded-md bg-slate-900 border border-slate-700 text-xs font-mono focus:outline-none focus:ring-1 focus:ring-emerald-400"
          />
        </label>
        <button class="btn btn-primary self-start text-xs" type="submit">
          Query balances
        </button>
      </form>

      <div v-if="loading" class="mt-3 text-xs text-slate-400">
        Loading account…
      </div>
      <div v-if="error" class="mt-2 text-xs text-rose-300">
        {{ error }}
      </div>

      <div v-if="bech32Address" class="mt-4 text-xs text-slate-200">
        <div class="mb-2">
          <span class="font-semibold text-slate-300">Address:</span>
          <code class="break-all">{{ bech32Address }}</code>
        </div>
        <div v-if="balances.length === 0" class="text-slate-400">
          No balances found.
        </div>
        <table v-else class="table">
          <thead>
            <tr class="text-xs text-slate-300">
              <th>Denom</th>
              <th>Amount</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="b in balances" :key="b.denom">
              <td class="font-mono text-[11px]">{{ b.denom }}</td>
              <td class="font-mono text-[11px]">{{ b.amount }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div class="card text-xs text-slate-300 leading-relaxed">
      <h2 class="text-sm font-semibold mb-1 text-slate-100">
        Tips for RetroChain dev accounts
      </h2>
      <ul class="list-disc list-inside space-y-1">
        <li>
          By default, Ignite's
          <code>ignite chain serve</code>
          gives you
          <code>alice</code>
          and
          <code>bob</code>
          accounts; use
          <code>ignite chain serve --reset-once</code>
          if you change
          <code>config.yml</code>.
        </li>
        <li>
          Use the faucet (
          <code>http://localhost:4500</code>
          ) or CLI to send RETRO to any address, then refresh this page.
        </li>
        <li>
          All values are shown in raw Cosmos coin units (e.g.
          <code>uretro</code>
          ); divide by
          <code>1_000_000</code>
          for display as RETRO.
        </li>
      </ul>
    </div>
  </div>
</template>
