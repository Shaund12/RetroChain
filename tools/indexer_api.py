#!/usr/bin/env python3
"""Retrochain Indexer Read API (SQLite)

Serves explorer-friendly JSON endpoints backed by the SQLite DB produced by
`tools/sql_indexer.py`.

This is intentionally standalone and does NOT modify any existing chain REST/gRPC
endpoints.

Endpoints (v1):
- GET /v1/health
- GET /v1/status
- GET /v1/blocks?limit=20&offset=0&order=desc
- GET /v1/blocks/<height>?include_raw=1
- GET /v1/txs/<tx_hash>
- GET /v1/events?height=&tx_hash=&type=&source=&limit=&offset=&order=asc

CORS:
- Disabled by default.
- Configure an allowlist via `--cors-origins` or `INDEXER_API_CORS_ORIGINS`.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse


def _cors_origin_for_request(handler: BaseHTTPRequestHandler) -> str | None:
    allowed: list[str] = getattr(handler.server, "cors_allowed_origins", [])  # type: ignore[attr-defined]
    origin = (handler.headers.get("Origin") or "").strip()
    if not origin or not allowed:
        return None
    if "*" in allowed:
        return "*"
    return origin if origin in allowed else None


def _maybe_write_cors_headers(handler: BaseHTTPRequestHandler) -> None:
    cors_origin = _cors_origin_for_request(handler)
    if not cors_origin:
        return
    handler.send_header("Access-Control-Allow-Origin", cors_origin)
    handler.send_header("Vary", "Origin")
    handler.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type")


def _json_response(handler: BaseHTTPRequestHandler, status: int, obj: Any) -> None:
    body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    _maybe_write_cors_headers(handler)
    handler.end_headers()
    handler.wfile.write(body)


def _bad_request(handler: BaseHTTPRequestHandler, msg: str) -> None:
    _json_response(handler, HTTPStatus.BAD_REQUEST, {"error": msg})


def _not_found(handler: BaseHTTPRequestHandler) -> None:
    _json_response(handler, HTTPStatus.NOT_FOUND, {"error": "not found"})


def _parse_int(q: dict[str, list[str]], key: str, default: int, min_value: int, max_value: int) -> int:
    raw = (q.get(key) or [""])[0].strip()
    if not raw:
        return default
    try:
        val = int(raw)
    except ValueError:
        return default
    return max(min_value, min(max_value, val))


def _parse_str(q: dict[str, list[str]], key: str) -> str | None:
    raw = (q.get(key) or [""])[0].strip()
    return raw or None


class IndexerDB:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=15)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only=ON")
        return conn

    def meta(self) -> dict[str, str]:
        with self.connect() as conn:
            rows = conn.execute("SELECT key, value FROM meta").fetchall()
            return {str(r["key"]): str(r["value"]) for r in rows}

    def blocks(self, limit: int, offset: int, order: str) -> tuple[int, list[dict[str, Any]]]:
        order_sql = "DESC" if order.lower() != "asc" else "ASC"
        with self.connect() as conn:
            total = conn.execute("SELECT COUNT(1) AS c FROM blocks").fetchone()["c"]
            rows = conn.execute(
                f"SELECT height, time, proposer_address, block_id_hash, tx_count, indexed_at FROM blocks ORDER BY height {order_sql} LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
            items = [dict(r) for r in rows]
            return int(total), items

    def block(self, height: int) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT height, time, proposer_address, block_id_hash, tx_count, block_json, results_json, indexed_at FROM blocks WHERE height = ?",
                (height,),
            ).fetchone()
            return dict(row) if row else None

    def tx(self, tx_hash: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT t.tx_hash, t.height, t.tx_index, t.code, t.gas_wanted, t.gas_used, t.tx_b64, t.raw_log, t.events_json, t.indexed_at, b.time AS block_time "
                "FROM txs t LEFT JOIN blocks b ON b.height = t.height WHERE t.tx_hash = ?",
                (tx_hash,),
            ).fetchone()
            return dict(row) if row else None

    def txs(self, limit: int, offset: int, order: str, height: int | None) -> tuple[int, list[dict[str, Any]]]:
        order_sql = "DESC" if order.lower() != "asc" else "ASC"
        where: list[str] = []
        params: list[Any] = []
        if height is not None:
            where.append("t.height = ?")
            params.append(int(height))
        where_sql = ("WHERE " + " AND ".join(where)) if where else ""

        # Stable ordering: height then tx_index.
        order_by = f"t.height {order_sql}, t.tx_index {'ASC' if order_sql == 'DESC' else 'DESC'}"

        with self.connect() as conn:
            total = conn.execute(f"SELECT COUNT(1) AS c FROM txs t {where_sql}", tuple(params)).fetchone()["c"]
            rows = conn.execute(
                f"SELECT t.tx_hash, t.height, t.tx_index, t.code, t.gas_wanted, t.gas_used, t.raw_log, t.indexed_at, b.time AS block_time "
                f"FROM txs t LEFT JOIN blocks b ON b.height = t.height {where_sql} ORDER BY {order_by} LIMIT ? OFFSET ?",
                tuple(params + [limit, offset]),
            ).fetchall()
            return int(total), [dict(r) for r in rows]

    def events(
        self,
        limit: int,
        offset: int,
        order: str,
        height: int | None,
        tx_hash: str | None,
        event_type: str | None,
        source: str | None,
    ) -> tuple[int, list[dict[str, Any]]]:
        order_sql = "DESC" if order.lower() == "desc" else "ASC"
        where: list[str] = []
        params: list[Any] = []
        if height is not None:
            where.append("height = ?")
            params.append(int(height))
        if tx_hash is not None:
            where.append("tx_hash = ?")
            params.append(tx_hash)
        if event_type is not None:
            where.append("event_type = ?")
            params.append(event_type)
        if source is not None:
            where.append("source = ?")
            params.append(source)

        where_sql = ("WHERE " + " AND ".join(where)) if where else ""

        with self.connect() as conn:
            total = conn.execute(f"SELECT COUNT(1) AS c FROM events {where_sql}", tuple(params)).fetchone()["c"]
            rows = conn.execute(
                f"SELECT id, height, tx_hash, source, event_index, event_type, attributes_json FROM events {where_sql} ORDER BY id {order_sql} LIMIT ? OFFSET ?",
                tuple(params + [limit, offset]),
            ).fetchall()
            return int(total), [dict(r) for r in rows]


class Handler(BaseHTTPRequestHandler):
    server_version = "RetrochainIndexerAPI/1.0"

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(HTTPStatus.NO_CONTENT)
        _maybe_write_cors_headers(self)
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        q = parse_qs(parsed.query)

        db: IndexerDB = self.server.db  # type: ignore[attr-defined]

        if path in ("", "/"):
            _json_response(self, 200, {"name": "retrochain-indexer-api", "version": "v1"})
            return

        if path == "/v1/health":
            _json_response(self, 200, {"status": "ok"})
            return

        if path == "/v1/status":
            meta = db.meta()
            _json_response(
                self,
                200,
                {
                    "db_path": db.db_path,
                    "chain_id": meta.get("chain_id"),
                    "last_indexed_height": int(meta["last_indexed_height"]) if meta.get("last_indexed_height") else None,
                },
            )
            return

        if path == "/v1/blocks":
            limit = _parse_int(q, "limit", default=20, min_value=1, max_value=200)
            offset = _parse_int(q, "offset", default=0, min_value=0, max_value=10_000_000)
            order = (q.get("order") or ["desc"])[0]
            total, items = db.blocks(limit=limit, offset=offset, order=order)
            _json_response(self, 200, {"total": total, "limit": limit, "offset": offset, "items": items})
            return

        if path.startswith("/v1/blocks/"):
            height_str = path.split("/")[-1]
            try:
                height = int(height_str)
            except ValueError:
                _bad_request(self, "height must be an integer")
                return
            row = db.block(height)
            if not row:
                _not_found(self)
                return
            include_raw = (q.get("include_raw") or ["0"])[0] in ("1", "true", "yes")
            if include_raw:
                # Parse the stored JSON for convenience.
                try:
                    row["block_json"] = json.loads(row["block_json"]) if row.get("block_json") else None
                except Exception:
                    pass
                try:
                    row["results_json"] = json.loads(row["results_json"]) if row.get("results_json") else None
                except Exception:
                    pass
            else:
                row.pop("block_json", None)
                row.pop("results_json", None)
            _json_response(self, 200, row)
            return

        if path.startswith("/v1/txs/"):
            tx_hash = path.split("/")[-1].strip().upper()
            if not tx_hash:
                _bad_request(self, "tx_hash required")
                return
            row = db.tx(tx_hash)
            if not row:
                _not_found(self)
                return
            # Parse events_json for convenience.
            try:
                row["events"] = json.loads(row["events_json"]) if row.get("events_json") else []
            except Exception:
                row["events"] = []
            row.pop("events_json", None)
            _json_response(self, 200, row)
            return

        if path == "/v1/txs":
            limit = _parse_int(q, "limit", default=50, min_value=1, max_value=500)
            offset = _parse_int(q, "offset", default=0, min_value=0, max_value=10_000_000)
            order = (q.get("order") or ["desc"])[0]
            height_raw = _parse_str(q, "height")
            height = int(height_raw) if height_raw and height_raw.isdigit() else None

            total, items = db.txs(limit=limit, offset=offset, order=order, height=height)
            _json_response(self, 200, {"total": total, "limit": limit, "offset": offset, "items": items})
            return

        if path == "/v1/events":
            limit = _parse_int(q, "limit", default=50, min_value=1, max_value=500)
            offset = _parse_int(q, "offset", default=0, min_value=0, max_value=10_000_000)
            order = (q.get("order") or ["asc"])[0]

            height_raw = _parse_str(q, "height")
            height = int(height_raw) if height_raw and height_raw.isdigit() else None
            tx_hash = _parse_str(q, "tx_hash")
            if tx_hash:
                tx_hash = tx_hash.upper()
            event_type = _parse_str(q, "type")
            source = _parse_str(q, "source")

            total, items = db.events(limit=limit, offset=offset, order=order, height=height, tx_hash=tx_hash, event_type=event_type, source=source)
            _json_response(self, 200, {"total": total, "limit": limit, "offset": offset, "items": items})
            return

        _not_found(self)

    def log_message(self, fmt: str, *args: Any) -> None:  # noqa: D401
        # quiet by default (reduce noise); uncomment for debugging
        return


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--db", default=os.path.expanduser("~/.retrochain/indexer.sqlite"), help="Path to SQLite DB")
    p.add_argument("--listen", default="127.0.0.1:8081", help="host:port")
    p.add_argument(
        "--cors-origins",
        default=(os.environ.get("INDEXER_API_CORS_ORIGINS") or "").strip(),
        help="Comma-separated Origin allowlist for browser CORS (or '*'); default: disabled",
    )
    args = p.parse_args()

    db_path = os.path.expanduser(args.db)
    if not os.path.isfile(db_path):
        raise SystemExit(f"DB not found: {db_path}")

    host, port_str = args.listen.rsplit(":", 1)
    port = int(port_str)

    allowed_origins = [o.strip() for o in str(args.cors_origins).split(",") if o.strip()]

    httpd = ThreadingHTTPServer((host, port), Handler)
    httpd.db = IndexerDB(db_path)  # type: ignore[attr-defined]
    httpd.cors_allowed_origins = allowed_origins  # type: ignore[attr-defined]
    print(f"Indexer API listening on http://{host}:{port}")
    httpd.serve_forever()


if __name__ == "__main__":
    main()
