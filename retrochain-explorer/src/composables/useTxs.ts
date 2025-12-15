// src/composables/useTxs.ts
import { ref } from "vue";
import { useApi } from "./useApi";
import { defaultRegistryTypes } from "@cosmjs/stargate";
import { fromBase64 } from "@cosmjs/encoding";
import { Registry, decodeTxRaw } from "@cosmjs/proto-signing";
import { isIndexerEnabled, useIndexerApi } from "./useApi";

const registry = new Registry(defaultRegistryTypes);

export interface TxSummary {
  hash: string;
  height: number;
  codespace?: string;
  code?: number;
  gasWanted?: string;
  gasUsed?: string;
  timestamp?: string;
}

export function useTxs() {
  const api = useApi();
  const indexerApi = useIndexerApi();
  const txs = ref<TxSummary[]>([]);
  const loading = ref(false);
  const error = ref<string | null>(null);

  // NOTE: pagination.limit is the correct param for this endpoint.
  const searchRecent = async (limit = 20) => {
    loading.value = true;
    error.value = null;
    txs.value = []; // Clear previous data
    
    try {
      if (isIndexerEnabled()) {
        const res = await indexerApi.get("/v1/txs", {
          params: { limit, offset: 0, order: "desc" }
        });
        const items = (res.data?.items as any[]) || [];
        txs.value = items.map((t: any) => ({
          hash: String(t.tx_hash || t.hash || ""),
          height: Number(t.height || 0),
          code: typeof t.code === "number" ? t.code : (t.code != null ? Number(t.code) : undefined),
          gasWanted: t.gas_wanted != null ? String(t.gas_wanted) : undefined,
          gasUsed: t.gas_used != null ? String(t.gas_used) : undefined,
          timestamp: t.block_time ? String(t.block_time) : undefined
        }));
        return;
      }

      const base = api.defaults.baseURL || "";
      const proxyAvailable = !base || base.startsWith("/");

      if (proxyAvailable) {
        // Try fast aggregator first
        const fast = await api.get(`/recent-txs`, { params: { limit } });
        if (Array.isArray(fast.data?.txs) && fast.data.txs.length) {
          txs.value = fast.data.txs.map((t: any) => ({
            hash: t.hash,
            height: t.height,
            timestamp: t.timestamp
          }));
          return;
        }
        throw new Error("fallback-scan");
      }

      throw new Error("skip-proxy");
    } catch (e: any) {
      if (e?.message !== "fallback-scan" && e?.message !== "skip-proxy") {
        console.error("Failed to fetch transactions:", e);
      }
      // Fallback: scan recent blocks, parse base64 txs, compute hash and optionally enrich via /txs/{hash}
      try {
        const latestRes = await api.get(`/cosmos/base/tendermint/v1beta1/blocks/latest`);
        const latestBlock = latestRes.data?.block;
        const latest = parseInt(latestBlock?.header?.height ?? "0", 10);
        const collected: TxSummary[] = [];

        // helper: compute SHA-256 hash (uppercase hex) from base64 tx bytes
        const hashFromBase64 = async (b64: string) => {
          const bytes = Uint8Array.from(atob(b64), c => c.charCodeAt(0));
          const digest = await crypto.subtle.digest("SHA-256", bytes);
          return Array.from(new Uint8Array(digest)).map(b => b.toString(16).padStart(2, "0")).join("").toUpperCase();
        };

        for (let h = latest; h > 0 && collected.length < limit; h--) {
          const bRes = await api.get(`/cosmos/base/tendermint/v1beta1/blocks/${h}`);
          const blk = bRes.data?.block;
          const header = blk?.header;
          const time = header?.time as string | undefined;
          const txList: string[] = blk?.data?.txs || [];
          if (!txList.length) continue;

          for (const raw of txList) {
            try {
              const hash = await hashFromBase64(raw);
              let summary: TxSummary = { hash, height: h, timestamp: time };
              // Enrich from /txs/{hash} if available
              try {
                const d = await api.get(`/cosmos/tx/v1beta1/txs/${hash}`);
                const r = d.data?.tx_response;
                if (r) {
                  summary = {
                    hash: r.txhash || hash,
                    height: parseInt(r.height ?? String(h), 10),
                    codespace: r.codespace,
                    code: r.code,
                    gasWanted: r.gas_wanted,
                    gasUsed: r.gas_used,
                    timestamp: r.timestamp || time
                  };
                }
              } catch {}
              collected.push(summary);
              if (collected.length >= limit) break;
            } catch {}
          }
        }

        txs.value = collected.slice(0, limit);
        error.value = null;
      } catch (fallbackErr: any) {
        // Give up gracefully
        error.value = fallbackErr?.message ?? e?.message ?? String(e);
        txs.value = [];
      }
    } finally {
      loading.value = false;
    }
  };

  const getTx = async (hash: string) => {
    if (isIndexerEnabled()) {
      const res = await indexerApi.get(`/v1/txs/${hash}`);
      const row = res.data || {};

      const txB64 = String(row.tx_b64 || "");
      const decoded = txB64 ? decodeTxRaw(fromBase64(txB64)) : null;

      const decodedMessages = decoded
        ? decoded.body.messages.map((anyMsg) => {
            try {
              const decodedMsg: any = registry.decode(anyMsg);
              return { "@type": anyMsg.typeUrl, ...decodedMsg };
            } catch {
              return { "@type": anyMsg.typeUrl };
            }
          })
        : [];

      const tx = decoded
        ? {
            body: { ...decoded.body, messages: decodedMessages },
            auth_info: decoded.authInfo,
            signatures: decoded.signatures
          }
        : null;

      const txResponse = {
        txhash: String(row.tx_hash || hash).toUpperCase(),
        height: String(row.height ?? ""),
        code: row.code ?? 0,
        gas_wanted: row.gas_wanted != null ? String(row.gas_wanted) : undefined,
        gas_used: row.gas_used != null ? String(row.gas_used) : undefined,
        raw_log: row.raw_log ?? "",
        timestamp: row.block_time ?? undefined,
        logs: [] as any[]
      };

      return {
        tx,
        tx_response: txResponse,
        events: row.events || []
      };
    }

    const res = await api.get(`/cosmos/tx/v1beta1/txs/${hash}`);
    return res.data;
  };

  const searchByAddress = async (address: string, limit = 20) => {
    loading.value = true;
    error.value = null;
    try {
      const events = [
        `message.sender='${address}'`,
        `transfer.recipient='${address}'`,
        `transfer.sender='${address}'`
      ];

      const res = await api.get(`/cosmos/tx/v1beta1/txs`, {
        params: {
          events,
          order_by: "ORDER_BY_DESC",
          "pagination.limit": limit
        },
        paramsSerializer: (params) => {
          const search = new URLSearchParams();
          const eventList = Array.isArray(params.events) ? params.events : [];
          eventList.forEach((event: string) => search.append("events", event));
          if (params.order_by) search.append("order_by", params.order_by);
          if (params["pagination.limit"]) {
            search.append("pagination.limit", String(params["pagination.limit"]));
          }
          return search.toString();
        }
      });
      
      const raw = res.data?.tx_responses ?? [];
      const seen = new Set<string>();
      txs.value = raw.reduce((list: TxSummary[], resp: any) => {
        const hash = resp.txhash;
        if (!hash || seen.has(hash)) return list;
        seen.add(hash);
        list.push({
          hash,
          height: parseInt(resp.height ?? "0", 10),
          codespace: resp.codespace,
          code: resp.code,
          gasWanted: resp.gas_wanted,
          gasUsed: resp.gas_used,
          timestamp: resp.timestamp
        });
        return list;
      }, []);
    } catch (e: any) {
      error.value = e?.message ?? String(e);
      txs.value = [];
    } finally {
      loading.value = false;
    }
  };

  return { txs, loading, error, searchRecent, getTx, searchByAddress };
}
