# WBTC Staking Page (Explorer) - Build Notes for Copilot

Goal: add a WBTC staking view to the explorer that talks to the `btcstake` module on `retrochain-mainnet`. Users should see pool stats, their position, and be able to stake/unstake and claim rewards.

## APIs to use (gRPC-Gateway REST)
- Params: `GET /retrochain/btcstake/v1/params` (also available at `/btcstake/v1/params`)
- Pool: `GET /retrochain/btcstake/v1/pool` → fields: `allowed_denom`, `total_staked_amount`, `reward_balance_uretro`, `undistributed_uretro`, `reward_index`
- User stake: `GET /retrochain/btcstake/v1/stake/{address}` → `staked_amount`
- User pending rewards: `GET /retrochain/btcstake/v1/pending_rewards/{address}` → `pending_uretro`

## Tx messages (sign/broadcast via cosmjs)
- `retrochain.btcstake.v1.MsgStake` `{ creator, amount }`
- `retrochain.btcstake.v1.MsgUnstake` `{ creator, amount }`
- `retrochain.btcstake.v1.MsgClaimRewards` `{ creator }`
- `retrochain.btcstake.v1.MsgFundRewards` is authority-facing; do not expose on the user page.
- Note: `amount` is an integer string in base units of `params.allowed_denom` (IBC WBTC). The denom string is NOT included in the msg.

## UI layout
- Header: “Stake WBTC” with network status (RPC/REST endpoint health).
- Cards:
  - Pool stats: `allowed_denom`, `total_staked_amount` (format as WBTC with the correct exponent), reward pool balances (`reward_balance_uretro`, `undistributed_uretro`).
  - Your stake: current `staked_amount`, `pending_uretro` (convert to RETRO), last refreshed timestamp.
- Actions:
  - Stake form: input amount (WBTC), convert to base units before sending MsgStake.
  - Unstake form: input amount (WBTC), max button = current staked.
  - Claim rewards button (disable if pending == 0).
- Error/output toasts for tx failures; success shows tx hash and triggers a refresh of queries.

## Amount handling
- `allowed_denom` will be an IBC hash like `ibc/<HASH>`; assume underlying WBTC has 8 decimals. Convert user-friendly WBTC → base units by `amount * 10^8` (integer). Show a warning if params.allowed_denom is empty or not an IBC denom.

Current RetroChain WBTC denom (Osmosis factory WBTC over `transfer/channel-1`):
- `ibc/CF57A83CED6CEC7D706631B5DC53ABC21B7EDA7DF7490732B4361E6D5DD19C73`
- Rewards are in `uretro` (6 decimals). Convert to RETRO for display; send `pending_uretro` as-is for MsgClaimRewards (no amount field). Funding (ops-only) is also in `uretro`.

## Data refresh strategy
- On load: fetch params → pool → user stake/pending in parallel once wallet address is known.
- After any tx success: refetch pool + user stake + pending.
- Poll every 20–30s while the page is open, but back off on errors.

## Tx pipeline (cosmjs)
- Use `SigningStargateClient` with the RetroChain RPC.
- Msg type URLs:
  - `/retrochain.btcstake.v1.MsgStake`
  - `/retrochain.btcstake.v1.MsgUnstake`
  - `/retrochain.btcstake.v1.MsgClaimRewards`
- Fee suggestion: medium gas price (e.g., `0.025uretro`) and gas adjustment 1.3. Make fee configurable per env.
- Denoms: do not attach `allowed_denom` in the msg; only the `amount` field (string).

## Validation
- Stake/Unstake: require wallet connected; amount > 0; integer base units after conversion; for unstake ensure amount ≤ staked.
- Disable actions while a tx is in-flight.
- Show the `allowed_denom` hash somewhere so users know which channel the WBTC is expected to come from.

## Edge cases
- Params missing or `allowed_denom` empty → show an error banner and disable forms.
- If pool is funded while total stake is zero, rewards park as undistributed until someone stakes; pending stays at 0 until that happens.
- REST/RPC failures → show offline state and retry/backoff.

## Styling hints (Explorer)
- Keep consistent with existing explorer theme: use cards with concise labels, monospace for denoms/hashes, and green/orange badges for “active/offline”.
- Add a “View on chain” link to the pool stats (points to `/btcstake/v1/pool` endpoint in a new tab).

## Example REST shapes
- Pool response:
  ```json
  {
    "allowed_denom": "ibc/<HASH>",
    "total_staked_amount": "123456789",
    "reward_balance_uretro": "0",
    "undistributed_uretro": "0",
    "reward_index": "0.0"
  }
  ```
- Stake response:
  ```json
  { "staked_amount": "250000000" }
  ```
- Pending rewards:
  ```json
  { "pending_uretro": "12345" }
  ```
