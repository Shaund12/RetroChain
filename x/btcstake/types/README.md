# x/btcstake

Stake Cosmos WBTC (IBC denom) and earn `uretro` rewards.

- Staking token: configured by `params.allowed_denom` (expected to be an `ibc/...` denom).
- Rewards token: `uretro`.
- Unstaking: instant.

Funding rewards: call `tx btcstake fund-rewards [amount] --from <key>` to move `amount` `uretro` into the module reward pool.

This module uses a global reward index + per-user index to track pro-rata rewards without iterating over all stakers.
