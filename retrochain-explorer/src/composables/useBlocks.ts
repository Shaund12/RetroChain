import { ref } from "vue";
import { useApi } from "./useApi";
import { isIndexerEnabled, useIndexerApi } from "./useApi";

export interface BlockSummary {
  height: number;
  hash: string;
  time: string;
  txs: number;
  proposerAddress?: string;
}

export function useBlocks() {
  const api = useApi();
  const indexerApi = useIndexerApi();
  const loading = ref(false);
  const error = ref<string | null>(null);
  const blocks = ref<BlockSummary[]>([]);

  // Helper: fetch a single block by height (used by detail + list)
  const fetchByHeight = async (height: number) => {
    if (isIndexerEnabled()) {
      const res = await indexerApi.get(`/v1/blocks/${height}`, {
        params: { include_raw: 1 }
      });
      return res.data;
    }

    const res = await api.get(`/cosmos/base/tendermint/v1beta1/blocks/${height}`);
    return res.data;
  };

  // Fetch latest N blocks by walking down from latest height
  const fetchLatest = async (limit = 20) => {
    loading.value = true;
    error.value = null;

    try {
      if (isIndexerEnabled()) {
        const res = await indexerApi.get("/v1/blocks", {
          params: { limit, offset: 0, order: "desc" }
        });
        const items = (res.data?.items as any[]) || [];
        blocks.value = items.map((b: any) =>
          ({
            height: Number(b.height || 0),
            hash: String(b.block_id_hash || ""),
            time: String(b.time || ""),
            txs: Number(b.tx_count || 0),
            proposerAddress: b.proposer_address ? String(b.proposer_address) : undefined
          }) satisfies BlockSummary
        );
        return;
      }

      // Chain REST fallback
      const latestRes = await api.get("/cosmos/base/tendermint/v1beta1/blocks/latest");
      const latestBlock = latestRes.data?.block;
      if (!latestBlock) throw new Error("Latest block not found");

      const latestHeight = parseInt(latestBlock.header.height ?? "0", 10);
      if (!latestHeight || Number.isNaN(latestHeight)) throw new Error("Invalid latest block height");

      const heights: number[] = [];
      for (let h = latestHeight; h > 0 && heights.length < limit; h -= 1) heights.push(h);

      const results = await Promise.all(
        heights.map((h) => api.get(`/cosmos/base/tendermint/v1beta1/blocks/${h}`).then((r) => ({ height: h, data: r.data })))
      );

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
