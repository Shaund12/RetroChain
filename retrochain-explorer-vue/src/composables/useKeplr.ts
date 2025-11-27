// src/composables/useKeplr.ts
import { ref } from "vue";

declare global {
  interface Window {
    keplr?: any;
    getOfflineSigner?: (chainId: string) => any;
    getOfflineSignerAuto?: (chainId: string) => Promise<any>;
  }
}

const isAvailable = ref(false);
const address = ref<string | null>(null);
const connecting = ref(false);
const error = ref<string | null>(null);

// ==== RetroChain chain info for Keplr ====
// Tweak ports / denom / chainId if you changed them in config.yml
const CHAIN_ID = "retrochain-arcade-1";

const CHAIN_INFO = {
  chainId: CHAIN_ID,
  chainName: "RetroChain Arcade Devnet",
  rpc: "http://localhost:26657",
  rest: "http://localhost:1317",
  bip44: {
    coinType: 118
  },
  bech32Config: {
    bech32PrefixAccAddr: "cosmos",
    bech32PrefixAccPub: "cosmospub",
    bech32PrefixValAddr: "cosmosvaloper",
    bech32PrefixValPub: "cosmosvaloperpub",
    bech32PrefixConsAddr: "cosmosvalcons",
    bech32PrefixConsPub: "cosmosvalconspub"
  },
  currencies: [
    {
      coinDenom: "RETRO",
      coinMinimalDenom: "uretro",
      coinDecimals: 6,
      coinGeckoId: undefined
    }
  ],
  feeCurrencies: [
    {
      coinDenom: "RETRO",
      coinMinimalDenom: "uretro",
      coinDecimals: 6,
      coinGeckoId: undefined,
      gasPriceStep: {
        low: 0.025,
        average: 0.03,
        high: 0.04
      }
    }
  ],
  stakeCurrency: {
    coinDenom: "RETRO",
    coinMinimalDenom: "uretro",
    coinDecimals: 6
  },
  features: ["cosmwasm"], // you can trim this if you didn't enable wasm
  coinType: 118
};

export function useKeplr() {
  const checkAvailability = () => {
    if (typeof window === "undefined") {
      isAvailable.value = false;
      return;
    }
    isAvailable.value = !!window.keplr;
  };

  const suggestChain = async () => {
    if (!window.keplr) {
      throw new Error("Keplr extension not found.");
    }

    // Some versions gate this under experimentalSuggestChain
    if (!window.keplr.experimentalSuggestChain) {
      throw new Error("Keplr does not support experimentalSuggestChain.");
    }

    await window.keplr.experimentalSuggestChain(CHAIN_INFO);
  };

  const connect = async () => {
    try {
      connecting.value = true;
      error.value = null;
      checkAvailability();

      if (!isAvailable.value) {
        throw new Error("Keplr extension not detected. Install it and reload.");
      }

      // Add chain to Keplr, then enable it
      await suggestChain();
      await window.keplr.enable(CHAIN_ID);

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
    // Keplr doesn't have a "disconnect", we just clear local state
    address.value = null;
  };

  // run once on import
  checkAvailability();

  return {
    CHAIN_ID,
    isAvailable,
    address,
    connecting,
    error,
    connect,
    disconnect,
    checkAvailability
  };
}
