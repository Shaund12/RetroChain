# RetroChain SQLite Indexer — Transactions (SQL Guide)

This guide is a **Copilot-facing** reference for reading **transactions** from the SQLite DB produced by `tools/sql_indexer.py`.

Scope (for now): **tx list + tx by hash + txs by height**.

## DB location

Default path used across tools:
- `~/.retrochain/indexer.sqlite`

Related docs:
- `tools/INDEXER_READ_API.md` (HTTP read API backed by the same DB)

## Schema (transactions)

Table: `txs`

Columns:
- `tx_hash` `TEXT PRIMARY KEY` — uppercase hex SHA-256 of the raw tx bytes (CometBFT/Tendermint tx hash)
- `height` `INTEGER NOT NULL`
- `tx_index` `INTEGER NOT NULL` — index within the block
- `code` `INTEGER` — `0` for success, non-zero for failure
- `gas_wanted` `INTEGER`
- `gas_used` `INTEGER`
- `tx_b64` `TEXT` — base64 tx bytes as provided in `/block`
- `raw_log` `TEXT` — tendermint raw log string
- `events_json` `TEXT NOT NULL` — JSON array of normalized tx events
- `indexed_at` `TEXT NOT NULL` — ISO8601 UTC

Helpful join for timestamp:
- Table `blocks(height PRIMARY KEY, time TEXT, ...)` contains `time` from the block header.

Indexes:
- `txs_height_idx ON txs(height)`

## Read-only connection (recommended)

Use read-only mode and `query_only`.

Python example:
```py
import os
import sqlite3

DB = os.path.expanduser("~/.retrochain/indexer.sqlite")

# URI mode=ro prevents writes.
conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=15)
conn.row_factory = sqlite3.Row
conn.execute("PRAGMA query_only=ON")
```

Notes:
- The indexer writes with WAL enabled; SQLite supports concurrent readers.
- Keep queries parameterized (`?`) to avoid SQL injection.

## Canonical queries

### 1) Latest transactions (paged)

Inputs: `limit`, `offset`

```sql
SELECT
  t.tx_hash,
  t.height,
  t.tx_index,
  t.code,
  t.gas_wanted,
  t.gas_used,
  t.raw_log,
  b.time AS block_time
FROM txs t
LEFT JOIN blocks b ON b.height = t.height
ORDER BY t.height DESC, t.tx_index DESC
LIMIT ? OFFSET ?;
```

### 2) Transactions at a specific height

Input: `height`

```sql
SELECT
  t.tx_hash,
  t.height,
  t.tx_index,
  t.code,
  t.gas_wanted,
  t.gas_used,
  t.raw_log,
  b.time AS block_time
FROM txs t
LEFT JOIN blocks b ON b.height = t.height
WHERE t.height = ?
ORDER BY t.tx_index ASC;
```

### 3) Transaction details by hash

Input: `tx_hash` (normalize to uppercase)

```sql
SELECT
  t.tx_hash,
  t.height,
  t.tx_index,
  t.code,
  t.gas_wanted,
  t.gas_used,
  t.tx_b64,
  t.raw_log,
  t.events_json,
  b.time AS block_time
FROM txs t
LEFT JOIN blocks b ON b.height = t.height
WHERE t.tx_hash = ?;
```

In code, parse `events_json` with JSON.

## Minimal Python helpers (copy/paste)

```py
import json

def list_txs(conn, limit=50, offset=0):
    rows = conn.execute(
        """
        SELECT t.tx_hash, t.height, t.tx_index, t.code, t.gas_wanted, t.gas_used,
               t.raw_log, b.time AS block_time
        FROM txs t
        LEFT JOIN blocks b ON b.height = t.height
        ORDER BY t.height DESC, t.tx_index DESC
        LIMIT ? OFFSET ?
        """,
        (int(limit), int(offset)),
    ).fetchall()
    return [dict(r) for r in rows]


def get_tx(conn, tx_hash: str):
    tx_hash = (tx_hash or "").strip().upper()
    row = conn.execute(
        """
        SELECT t.tx_hash, t.height, t.tx_index, t.code, t.gas_wanted, t.gas_used,
               t.tx_b64, t.raw_log, t.events_json, b.time AS block_time
        FROM txs t
        LEFT JOIN blocks b ON b.height = t.height
        WHERE t.tx_hash = ?
        """,
        (tx_hash,),
    ).fetchone()
    if not row:
        return None
    out = dict(row)
    try:
        out["events"] = json.loads(out.get("events_json") or "[]")
    except Exception:
        out["events"] = []
    out.pop("events_json", None)
    return out
```

## Important constraints

- The DB stores tx bytes (`tx_b64`) but does **not** decode messages. If you need decoded tx bodies, use the chain’s tx endpoint (`/cosmos/tx/v1beta1/txs/<hash>`) or add decoding later.
- Avoid relying on querying inside `events_json`/`attributes_json` unless you explicitly confirm SQLite JSON1 support in the runtime (otherwise keep transaction queries to the `txs` columns).
