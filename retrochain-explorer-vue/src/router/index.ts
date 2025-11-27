import { createRouter, createWebHistory, RouteRecordRaw } from "vue-router";
import HomeView from "@/views/HomeView.vue";
import BlocksView from "@/views/BlocksView.vue";
import BlockDetailView from "@/views/BlockDetailView.vue";
import TxsView from "@/views/TxsView.vue";
import TxDetailView from "@/views/TxDetailView.vue";
import AccountView from "@/views/AccountView.vue";

const routes: RouteRecordRaw[] = [
  { path: "/", name: "home", component: HomeView },
  { path: "/blocks", name: "blocks", component: BlocksView },
  { path: "/blocks/:height", name: "block-detail", component: BlockDetailView, props: true },
  { path: "/txs", name: "txs", component: TxsView },
  { path: "/txs/:hash", name: "tx-detail", component: TxDetailView, props: true },
  { path: "/account/:address?", name: "account", component: AccountView, props: true }
];

const router = createRouter({
  history: createWebHistory(),
  routes
});

export default router;
