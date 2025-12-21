# x/btcstake

Deposit an IBC-denominated WBTC into a vault and receive `stwbtc` (receipt token) 1:1 in base units. Rewards (in `uretro`) accrue pro-rata when funded via `MsgFundRewards` and can be claimed with `MsgClaimRewards`.

- Underlying token: configured by `params.allowed_denom` (expected to be an `ibc/<hash>` denom for WBTC).
- Receipt token: `stwbtc` (minted on deposit, burned on withdraw).
- Withdrawals: instant (burn `stwbtc`, release underlying).

## Configuring the IBC WBTC denom

The vault only accepts a single denom, `params.allowed_denom`. For IBC WBTC this will be the IBC denom hash for the specific channel/path, like:

- `ibc/<HASH>`

You can verify what the chain is configured to accept via:

- CLI: `retrochaind q btcstake params`
- REST: `GET /btcstake/v1/params`

## Notes

- The `stake` tx takes an integer amount in base units of `params.allowed_denom` (do not include a denom suffix).

## Local smoketest (no IBC needed)

For local testing you can treat any `ibc/...` string as a denom and fund it directly in genesis.

1) Set allowed denom in genesis:

```bash
jq '.app_state.btcstake.params.allowed_denom="ibc/DEMO_WBTC_HASH"' \
	"$HOME/config/genesis.json" > /tmp/genesis.json && mv /tmp/genesis.json "$HOME/config/genesis.json"
```

2) Fund an account with that denom in genesis (example amount `1000000` base units):

```bash
jq '(.app_state.bank.balances[] | select(.address=="<ADDR>") | .coins) += [{"denom":"ibc/DEMO_WBTC_HASH","amount":"1000000"}]' \
	"$HOME/config/genesis.json" > /tmp/genesis.json && mv /tmp/genesis.json "$HOME/config/genesis.json"
```

Then, once the chain is running:

```bash
retrochaind tx btcstake stake 1000 --from <key> ...
retrochaind tx btcstake unstake 400 --from <key> ...
```
