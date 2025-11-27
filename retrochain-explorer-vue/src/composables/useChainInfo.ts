import { ref } from "vue";
import { useApi } from "./useApi";
import dayjs from "dayjs";

export interface ChainInfo {
  latestBlockHeight: number | null;
  latestBlockTime: string | null;
  chainId: string | null;
}

const info = ref<ChainInfo>({
  latestBlockHeight: null,
  latestBlockTime: null,
  chainId: null
});

const loading = ref(false);
const error = ref<string | null>(null);

export function useChainInfo() {
  const api = useApi();

  const refresh = async () => {
    loading.value = true;
    error.value = null;
    try {
      const [nodeRes, blockRes] = await Promise.all([
        api.get("/cosmos/base/tendermint/v1beta1/node_info"),
        api.get("/cosmos/base/tendermint/v1beta1/blocks/latest")
      ]);

      const nodeInfo = nodeRes.data?.default_node_info;
      const block = blockRes.data?.block;

      info.value.chainId = nodeInfo?.network ?? null;

      if (block) {
        const height = parseInt(block.header.height, 10);
        const time = block.header.time;
        info.value.latestBlockHeight = height;
        info.value.latestBlockTime = time
          ? dayjs(time).format("YYYY-MM-DD HH:mm:ss")
          : null;
      }
    } catch (e: any) {
      error.value = e?.message ?? String(e);
    } finally {
      loading.value = false;
    }
  };

  return {
    info,
    loading,
    error,
    refresh
  };
}
