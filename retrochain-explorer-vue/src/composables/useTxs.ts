// src/composables/useTxs.ts
import { ref } from "vue";
import { useApi } from "./useApi";

export interface TxSummary {
  hash: string;
  height: number;
  codespace?: string;
  code?: number;
  gasWanted?: string;
  gasUsed?: string;
  timestamp?: string;
}

const txs = ref<TxSummary[]>([]);
const loading = ref(false);
const error = ref<string | null>(null);

export function useTxs() {
  const api = useApi();

  // NOTE: pagination.limit is the correct param for this endpoint.
  const searchRecent = async (limit = 20) => {
    loading.value = true;
    error.value = null;
    try {
      const res = await api.get(
        `/cosmos/tx/v1beta1/txs?order_by=ORDER_BY_DESC&pagination.limit=${limit}`
      );
      const raw = res.data?.tx_responses ?? [];
      txs.value = raw.map((r: any) => ({
        hash: r.txhash,
        height: parseInt(r.height ?? "0", 10),
        codespace: r.codespace,
        code: r.code,
        gasWanted: r.gas_wanted,
        gasUsed: r.gas_used,
        timestamp: r.timestamp
      }));
    } catch (e: any) {
      error.value = e?.message ?? String(e);
    } finally {
      loading.value = false;
    }
  };

  const getTx = async (hash: string) => {
    const res = await api.get(`/cosmos/tx/v1beta1/txs/${hash}`);
    return res.data;
  };

  return { txs, loading, error, searchRecent, getTx };
}
