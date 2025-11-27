<script setup lang="ts">
import { RouterView } from "vue-router";
import RcHeader from "@/components/RcHeader.vue";
import RcToastHost from "@/components/RcToastHost.vue";
</script>

<template>
  <div class="min-h-screen flex flex-col bg-slate-950 text-slate-100">
    <RcHeader />
    <main class="flex-1 max-w-7xl mx-auto w-full px-4 sm:px-6 lg:px-8 py-6">
      <RouterView />
    </main>
    <footer class="border-t border-slate-800 py-4 text-center text-xs text-slate-500">
      RetroChain Arcade Explorer · Local REST: <code>http://localhost:1317</code>
    </footer>
    <RcToastHost />
  </div>
</template>
