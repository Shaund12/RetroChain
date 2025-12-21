# Retrochain Indexer DB + Read API

This repo now includes a lightweight SQLite indexer and a small HTTP read API for explorer usage.

## 1) Index the chain to SQLite

Use the **SQL Indexer** tab in `tools/gui_node_manager.py`.

- **RPC URL**: `http://localhost:26657`
- **DB path**: `~/.retrochain/indexer.sqlite`
- **Start height**: leave empty to resume, or set a specific height.

The DB stores:
- `blocks` (block metadata + raw `/block` + raw `/block_results`)
- `txs` (tx hash, height, index, gas/code, raw_log, tx events)
- `events` (begin/end block events + tx events)

## 2) Serve the DB to your explorer (no existing endpoints changed)

Run the read API (or start it from the **SQL Indexer** tab):

```bash
python3 tools/indexer_api.py \
  --db ~/.retrochain/indexer.sqlite \
  --listen 127.0.0.1:8081
```

### Endpoints

- `GET /v1/health`
- `GET /v1/status`
- `GET /v1/blocks?limit=20&offset=0&order=desc`
- `GET /v1/blocks/<height>?include_raw=1`
- `GET /v1/txs?limit=50&offset=0&order=desc&height=`
- `GET /v1/txs/<TX_HASH>`
- `GET /v1/events?height=&tx_hash=&type=&source=&limit=&offset=&order=asc`

CORS is **disabled by default**.

If your browser-based explorer runs at `retrochain.ddns.net`, allowlist it:

```bash
INDEXER_API_CORS_ORIGINS="https://retrochain.ddns.net,http://retrochain.ddns.net" \
  python3 tools/indexer_api.py --db ~/.retrochain/indexer.sqlite --listen 127.0.0.1:8081
```

You can also pass `--cors-origins` directly. Use `*` only for local/dev.

## 3) Resetting the DB

In the **SQL Indexer** tab, **Reset DB** renames the SQLite file to a timestamped backup and removes any `-wal`/`-shm` sidecars.
