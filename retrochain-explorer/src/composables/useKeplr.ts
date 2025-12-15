// src/composables/useKeplr.ts
import { ref } from "vue";
import { useNetwork } from "./useNetwork";

declare global {
  interface Window {
    keplr?: {
      enable: (chainId: string) => Promise<void>;
      experimentalSuggestChain: (chainInfo: any) => Promise<void>;
      getOfflineSigner: (chainId: string) => any;
      getOfflineSignerAuto: (chainId: string) => Promise<any>;
      signAmino: (chainId: string, signer: string, signDoc: any) => Promise<any>;
      signDirect: (chainId: string, signer: string, signDoc: any) => Promise<any>;
      signAndBroadcast: (chainId: string, signer: string, msgs: any[], fee: any, memo?: string) => Promise<any>;
      getKey: (chainId: string) => Promise<any>;
    };
    getOfflineSigner?: (chainId: string) => any;
    getOfflineSignerAuto?: (chainId: string) => Promise<any>;
  }
}

const isAvailable = ref(false);
const address = ref<string | null>(null);
const connecting = ref(false);
const error = ref<string | null>(null);

const KEPLR_DEFAULT_OPTS = {
  sign: {
    preferNoSetFee: true,
    preferNoSetMemo: true
  }
};

function configureKeplrDefaults() {
  if (typeof window === "undefined") return;
  if (!window.keplr) return;
  const current = (window.keplr as any).defaultOptions || {};
  if (
    current?.sign?.preferNoSetFee === KEPLR_DEFAULT_OPTS.sign.preferNoSetFee &&
    current?.sign?.preferNoSetMemo === KEPLR_DEFAULT_OPTS.sign.preferNoSetMemo
  ) {
    return;
  }
  (window.keplr as any).defaultOptions = KEPLR_DEFAULT_OPTS;
}

if (typeof window !== "undefined" && window.keplr) {
  configureKeplrDefaults();
}

const { restBase, rpcBase } = useNetwork();

const CHAIN_ID = "retrochain-mainnet";
const CHAIN_NAME = "RetroChain Mainnet";
const DEFAULT_FEE_DENOM = "uretro";
const DEFAULT_GAS_PRICE = 0.03; // uretro per gas unit
const DEFAULT_GAS_ADJUSTMENT = 1.3;
const DEFAULT_GAS_PER_MSG = 150000;
const MIN_GAS_LIMIT = 200000;
const MIN_TOTAL_FEE = 5000; // minimum fee in uretro to satisfy chain requirements

function buildChainInfo() {
  // Build absolute URLs - Keplr requires full URIs
  const origin = typeof window !== "undefined" ? window.location.origin : "http://localhost:5173";
  const rpcUrl = rpcBase.value ? (rpcBase.value.startsWith('http') ? rpcBase.value : `${origin}${rpcBase.value}`) : `${origin}/rpc`;
  const restUrl = restBase.value ? (restBase.value.startsWith('http') ? restBase.value : `${origin}${restBase.value}`) : `${origin}/api`;
  
  return {
    chainId: CHAIN_ID,
    chainName: CHAIN_NAME,
    rpc: rpcUrl,
    rest: restUrl,
    bip44: { coinType: 118 },
    bech32Config: {
      bech32PrefixAccAddr: "cosmos",
      bech32PrefixAccPub: "cosmospub",
      bech32PrefixValAddr: "cosmosvaloper",
      bech32PrefixValPub: "cosmosvaloperpub",
      bech32PrefixConsAddr: "cosmosvalcons",
      bech32PrefixConsPub: "cosmosvalconspub"
    },
    currencies: [
      { coinDenom: "RETRO", coinMinimalDenom: "uretro", coinDecimals: 6 }
    ],
    feeCurrencies: [{
      coinDenom: "RETRO",
      coinMinimalDenom: "uretro",
      coinDecimals: 6,
      gasPriceStep: { low: 0.03, average: 0.035, high: 0.04 }
    }],
    stakeCurrency: { coinDenom: "RETRO", coinMinimalDenom: "uretro", coinDecimals: 6 },
    features: ["ibc-transfer", "cosmwasm"]
  } as any;
}

export function useKeplr() {
  const checkAvailability = () => {
    if (typeof window === "undefined") {
      isAvailable.value = false;
      return;
    }
    isAvailable.value = !!window.keplr && typeof window.keplr.enable === "function";
    if (isAvailable.value) configureKeplrDefaults();
  };

  const suggestChain = async () => {
    if (!window.keplr) {
      throw new Error("Keplr extension not found.");
    }

    if (!window.keplr.experimentalSuggestChain) {
      throw new Error("Keplr does not support experimentalSuggestChain.");
    }

    await window.keplr.experimentalSuggestChain(buildChainInfo());
  };

  const connect = async () => {
    try {
      connecting.value = true;
      error.value = null;
      checkAvailability();

      if (!isAvailable.value) {
        throw new Error("Keplr extension not detected. Install it and reload.");
      }

      const keplr = window.keplr;
      if (!keplr) {
        throw new Error("Keplr extension not detected. Install it and reload.");
      }

      configureKeplrDefaults();
      await suggestChain();
      await keplr.enable(CHAIN_ID);

      const offlineSigner =
        (await window.getOfflineSignerAuto?.(CHAIN_ID)) ||
        window.getOfflineSigner?.(CHAIN_ID);

      if (!offlineSigner) {
        throw new Error("Unable to get offline signer from Keplr.");
      }

      const accounts = await offlineSigner.getAccounts();
      if (!accounts || accounts.length === 0) {
        throw new Error("No accounts available in Keplr.");
      }

      address.value = accounts[0].address;
      return accounts[0].address;
    } catch (e: any) {
      const msg = e?.message ?? String(e);
      error.value = msg;
      throw e;
    } finally {
      connecting.value = false;
    }
  };

  const disconnect = () => {
    address.value = null;
  };

  const signAndBroadcast = async (chainId: string, msgs: any[], fee: any, memo = "") => {
    if (!window.keplr) throw new Error("Keplr not available");
    if (!address.value) throw new Error("Not connected to Keplr");

    try {
      const offlineSigner = window.keplr.getOfflineSigner(chainId);
      const accounts = await offlineSigner.getAccounts();

      const { SigningStargateClient } = await import("@cosmjs/stargate");
      
      // Build absolute HTTP(S) RPC endpoint for CosmJS
      const origin = typeof window !== "undefined" ? window.location.origin : "http://localhost:5173";
      let rpcEndpoint = rpcBase.value || "/rpc";
      
      // Convert to absolute URL if relative
      if (!rpcEndpoint.startsWith('http')) {
        rpcEndpoint = `${origin}${rpcEndpoint.startsWith('/') ? '' : '/'}${rpcEndpoint}`;
      }
      
      const client = await SigningStargateClient.connectWithSigner(rpcEndpoint, offlineSigner);

      const result = await client.signAndBroadcast(
        accounts[0].address,
        msgs,
        fee,
        memo
      );

      return result;
    } catch (e: any) {
      console.error("Transaction failed:", e);
      throw e;
    }
  };

  // REST-based signing alternative (workaround for RPC protobuf issues)
  const signAndBroadcastWithREST = async (chainId: string, msgs: any[], fee?: any, memo = "") => {
    if (!window.keplr) throw new Error("Keplr not available");
    if (!address.value) throw new Error("Not connected to Keplr");

    try {
      console.log("Starting REST-based transaction...");

      // Import required utilities
      const { useApi } = await import("./useApi");
      const api = useApi();
      
      // Get account info from REST API (this works!)
      console.log("Fetching account info from REST API...");
      const accountRes = await api.get(`/cosmos/auth/v1beta1/accounts/${address.value}`);
      const account = accountRes.data?.account;
      
      if (!account) {
        throw new Error("Account not found. Make sure your account is funded.");
      }

      // Extract account number and sequence
      let accountNumber: string;
      let sequence: string;
      
      if (account["@type"] === "/cosmos.auth.v1beta1.BaseAccount") {
        accountNumber = account.account_number;
        sequence = account.sequence || "0";
      } else if (account.base_account) {
        accountNumber = account.base_account.account_number;
        sequence = account.base_account.sequence || "0";
      } else {
        throw new Error("Unknown account type");
      }

      console.log("Account info:", { accountNumber, sequence });

      // Get offline signer from Keplr
      const offlineSigner = window.keplr.getOfflineSigner(chainId);
      const accounts = await offlineSigner.getAccounts();
      const signerAddress = accounts[0].address;
      const signerPubkey = accounts[0].pubkey;

      console.log("Signer address:", signerAddress);

      // Import CosmJS utilities
      const { Registry } = await import("@cosmjs/proto-signing");
      const { defaultRegistryTypes } = await import("@cosmjs/stargate");
      const { encodePubkey, makeAuthInfoBytes, makeSignDoc: makeSignDocDirect } = await import("@cosmjs/proto-signing");
      const { TxRaw, AuthInfo, TxBody } = await import("cosmjs-types/cosmos/tx/v1beta1/tx");
      const { toBase64, fromBase64 } = await import("@cosmjs/encoding");
      const { Int53 } = await import("@cosmjs/math");

      // Create registry with default Cosmos SDK types (includes staking, distribution, etc.)
      const registry = new Registry(defaultRegistryTypes);
      
      // Encode transaction body
      const anyMsgs = msgs.map(msg => registry.encodeAsAny(msg));
      const txBody = TxBody.fromPartial({
        messages: anyMsgs,
        memo: memo || ""
      });
      const txBodyBytes = TxBody.encode(txBody).finish();

      console.log("Transaction body encoded");

      // Encode public key
      const pubkey = encodePubkey({
        type: "tendermint/PubKeySecp256k1",
        value: toBase64(signerPubkey)
      });

      const sequenceNumber = Int53.fromString(sequence).toNumber();

      const signTx = async (feeValue: any, debugLabel?: string) => {
        const authInfoBytes = makeAuthInfoBytes(
          [{ pubkey, sequence: sequenceNumber }],
          feeValue.amount,
          parseInt(feeValue.gas, 10),
          feeValue.granter,
          feeValue.payer
        );

        const signDoc = makeSignDocDirect(
          txBodyBytes,
          authInfoBytes,
          chainId,
          Int53.fromString(accountNumber).toNumber()
        );

        const { signature, signed } = await offlineSigner.signDirect(
          signerAddress,
          signDoc,
          KEPLR_DEFAULT_OPTS as any
        );

        const txRaw = TxRaw.fromPartial({
          bodyBytes: signed.bodyBytes,
          authInfoBytes: signed.authInfoBytes,
          signatures: [fromBase64(signature.signature)]
        });

        const txBytes = TxRaw.encode(txRaw).finish();

        if (debugLabel) {
          const authInfo = AuthInfo.decode(txRaw.authInfoBytes);
          console.log(`${debugLabel} fee`, {
            amount: authInfo.fee?.amount?.map(c => ({ denom: c.denom, amount: c.amount })),
            gasLimit: authInfo.fee?.gasLimit?.toString()
          });
        }

        return { txRaw, txBytesBase64: toBase64(txBytes) };
      };

      const baseGasLimit = Math.max(MIN_GAS_LIMIT, msgs.length * DEFAULT_GAS_PER_MSG);
      let feeToUse = fee ?? null;

      if (!feeToUse) {
        const simulateFee = {
          amount: [{ denom: DEFAULT_FEE_DENOM, amount: "1" }],
          gas: baseGasLimit.toString()
        };

        try {
          const { txBytesBase64 } = await signTx(simulateFee, "simulate");
          const simulateRes = await api.post("/cosmos/tx/v1beta1/simulate", {
            tx_bytes: txBytesBase64
          });

          const gasUsed = Number(simulateRes.data?.gas_info?.gas_used ?? baseGasLimit);
          const adjustedGas = Math.ceil(gasUsed * DEFAULT_GAS_ADJUSTMENT);
          const feeAmount = Math.max(Math.ceil(adjustedGas * DEFAULT_GAS_PRICE), MIN_TOTAL_FEE).toString();

          feeToUse = {
            amount: [{ denom: DEFAULT_FEE_DENOM, amount: feeAmount }],
            gas: adjustedGas.toString()
          };

          console.log("Gas simulation success", { gasUsed, adjustedGas, feeAmount });
        } catch (simErr) {
          console.warn("Gas simulation failed, falling back to defaults:", simErr);
          const fallbackGas = baseGasLimit;
          feeToUse = {
            amount: [{ denom: DEFAULT_FEE_DENOM, amount: Math.max(Math.ceil(fallbackGas * DEFAULT_GAS_PRICE), MIN_TOTAL_FEE).toString() }],
            gas: fallbackGas.toString()
          };
        }
      }

      console.log("Using final fee", feeToUse);

      const { txBytesBase64 } = await signTx(feeToUse, "broadcast");

      console.log("Transaction encoded, length:", txBytesBase64.length);

      // Broadcast via REST API
      const broadcastRes = await api.post("/cosmos/tx/v1beta1/txs", {
        tx_bytes: txBytesBase64,
        mode: "BROADCAST_MODE_SYNC"
      });

      console.log("Broadcast response:", broadcastRes.data);

      const txResponse = broadcastRes.data?.tx_response;
      
      if (txResponse?.code !== 0) {
        throw new Error(txResponse?.raw_log || txResponse?.log || "Transaction failed");
      }

      return txResponse;
    } catch (e: any) {
      console.error("Transaction failed:", e);
      throw e;
    }
  };

  if (typeof window !== "undefined" && window.keplr && !window.keplr.signAndBroadcast) {
    window.keplr.signAndBroadcast = async (chainId: string, signer: string, msgs: any[], fee: any, memo = "") => {
      return signAndBroadcast(chainId, msgs, fee, memo);
    };
  }

  checkAvailability();

  if (typeof window !== "undefined") {
    setTimeout(() => {
      checkAvailability();
    }, 1000);
  }

  return {
    isAvailable,
    address,
    connecting,
    error,
    connect,
    disconnect,
    checkAvailability,
    signAndBroadcast,
    signAndBroadcastWithREST
  };
}
