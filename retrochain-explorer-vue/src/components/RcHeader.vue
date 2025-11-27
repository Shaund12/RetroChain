<script setup lang="ts">
import { computed } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useKeplr } from "@/composables/useKeplr";

const route = useRoute();
const router = useRouter();
const { installed, connected, address, loading, connect, disconnect } = useKeplr();

const navItems = [
  { label: "Overview", to: { name: "home" } },
  { label: "Blocks", to: { name: "blocks" } },
  { label: "Transactions", to: { name: "txs" } },
  { label: "Accounts", to: { name: "account" } }
];

const isActive = (to: any) =>
  computed(() => route.name === to.name);

const shortAddress = computed(() => {
  if (!address.value) return "";
  return `${address.value.slice(0, 8)}…${address.value.slice(-4)}`;
});
</script>

<template>
  <header class="border-b border-slate-800 bg-slate-950/95 backdrop-blur">
    <div
      class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-14 flex items-center justify-between gap-4"
    >
      <!-- Logo / title -->
      <button
        class="flex items-center gap-2 group"
        @click="router.push({ name: 'home' })"
      >
        <div
          class="h-8 w-8 rounded-xl bg-gradient-to-br from-emerald-500 via-cyan-400 to-indigo-500 flex items-center justify-center text-xs font-black shadow-lg shadow-emerald-500/50"
        >
          RC
        </div>
        <div class="flex flex-col items-start leading-tight">
          <span class="text-sm font-semibold">
            RetroChain
            <span
              class="ml-1 text-[10px] px-1.5 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/40 uppercase tracking-[0.15em]"
            >
              Arcade
            </span>
          </span>
          <span class="text-[10px] text-slate-400 tracking-wide">
            Cosmos-SDK · Local devnet
          </span>
        </div>
      </button>

      <!-- Nav -->
      <nav class="flex items-center gap-1 text-xs sm:text-sm">
        <button
          v-for="item in navItems"
          :key="item.label"
          class="px-3 py-1.5 rounded-full border text-xs font-medium transition-colors"
          :class="
            isActive(item.to).value
              ? 'border-emerald-400 bg-emerald-500/10 text-emerald-200'
              : 'border-slate-700 hover:border-emerald-400 text-slate-300 hover:text-emerald-200'
          "
          @click="router.push(item.to)"
        >
          {{ item.label }}
        </button>
      </nav>

      <!-- Keplr connect -->
      <div class="flex items-center gap-2">
        <span v-if="!installed" class="text-[11px] text-slate-500 hidden sm:inline">
          Install Keplr to sign RETRO txs
        </span>

        <button
          v-if="!connected"
          class="btn btn-primary text-xs"
          :disabled="!installed || loading"
          @click="connect"
        >
          <span v-if="loading">Connecting…</span>
          <span v-else-if="installed">Connect Keplr</span>
          <span v-else>Keplr not found</span>
        </button>

        <button
          v-else
          class="btn text-xs border-emerald-400/70 text-emerald-200 bg-emerald-500/5"
          @click="disconnect"
        >
          {{ shortAddress }}
        </button>
      </div>
    </div>
  </header>
</template>
