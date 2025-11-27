import { ref } from "vue";
import { useApi } from "./useApi";

export interface BlockSummary {
  height: number;
  hash: string;
  time: string;
  txs: number;
  proposerAddress?: string;
}

const loading = ref(false);
const error = ref<string | null>(null);
const blocks = ref<BlockSummary[]>([]);

export function useBlocks() {
  const api = useApi();

  // Helper: fetch a single block by height (used by detail + list)
  const fetchByHeight = async (height: number) => {
    const res = await api.get(
      `/cosmos/base/tendermint/v1beta1/blocks/${height}`
    );
    return res.data;
  };

  // Fetch latest N blocks by walking down from latest height
  const fetchLatest = async (limit = 20) => {
    loading.value = true;
    error.value = null;

    try {
      // 1) Get latest block so we know the tip height
      const latestRes = await api.get(
        "/cosmos/base/tendermint/v1beta1/blocks/latest"
      );
      const latestBlock = latestRes.data?.block;
      if (!latestBlock) {
        throw new Error("Latest block not found");
      }

      const latestHeight = parseInt(latestBlock.header.height ?? "0", 10);
      if (!latestHeight || Number.isNaN(latestHeight)) {
        throw new Error("Invalid latest block height");
      }

      // 2) Decide which heights to fetch
      const heights: number[] = [];
      for (
        let h = latestHeight;
        h > 0 && heights.length < limit;
        h -= 1
      ) {
        heights.push(h);
      }

      // 3) Fetch each block in parallel
      const results = await Promise.all(
        heights.map((h) =>
          api
            .get(`/cosmos/base/tendermint/v1beta1/blocks/${h}`)
            .then((r) => ({ height: h, data: r.data }))
        )
      );

      // 4) Map into BlockSummary[]
      blocks.value = results.map((entry) => {
        const blk = entry.data.block;
        const header = blk?.header ?? {};
        return {
          height: entry.height,
          hash: entry.data.block_id?.hash ?? "",
          time: header.time ?? "",
          txs: blk?.data?.txs?.length ?? 0,
          proposerAddress: header.proposer_address ?? undefined
        } as BlockSummary;
      });
    } catch (e: any) {
      error.value = e?.message ?? String(e);
      blocks.value = [];
    } finally {
      loading.value = false;
    }
  };

  return {
    blocks,
    loading,
    error,
    fetchLatest,
    fetchByHeight
  };
}
