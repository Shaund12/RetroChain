# Genesis NFT Airdrop (RetroChain)

Yes — RetroChain includes the native Cosmos SDK NFT module (`x/nft`). You can pre-mint NFTs **at genesis** to specific addresses by editing `genesis.json`.

Important limitation:
- In this chain configuration, the `x/nft` module exposes a tx for **sending** NFTs (`tx nft send`), but **does not expose txs to mint/issue** classes or NFTs.
- Practically, that means **native NFTs must be created at genesis** (or via custom module code in a future upgrade).

If you want to mint NFTs on the already-running chain today, use **CosmWasm CW721** instead.

---

## Option A — True genesis NFTs (native `x/nft`)

Use this if:
- You’re launching a new network / resetting a testnet / preparing a future mainnet genesis.
- You want NFTs queryable via standard endpoints like `/cosmos/nft/v1beta1/*`.

### Genesis JSON structure

The NFT module genesis state lives at:

- `app_state.nft`

Schema (as JSON):

- `app_state.nft.classes[]`
  - `id`, `name`, `symbol`, `description`, `uri`, `uri_hash` (and optional `data`)
- `app_state.nft.entries[]`
  - `owner`
  - `nfts[]` where each NFT has: `class_id`, `id`, `uri`, `uri_hash` (and optional `data`)

### Minimal example snippet

```json
{
  "classes": [
    {
      "id": "retro-genesis-2025",
      "name": "RetroChain Genesis",
      "symbol": "GENESIS",
      "description": "Genesis NFT for early RetroChain wallets",
      "uri": "ipfs://REPLACE_ME/class.json",
      "uri_hash": "",
      "data": null
    }
  ],
  "entries": [
    {
      "owner": "cosmos1...",
      "nfts": [
        {
          "class_id": "retro-genesis-2025",
          "id": "genesis-0001",
          "uri": "ipfs://REPLACE_ME/nft-0001.json",
          "uri_hash": "",
          "data": null
        }
      ]
    }
  ]
}
```

### Generate a correct snippet automatically

Use:
- `tools/genesis_nft_airdrop.py`

Example:

```bash
python3 tools/genesis_nft_airdrop.py \
  --class-id retro-genesis-2025 \
  --class-name "RetroChain Genesis" \
  --class-symbol GENESIS \
  --class-description "Genesis NFT for early RetroChain wallets" \
  --class-uri "ipfs://REPLACE_ME/class.json" \
  --token-uri "ipfs://REPLACE_ME/nft.json" \
  --owner cosmos1fscvf7rphx477z6vd4sxsusm2u8a70kewvc8wy \
  --owner cosmos1exqr633rjzls2h4txrpu0cxhnxx0dquylf074x
```

Then merge the produced JSON into `genesis.json` under `app_state.nft` before starting the chain.

---

## "Any wallet before block 1,000,000 gets one" (what this means)

That rule is a great definition for an **early-wallet airdrop on a running chain**, but it is **not something you can bake into genesis** (because at genesis you don't yet know which wallets will appear by height 1,000,000).

So there are two practical ways to do it:

1) **CW721 airdrop at/after height 1,000,000** (recommended for an already-running chain)
- Use CosmWasm to mint NFTs after launch.

2) **Chain upgrade that mints native `x/nft` NFTs at a specific height** (more work)
- Requires adding an upgrade handler that calls the nft keeper to create the class + mint tokens.

### Deriving the eligible wallet list (SQLite indexer)

If you want “wallets before height N” in a deterministic way, you need an address set derived from chain history.

This repo’s SQLite indexer already stores ABCI events per block/tx. A simple deterministic eligibility definition is:

- **Eligible = any `cosmos1...` address that appears in any event attribute at heights <= N**

Generate that list from the indexer DB:

```bash
python3 tools/eligible_wallets_before_height.py \
  --db ~/.retrochain/indexer.sqlite \
  --max-height 1000000 \
  > owners.txt
```

You can then use `owners.txt` as the input owner list for whatever minting mechanism you choose (CW721 txs, or a chain upgrade).

---

## Option B — “Genesis” NFT collection minted on the live chain (CW721)

Use this if:
- The chain is already running and you want to drop NFTs to early wallets now.

Approach:
- Upload and instantiate a CW721 contract in `x/wasm`.
- Mint tokens to the early-wallet list.

Note:
- This is **not** `x/nft` native NFTs; it’s contract NFTs.
- Whether an explorer shows these depends on whether it supports CosmWasm contract indexing.

---

## Suggested “cool” airdrop ideas (minimal)

- **One per early wallet:** “Retro Genesis Pass” NFT.
- **Rarity by role:** treasury wallets get a “Founder” variant; testers get “Early Player” variant.
- Metadata host: IPFS (recommended) using `uri` fields.
