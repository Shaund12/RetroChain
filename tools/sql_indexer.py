#!/usr/bin/env python3
"""Retrochain SQL Indexer (SQLite)

A lightweight, dependency-free indexer that pulls blocks + ABCI events from
CometBFT/Tendermint RPC and stores them in a local SQLite DB.

Design goals:
- No external Python deps (stdlib only)
- Resumable: persists last indexed height in DB
- Indexes: blocks, txs, begin/end block events, tx events (from block_results)

This is meant to power a simple explorer backend (read-side).
"""

from __future__ import annotations

import base64
import datetime
import hashlib
import json
import os
import sqlite3
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any


def _utc_now_iso() -> str:
    return datetime.datetime.now(datetime.UTC).isoformat()


def _join_url(base: str, path: str) -> str:
    base = (base or "").rstrip("/")
    if not base:
        raise ValueError("rpc_url is required")
    if not path.startswith("/"):
        path = "/" + path
    return base + path


def _http_get_json(url: str, timeout_s: float = 15.0) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:  # noqa: S310
        body = resp.read().decode("utf-8")
    return json.loads(body)


def _b64_to_bytes(value: str) -> bytes | None:
    if not value:
        return None
    try:
        return base64.b64decode(value, validate=False)
    except Exception:
        return None


def _maybe_b64_to_text(value: str) -> str:
    """Attempt to base64-decode to UTF-8 text; fall back to original value."""
    raw = _b64_to_bytes(value)
    if raw is None:
        return value
    try:
        text = raw.decode("utf-8")
    except Exception:
        return value
    # Avoid returning binary-ish strings.
    if any(ord(ch) < 9 for ch in text):
        return value
    return text


def _tx_hash_hex(tx_b64: str) -> str:
    tx_bytes = _b64_to_bytes(tx_b64) or b""
    return hashlib.sha256(tx_bytes).hexdigest().upper()


def _normalize_events(events: Any) -> list[dict[str, Any]]:
    if not events:
        return []
    if isinstance(events, list):
        out: list[dict[str, Any]] = []
        for ev in events:
            if not isinstance(ev, dict):
                continue
            ev_type = ev.get("type")
            attrs = ev.get("attributes")
            norm_attrs: list[dict[str, Any]] = []
            if isinstance(attrs, list):
                for a in attrs:
                    if not isinstance(a, dict):
                        continue
                    k = a.get("key", "")
                    v = a.get("value", "")
                    norm_attrs.append(
                        {
                            "key": k,
                            "value": v,
                            "key_text": _maybe_b64_to_text(k) if isinstance(k, str) else k,
                            "value_text": _maybe_b64_to_text(v) if isinstance(v, str) else v,
                            "index": a.get("index"),
                        }
                    )
            out.append({"type": ev_type, "attributes": norm_attrs})
        return out
    return []


@dataclass(frozen=True)
class IndexerConfig:
    rpc_url: str
    db_path: str
    poll_seconds: float = 2.0
    start_height: int | None = None
    timeout_seconds: float = 15.0


class SqlIndexer:
    def __init__(self, cfg: IndexerConfig) -> None:
        self.cfg = cfg
        self._conn: sqlite3.Connection | None = None

    def open(self) -> None:
        os.makedirs(os.path.dirname(self.cfg.db_path) or ".", exist_ok=True)
        self._conn = sqlite3.connect(self.cfg.db_path, timeout=30, isolation_level=None)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._migrate()

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def _migrate(self) -> None:
        assert self._conn is not None
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS meta (
              key TEXT PRIMARY KEY,
              value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS blocks (
              height INTEGER PRIMARY KEY,
              time TEXT,
              proposer_address TEXT,
              block_id_hash TEXT,
              tx_count INTEGER NOT NULL,
              block_json TEXT NOT NULL,
              results_json TEXT NOT NULL,
              indexed_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS txs (
              tx_hash TEXT PRIMARY KEY,
              height INTEGER NOT NULL,
              tx_index INTEGER NOT NULL,
              code INTEGER,
              gas_wanted INTEGER,
              gas_used INTEGER,
              tx_b64 TEXT,
              raw_log TEXT,
              events_json TEXT NOT NULL,
              indexed_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS txs_height_idx ON txs(height);

            CREATE TABLE IF NOT EXISTS events (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              height INTEGER NOT NULL,
              tx_hash TEXT,
              source TEXT NOT NULL,
              event_index INTEGER NOT NULL,
              event_type TEXT,
              attributes_json TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS events_height_idx ON events(height);
            CREATE INDEX IF NOT EXISTS events_type_idx ON events(event_type);
            CREATE INDEX IF NOT EXISTS events_tx_hash_idx ON events(tx_hash);
            """
        )

    def _meta_get_int(self, key: str) -> int | None:
        assert self._conn is not None
        row = self._conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        if not row:
            return None
        try:
            return int(row[0])
        except Exception:
            return None

    def _meta_set(self, key: str, value: str) -> None:
        assert self._conn is not None
        self._conn.execute(
            "INSERT INTO meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )

    def get_status(self) -> tuple[str | None, int]:
        url = _join_url(self.cfg.rpc_url, "/status")
        parsed = _http_get_json(url, timeout_s=self.cfg.timeout_seconds)
        result = parsed.get("result") or {}
        node_info = result.get("node_info") or {}
        sync_info = result.get("sync_info") or {}
        chain_id = node_info.get("network")
        latest = int(sync_info.get("latest_block_height") or 0)
        return chain_id, latest

    def run_forever(self, stop_event, log_fn) -> None:
        """Run until stop_event is set."""
        if self._conn is None:
            self.open()

        assert self._conn is not None
        chain_id, latest = self.get_status()
        if chain_id:
            self._meta_set("chain_id", str(chain_id))

        if self.cfg.start_height is not None:
            next_height = int(self.cfg.start_height)
        else:
            last = self._meta_get_int("last_indexed_height")
            next_height = (last + 1) if last is not None else 1

        log_fn(f"==> indexer db: {self.cfg.db_path}\n")
        log_fn(f"==> rpc: {self.cfg.rpc_url}\n")
        if chain_id:
            log_fn(f"==> chain_id: {chain_id}\n")
        log_fn(f"==> starting from height: {next_height}\n")

        while not stop_event.is_set():
            try:
                _, latest = self.get_status()
                if next_height <= 0:
                    next_height = 1

                if next_height > latest:
                    time.sleep(max(0.5, float(self.cfg.poll_seconds)))
                    continue

                self.index_height(next_height)
                self._meta_set("last_indexed_height", str(next_height))
                log_fn(f"Indexed height {next_height} (latest={latest})\n")
                next_height += 1

            except Exception as exc:  # noqa: BLE001
                log_fn(f"ERROR: {exc}\n")
                time.sleep(2.0)

    def index_height(self, height: int) -> None:
        assert self._conn is not None

        block_url = _join_url(self.cfg.rpc_url, "/block") + "?" + urllib.parse.urlencode({"height": str(height)})
        res_url = _join_url(self.cfg.rpc_url, "/block_results") + "?" + urllib.parse.urlencode({"height": str(height)})

        block_doc = _http_get_json(block_url, timeout_s=self.cfg.timeout_seconds)
        results_doc = _http_get_json(res_url, timeout_s=self.cfg.timeout_seconds)

        block = (block_doc.get("result") or {}).get("block") or {}
        block_id = (block_doc.get("result") or {}).get("block_id") or {}
        header = (block.get("header") or {}) if isinstance(block, dict) else {}
        data = (block.get("data") or {}) if isinstance(block, dict) else {}
        txs = data.get("txs") if isinstance(data, dict) else None
        txs_list: list[str] = txs if isinstance(txs, list) else []

        time_str = header.get("time")
        proposer = header.get("proposer_address")
        block_hash = block_id.get("hash")

        txs_results = (results_doc.get("result") or {}).get("txs_results")
        txs_results_list: list[dict[str, Any]] = txs_results if isinstance(txs_results, list) else []

        # Persist in a single transaction.
        self._conn.execute("BEGIN")
        try:
            self._conn.execute(
                "INSERT OR REPLACE INTO blocks(height,time,proposer_address,block_id_hash,tx_count,block_json,results_json,indexed_at) "
                "VALUES(?,?,?,?,?,?,?,?)",
                (
                    int(height),
                    time_str,
                    proposer,
                    block_hash,
                    int(len(txs_list)),
                    json.dumps(block_doc, ensure_ascii=False),
                    json.dumps(results_doc, ensure_ascii=False),
                    _utc_now_iso(),
                ),
            )

            # Clear any existing txs/events for this height (reindex-safe).
            self._conn.execute("DELETE FROM events WHERE height = ?", (int(height),))
            self._conn.execute("DELETE FROM txs WHERE height = ?", (int(height),))

            # Block-level events.
            result_obj = results_doc.get("result") or {}
            block_event_sources = [
                ("begin_block", result_obj.get("begin_block_events")),
                ("end_block", result_obj.get("end_block_events")),
                ("finalize_block", result_obj.get("finalize_block_events")),
            ]
            ev_id = 0
            for source, evs in block_event_sources:
                norm = _normalize_events(evs)
                for e in norm:
                    self._conn.execute(
                        "INSERT INTO events(height,tx_hash,source,event_index,event_type,attributes_json) VALUES(?,?,?,?,?,?)",
                        (int(height), None, source, ev_id, e.get("type"), json.dumps(e.get("attributes"), ensure_ascii=False)),
                    )
                    ev_id += 1

            # Tx-level rows + tx events.
            for i, tx_b64 in enumerate(txs_list):
                tx_hash = _tx_hash_hex(tx_b64)
                txr = txs_results_list[i] if i < len(txs_results_list) else {}
                code = txr.get("code")
                gas_wanted = txr.get("gas_wanted")
                gas_used = txr.get("gas_used")
                raw_log = txr.get("log")
                events_norm = _normalize_events(txr.get("events"))

                self._conn.execute(
                    "INSERT OR REPLACE INTO txs(tx_hash,height,tx_index,code,gas_wanted,gas_used,tx_b64,raw_log,events_json,indexed_at) "
                    "VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (
                        tx_hash,
                        int(height),
                        int(i),
                        int(code) if code is not None else None,
                        int(gas_wanted) if gas_wanted is not None else None,
                        int(gas_used) if gas_used is not None else None,
                        tx_b64,
                        raw_log,
                        json.dumps(events_norm, ensure_ascii=False),
                        _utc_now_iso(),
                    ),
                )

                for e in events_norm:
                    self._conn.execute(
                        "INSERT INTO events(height,tx_hash,source,event_index,event_type,attributes_json) VALUES(?,?,?,?,?,?)",
                        (
                            int(height),
                            tx_hash,
                            "tx",
                            ev_id,
                            e.get("type"),
                            json.dumps(e.get("attributes"), ensure_ascii=False),
                        ),
                    )
                    ev_id += 1

            self._conn.execute("COMMIT")
        except Exception:
            self._conn.execute("ROLLBACK")
            raise
