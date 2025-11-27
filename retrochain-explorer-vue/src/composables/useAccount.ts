import { ref } from "vue";
import { useApi } from "./useApi";

export interface Balance {
  denom: string;
  amount: string;
}

const loading = ref(false);
const error = ref<string | null>(null);
const balances = ref<Balance[]>([]);
const bech32Address = ref<string>("");

export function useAccount() {
  const api = useApi();

  const load = async (address: string) => {
    loading.value = true;
    error.value = null;
    balances.value = [];
    bech32Address.value = address;

    try {
      const [acc, bal] = await Promise.all([
        api.get(`/cosmos/auth/v1beta1/accounts/${address}`),
        api.get(`/cosmos/bank/v1beta1/balances/${address}`)
      ]);

      const rawBalances = bal.data?.balances ?? [];
      balances.value = rawBalances.map((b: any) => ({
        denom: b.denom,
        amount: b.amount
      }));
    } catch (e: any) {
      error.value = e?.message ?? String(e);
    } finally {
      loading.value = false;
    }
  };

  return { balances, bech32Address, loading, error, load };
}
