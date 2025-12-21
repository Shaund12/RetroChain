#!/usr/bin/env python3
"""
Lightweight Tkinter GUI to manage a local retrochaind instance.
- Start/stop/restart the node
- Show process status and streamed logs
- Uses the installed `retrochaind` binary (defaults to PATH) and default home `~/.retrochain`
"""
import datetime
import json
import os
import queue
import re
import shlex
import shutil
import signal
import subprocess
import threading
import time
import sys
import urllib.error
import urllib.request
import hashlib
import sqlite3
import webbrowser
from collections import Counter
from typing import NamedTuple
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, simpledialog, ttk

try:
    import fcntl  # type: ignore
except Exception:  # pragma: no cover
    fcntl = None

from sql_indexer import IndexerConfig, SqlIndexer


def _repo_root() -> str:
    # tools/gui_node_manager.py -> repo root
    return os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


def _repo_retrochaind_build() -> str:
    return os.path.join(_repo_root(), "build", "retrochaind")


def _default_retrochaind_binary() -> str:
    cand = _repo_retrochaind_build()
    if os.path.isfile(cand) and os.access(cand, os.X_OK):
        return cand
    return "retrochaind"


DEFAULT_BINARY = _default_retrochaind_binary()
DEFAULT_HOME = os.path.expanduser("~/.retrochain")
DEFAULT_TESTNET_HOME = os.path.join(_repo_root(), "testnet", "home")
DEFAULT_ARGS = "--log_no_color"
DEFAULT_KEYRING_BACKEND = "os"
DEFAULT_HERMES_BINARY = "hermes"
DEFAULT_HERMES_CONFIG = os.path.expanduser("~/.hermes/config.toml")

DEFAULT_SQL_INDEXER_RPC = "http://localhost:26657"
DEFAULT_SQL_INDEXER_DB = os.path.expanduser("~/.retrochain/indexer.sqlite")
DEFAULT_SQL_INDEXER_POLL_SECONDS = "2"
DEFAULT_INDEXER_API_LISTEN = "127.0.0.1:8081"

DEFAULT_SETUP_CHAIN_ID = "retrochain-mainnet"
DEFAULT_SETUP_MIN_GAS_PRICES = "0uretro"


def _format_bytes(num_bytes: int) -> str:
    if num_bytes < 0:
        return "?"
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(num_bytes)
    for unit in units:
        if size < 1024.0 or unit == units[-1]:
            if unit == "B":
                return f"{int(size)} {unit}"
            return f"{size:.1f} {unit}"
        size /= 1024.0


def _age_days_from_mtime(mtime: float | None) -> int | None:
    if not mtime:
        return None
    try:
        return int((time.time() - float(mtime)) // 86400)
    except Exception:
        return None


def _parse_rfc3339(ts: str | None) -> datetime.datetime | None:
    if not ts or not isinstance(ts, str):
        return None
    try:
        s = ts.strip()
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        return dt
    except Exception:
        return None

# Default alternate ports for running a parallel "testnet" instance locally.
DEFAULT_TESTNET_RPC_LADDR = "tcp://0.0.0.0:27657"
DEFAULT_TESTNET_P2P_LADDR = "tcp://0.0.0.0:27656"
DEFAULT_TESTNET_API_ADDR = "tcp://0.0.0.0:1417"
DEFAULT_TESTNET_GRPC_ADDR = "0.0.0.0:9190"


class NodeManagerGUI:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Retrochain Node Manager - Shaunware Solutions")
        self.process: subprocess.Popen | None = None
        self.node_log_queue: queue.Queue[str] = queue.Queue()

        self.testnet_process: subprocess.Popen | None = None
        self.testnet_log_queue: queue.Queue[str] = queue.Queue()
        self.testnet_reader_thread: threading.Thread | None = None
        self.testnet_stop_event = threading.Event()

        self.hermes_log_queue: queue.Queue[str] = queue.Queue()
        self.module_log_queue: queue.Queue[str] = queue.Queue()
        self.indexer_log_queue: queue.Queue[str] = queue.Queue()
        self.nginx_log_queue: queue.Queue[str] = queue.Queue()
        self.setup_log_queue: queue.Queue[str] = queue.Queue()
        self.reader_thread: threading.Thread | None = None
        self.stop_event = threading.Event()
        self.tail_process: subprocess.Popen | None = None
        self.tail_thread: threading.Thread | None = None
        self.tail_stop_event = threading.Event()

        self.hermes_process: subprocess.Popen | None = None
        self.hermes_thread: threading.Thread | None = None
        self.hermes_stop_event = threading.Event()

        self.indexer_thread: threading.Thread | None = None
        self.indexer_stop_event = threading.Event()

        self.sql_indexer: SqlIndexer | None = None

        self.indexer_api_process: subprocess.Popen | None = None
        self.indexer_api_thread: threading.Thread | None = None

        self._indexer_status_last_refresh: float = 0.0
        self._indexer_status_refresh_in_flight: bool = False

        self._nginx_status_last_refresh: float = 0.0
        self._nginx_status_refresh_in_flight: bool = False

        self._nginx_sites_tree: ttk.Treeview | None = None
        self._nginx_sites_rows_by_iid: dict[str, dict] = {}
        self.nginx_sites_minutes_var: tk.StringVar | None = None
        self.nginx_sites_max_lines_var: tk.StringVar | None = None
        self.nginx_sites_analytics: scrolledtext.ScrolledText | None = None

        self.keys_data: list[dict] = []

        self.available_query_modules: list[str] = []
        self.available_tx_modules: list[str] = []

        # Scheduled restart (upgrade) watcher state
        self._sched_stop_event = threading.Event()
        self._sched_thread: threading.Thread | None = None
        self._sched_latest_height: int | None = None
        self._sched_latest_height_at: float | None = None
        self._sched_latest_chain_id: str | None = None
        self._sched_latest_chain_id_at: float | None = None
        self._sched_target_height: int | None = None
        self._sched_armed: bool = False
        self._sched_rpc_url: str = DEFAULT_SQL_INDEXER_RPC

        # Scheduled restart safety: expected chain-id (from local genesis, when available)
        self._sched_expected_chain_id: str | None = None
        self._sched_expected_chain_id_home: str | None = None

        # Upgrade binary swap state
        self._upgrade_swap_in_progress: bool = False
        self._upgrade_swap_last_at: float | None = None

        # Analytics watcher state
        self._analytics_stop_event = threading.Event()
        self._analytics_thread: threading.Thread | None = None
        self._analytics_latest: dict | None = None
        self._analytics_latest_at: float | None = None
        self._analytics_force_refresh: bool = False
        self._analytics_rpc_url: str = DEFAULT_SQL_INDEXER_RPC
        self._analytics_refresh_enabled: bool = True
        self._analytics_log_queue: queue.Queue[str] = queue.Queue()

        # Binary backup manager window state
        self._bbm_window: tk.Toplevel | None = None
        self._bbm_tree: ttk.Treeview | None = None
        self._bbm_status_var: tk.StringVar | None = None
        self._bbm_backup_dir_var: tk.StringVar | None = None
        self._bbm_delete_older_days_var: tk.StringVar | None = None
        self._bbm_scan_queue: queue.Queue[list[dict]] | None = None
        self._bbm_scan_cancel = threading.Event()
        self._bbm_scan_thread: threading.Thread | None = None
        self._bbm_scan_roots_vars: dict[str, tk.BooleanVar] = {}
        self._bbm_extra_paths_var: tk.StringVar | None = None
        self._bbm_rows_by_path: dict[str, dict] = {}
        self._bbm_details_vars: dict[str, tk.StringVar] = {}
        self._bbm_hash_thread: threading.Thread | None = None
        self._bbm_version_thread: threading.Thread | None = None

        self._build_ui()
        self._start_scheduled_restart_watcher()
        # Analytics is opt-in: the user explicitly starts it from the Analytics tab.
        self._poll_log_queues()

    def _build_ui(self) -> None:
        frm = ttk.Frame(self.root, padding=10)
        frm.grid(row=0, column=0, sticky="nsew")
        self.root.rowconfigure(0, weight=1)
        self.root.columnconfigure(0, weight=1)

        # Menubar
        menubar = tk.Menu(self.root)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Start", command=self.start_node)
        file_menu.add_command(label="Stop", command=self.stop_node)
        file_menu.add_command(label="Restart", command=self.restart_node)
        file_menu.add_command(label="Backup", command=self.backup_node)
        file_menu.add_command(label="Binary Backup Manager", command=self.open_binary_backup_manager)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        menubar.add_cascade(label="File", menu=file_menu)

        key_menu = tk.Menu(menubar, tearoff=0)
        key_menu.add_command(label="Refresh Keys", command=self.refresh_keys)
        key_menu.add_command(label="Create Key (mnemonic)", command=self.create_key_with_mnemonic)
        key_menu.add_command(label="Add Key", command=self.add_key)
        key_menu.add_command(label="Import Mnemonic", command=self.import_mnemonic)
        key_menu.add_command(label="Delete Key", command=self.delete_key)
        menubar.add_cascade(label="Keyring", menu=key_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="About", command=self.show_about)
        menubar.add_cascade(label="Help", menu=help_menu)

        self.root.config(menu=menubar)

        notebook = ttk.Notebook(frm)
        notebook.grid(row=0, column=0, sticky="nsew")
        frm.rowconfigure(0, weight=1)
        frm.columnconfigure(0, weight=1)

        node_tab = ttk.Frame(notebook, padding=4)
        testnet_tab = ttk.Frame(notebook, padding=4)
        setup_tab = ttk.Frame(notebook, padding=4)
        analytics_tab = ttk.Frame(notebook, padding=4)
        hermes_tab = ttk.Frame(notebook, padding=4)
        modules_tab = ttk.Frame(notebook, padding=4)
        indexer_tab = ttk.Frame(notebook, padding=4)
        nginx_tab = ttk.Frame(notebook, padding=4)
        notebook.add(node_tab, text="Node")
        notebook.add(testnet_tab, text="Testnet")
        notebook.add(setup_tab, text="Setup")
        notebook.add(analytics_tab, text="Analytics")
        notebook.add(hermes_tab, text="Hermes")
        notebook.add(modules_tab, text="Modules")
        notebook.add(indexer_tab, text="SQL Indexer")
        notebook.add(nginx_tab, text="Nginx")

        ttk.Label(node_tab, text="retrochaind binary").grid(row=0, column=0, sticky="w")
        self.bin_var = tk.StringVar(value=DEFAULT_BINARY)
        ttk.Entry(node_tab, textvariable=self.bin_var, width=50).grid(row=0, column=1, sticky="ew", padx=6)
        ttk.Button(node_tab, text="Browse", command=self.browse_retrochaind_binary).grid(row=0, column=2, sticky="w")

        ttk.Label(node_tab, text="--home").grid(row=1, column=0, sticky="w")
        self.home_var = tk.StringVar(value=DEFAULT_HOME)
        ttk.Entry(node_tab, textvariable=self.home_var, width=50).grid(row=1, column=1, sticky="ew", padx=6)

        ttk.Label(node_tab, text="extra args").grid(row=2, column=0, sticky="w")
        self.args_var = tk.StringVar(value=DEFAULT_ARGS)
        ttk.Entry(node_tab, textvariable=self.args_var, width=50).grid(row=2, column=1, sticky="ew", padx=6)

        ttk.Label(node_tab, text="log file (optional)").grid(row=3, column=0, sticky="w")
        self.logfile_var = tk.StringVar(value=os.path.expanduser("~/.retrochain/logs/retrochaind.log"))
        ttk.Entry(node_tab, textvariable=self.logfile_var, width=50).grid(row=3, column=1, sticky="ew", padx=6)

        btn_frame = ttk.Frame(node_tab)
        btn_frame.grid(row=4, column=0, columnspan=2, pady=8, sticky="w")
        ttk.Button(btn_frame, text="Start", command=self.start_node).grid(row=0, column=0, padx=4)
        ttk.Button(btn_frame, text="Stop", command=self.stop_node).grid(row=0, column=1, padx=4)
        ttk.Button(btn_frame, text="Restart", command=self.restart_node).grid(row=0, column=2, padx=4)
        ttk.Button(btn_frame, text="Status", command=self.show_status).grid(row=0, column=3, padx=4)
        ttk.Button(btn_frame, text="Backup", command=self.backup_node).grid(row=0, column=4, padx=4)

        tail_frame = ttk.Frame(node_tab)
        tail_frame.grid(row=5, column=0, columnspan=2, pady=(0, 8), sticky="w")
        ttk.Button(tail_frame, text="Tail On", command=self.start_tail).grid(row=0, column=0, padx=4)
        ttk.Button(tail_frame, text="Tail Off", command=self.stop_tail).grid(row=0, column=1, padx=4)

        preset_frame = ttk.Frame(node_tab)
        preset_frame.grid(row=6, column=0, columnspan=2, pady=(0, 8), sticky="w")
        ttk.Button(preset_frame, text="Preset: Mainnet", command=self.apply_mainnet_preset).grid(row=0, column=0, padx=4)
        ttk.Button(preset_frame, text="Preset: Local", command=self.apply_local_preset).grid(row=0, column=1, padx=4)

        systemd_frame = ttk.Frame(node_tab)
        systemd_frame.grid(row=7, column=0, columnspan=2, pady=(0, 8), sticky="w")
        ttk.Label(systemd_frame, text="systemd service").grid(row=0, column=0, sticky="w")
        self.service_var = tk.StringVar(value="retrochaind")
        ttk.Entry(systemd_frame, textvariable=self.service_var, width=24).grid(row=0, column=1, padx=4, sticky="w")
        ttk.Button(systemd_frame, text="systemd start", command=lambda: self.systemd_action("start")).grid(row=0, column=2, padx=4)
        ttk.Button(systemd_frame, text="systemd stop", command=lambda: self.systemd_action("stop")).grid(row=0, column=3, padx=4)
        ttk.Button(systemd_frame, text="systemd status", command=lambda: self.systemd_action("status")).grid(row=0, column=4, padx=4)

        # Scheduled restart (useful for coordinating binary upgrades around gov upgrade heights)
        sched = ttk.LabelFrame(node_tab, text="Scheduled restart (upgrade)", padding=8)
        sched.grid(row=8, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        sched.columnconfigure(1, weight=1)
        sched.columnconfigure(3, weight=1)

        ttk.Label(sched, text="RPC (CometBFT)").grid(row=0, column=0, sticky="w")
        self.sched_rpc_var = tk.StringVar(value=DEFAULT_SQL_INDEXER_RPC)
        ttk.Entry(sched, textvariable=self.sched_rpc_var, width=38).grid(row=0, column=1, sticky="ew", padx=6)

        ttk.Label(sched, text="Restart at height").grid(row=0, column=2, sticky="w")
        self.sched_height_var = tk.StringVar(value="")
        ttk.Entry(sched, textvariable=self.sched_height_var, width=14).grid(row=0, column=3, sticky="w", padx=6)

        ttk.Label(sched, text="Upgraded binary").grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.upgrade_bin_var = tk.StringVar(value="")
        ttk.Entry(sched, textvariable=self.upgrade_bin_var, width=38).grid(row=1, column=1, sticky="ew", padx=6, pady=(6, 0))
        ttk.Button(sched, text="Browse", command=self.browse_upgrade_binary).grid(row=1, column=2, sticky="w", padx=4, pady=(6, 0))

        self.sched_swap_binary_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(sched, text="Swap binary on restart", variable=self.sched_swap_binary_var).grid(
            row=1, column=3, sticky="w", padx=6, pady=(6, 0)
        )

        self.auto_swap_on_halt_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(sched, text="Auto-swap on upgrade halt", variable=self.auto_swap_on_halt_var).grid(
            row=2, column=1, sticky="w", padx=6, pady=(6, 0)
        )

        self.backup_before_swap_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(sched, text="Backup current binary before swap", variable=self.backup_before_swap_var).grid(
            row=2, column=3, sticky="w", padx=6, pady=(6, 0)
        )

        self.swap_in_place_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(sched, text="Swap in-place (overwrite build/retrochaind)", variable=self.swap_in_place_var).grid(
            row=2, column=2, sticky="w", padx=6, pady=(6, 0)
        )

        sched_btns = ttk.Frame(sched)
        sched_btns.grid(row=3, column=0, columnspan=4, sticky="w", pady=(6, 0))
        ttk.Button(sched_btns, text="Arm", command=self.arm_scheduled_restart).grid(row=0, column=0, padx=4)
        ttk.Button(sched_btns, text="Disarm", command=self.disarm_scheduled_restart).grid(row=0, column=1, padx=4)
        self.sched_status_var = tk.StringVar(value="Not armed")
        ttk.Label(sched_btns, textvariable=self.sched_status_var, foreground="gray").grid(row=0, column=2, padx=8)

        self.status_var = tk.StringVar(value="Idle")
        ttk.Label(node_tab, textvariable=self.status_var, foreground="blue").grid(row=9, column=0, columnspan=2, sticky="w", pady=(0, 6))

        self.node_log = scrolledtext.ScrolledText(node_tab, height=18, wrap=tk.WORD, state="disabled")
        self.node_log.grid(row=10, column=0, columnspan=2, sticky="nsew")
        node_tab.rowconfigure(10, weight=1)
        node_tab.columnconfigure(1, weight=1)

        # ----------------------- Analytics tab content -----------------------
        analytics_tab.columnconfigure(1, weight=1)
        analytics_tab.columnconfigure(3, weight=1)

        top = ttk.LabelFrame(analytics_tab, text="RPC + refresh", padding=8)
        top.grid(row=0, column=0, columnspan=4, sticky="ew", pady=(0, 8))
        top.columnconfigure(1, weight=1)

        ttk.Label(top, text="CometBFT RPC").grid(row=0, column=0, sticky="w")
        self.analytics_rpc_var = tk.StringVar(value=DEFAULT_SQL_INDEXER_RPC)
        ttk.Entry(top, textvariable=self.analytics_rpc_var, width=44).grid(row=0, column=1, sticky="ew", padx=6)

        self.analytics_auto_refresh_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(top, text="Auto refresh", variable=self.analytics_auto_refresh_var).grid(row=0, column=2, sticky="w", padx=6)
        ttk.Button(top, text="Start analytics", command=self.start_analytics).grid(row=0, column=3, sticky="w", padx=(0, 6))

        ttk.Button(top, text="Stop analytics", command=self.stop_analytics).grid(row=1, column=2, sticky="w", padx=6, pady=(6, 0))
        ttk.Button(top, text="Refresh now", command=self.analytics_refresh_now).grid(row=1, column=3, sticky="w", pady=(6, 0))

        self.analytics_status_var = tk.StringVar(value="Waiting for first sample")
        ttk.Label(top, textvariable=self.analytics_status_var, foreground="gray").grid(row=1, column=0, columnspan=4, sticky="w", pady=(6, 0))

        alerts = ttk.LabelFrame(analytics_tab, text="Alerts", padding=8)
        alerts.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(0, 8))
        alerts.columnconfigure(0, weight=1)
        self.analytics_alerts_var = tk.StringVar(value="-")
        ttk.Label(alerts, textvariable=self.analytics_alerts_var, foreground="gray").grid(row=0, column=0, sticky="w")

        chain = ttk.LabelFrame(analytics_tab, text="Chain", padding=8)
        chain.grid(row=2, column=0, columnspan=4, sticky="ew", pady=(0, 8))
        chain.columnconfigure(1, weight=1)
        chain.columnconfigure(3, weight=1)

        self.analytics_chain_id_var = tk.StringVar(value="-")
        self.analytics_height_var = tk.StringVar(value="-")
        self.analytics_catching_up_var = tk.StringVar(value="-")
        self.analytics_latest_time_var = tk.StringVar(value="-")
        self.analytics_node_version_var = tk.StringVar(value="-")
        self.analytics_moniker_var = tk.StringVar(value="-")
        self.analytics_rpc_latency_var = tk.StringVar(value="-")

        ttk.Label(chain, text="chain-id").grid(row=0, column=0, sticky="w")
        ttk.Label(chain, textvariable=self.analytics_chain_id_var).grid(row=0, column=1, sticky="w")
        ttk.Label(chain, text="height").grid(row=0, column=2, sticky="w", padx=(12, 0))
        ttk.Label(chain, textvariable=self.analytics_height_var).grid(row=0, column=3, sticky="w")

        ttk.Label(chain, text="catching up").grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Label(chain, textvariable=self.analytics_catching_up_var).grid(row=1, column=1, sticky="w", pady=(6, 0))
        ttk.Label(chain, text="latest block time").grid(row=1, column=2, sticky="w", padx=(12, 0), pady=(6, 0))
        ttk.Label(chain, textvariable=self.analytics_latest_time_var).grid(row=1, column=3, sticky="w", pady=(6, 0))

        ttk.Label(chain, text="node version").grid(row=2, column=0, sticky="w", pady=(6, 0))
        ttk.Label(chain, textvariable=self.analytics_node_version_var).grid(row=2, column=1, sticky="w", pady=(6, 0))
        ttk.Label(chain, text="moniker").grid(row=2, column=2, sticky="w", padx=(12, 0), pady=(6, 0))
        ttk.Label(chain, textvariable=self.analytics_moniker_var).grid(row=2, column=3, sticky="w", pady=(6, 0))

        ttk.Label(chain, text="RPC latency").grid(row=3, column=0, sticky="w", pady=(6, 0))
        ttk.Label(chain, textvariable=self.analytics_rpc_latency_var).grid(row=3, column=1, sticky="w", pady=(6, 0))

        self.analytics_latest_hash_var = tk.StringVar(value="-")
        self.analytics_latest_app_hash_var = tk.StringVar(value="-")
        self.analytics_block_lag_var = tk.StringVar(value="-")
        self.analytics_avg_block_time_var = tk.StringVar(value="-")
        self.analytics_node_id_var = tk.StringVar(value="-")
        self.analytics_listen_addr_var = tk.StringVar(value="-")
        self.analytics_validator_addr_var = tk.StringVar(value="-")
        self.analytics_validator_power_var = tk.StringVar(value="-")
        self.analytics_validator_set_total_var = tk.StringVar(value="-")
        self.analytics_abci_app_var = tk.StringVar(value="-")
        self.analytics_abci_version_var = tk.StringVar(value="-")
        self.analytics_tx_index_var = tk.StringVar(value="-")
        self.analytics_validator_pubkey_var = tk.StringVar(value="-")
        self.analytics_rpc_health_var = tk.StringVar(value="-")

        ttk.Label(chain, text="latest block hash").grid(row=4, column=0, sticky="w", pady=(6, 0))
        ttk.Label(chain, textvariable=self.analytics_latest_hash_var).grid(row=4, column=1, sticky="w", pady=(6, 0))
        ttk.Label(chain, text="latest app hash").grid(row=4, column=2, sticky="w", padx=(12, 0), pady=(6, 0))
        ttk.Label(chain, textvariable=self.analytics_latest_app_hash_var).grid(row=4, column=3, sticky="w", pady=(6, 0))

        ttk.Label(chain, text="block lag").grid(row=5, column=0, sticky="w", pady=(6, 0))
        ttk.Label(chain, textvariable=self.analytics_block_lag_var).grid(row=5, column=1, sticky="w", pady=(6, 0))
        ttk.Label(chain, text="avg block time").grid(row=5, column=2, sticky="w", padx=(12, 0), pady=(6, 0))
        ttk.Label(chain, textvariable=self.analytics_avg_block_time_var).grid(row=5, column=3, sticky="w", pady=(6, 0))

        ttk.Label(chain, text="node id").grid(row=6, column=0, sticky="w", pady=(6, 0))
        ttk.Label(chain, textvariable=self.analytics_node_id_var).grid(row=6, column=1, sticky="w", pady=(6, 0))
        ttk.Label(chain, text="listen addr").grid(row=6, column=2, sticky="w", padx=(12, 0), pady=(6, 0))
        ttk.Label(chain, textvariable=self.analytics_listen_addr_var).grid(row=6, column=3, sticky="w", pady=(6, 0))

        ttk.Label(chain, text="validator addr").grid(row=7, column=0, sticky="w", pady=(6, 0))
        ttk.Label(chain, textvariable=self.analytics_validator_addr_var).grid(row=7, column=1, sticky="w", pady=(6, 0))
        ttk.Label(chain, text="voting power").grid(row=7, column=2, sticky="w", padx=(12, 0), pady=(6, 0))
        ttk.Label(chain, textvariable=self.analytics_validator_power_var).grid(row=7, column=3, sticky="w", pady=(6, 0))

        ttk.Label(chain, text="validators (set)").grid(row=8, column=0, sticky="w", pady=(6, 0))
        ttk.Label(chain, textvariable=self.analytics_validator_set_total_var).grid(row=8, column=1, sticky="w", pady=(6, 0))
        ttk.Label(chain, text="ABCI app / ver").grid(row=8, column=2, sticky="w", padx=(12, 0), pady=(6, 0))
        ttk.Label(chain, textvariable=self.analytics_abci_app_var).grid(row=8, column=3, sticky="w", pady=(6, 0))

        ttk.Label(chain, text="tx_index").grid(row=9, column=0, sticky="w", pady=(6, 0))
        ttk.Label(chain, textvariable=self.analytics_tx_index_var).grid(row=9, column=1, sticky="w", pady=(6, 0))
        ttk.Label(chain, text="validator pubkey").grid(row=9, column=2, sticky="w", padx=(12, 0), pady=(6, 0))
        ttk.Label(chain, textvariable=self.analytics_validator_pubkey_var).grid(row=9, column=3, sticky="w", pady=(6, 0))

        ttk.Label(chain, text="RPC /health").grid(row=10, column=0, sticky="w", pady=(6, 0))
        ttk.Label(chain, textvariable=self.analytics_rpc_health_var).grid(row=10, column=1, sticky="w", pady=(6, 0))

        net = ttk.LabelFrame(analytics_tab, text="Network + mempool", padding=8)
        net.grid(row=3, column=0, columnspan=4, sticky="ew", pady=(0, 8))
        net.columnconfigure(1, weight=1)
        net.columnconfigure(3, weight=1)

        self.analytics_peers_var = tk.StringVar(value="-")
        self.analytics_listening_var = tk.StringVar(value="-")
        self.analytics_mempool_txs_var = tk.StringVar(value="-")
        self.analytics_mempool_bytes_var = tk.StringVar(value="-")

        ttk.Label(net, text="peers").grid(row=0, column=0, sticky="w")
        ttk.Label(net, textvariable=self.analytics_peers_var).grid(row=0, column=1, sticky="w")
        ttk.Label(net, text="listening").grid(row=0, column=2, sticky="w", padx=(12, 0))
        ttk.Label(net, textvariable=self.analytics_listening_var).grid(row=0, column=3, sticky="w")

        ttk.Label(net, text="mempool txs").grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Label(net, textvariable=self.analytics_mempool_txs_var).grid(row=1, column=1, sticky="w", pady=(6, 0))
        ttk.Label(net, text="mempool size").grid(row=1, column=2, sticky="w", padx=(12, 0), pady=(6, 0))
        ttk.Label(net, textvariable=self.analytics_mempool_bytes_var).grid(row=1, column=3, sticky="w", pady=(6, 0))

        peers_box = ttk.LabelFrame(analytics_tab, text="Peer sample (first 30)", padding=8)
        peers_box.grid(row=4, column=0, columnspan=4, sticky="nsew", pady=(0, 8))
        peers_box.columnconfigure(0, weight=1)
        self.analytics_peers_text = scrolledtext.ScrolledText(peers_box, height=8, wrap=tk.WORD, state="disabled")
        self.analytics_peers_text.grid(row=0, column=0, sticky="nsew")

        host = ttk.LabelFrame(analytics_tab, text="Host", padding=8)
        host.grid(row=5, column=0, columnspan=4, sticky="ew", pady=(0, 8))
        host.columnconfigure(1, weight=1)
        host.columnconfigure(3, weight=1)

        self.analytics_loadavg_var = tk.StringVar(value="-")
        self.analytics_memhost_var = tk.StringVar(value="-")
        ttk.Label(host, text="load avg (1/5/15)").grid(row=0, column=0, sticky="w")
        ttk.Label(host, textvariable=self.analytics_loadavg_var).grid(row=0, column=1, sticky="w")
        ttk.Label(host, text="RAM (avail/total)").grid(row=0, column=2, sticky="w", padx=(12, 0))
        ttk.Label(host, textvariable=self.analytics_memhost_var).grid(row=0, column=3, sticky="w")

        proc = ttk.LabelFrame(analytics_tab, text="Process + disk", padding=8)
        proc.grid(row=6, column=0, columnspan=4, sticky="ew", pady=(0, 8))
        proc.columnconfigure(1, weight=1)
        proc.columnconfigure(3, weight=1)

        alog = ttk.LabelFrame(analytics_tab, text="Analytics log", padding=8)
        alog.grid(row=7, column=0, columnspan=4, sticky="nsew")
        alog.columnconfigure(0, weight=1)
        self.analytics_log = scrolledtext.ScrolledText(alog, height=10, wrap=tk.WORD, state="disabled")
        self.analytics_log.grid(row=0, column=0, sticky="nsew")
        analytics_tab.rowconfigure(7, weight=1)

        self.analytics_proc_var = tk.StringVar(value="-")
        self.analytics_cpu_var = tk.StringVar(value="-")
        self.analytics_mem_var = tk.StringVar(value="-")
        self.analytics_uptime_var = tk.StringVar(value="-")
        self.analytics_disk_var = tk.StringVar(value="-")
        self.analytics_data_dir_var = tk.StringVar(value="-")

        ttk.Label(proc, text="retrochaind").grid(row=0, column=0, sticky="w")
        ttk.Label(proc, textvariable=self.analytics_proc_var).grid(row=0, column=1, sticky="w")
        ttk.Label(proc, text="CPU / RAM").grid(row=0, column=2, sticky="w", padx=(12, 0))
        ttk.Label(proc, textvariable=self.analytics_cpu_var).grid(row=0, column=3, sticky="w")

        ttk.Label(proc, text="uptime").grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Label(proc, textvariable=self.analytics_uptime_var).grid(row=1, column=1, sticky="w", pady=(6, 0))
        ttk.Label(proc, text="disk (home fs)").grid(row=1, column=2, sticky="w", padx=(12, 0), pady=(6, 0))
        ttk.Label(proc, textvariable=self.analytics_disk_var).grid(row=1, column=3, sticky="w", pady=(6, 0))

        ttk.Label(proc, text="data dir size").grid(row=2, column=0, sticky="w", pady=(6, 0))
        ttk.Label(proc, textvariable=self.analytics_data_dir_var).grid(row=2, column=1, sticky="w", pady=(6, 0))

        # ----------------------- Testnet tab content -----------------------
        testnet_tab.columnconfigure(1, weight=1)

        ttk.Label(testnet_tab, text="retrochaind binary").grid(row=0, column=0, sticky="w")
        self.test_bin_var = tk.StringVar(value=DEFAULT_BINARY)
        ttk.Entry(testnet_tab, textvariable=self.test_bin_var, width=50).grid(row=0, column=1, sticky="ew", padx=6)

        ttk.Label(testnet_tab, text="--home").grid(row=1, column=0, sticky="w")
        self.test_home_var = tk.StringVar(value=DEFAULT_TESTNET_HOME)
        ttk.Entry(testnet_tab, textvariable=self.test_home_var, width=50).grid(row=1, column=1, sticky="ew", padx=6)

        ttk.Label(testnet_tab, text="extra args").grid(row=2, column=0, sticky="w")
        self.test_args_var = tk.StringVar(value=DEFAULT_ARGS)
        ttk.Entry(testnet_tab, textvariable=self.test_args_var, width=50).grid(row=2, column=1, sticky="ew", padx=6)

        ttk.Label(testnet_tab, text="log file (optional)").grid(row=3, column=0, sticky="w")
        self.test_logfile_var = tk.StringVar(value=os.path.join(DEFAULT_TESTNET_HOME, "logs", "retrochaind.log"))
        ttk.Entry(testnet_tab, textvariable=self.test_logfile_var, width=50).grid(row=3, column=1, sticky="ew", padx=6)

        ports = ttk.LabelFrame(testnet_tab, text="Ports (write to TOML)", padding=8)
        ports.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        ports.columnconfigure(1, weight=1)
        ports.columnconfigure(3, weight=1)

        ttk.Label(ports, text="rpc.laddr").grid(row=0, column=0, sticky="w")
        self.test_rpc_laddr_var = tk.StringVar(value=DEFAULT_TESTNET_RPC_LADDR)
        ttk.Entry(ports, textvariable=self.test_rpc_laddr_var, width=26).grid(row=0, column=1, sticky="ew", padx=6)

        ttk.Label(ports, text="p2p.laddr").grid(row=0, column=2, sticky="w")
        self.test_p2p_laddr_var = tk.StringVar(value=DEFAULT_TESTNET_P2P_LADDR)
        ttk.Entry(ports, textvariable=self.test_p2p_laddr_var, width=26).grid(row=0, column=3, sticky="ew", padx=6)

        ttk.Label(ports, text="api.address").grid(row=1, column=0, sticky="w")
        self.test_api_addr_var = tk.StringVar(value=DEFAULT_TESTNET_API_ADDR)
        ttk.Entry(ports, textvariable=self.test_api_addr_var, width=26).grid(row=1, column=1, sticky="ew", padx=6, pady=(6, 0))

        ttk.Label(ports, text="grpc.address").grid(row=1, column=2, sticky="w")
        self.test_grpc_addr_var = tk.StringVar(value=DEFAULT_TESTNET_GRPC_ADDR)
        ttk.Entry(ports, textvariable=self.test_grpc_addr_var, width=26).grid(row=1, column=3, sticky="ew", padx=6, pady=(6, 0))

        test_btns = ttk.Frame(testnet_tab)
        test_btns.grid(row=5, column=0, columnspan=2, pady=8, sticky="w")
        ttk.Button(test_btns, text="Start", command=self.start_testnet_node).grid(row=0, column=0, padx=4)
        ttk.Button(test_btns, text="Stop", command=self.stop_testnet_node).grid(row=0, column=1, padx=4)
        ttk.Button(test_btns, text="Restart", command=self.restart_testnet_node).grid(row=0, column=2, padx=4)
        ttk.Button(test_btns, text="Status", command=self.show_testnet_status).grid(row=0, column=3, padx=4)
        ttk.Button(test_btns, text="Clone config from main", command=self.clone_mainnet_config_to_testnet).grid(row=0, column=4, padx=4)
        ttk.Button(test_btns, text="Apply ports", command=self.apply_testnet_ports).grid(row=0, column=5, padx=4)

        self.testnet_status_var = tk.StringVar(value="Idle")
        ttk.Label(testnet_tab, textvariable=self.testnet_status_var, foreground="blue").grid(row=6, column=0, columnspan=2, sticky="w", pady=(0, 6))

        self.testnet_log = scrolledtext.ScrolledText(testnet_tab, height=18, wrap=tk.WORD, state="disabled")
        self.testnet_log.grid(row=7, column=0, columnspan=2, sticky="nsew")
        testnet_tab.rowconfigure(7, weight=1)

        # Keyring management section
        keyring_frame = ttk.LabelFrame(node_tab, text="Keyring", padding=8)
        keyring_frame.grid(row=11, column=0, columnspan=2, sticky="nsew", pady=(10, 0))
        node_tab.rowconfigure(11, weight=1)

        ttk.Label(keyring_frame, text="backend").grid(row=0, column=0, sticky="w")
        self.keyring_backend_var = tk.StringVar(value=DEFAULT_KEYRING_BACKEND)
        ttk.Entry(keyring_frame, textvariable=self.keyring_backend_var, width=12).grid(row=0, column=1, sticky="w", padx=4)

        ttk.Label(keyring_frame, text="passphrase (optional)").grid(row=0, column=2, sticky="w")
        self.keyring_pass_var = tk.StringVar()
        ttk.Entry(keyring_frame, textvariable=self.keyring_pass_var, width=18, show="*").grid(row=0, column=3, sticky="w", padx=4)

        ttk.Button(keyring_frame, text="Refresh", command=self.refresh_keys).grid(row=0, column=4, padx=4)
        ttk.Button(keyring_frame, text="Show address", command=self.show_selected_address).grid(row=0, column=5, padx=4)
        ttk.Button(keyring_frame, text="Show pubkey", command=self.show_selected_pubkey).grid(row=0, column=6, padx=4)
        ttk.Button(keyring_frame, text="Add key", command=self.add_key).grid(row=0, column=7, padx=4)
        ttk.Button(keyring_frame, text="Create w/ mnemonic", command=self.create_key_with_mnemonic).grid(row=0, column=8, padx=4)
        ttk.Button(keyring_frame, text="Import mnemonic", command=self.import_mnemonic).grid(row=0, column=9, padx=4)
        ttk.Button(keyring_frame, text="Delete key", command=self.delete_key).grid(row=0, column=10, padx=4)

        self.keys_tree = ttk.Treeview(keyring_frame, columns=("name", "type", "address", "algo"), show="headings", height=8)
        for col, width in [("name", 140), ("type", 90), ("address", 320), ("algo", 100)]:
            self.keys_tree.heading(col, text=col)
            self.keys_tree.column(col, width=width, anchor="w")
        self.keys_tree.grid(row=1, column=0, columnspan=11, sticky="nsew", pady=(6, 0))
        keyring_frame.rowconfigure(1, weight=1)
        keyring_frame.columnconfigure(3, weight=1)

        # Hermes tab content
        hermes_tab.columnconfigure(1, weight=1)
        hermes_tab.columnconfigure(3, weight=1)

        ttk.Label(hermes_tab, text="binary").grid(row=0, column=0, sticky="w")
        self.hermes_bin_var = tk.StringVar(value=DEFAULT_HERMES_BINARY)
        ttk.Entry(hermes_tab, textvariable=self.hermes_bin_var).grid(row=0, column=1, sticky="ew", padx=4)
        ttk.Button(hermes_tab, text="Browse", command=self.browse_hermes_binary).grid(row=0, column=2, sticky="w")

        ttk.Label(hermes_tab, text="config").grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.hermes_config_var = tk.StringVar(value=DEFAULT_HERMES_CONFIG)
        ttk.Entry(hermes_tab, textvariable=self.hermes_config_var).grid(row=1, column=1, sticky="ew", padx=4, pady=(6, 0))
        ttk.Button(hermes_tab, text="Browse", command=self.browse_hermes_config).grid(row=1, column=2, sticky="w", pady=(6, 0))
        ttk.Button(hermes_tab, text="Load chains", command=self.refresh_hermes_config_info).grid(row=1, column=3, sticky="w", pady=(6, 0))

        self.hermes_config_info_var = tk.StringVar(value="config: (not loaded)")
        ttk.Label(hermes_tab, textvariable=self.hermes_config_info_var, foreground="gray").grid(
            row=2, column=0, columnspan=4, sticky="w", pady=(6, 0)
        )

        btns = ttk.Frame(hermes_tab)
        btns.grid(row=3, column=0, columnspan=4, pady=6, sticky="w")
        ttk.Button(btns, text="Start", command=self.start_hermes).grid(row=0, column=0, padx=4)
        ttk.Button(btns, text="Stop", command=self.stop_hermes).grid(row=0, column=1, padx=4)
        ttk.Button(btns, text="Health", command=self.hermes_health_check).grid(row=0, column=2, padx=4)
        ttk.Button(btns, text="Version", command=self.hermes_version).grid(row=0, column=3, padx=(14, 4))
        ttk.Button(btns, text="Validate config", command=self.hermes_validate_config).grid(row=0, column=4, padx=4)
        ttk.Button(btns, text="Clear log", command=self.clear_hermes_log).grid(row=0, column=5, padx=(14, 4))
        self.hermes_status_var = tk.StringVar(value="Hermes idle")
        ttk.Label(btns, textvariable=self.hermes_status_var, foreground="green").grid(row=0, column=6, padx=8)

        tools = ttk.LabelFrame(hermes_tab, text="Queries + tools", padding=8)
        tools.grid(row=4, column=0, columnspan=4, sticky="ew", pady=(0, 6))
        tools.columnconfigure(1, weight=1)
        tools.columnconfigure(3, weight=1)

        ttk.Label(tools, text="chain").grid(row=0, column=0, sticky="w")
        self.hermes_chain_var = tk.StringVar(value="")
        self.hermes_chain_combo = ttk.Combobox(tools, textvariable=self.hermes_chain_var, width=28, state="normal")
        self.hermes_chain_combo.grid(row=0, column=1, sticky="w", padx=6)
        ttk.Button(tools, text="Keys list", command=self.hermes_keys_list).grid(row=0, column=2, padx=4)
        ttk.Button(tools, text="Query channels", command=self.hermes_query_channels).grid(row=0, column=3, padx=4, sticky="w")

        ttk.Button(tools, text="Query clients", command=self.hermes_query_clients).grid(row=1, column=2, padx=4, pady=(6, 0))
        ttk.Button(tools, text="Query connections", command=self.hermes_query_connections).grid(row=1, column=3, padx=4, pady=(6, 0), sticky="w")

        ttk.Label(tools, text="args").grid(row=2, column=0, sticky="w", pady=(8, 0))
        self.hermes_cmd_args_var = tk.StringVar(value="query channels --chain <chain-id>")
        ttk.Entry(tools, textvariable=self.hermes_cmd_args_var).grid(row=2, column=1, columnspan=2, sticky="ew", padx=6, pady=(8, 0))
        ttk.Button(tools, text="Run", command=self.hermes_run_args).grid(row=2, column=3, sticky="w", pady=(8, 0))

        ibc = ttk.LabelFrame(hermes_tab, text="IBC links", padding=8)
        ibc.grid(row=5, column=0, columnspan=4, sticky="ew", pady=(0, 6))
        ibc.columnconfigure(1, weight=1)
        ibc.columnconfigure(3, weight=1)

        ttk.Label(ibc, text="from").grid(row=0, column=0, sticky="w")
        self.hermes_ibc_from_var = tk.StringVar(value="retrochain-mainnet")
        self.hermes_ibc_from_combo = ttk.Combobox(ibc, textvariable=self.hermes_ibc_from_var, width=28, state="normal")
        self.hermes_ibc_from_combo.grid(row=0, column=1, sticky="w", padx=6)

        ttk.Label(ibc, text="to").grid(row=0, column=2, sticky="w")
        self.hermes_ibc_to_var = tk.StringVar(value="cosmoshub-4")
        self.hermes_ibc_to_combo = ttk.Combobox(ibc, textvariable=self.hermes_ibc_to_var, width=28, state="normal")
        self.hermes_ibc_to_combo.grid(row=0, column=3, sticky="w", padx=6)

        ttk.Button(ibc, text="Refresh", command=self.hermes_refresh_ibc_links).grid(row=0, column=4, sticky="e", padx=(10, 0))

        self.hermes_ibc_summary = scrolledtext.ScrolledText(ibc, height=8, wrap=tk.WORD, state="disabled")
        self.hermes_ibc_summary.grid(row=1, column=0, columnspan=5, sticky="ew", pady=(6, 0))

        self.hermes_log = scrolledtext.ScrolledText(hermes_tab, height=22, wrap=tk.WORD, state="disabled")
        self.hermes_log.grid(row=6, column=0, columnspan=4, sticky="nsew")
        hermes_tab.rowconfigure(6, weight=1)

        # Initialize config-derived info.
        self.refresh_hermes_config_info()

        # Modules tab content
        modules_tab.columnconfigure(0, weight=0)
        modules_tab.columnconfigure(1, weight=1)
        modules_tab.rowconfigure(2, weight=1)

        left = ttk.Frame(modules_tab)
        left.grid(row=0, column=0, rowspan=3, sticky="ns", padx=(0, 10))

        ttk.Label(left, text="Query module").grid(row=0, column=0, sticky="w")
        self.query_module_var = tk.StringVar(value="arcade")
        self.query_module_combo = ttk.Combobox(left, textvariable=self.query_module_var, width=24, state="normal")
        self.query_module_combo.grid(row=1, column=0, sticky="w", pady=(0, 8))

        ttk.Label(left, text="Tx module").grid(row=2, column=0, sticky="w")
        self.tx_module_var = tk.StringVar(value="arcade")
        self.tx_module_combo = ttk.Combobox(left, textvariable=self.tx_module_var, width=24, state="normal")
        self.tx_module_combo.grid(row=3, column=0, sticky="w", pady=(0, 8))

        ttk.Button(left, text="Refresh modules", command=self.refresh_modules).grid(row=4, column=0, sticky="w")

        self.modules_bin_status_var = tk.StringVar(value="binary: (not resolved)")
        ttk.Label(left, textvariable=self.modules_bin_status_var, foreground="gray").grid(row=5, column=0, sticky="w", pady=(6, 0))

        right = ttk.Frame(modules_tab)
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(1, weight=1)

        ttk.Label(right, text="Command").grid(row=0, column=0, sticky="w")
        self.module_cmd_var = tk.StringVar(value="query arcade params --output json")
        ttk.Entry(right, textvariable=self.module_cmd_var).grid(row=0, column=1, sticky="ew", padx=6)
        ttk.Button(right, text="Run", command=self.run_module_command).grid(row=0, column=2, sticky="e")

        actions = ttk.Frame(modules_tab)
        actions.grid(row=1, column=1, sticky="w", pady=(6, 6))
        ttk.Button(actions, text="List query cmds", command=self.list_query_commands).grid(row=0, column=0, padx=(0, 6))
        ttk.Button(actions, text="Query params", command=self.query_selected_params).grid(row=0, column=1, padx=(0, 6))
        ttk.Button(actions, text="List tx cmds", command=self.list_tx_commands).grid(row=0, column=2, padx=(0, 6))

        hint = (
            "Note: Cosmos SDK modules are compiled into the binary; this tab helps you run safe CLI queries/txs \
    against modules (e.g. params, arcade queries)."
        )
        ttk.Label(modules_tab, text=hint, foreground="gray").grid(row=2, column=1, sticky="w")

        self.module_log = scrolledtext.ScrolledText(modules_tab, height=18, wrap=tk.WORD, state="disabled")
        self.module_log.grid(row=3, column=1, sticky="nsew")
        modules_tab.rowconfigure(3, weight=1)

        # Populate module lists once at startup
        self.refresh_modules()

        # SQL Indexer tab content
        indexer_tab.columnconfigure(1, weight=1)
        indexer_tab.rowconfigure(10, weight=1)

        ttk.Label(indexer_tab, text="RPC URL").grid(row=0, column=0, sticky="w")
        self.indexer_rpc_var = tk.StringVar(value=DEFAULT_SQL_INDEXER_RPC)
        ttk.Entry(indexer_tab, textvariable=self.indexer_rpc_var).grid(row=0, column=1, sticky="ew", padx=6)

        ttk.Label(indexer_tab, text="DB path (SQLite)").grid(row=1, column=0, sticky="w")
        self.indexer_db_var = tk.StringVar(value=DEFAULT_SQL_INDEXER_DB)
        ttk.Entry(indexer_tab, textvariable=self.indexer_db_var).grid(row=1, column=1, sticky="ew", padx=6)
        ttk.Button(indexer_tab, text="Browse", command=self.browse_indexer_db).grid(row=1, column=2, sticky="w")

        ttk.Label(indexer_tab, text="Poll seconds").grid(row=2, column=0, sticky="w")
        self.indexer_poll_var = tk.StringVar(value=DEFAULT_SQL_INDEXER_POLL_SECONDS)
        ttk.Entry(indexer_tab, textvariable=self.indexer_poll_var, width=10).grid(row=2, column=1, sticky="w", padx=6)

        ttk.Label(indexer_tab, text="Start height (optional)").grid(row=3, column=0, sticky="w")
        self.indexer_start_height_var = tk.StringVar(value="")
        ttk.Entry(indexer_tab, textvariable=self.indexer_start_height_var, width=14).grid(row=3, column=1, sticky="w", padx=6)

        ttk.Label(indexer_tab, text="Explorer API listen").grid(row=4, column=0, sticky="w")
        self.indexer_api_listen_var = tk.StringVar(value=DEFAULT_INDEXER_API_LISTEN)
        ttk.Entry(indexer_tab, textvariable=self.indexer_api_listen_var, width=18).grid(row=4, column=1, sticky="w", padx=6)

        ttk.Label(indexer_tab, text="API CORS origins (optional)").grid(row=5, column=0, sticky="w")
        self.indexer_api_cors_origins_var = tk.StringVar(value="")
        ttk.Entry(indexer_tab, textvariable=self.indexer_api_cors_origins_var).grid(row=5, column=1, sticky="ew", padx=6)

        idx_btns = ttk.Frame(indexer_tab)
        idx_btns.grid(row=6, column=0, columnspan=3, sticky="w", pady=6)
        ttk.Button(idx_btns, text="Start indexer", command=self.start_sql_indexer).grid(row=0, column=0, padx=4)
        ttk.Button(idx_btns, text="Stop indexer", command=self.stop_sql_indexer).grid(row=0, column=1, padx=4)
        ttk.Button(idx_btns, text="Reset DB", command=self.reset_sql_indexer_db).grid(row=0, column=2, padx=4)
        ttk.Button(idx_btns, text="Clear log", command=self.clear_sql_indexer_log).grid(row=0, column=3, padx=4)
        self.indexer_status_var = tk.StringVar(value="Indexer idle")
        ttk.Label(idx_btns, textvariable=self.indexer_status_var, foreground="green").grid(row=0, column=4, padx=10)

        api_btns = ttk.Frame(indexer_tab)
        api_btns.grid(row=7, column=0, columnspan=3, sticky="w", pady=(0, 6))
        ttk.Button(api_btns, text="Start API", command=self.start_indexer_api).grid(row=0, column=0, padx=4)
        ttk.Button(api_btns, text="Stop API", command=self.stop_indexer_api).grid(row=0, column=1, padx=4)
        ttk.Button(api_btns, text="Open API /v1/status", command=self.open_indexer_api_status).grid(row=0, column=2, padx=(14, 4))
        self.indexer_api_status_var = tk.StringVar(value="API idle")
        ttk.Label(api_btns, textvariable=self.indexer_api_status_var, foreground="green").grid(row=0, column=3, padx=10)

        status_box = ttk.LabelFrame(indexer_tab, text="Status", padding=8)
        status_box.grid(row=8, column=0, columnspan=3, sticky="ew", pady=(0, 6))
        status_box.columnconfigure(0, weight=1)

        status_top = ttk.Frame(status_box)
        status_top.grid(row=0, column=0, sticky="ew")
        status_top.columnconfigure(2, weight=1)

        self.indexer_auto_refresh_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(status_top, text="Auto refresh", variable=self.indexer_auto_refresh_var).grid(row=0, column=0, sticky="w")
        ttk.Button(status_top, text="Refresh now", command=self.refresh_indexer_status).grid(row=0, column=1, padx=(10, 0), sticky="w")

        self.indexer_status_details_var = tk.StringVar(value="(not refreshed yet)")
        ttk.Label(status_box, textvariable=self.indexer_status_details_var, justify="left").grid(row=1, column=0, sticky="w", pady=(6, 0))

        hint2 = (
            "Built-in indexer: pulls blocks + txs + ABCI events from CometBFT RPC and stores them in SQLite.\n"
            "It indexes begin_block/end_block events and tx events (from /block_results).\n"
            "Leave Start height empty to resume from the last indexed height in the DB."
        )
        ttk.Label(indexer_tab, text=hint2, foreground="gray").grid(row=9, column=0, columnspan=3, sticky="w", pady=(0, 6))

        self.indexer_log = scrolledtext.ScrolledText(indexer_tab, height=20, wrap=tk.WORD, state="disabled")
        self.indexer_log.grid(row=10, column=0, columnspan=3, sticky="nsew")
        indexer_tab.rowconfigure(10, weight=1)

        # ----------------------- Nginx tab content -----------------------
        nginx_tab.columnconfigure(1, weight=1)
        nginx_tab.rowconfigure(6, weight=1)

        ttk.Label(nginx_tab, text="Service name").grid(row=0, column=0, sticky="w")
        self.nginx_service_var = tk.StringVar(value="nginx")
        ttk.Entry(nginx_tab, textvariable=self.nginx_service_var, width=18).grid(row=0, column=1, sticky="w", padx=6)

        ttk.Label(nginx_tab, text="stub_status URL (optional)").grid(row=1, column=0, sticky="w")
        self.nginx_stub_status_url_var = tk.StringVar(value="")
        ttk.Entry(nginx_tab, textvariable=self.nginx_stub_status_url_var).grid(row=1, column=1, sticky="ew", padx=6)

        btns = ttk.Frame(nginx_tab)
        btns.grid(row=2, column=0, columnspan=3, sticky="w", pady=(6, 6))
        ttk.Button(btns, text="Start", command=lambda: self.nginx_service_action("start")).grid(row=0, column=0, padx=4)
        ttk.Button(btns, text="Stop", command=lambda: self.nginx_service_action("stop")).grid(row=0, column=1, padx=4)
        ttk.Button(btns, text="Restart", command=lambda: self.nginx_service_action("restart")).grid(row=0, column=2, padx=4)
        ttk.Button(btns, text="Reload", command=lambda: self.nginx_service_action("reload")).grid(row=0, column=3, padx=4)
        ttk.Button(btns, text="Test config (nginx -t)", command=self.nginx_test_config).grid(row=0, column=4, padx=(14, 4))

        status_box = ttk.LabelFrame(nginx_tab, text="Status", padding=8)
        status_box.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(0, 6))
        status_box.columnconfigure(0, weight=1)

        status_top = ttk.Frame(status_box)
        status_top.grid(row=0, column=0, sticky="ew")
        status_top.columnconfigure(3, weight=1)

        self.nginx_auto_refresh_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(status_top, text="Auto refresh", variable=self.nginx_auto_refresh_var).grid(row=0, column=0, sticky="w")
        ttk.Button(status_top, text="Refresh now", command=self.refresh_nginx_status).grid(row=0, column=1, padx=(10, 0), sticky="w")
        self.nginx_status_var = tk.StringVar(value="(not refreshed yet)")
        ttk.Label(status_top, textvariable=self.nginx_status_var, foreground="gray").grid(row=0, column=2, padx=(10, 0), sticky="w")

        self.nginx_status_details_var = tk.StringVar(value="")
        ttk.Label(status_box, textvariable=self.nginx_status_details_var, justify="left").grid(row=1, column=0, sticky="w", pady=(6, 0))

        sites = ttk.LabelFrame(nginx_tab, text="Sites (enabled)", padding=8)
        sites.grid(row=4, column=0, columnspan=3, sticky="nsew", pady=(0, 6))
        sites.columnconfigure(0, weight=1)
        sites.columnconfigure(1, weight=1)
        sites.rowconfigure(1, weight=1)
        sites.rowconfigure(3, weight=1)

        sites_top = ttk.Frame(sites)
        sites_top.grid(row=0, column=0, columnspan=2, sticky="ew")
        ttk.Button(sites_top, text="Refresh sites", command=self.refresh_nginx_sites).grid(row=0, column=0, padx=(0, 6))
        ttk.Label(sites_top, text="Minutes").grid(row=0, column=1, sticky="e")
        self.nginx_sites_minutes_var = tk.StringVar(value="10")
        ttk.Entry(sites_top, textvariable=self.nginx_sites_minutes_var, width=6).grid(row=0, column=2, padx=(4, 10), sticky="w")
        ttk.Label(sites_top, text="Max lines").grid(row=0, column=3, sticky="e")
        self.nginx_sites_max_lines_var = tk.StringVar(value="4000")
        ttk.Entry(sites_top, textvariable=self.nginx_sites_max_lines_var, width=8).grid(row=0, column=4, padx=(4, 10), sticky="w")
        ttk.Button(sites_top, text="Analyze selected", command=self.nginx_analyze_selected_site).grid(row=0, column=5, padx=(0, 6))

        sites_tree = ttk.Treeview(
            sites,
            columns=("file", "server", "listen", "type", "access_log"),
            show="headings",
            height=7,
        )
        sites_tree.heading("file", text="Config")
        sites_tree.heading("server", text="server_name")
        sites_tree.heading("listen", text="listen")
        sites_tree.heading("type", text="type")
        sites_tree.heading("access_log", text="access_log")
        sites_tree.column("file", width=220, anchor="w")
        sites_tree.column("server", width=220, anchor="w")
        sites_tree.column("listen", width=110, anchor="w")
        sites_tree.column("type", width=70, anchor="w")
        sites_tree.column("access_log", width=240, anchor="w")
        sites_tree.grid(row=1, column=0, columnspan=2, sticky="nsew")
        self._nginx_sites_tree = sites_tree

        yscroll_sites = ttk.Scrollbar(sites, orient="vertical", command=sites_tree.yview)
        sites_tree.configure(yscrollcommand=yscroll_sites.set)
        yscroll_sites.grid(row=1, column=2, sticky="ns")

        details = ttk.LabelFrame(sites, text="Selected site details", padding=8)
        details.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        details.columnconfigure(0, weight=1)
        self.nginx_site_details_var = tk.StringVar(value="(select a site)")
        ttk.Label(details, textvariable=self.nginx_site_details_var, justify="left").grid(row=0, column=0, sticky="w")

        self.nginx_sites_analytics = scrolledtext.ScrolledText(sites, height=9, wrap=tk.WORD, state="disabled")
        self.nginx_sites_analytics.grid(row=3, column=0, columnspan=2, sticky="nsew", pady=(6, 0))

        hint_ng = (
            "Note: Start/stop/reload uses systemd (systemctl). If you see permission errors, run the GUI with appropriate privileges "
            "or configure polkit for service management."
        )
        ttk.Label(nginx_tab, text=hint_ng, foreground="gray").grid(row=5, column=0, columnspan=3, sticky="w", pady=(0, 6))

        self.nginx_log = scrolledtext.ScrolledText(nginx_tab, height=18, wrap=tk.WORD, state="disabled")
        self.nginx_log.grid(row=6, column=0, columnspan=3, sticky="nsew")

        try:
            sites_tree.bind("<<TreeviewSelect>>", lambda _e: self._nginx_sites_on_select())
        except Exception:
            pass

        # Populate sites list once at startup.
        self.refresh_nginx_sites()

        # Setup tab content
        setup_tab.columnconfigure(1, weight=1)
        setup_tab.rowconfigure(6, weight=1)

        common = ttk.LabelFrame(setup_tab, text="Common", padding=8)
        common.grid(row=0, column=0, columnspan=3, sticky="nsew")
        common.columnconfigure(1, weight=1)

        ttk.Label(common, text="Chain ID").grid(row=0, column=0, sticky="w")
        self.setup_chain_id_var = tk.StringVar(value=DEFAULT_SETUP_CHAIN_ID)
        ttk.Entry(common, textvariable=self.setup_chain_id_var, width=28).grid(row=0, column=1, sticky="w", padx=6)

        ttk.Label(common, text="Moniker").grid(row=0, column=2, sticky="w", padx=(12, 0))
        self.setup_moniker_var = tk.StringVar(value=(os.uname().nodename if hasattr(os, "uname") else "retro-node"))
        ttk.Entry(common, textvariable=self.setup_moniker_var, width=28).grid(row=0, column=3, sticky="w", padx=6)

        ttk.Label(common, text="Genesis URL (optional)").grid(row=1, column=0, sticky="w")
        self.setup_genesis_url_var = tk.StringVar(value="")
        ttk.Entry(common, textvariable=self.setup_genesis_url_var).grid(row=1, column=1, columnspan=3, sticky="ew", padx=6)

        ttk.Label(common, text="Seeds (optional)").grid(row=2, column=0, sticky="w")
        self.setup_seeds_var = tk.StringVar(value="")
        ttk.Entry(common, textvariable=self.setup_seeds_var).grid(row=2, column=1, columnspan=3, sticky="ew", padx=6)

        ttk.Label(common, text="Persistent peers (optional)").grid(row=3, column=0, sticky="w")
        self.setup_persistent_peers_var = tk.StringVar(value="")
        ttk.Entry(common, textvariable=self.setup_persistent_peers_var).grid(row=3, column=1, columnspan=3, sticky="ew", padx=6)

        ttk.Label(common, text="Minimum gas prices").grid(row=4, column=0, sticky="w")
        self.setup_min_gas_prices_var = tk.StringVar(value=DEFAULT_SETUP_MIN_GAS_PRICES)
        ttk.Entry(common, textvariable=self.setup_min_gas_prices_var, width=18).grid(row=4, column=1, sticky="w", padx=6)

        common_btns = ttk.Frame(common)
        common_btns.grid(row=5, column=0, columnspan=4, sticky="w", pady=(8, 0))
        ttk.Button(common_btns, text="Init node", command=self.setup_init_node).grid(row=0, column=0, padx=4)
        ttk.Button(common_btns, text="Download genesis", command=self.setup_download_genesis).grid(row=0, column=1, padx=4)
        ttk.Button(common_btns, text="Apply basic config", command=self.setup_apply_basic_config).grid(row=0, column=2, padx=4)
        ttk.Button(common_btns, text="Clear log", command=self.clear_setup_log).grid(row=0, column=3, padx=4)

        rpc = ttk.LabelFrame(setup_tab, text="RPC Node Setup", padding=8)
        rpc.grid(row=1, column=0, columnspan=3, sticky="nsew", pady=(10, 0))
        rpc.columnconfigure(1, weight=1)

        ttk.Label(rpc, text="RPC servers (for state sync)").grid(row=0, column=0, sticky="w")
        self.setup_statesync_rpc_servers_var = tk.StringVar(value="")
        ttk.Entry(rpc, textvariable=self.setup_statesync_rpc_servers_var).grid(row=0, column=1, columnspan=3, sticky="ew", padx=6)

        self.setup_public_rpc_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(rpc, text="Public RPC (0.0.0.0:26657)", variable=self.setup_public_rpc_var).grid(
            row=1, column=0, sticky="w", pady=(6, 0)
        )

        self.setup_statesync_enable_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(rpc, text="Enable state sync", variable=self.setup_statesync_enable_var).grid(
            row=1, column=1, sticky="w", pady=(6, 0)
        )

        ttk.Label(rpc, text="Trust height").grid(row=2, column=0, sticky="w")
        self.setup_statesync_trust_height_var = tk.StringVar(value="")
        ttk.Entry(rpc, textvariable=self.setup_statesync_trust_height_var, width=14).grid(row=2, column=1, sticky="w", padx=6)

        ttk.Label(rpc, text="Trust hash").grid(row=2, column=2, sticky="w", padx=(12, 0))
        self.setup_statesync_trust_hash_var = tk.StringVar(value="")
        ttk.Entry(rpc, textvariable=self.setup_statesync_trust_hash_var, width=50).grid(row=2, column=3, sticky="w", padx=6)

        rpc_btns = ttk.Frame(rpc)
        rpc_btns.grid(row=3, column=0, columnspan=4, sticky="w", pady=(8, 0))
        ttk.Button(rpc_btns, text="Auto-fill trust params", command=self.setup_autofill_trust).grid(row=0, column=0, padx=4)
        ttk.Button(rpc_btns, text="Apply RPC config", command=self.setup_apply_rpc_config).grid(row=0, column=1, padx=4)

        val = ttk.LabelFrame(setup_tab, text="Validator Setup", padding=8)
        val.grid(row=2, column=0, columnspan=3, sticky="nsew", pady=(10, 0))
        val.columnconfigure(1, weight=1)

        ttk.Label(val, text="Key name").grid(row=0, column=0, sticky="w")
        self.setup_val_key_name_var = tk.StringVar(value="validator")
        ttk.Entry(val, textvariable=self.setup_val_key_name_var, width=22).grid(row=0, column=1, sticky="w", padx=6)

        ttk.Label(val, text="Self-delegate amount").grid(row=0, column=2, sticky="w", padx=(12, 0))
        self.setup_val_amount_var = tk.StringVar(value="1000000uretro")
        ttk.Entry(val, textvariable=self.setup_val_amount_var, width=18).grid(row=0, column=3, sticky="w", padx=6)

        ttk.Label(val, text="Fees").grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.setup_val_fees_var = tk.StringVar(value="5000uretro")
        ttk.Entry(val, textvariable=self.setup_val_fees_var, width=18).grid(row=1, column=1, sticky="w", padx=6, pady=(6, 0))

        ttk.Label(val, text="Commission (rate/max/max-change)").grid(row=1, column=2, sticky="w", padx=(12, 0), pady=(6, 0))
        self.setup_val_commission_var = tk.StringVar(value="0.10/0.20/0.01")
        ttk.Entry(val, textvariable=self.setup_val_commission_var, width=22).grid(row=1, column=3, sticky="w", padx=6, pady=(6, 0))

        ttk.Label(val, text="Min self-delegation").grid(row=2, column=0, sticky="w", pady=(6, 0))
        self.setup_val_min_self_del_var = tk.StringVar(value="1")
        ttk.Entry(val, textvariable=self.setup_val_min_self_del_var, width=10).grid(row=2, column=1, sticky="w", padx=6, pady=(6, 0))

        val_btns = ttk.Frame(val)
        val_btns.grid(row=3, column=0, columnspan=4, sticky="w", pady=(8, 0))
        ttk.Button(val_btns, text="Create key", command=self.setup_create_validator_key).grid(row=0, column=0, padx=4)
        ttk.Button(val_btns, text="Show validator pubkey", command=self.setup_show_validator_pubkey).grid(row=0, column=1, padx=4)
        ttk.Button(val_btns, text="Generate create-validator cmd", command=self.setup_generate_create_validator_cmd).grid(
            row=0, column=2, padx=4
        )
        ttk.Button(val_btns, text="Broadcast create-validator", command=self.setup_broadcast_create_validator).grid(
            row=0, column=3, padx=4
        )

        hint_setup = (
            "This tab helps new users bootstrap a node home directory and basic configs.\n"
            "- RPC node: optionally enable state-sync and public RPC listening.\n"
            "- Validator: generates a create-validator tx command (you still need funded keys)."
        )
        ttk.Label(setup_tab, text=hint_setup, foreground="gray").grid(row=3, column=0, columnspan=3, sticky="w", pady=(8, 0))

        self.setup_log = scrolledtext.ScrolledText(setup_tab, height=18, wrap=tk.WORD, state="disabled")
        self.setup_log.grid(row=6, column=0, columnspan=3, sticky="nsew", pady=(8, 0))

    def append_node_log(self, line: str) -> None:
        self.node_log.configure(state="normal")
        self.node_log.insert(tk.END, line)
        self.node_log.see(tk.END)
        self.node_log.configure(state="disabled")

    def browse_upgrade_binary(self) -> None:
        initial = _repo_root()
        try:
            build_dir = os.path.join(_repo_root(), "build")
            if os.path.isdir(build_dir):
                initial = build_dir
        except Exception:
            pass

        path = filedialog.askopenfilename(
            title="Select upgraded retrochaind binary",
            initialdir=initial,
            filetypes=[("All files", "*"), ("retrochaind", "retrochaind*"), ("All", "*")],
        )
        if path:
            self.upgrade_bin_var.set(path)

    def open_binary_backup_manager(self) -> None:
        if self._bbm_window and self._bbm_window.winfo_exists():
            try:
                self._bbm_window.lift()
                self._bbm_window.focus_force()
            except Exception:
                pass
            return

        win = tk.Toplevel(self.root)
        win.title("Binary Backup Manager")
        win.geometry("1150x700")
        win.transient(self.root)
        self._bbm_window = win

        outer = ttk.Frame(win, padding=10)
        outer.grid(row=0, column=0, sticky="nsew")
        win.rowconfigure(0, weight=1)
        win.columnconfigure(0, weight=1)

        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(2, weight=1)
        outer.rowconfigure(5, weight=1)

        # Backup destination
        home_root = os.path.expanduser(self.home_var.get().strip() or DEFAULT_HOME)
        backup_dir_default = os.path.join(home_root, "bin_backups", "collected")
        self._bbm_backup_dir_var = tk.StringVar(value=backup_dir_default)
        backup_row = ttk.Frame(outer)
        backup_row.grid(row=0, column=0, sticky="ew")
        backup_row.columnconfigure(1, weight=1)
        ttk.Label(backup_row, text="Backup folder").grid(row=0, column=0, sticky="w")
        ttk.Entry(backup_row, textvariable=self._bbm_backup_dir_var, width=80).grid(row=0, column=1, sticky="ew", padx=6)
        ttk.Button(backup_row, text="Browse", command=self._bbm_browse_backup_dir).grid(row=0, column=2, padx=4)

        # Scan roots
        roots = ttk.LabelFrame(outer, text="Scan locations", padding=8)
        roots.grid(row=1, column=0, sticky="ew", pady=(8, 8))
        roots.columnconfigure(1, weight=1)
        roots.columnconfigure(3, weight=1)

        common_roots: list[tuple[str, str, bool]] = [
            ("Repo build", os.path.join(_repo_root(), "build"), True),
            ("~/.retrochain", os.path.expanduser("~/.retrochain"), True),
            ("~", os.path.expanduser("~"), False),
            ("/usr/local/bin", "/usr/local/bin", True),
            ("/usr/bin", "/usr/bin", False),
            ("/opt", "/opt", False),
            ("/", "/", False),
        ]
        self._bbm_scan_roots_vars = {}
        for i, (label, path, enabled) in enumerate(common_roots):
            var = tk.BooleanVar(value=enabled)
            self._bbm_scan_roots_vars[path] = var
            ttk.Checkbutton(roots, text=f"{label}: {path}", variable=var).grid(
                row=i // 2, column=(i % 2) * 2, columnspan=2, sticky="w", padx=6, pady=2
            )

        # Extra paths
        self._bbm_extra_paths_var = tk.StringVar(value="")
        ttk.Label(roots, text="Extra paths (comma-separated)").grid(row=4, column=0, sticky="w", padx=6, pady=(6, 0))
        ttk.Entry(roots, textvariable=self._bbm_extra_paths_var, width=60).grid(
            row=4, column=1, columnspan=2, sticky="ew", padx=6, pady=(6, 0)
        )
        ttk.Button(roots, text="Add Folder", command=self._bbm_add_extra_path).grid(
            row=4, column=3, sticky="w", padx=4, pady=(6, 0)
        )

        # Results table
        table_frame = ttk.Frame(outer)
        table_frame.grid(row=2, column=0, sticky="nsew")
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)

        cols = ("name", "path", "size", "mtime", "age", "sha256", "version", "protected")
        tree = ttk.Treeview(table_frame, columns=cols, show="headings", selectmode="extended")
        self._bbm_tree = tree
        tree.heading("name", text="Name")
        tree.heading("path", text="Path")
        tree.heading("size", text="Size")
        tree.heading("mtime", text="Modified")
        tree.heading("age", text="Age (days)")
        tree.heading("sha256", text="SHA256")
        tree.heading("version", text="Version")
        tree.heading("protected", text="Protected")
        tree.column("name", width=170, anchor="w")
        tree.column("path", width=680, anchor="w")
        tree.column("size", width=90, anchor="e")
        tree.column("mtime", width=160, anchor="w")
        tree.column("age", width=90, anchor="e")
        tree.column("sha256", width=120, anchor="w")
        tree.column("version", width=170, anchor="w")
        tree.column("protected", width=80, anchor="w")
        tree.grid(row=0, column=0, sticky="nsew")

        try:
            tree.bind("<<TreeviewSelect>>", lambda _evt: self._bbm_update_details_from_selection())
        except Exception:
            pass

        yscroll = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=yscroll.set)
        yscroll.grid(row=0, column=1, sticky="ns")

        # Actions
        actions = ttk.Frame(outer)
        actions.grid(row=3, column=0, sticky="ew", pady=(8, 0))

        ttk.Button(actions, text="Scan", command=self._bbm_scan).grid(row=0, column=0, padx=4)
        ttk.Button(actions, text="Cancel scan", command=self._bbm_cancel_scan).grid(row=0, column=1, padx=4)
        ttk.Button(actions, text="Select All", command=self._bbm_select_all).grid(row=0, column=2, padx=4)
        ttk.Button(actions, text="Move selected to backup", command=self._bbm_move_selected).grid(row=0, column=3, padx=4)
        ttk.Button(actions, text="Delete selected", command=self._bbm_delete_selected).grid(row=0, column=4, padx=4)

        self._bbm_delete_older_days_var = tk.StringVar(value="60")
        ttk.Label(actions, text="Delete older than (days)").grid(row=0, column=5, padx=(14, 4), sticky="e")
        ttk.Entry(actions, textvariable=self._bbm_delete_older_days_var, width=8).grid(row=0, column=6, sticky="w")
        ttk.Button(actions, text="Delete", command=self._bbm_delete_older_than).grid(row=0, column=7, padx=4)

        ttk.Button(actions, text="Hash selected", command=self._bbm_hash_selected).grid(row=0, column=8, padx=(14, 4))
        ttk.Button(actions, text="Version selected", command=self._bbm_version_selected).grid(row=0, column=9, padx=4)

        # Details
        details = ttk.LabelFrame(outer, text="Selected binary details", padding=8)
        details.grid(row=4, column=0, sticky="ew", pady=(8, 0))
        details.columnconfigure(1, weight=1)
        details.columnconfigure(3, weight=1)

        def _mk(key: str, default: str = "-") -> tk.StringVar:
            v = tk.StringVar(value=default)
            self._bbm_details_vars[key] = v
            return v

        ttk.Label(details, text="path").grid(row=0, column=0, sticky="w")
        ttk.Label(details, textvariable=_mk("path")).grid(row=0, column=1, columnspan=3, sticky="w")

        ttk.Label(details, text="realpath").grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Label(details, textvariable=_mk("realpath")).grid(row=1, column=1, columnspan=3, sticky="w", pady=(6, 0))

        ttk.Label(details, text="sha256").grid(row=2, column=0, sticky="w", pady=(6, 0))
        ttk.Label(details, textvariable=_mk("sha256")).grid(row=2, column=1, columnspan=3, sticky="w", pady=(6, 0))

        ttk.Label(details, text="version").grid(row=3, column=0, sticky="w", pady=(6, 0))
        ttk.Label(details, textvariable=_mk("version")).grid(row=3, column=1, columnspan=3, sticky="w", pady=(6, 0))

        ttk.Label(details, text="size / mtime").grid(row=4, column=0, sticky="w", pady=(6, 0))
        ttk.Label(details, textvariable=_mk("meta")).grid(row=4, column=1, sticky="w", pady=(6, 0))
        ttk.Label(details, text="protected").grid(row=4, column=2, sticky="w", padx=(12, 0), pady=(6, 0))
        ttk.Label(details, textvariable=_mk("protected")).grid(row=4, column=3, sticky="w", pady=(6, 0))

        # Status
        self._bbm_status_var = tk.StringVar(value="Ready")
        ttk.Label(outer, textvariable=self._bbm_status_var, foreground="gray").grid(row=5, column=0, sticky="w", pady=(6, 0))

        self._bbm_scan_queue = queue.Queue()
        self._bbm_poll_scan_queue()

    def _bbm_browse_backup_dir(self) -> None:
        if not self._bbm_backup_dir_var:
            return
        path = filedialog.askdirectory(title="Select backup folder")
        if path:
            self._bbm_backup_dir_var.set(path)

    def _bbm_add_extra_path(self) -> None:
        if not self._bbm_extra_paths_var:
            return
        path = filedialog.askdirectory(title="Add scan folder")
        if not path:
            return
        cur = (self._bbm_extra_paths_var.get() or "").strip()
        if not cur:
            self._bbm_extra_paths_var.set(path)
            return
        parts = [p.strip() for p in cur.split(",") if p.strip()]
        if path not in parts:
            parts.append(path)
        self._bbm_extra_paths_var.set(", ".join(parts))

    def _bbm_set_status(self, msg: str) -> None:
        if self._bbm_status_var:
            self._bbm_status_var.set(msg)

    def _bbm_poll_scan_queue(self) -> None:
        if not (self._bbm_window and self._bbm_window.winfo_exists()):
            return
        if self._bbm_scan_queue and self._bbm_tree:
            try:
                results = self._bbm_scan_queue.get_nowait()
            except queue.Empty:
                results = None
            if results is not None:
                self._bbm_render_results(results)
        self.root.after(250, self._bbm_poll_scan_queue)

    def _bbm_render_results(self, results: list[dict]) -> None:
        if not self._bbm_tree:
            return
        tree = self._bbm_tree
        for iid in tree.get_children():
            tree.delete(iid)

        self._bbm_rows_by_path = {}
        protected = self._bbm_current_bin_paths_protected()

        for item in results:
            path = item.get("path", "")
            ap = os.path.abspath(str(path))
            name = os.path.basename(ap)
            size = int(item.get("size", -1))
            mtime = item.get("mtime")
            try:
                mtime_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(float(mtime))) if mtime else ""
            except Exception:
                mtime_str = ""
            age = _age_days_from_mtime(float(mtime) if mtime else None)
            age_str = "" if age is None else str(age)

            is_protected = "yes" if ap in protected else ""
            sha_short = str(item.get("sha256_short") or "")
            ver = str(item.get("version") or "")
            tree.insert("", "end", values=(name, ap, _format_bytes(size), mtime_str, age_str, sha_short, ver, is_protected))
            self._bbm_rows_by_path[ap] = {
                "path": ap,
                "realpath": str(item.get("realpath") or ""),
                "size": size,
                "mtime": float(mtime) if mtime else None,
                "sha256": str(item.get("sha256") or ""),
                "sha256_short": sha_short,
                "version": ver,
                "protected": bool(ap in protected),
            }

        self._bbm_set_status(f"Found {len(results)} retrochaind* binaries")
        self._bbm_update_details_from_selection()

    def _bbm_update_details_from_selection(self) -> None:
        if not self._bbm_details_vars:
            return
        sel = self._bbm_selected_paths()
        if not sel:
            for k, v in self._bbm_details_vars.items():
                v.set("-" if k != "protected" else "")
            return
        p = os.path.abspath(sel[0])
        row = (self._bbm_rows_by_path or {}).get(p, {})
        self._bbm_details_vars.get("path", tk.StringVar()).set(p)
        rp = row.get("realpath") or ""
        if not rp:
            try:
                rp = os.path.realpath(p)
            except Exception:
                rp = ""
        self._bbm_details_vars.get("realpath", tk.StringVar()).set(rp or "-")
        self._bbm_details_vars.get("sha256", tk.StringVar()).set(row.get("sha256") or "-")
        self._bbm_details_vars.get("version", tk.StringVar()).set(row.get("version") or "-")
        try:
            st = os.lstat(p)
            mtime_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(float(st.st_mtime)))
            meta = f"{_format_bytes(int(st.st_size))} / {mtime_str}"
        except Exception:
            meta = "-"
        self._bbm_details_vars.get("meta", tk.StringVar()).set(meta)
        self._bbm_details_vars.get("protected", tk.StringVar()).set("yes" if row.get("protected") else "")

    def _bbm_cancel_scan(self) -> None:
        self._bbm_scan_cancel.set()
        self._bbm_set_status("Scan cancel requested...")

    def _bbm_get_scan_roots(self) -> list[str]:
        roots: list[str] = []
        for path, var in (self._bbm_scan_roots_vars or {}).items():
            try:
                if bool(var.get()):
                    roots.append(path)
            except Exception:
                continue

        extra = (self._bbm_extra_paths_var.get().strip() if self._bbm_extra_paths_var else "")
        if extra:
            for part in [p.strip() for p in extra.split(",") if p.strip()]:
                roots.append(os.path.expanduser(part))

        seen: set[str] = set()
        out: list[str] = []
        for r in roots:
            rr = os.path.abspath(r)
            if rr not in seen:
                seen.add(rr)
                out.append(rr)
        return out

    def _bbm_scan(self) -> None:
        selected_roots = self._bbm_get_scan_roots()
        if "/" in selected_roots:
            if not messagebox.askyesno(
                "Confirm scan",
                "Scanning '/' can be slow and may hit permission errors.\n\nContinue?",
                parent=self._bbm_window or self.root,
            ):
                return

        if self._bbm_scan_thread and self._bbm_scan_thread.is_alive():
            messagebox.showinfo("Scan", "A scan is already running.", parent=self._bbm_window or self.root)
            return

        self._bbm_set_status("Scanning...")
        self._bbm_scan_cancel.clear()
        self._bbm_scan_thread = threading.Thread(target=self._bbm_scan_worker, args=(selected_roots,), daemon=True)
        self._bbm_scan_thread.start()

    def _bbm_scan_worker(self, roots: list[str]) -> None:
        results: list[dict] = []
        name_prefix = "retrochaind"
        for root_path in roots:
            if self._bbm_scan_cancel.is_set():
                break
            if not os.path.exists(root_path):
                continue
            try:
                for dirpath, dirnames, filenames in os.walk(root_path, followlinks=False):
                    if self._bbm_scan_cancel.is_set():
                        break

                    try:
                        dirnames[:] = [d for d in dirnames if d not in {".git", "node_modules", "__pycache__", ".cache"}]
                    except Exception:
                        pass

                    for fname in filenames:
                        if not fname.startswith(name_prefix):
                            continue
                        path = os.path.join(dirpath, fname)
                        try:
                            st = os.lstat(path)
                            if not os.path.isfile(path) and not os.path.islink(path):
                                continue
                            if os.path.islink(path):
                                try:
                                    target = os.path.realpath(path)
                                    if not os.path.isfile(target):
                                        continue
                                except Exception:
                                    continue
                            if not os.access(path, os.X_OK):
                                continue
                            realp = ""
                            try:
                                realp = os.path.realpath(path)
                            except Exception:
                                realp = ""
                            results.append({"path": path, "realpath": realp, "size": int(st.st_size), "mtime": float(st.st_mtime)})
                        except PermissionError:
                            continue
                        except FileNotFoundError:
                            continue
                        except OSError:
                            continue
            except PermissionError:
                continue
            except OSError:
                continue

        results.sort(key=lambda x: x.get("mtime", 0.0), reverse=True)
        if self._bbm_scan_queue:
            self._bbm_scan_queue.put(results)

    def _bbm_select_all(self) -> None:
        if not self._bbm_tree:
            return
        for iid in self._bbm_tree.get_children():
            self._bbm_tree.selection_add(iid)

    def _bbm_selected_paths(self) -> list[str]:
        if not self._bbm_tree:
            return []
        paths: list[str] = []
        for iid in self._bbm_tree.selection():
            vals = self._bbm_tree.item(iid, "values")
            # Column 0 is name; column 1 is path.
            if vals and len(vals) >= 2:
                paths.append(str(vals[1]))
        return paths

    def _bbm_hash_selected(self) -> None:
        paths = self._bbm_selected_paths()
        if not paths:
            messagebox.showinfo("Hash", "No rows selected.", parent=self._bbm_window or self.root)
            return
        if self._bbm_hash_thread and self._bbm_hash_thread.is_alive():
            messagebox.showinfo("Hash", "Hashing already running.", parent=self._bbm_window or self.root)
            return

        self._bbm_set_status(f"Hashing {len(paths)} file(s)...")

        def _worker() -> None:
            updated = 0
            for p in paths:
                ap = os.path.abspath(p)
                try:
                    h = hashlib.sha256()
                    with open(ap, "rb") as f:
                        for chunk in iter(lambda: f.read(1024 * 1024), b""):
                            h.update(chunk)
                    digest = h.hexdigest()
                    short = digest[:12]
                    row = (self._bbm_rows_by_path or {}).get(ap)
                    if row is not None:
                        row["sha256"] = digest
                        row["sha256_short"] = short
                    updated += 1
                    try:
                        self.root.after(0, self._bbm_refresh_row_for_path, ap)
                    except Exception:
                        pass
                except Exception:
                    continue
            try:
                self.root.after(0, lambda: self._bbm_set_status(f"Hashed {updated} file(s)"))
            except Exception:
                pass

        self._bbm_hash_thread = threading.Thread(target=_worker, daemon=True)
        self._bbm_hash_thread.start()

    def _bbm_version_selected(self) -> None:
        paths = self._bbm_selected_paths()
        if not paths:
            messagebox.showinfo("Version", "No rows selected.", parent=self._bbm_window or self.root)
            return
        if self._bbm_version_thread and self._bbm_version_thread.is_alive():
            messagebox.showinfo("Version", "Version check already running.", parent=self._bbm_window or self.root)
            return

        self._bbm_set_status(f"Reading version for {len(paths)} file(s)...")

        def _worker() -> None:
            updated = 0
            for p in paths:
                ap = os.path.abspath(p)
                try:
                    proc = subprocess.Popen([ap, "version"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                    out = (proc.stdout.read() if proc.stdout else "")
                    proc.wait(timeout=6)
                    first = out.strip().splitlines()[0] if out.strip() else ""
                    ver = first[:80]
                    row = (self._bbm_rows_by_path or {}).get(ap)
                    if row is not None:
                        row["version"] = ver
                    updated += 1
                    try:
                        self.root.after(0, self._bbm_refresh_row_for_path, ap)
                    except Exception:
                        pass
                except Exception:
                    continue
            try:
                self.root.after(0, lambda: self._bbm_set_status(f"Updated version for {updated} file(s)"))
            except Exception:
                pass

        self._bbm_version_thread = threading.Thread(target=_worker, daemon=True)
        self._bbm_version_thread.start()

    def _bbm_refresh_row_for_path(self, path: str) -> None:
        if not self._bbm_tree:
            return
        ap = os.path.abspath(path)
        row = (self._bbm_rows_by_path or {}).get(ap)
        if not row:
            return
        for iid in self._bbm_tree.get_children():
            vals = self._bbm_tree.item(iid, "values")
            if not vals or len(vals) < 2:
                continue
            if os.path.abspath(str(vals[1])) != ap:
                continue

            name = os.path.basename(ap)
            size = row.get("size")
            try:
                st = os.lstat(ap)
                mtime = float(st.st_mtime)
                mtime_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(mtime))
                age = _age_days_from_mtime(mtime)
                age_str = "" if age is None else str(age)
                size_str = _format_bytes(int(st.st_size))
            except Exception:
                mtime_str = ""
                age_str = ""
                size_str = _format_bytes(int(size)) if isinstance(size, int) else "?"

            sha_short = row.get("sha256_short") or ""
            ver = row.get("version") or ""
            prot = "yes" if row.get("protected") else ""
            self._bbm_tree.item(iid, values=(name, ap, size_str, mtime_str, age_str, sha_short, ver, prot))
            break

        self._bbm_update_details_from_selection()

    def _bbm_current_bin_paths_protected(self) -> set[str]:
        protected: set[str] = set()
        try:
            cur_raw = (self.bin_var.get() or "").strip()
            cur_res = self._resolve_binary(cur_raw, [DEFAULT_BINARY, _repo_retrochaind_build()])
            if cur_res:
                protected.add(os.path.abspath(cur_res))
        except Exception:
            pass
        try:
            up_raw = (self.upgrade_bin_var.get() or "").strip()
            if up_raw:
                protected.add(os.path.abspath(up_raw))
        except Exception:
            pass
        return protected

    def _bbm_move_selected(self) -> None:
        paths = self._bbm_selected_paths()
        if not paths:
            messagebox.showinfo("Move", "No rows selected.", parent=self._bbm_window or self.root)
            return
        self._bbm_move_paths(paths)

    def _bbm_move_paths(self, paths: list[str]) -> None:
        if not self._bbm_backup_dir_var:
            return
        dest_dir = (self._bbm_backup_dir_var.get() or "").strip()
        if not dest_dir:
            messagebox.showerror("Move", "Backup folder is empty.", parent=self._bbm_window or self.root)
            return
        os.makedirs(dest_dir, exist_ok=True)

        protected = self._bbm_current_bin_paths_protected()
        moved = 0
        skipped = 0
        for p in paths:
            ap = os.path.abspath(p)
            if ap in protected:
                skipped += 1
                continue
            if not os.path.exists(ap):
                skipped += 1
                continue
            base = os.path.basename(ap)
            target = os.path.join(dest_dir, base)
            if os.path.exists(target):
                ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
                target = os.path.join(dest_dir, f"{base}.{ts}")
            try:
                shutil.move(ap, target)
                moved += 1
            except Exception:
                skipped += 1
                continue

        self._bbm_set_status(f"Moved {moved}, skipped {skipped}")
        self._bbm_scan()

    def _bbm_delete_selected(self) -> None:
        paths = self._bbm_selected_paths()
        if not paths:
            messagebox.showinfo("Delete", "No rows selected.", parent=self._bbm_window or self.root)
            return
        if not messagebox.askyesno(
            "Confirm delete",
            f"Delete {len(paths)} selected file(s)?\n\nThis is permanent.",
            parent=self._bbm_window or self.root,
        ):
            return
        self._bbm_delete_paths(paths)

    def _bbm_delete_older_than(self) -> None:
        if not self._bbm_tree:
            return
        raw = (self._bbm_delete_older_days_var.get().strip() if self._bbm_delete_older_days_var else "")
        try:
            days = int(raw)
        except Exception:
            messagebox.showerror("Delete", "Invalid days value.", parent=self._bbm_window or self.root)
            return
        if days < 0:
            messagebox.showerror("Delete", "Days must be >= 0.", parent=self._bbm_window or self.root)
            return
        cutoff = time.time() - (days * 86400)

        candidates: list[str] = []
        for iid in self._bbm_tree.get_children():
            vals = self._bbm_tree.item(iid, "values")
            if not vals or len(vals) < 1:
                continue
            path = str(vals[0])
            try:
                mtime = os.lstat(path).st_mtime
            except Exception:
                continue
            if mtime <= cutoff:
                candidates.append(path)

        if not candidates:
            messagebox.showinfo("Delete", "No binaries match that age threshold.", parent=self._bbm_window or self.root)
            return
        if not messagebox.askyesno(
            "Confirm delete",
            f"Delete {len(candidates)} file(s) older than {days} days?\n\nThis is permanent.",
            parent=self._bbm_window or self.root,
        ):
            return
        self._bbm_delete_paths(candidates)

    def _bbm_delete_paths(self, paths: list[str]) -> None:
        protected = self._bbm_current_bin_paths_protected()
        deleted = 0
        skipped = 0
        for p in paths:
            ap = os.path.abspath(p)
            if ap in protected:
                skipped += 1
                continue
            if not os.path.exists(ap):
                skipped += 1
                continue
            try:
                os.remove(ap)
                deleted += 1
            except Exception:
                skipped += 1
                continue

        self._bbm_set_status(f"Deleted {deleted}, skipped {skipped}")
        self._bbm_scan()

    def _maybe_swap_to_upgraded_binary(self, reason: str) -> bool:
        """Swap self.bin_var to the upgraded binary if configured.

        Returns True if the swap was applied.
        """
        if self._upgrade_swap_in_progress:
            return False

        upgrade_raw = (self.upgrade_bin_var.get() or "").strip()
        if not upgrade_raw:
            return False

        upgrade_bin = self._resolve_binary(upgrade_raw, [upgrade_raw])
        if not upgrade_bin:
            self.append_node_log(f"\n==> Upgrade swap skipped: binary not found: {upgrade_raw}\n")
            return False

        # In-place mode: overwrite repo build/retrochaind so *everything* that expects that path
        # (including the GUI default resolver) will run the upgraded binary.
        if bool(self.swap_in_place_var.get()):
            target = _repo_retrochaind_build()
            try:
                os.makedirs(os.path.dirname(target), exist_ok=True)
                # Optional safety backup of the target before overwrite.
                if bool(self.backup_before_swap_var.get()) and os.path.isfile(target):
                    backup_dir = os.path.join(os.path.expanduser(self.home_var.get().strip() or DEFAULT_HOME), "bin_backups")
                    os.makedirs(backup_dir, exist_ok=True)
                    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
                    backup_path = os.path.join(backup_dir, f"{os.path.basename(target)}.{ts}")
                    shutil.copy2(target, backup_path)
                    self.append_node_log(f"\n==> Backed up {target} to: {backup_path}\n")

                shutil.copy2(upgrade_bin, target)
                try:
                    os.chmod(target, 0o755)
                except Exception:
                    pass

                self.bin_var.set(target)
                self.append_node_log(
                    f"\n==> Upgrade swap (in-place): overwrote {target} with {upgrade_bin} ({reason})\n"
                )
                return True
            except Exception as exc:  # noqa: BLE001
                self.append_node_log(f"\n==> ERROR: in-place swap failed: {exc}\n")
                return False

        # Optional safety: back up the currently selected binary (to a user-writable location)
        # before switching to the upgraded binary. This does NOT modify any binaries in-place.
        if bool(self.backup_before_swap_var.get()):
            try:
                current_raw = (self.bin_var.get() or "").strip() or DEFAULT_BINARY
                current_bin = self._resolve_binary(current_raw, [DEFAULT_BINARY, _repo_retrochaind_build()])
                if current_bin and os.path.isfile(current_bin):
                    backup_dir = os.path.join(os.path.expanduser(self.home_var.get().strip() or DEFAULT_HOME), "bin_backups")
                    os.makedirs(backup_dir, exist_ok=True)
                    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
                    backup_path = os.path.join(backup_dir, f"{os.path.basename(current_bin)}.{ts}")
                    shutil.copy2(current_bin, backup_path)
                    self.append_node_log(f"\n==> Backed up current binary to: {backup_path}\n")
            except Exception as exc:  # noqa: BLE001
                self.append_node_log(f"\n==> WARNING: failed to back up current binary before swap: {exc}\n")

        self._upgrade_swap_in_progress = True
        self._upgrade_swap_last_at = time.time()
        self.bin_var.set(upgrade_bin)
        self.append_node_log(f"\n==> Upgrade swap: using upgraded binary ({reason}): {upgrade_bin}\n")

        # Clear in-progress flag shortly after; restart is async.
        def _clear() -> None:
            self._upgrade_swap_in_progress = False

        self.root.after(3000, _clear)
        return True

    def _detect_upgrade_halt_line(self, line: str) -> tuple[str | None, int | None]:
        """Return (plan_name, height) if the line looks like an upgrade halt message."""
        s = (line or "").strip()
        if not s:
            return (None, None)

        # Common Cosmos SDK patterns:
        # - UPGRADE "<name>" NEEDED at height: <height>
        # - UPGRADE NEEDED at height: <height>
        m = re.search(r'UPGRADE\s+"?([A-Za-z0-9_.\-]+)"?\s+NEEDED\s+at\s+height:?\s*(\d+)', s)
        if m:
            return (m.group(1), int(m.group(2)))
        m = re.search(r'UPGRADE\s+NEEDED\s+at\s+height:?\s*(\d+)', s)
        if m:
            return (None, int(m.group(1)))

        return (None, None)

    def _maybe_handle_upgrade_halt(self, line: str) -> None:
        if not bool(self.auto_swap_on_halt_var.get()):
            return
        if not (self.upgrade_bin_var.get() or "").strip():
            return

        plan, height = self._detect_upgrade_halt_line(line)
        if height is None:
            return

        plan_txt = plan or "(unknown plan)"
        self.append_node_log(f"\n==> Detected upgrade halt: {plan_txt} at height {height}\n")

        # Swap binary immediately, then restart shortly after.
        swapped = self._maybe_swap_to_upgraded_binary(reason=f"upgrade halt detected ({plan_txt} @ {height})")
        if swapped:
            self.root.after(1200, self.restart_node)

    def append_testnet_log(self, line: str) -> None:
        self.testnet_log.configure(state="normal")
        self.testnet_log.insert(tk.END, line)
        self.testnet_log.see(tk.END)
        self.testnet_log.configure(state="disabled")

    def append_hermes_log(self, line: str) -> None:
        self.hermes_log.configure(state="normal")
        self.hermes_log.insert(tk.END, line)
        self.hermes_log.see(tk.END)
        self.hermes_log.configure(state="disabled")

    def clear_hermes_log(self) -> None:
        try:
            self.hermes_log.configure(state="normal")
            self.hermes_log.delete("1.0", tk.END)
            self.hermes_log.configure(state="disabled")
        except Exception:
            pass

    def append_module_log(self, line: str) -> None:
        self.module_log.configure(state="normal")
        self.module_log.insert(tk.END, line)
        self.module_log.see(tk.END)
        self.module_log.configure(state="disabled")

    def append_nginx_log(self, line: str) -> None:
        self.nginx_log.configure(state="normal")
        self.nginx_log.insert(tk.END, line)
        self.nginx_log.see(tk.END)
        self.nginx_log.configure(state="disabled")

    def append_indexer_log(self, line: str) -> None:
        self.indexer_log.configure(state="normal")
        self.indexer_log.insert(tk.END, line)
        self.indexer_log.see(tk.END)
        self.indexer_log.configure(state="disabled")

    def append_setup_log(self, line: str) -> None:
        self.setup_log.configure(state="normal")
        self.setup_log.insert(tk.END, line)
        self.setup_log.see(tk.END)
        self.setup_log.configure(state="disabled")

    def _run_command_async(
        self,
        cmd_list: list[str],
        input_text: str | None = None,
        success_cb=None,
        target_queue: queue.Queue[str] | None = None,
        start_log_cb=None,
    ) -> None:
        """Run a command in a background thread and stream output into the chosen log queue."""

        log_queue = target_queue or self.node_log_queue
        start_logger = start_log_cb or self.append_node_log

        def _runner() -> None:
            try:
                start_logger(f"\n==> {' '.join(shlex.quote(x) for x in cmd_list)}\n")
                proc = subprocess.Popen(
                    cmd_list,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    stdin=subprocess.PIPE if input_text else None,
                )
                if input_text and proc.stdin:
                    proc.stdin.write(input_text)
                    proc.stdin.flush()
                    proc.stdin.close()

                for line in proc.stdout or []:
                    log_queue.put(line)
                proc.wait()
                log_queue.put(f"==> exit {proc.returncode}\n")
                if success_cb and proc.returncode == 0:
                    success_cb()
            except FileNotFoundError:
                log_queue.put(f"ERROR: command not found: {cmd_list[0]}\n")
            except Exception as exc:  # noqa: BLE001
                log_queue.put(f"ERROR running command: {exc}\n")

        threading.Thread(target=_runner, daemon=True).start()

    def _poll_log_queues(self) -> None:
        try:
            while True:
                line = self.node_log_queue.get_nowait()
                self.append_node_log(line)
                self._maybe_handle_upgrade_halt(line)
        except queue.Empty:
            pass
        try:
            while True:
                line = self.testnet_log_queue.get_nowait()
                self.append_testnet_log(line)
        except queue.Empty:
            pass
        try:
            while True:
                line = self.hermes_log_queue.get_nowait()
                self.append_hermes_log(line)
        except queue.Empty:
            pass
        try:
            while True:
                line = self.module_log_queue.get_nowait()
                self.append_module_log(line)
        except queue.Empty:
            pass
        try:
            while True:
                line = self.indexer_log_queue.get_nowait()
                self.append_indexer_log(line)
        except queue.Empty:
            pass
        try:
            while True:
                line = self.nginx_log_queue.get_nowait()
                self.append_nginx_log(line)
        except queue.Empty:
            pass
        try:
            while True:
                line = self.setup_log_queue.get_nowait()
                self.append_setup_log(line)
        except queue.Empty:
            pass

        try:
            while True:
                line = self._analytics_log_queue.get_nowait()
                self.append_analytics_log(line)
        except queue.Empty:
            pass

        self._scheduled_restart_tick()
        self._analytics_tick()
        self._indexer_status_tick()
        self._nginx_status_tick()
        self.root.after(150, self._poll_log_queues)

    # ----------------------- Analytics -----------------------

    def append_analytics_log(self, text: str) -> None:
        try:
            self.analytics_log.configure(state="normal")
            self.analytics_log.insert(tk.END, text)
            self.analytics_log.see(tk.END)
            self.analytics_log.configure(state="disabled")
        except Exception:
            pass

    def _analytics_emit(self, level: str, msg: str) -> None:
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self._analytics_log_queue.put(f"[{ts}] {level.upper():<5} {msg}\n")

    def browse_retrochaind_binary(self) -> None:
        path = filedialog.askopenfilename(title="Select retrochaind binary")
        if path:
            self.bin_var.set(path)

    def start_analytics(self) -> None:
        # Start polling thread; do not depend on node start.
        try:
            self.analytics_auto_refresh_var.set(True)
        except Exception:
            pass
        self._analytics_force_refresh = True
        self._start_analytics_watcher()
        self.analytics_status_var.set("Starting analytics...")

    def stop_analytics(self) -> None:
        # Stop polling thread; safe to restart later.
        try:
            self.analytics_auto_refresh_var.set(False)
        except Exception:
            pass
        self._analytics_refresh_enabled = False
        self._analytics_force_refresh = False
        self._analytics_stop_event.set()
        t = self._analytics_thread
        if t and t.is_alive():
            try:
                t.join(timeout=0.8)
            except Exception:
                pass
        self._analytics_thread = None
        self.analytics_status_var.set("Analytics stopped")

    def analytics_refresh_now(self) -> None:
        # Allow one-shot refresh without enabling auto refresh.
        self._analytics_force_refresh = True
        if not (self._analytics_thread and self._analytics_thread.is_alive()):
            self._start_analytics_watcher()
        self.analytics_status_var.set("Refreshing...")

    def _start_analytics_watcher(self) -> None:
        if self._analytics_thread and self._analytics_thread.is_alive():
            return

        self._analytics_stop_event.clear()

        def _worker() -> None:
            prev_height: int | None = None
            prev_bt: datetime.datetime | None = None
            prev_ok: bool | None = None
            prev_catching: bool | None = None
            prev_health: bool | None = None
            prev_peers: int | None = None
            while not self._analytics_stop_event.is_set():
                if not self._analytics_refresh_enabled and not self._analytics_force_refresh:
                    time.sleep(0.5)
                    continue

                rpc = (self._analytics_rpc_url or "").strip() or DEFAULT_SQL_INDEXER_RPC
                snap = self._collect_analytics_snapshot(rpc)

                # Derived metrics across samples
                try:
                    h = snap.get("height")
                    bt = _parse_rfc3339(snap.get("latest_block_time"))
                    if isinstance(h, int) and bt and isinstance(prev_height, int) and prev_bt and h > prev_height:
                        dt_s = (bt - prev_bt).total_seconds()
                        dh = h - prev_height
                        if dt_s > 0 and dh > 0:
                            snap["avg_block_time_s"] = dt_s / float(dh)
                            snap["blocks_per_min"] = (60.0 * float(dh)) / dt_s
                    if isinstance(h, int):
                        prev_height = h
                    if bt:
                        prev_bt = bt
                except Exception:
                    pass

                # Emit actionable events (best-effort, avoid spamming)
                try:
                    ok = bool(snap.get("ok"))
                    if prev_ok is not None and ok != prev_ok:
                        self._analytics_emit("INFO" if ok else "WARN", "RPC became reachable" if ok else "RPC became unreachable")
                    prev_ok = ok

                    catching = snap.get("catching_up")
                    if isinstance(catching, bool) and (prev_catching is None or catching != prev_catching):
                        self._analytics_emit("WARN" if catching else "INFO", "Node catching_up=true" if catching else "Node caught up")
                    if isinstance(catching, bool):
                        prev_catching = catching

                    health_ok = snap.get("rpc_health_ok")
                    if isinstance(health_ok, bool) and (prev_health is None or health_ok != prev_health):
                        self._analytics_emit("INFO" if health_ok else "WARN", "/health OK" if health_ok else "/health failed")
                        prev_health = health_ok

                    lag_s = snap.get("block_lag_s")
                    if isinstance(lag_s, (int, float)) and lag_s >= 20.0:
                        self._analytics_emit("WARN", f"Block time lag {lag_s:.1f}s")

                    peers = snap.get("peers")
                    if isinstance(peers, int):
                        if prev_peers is not None and peers == 0 and prev_peers > 0:
                            self._analytics_emit("WARN", "Peers dropped to 0")
                        if peers < 3:
                            self._analytics_emit("WARN", f"Low peers: {peers}")
                        prev_peers = peers

                    disk = snap.get("disk") or {}
                    if isinstance(disk, dict) and disk.get("ok"):
                        free = float(disk.get("free_bytes") or 0)
                        total = float(disk.get("total_bytes") or 0)
                        if total > 0:
                            pct = 100.0 * free / total
                            if pct < 10.0:
                                self._analytics_emit("WARN", f"Low disk free: {pct:.1f}%")
                except Exception:
                    pass

                self._analytics_latest = snap
                self._analytics_latest_at = time.time()
                self._analytics_force_refresh = False
                time.sleep(2.0)

        self._analytics_thread = threading.Thread(target=_worker, daemon=True)
        self._analytics_thread.start()

    def _analytics_tick(self) -> None:
        # Pull UI inputs on the main thread.
        try:
            self._analytics_rpc_url = (self.analytics_rpc_var.get().strip() or DEFAULT_SQL_INDEXER_RPC)
        except Exception:
            self._analytics_rpc_url = DEFAULT_SQL_INDEXER_RPC

        try:
            self._analytics_refresh_enabled = bool(self.analytics_auto_refresh_var.get())
        except Exception:
            self._analytics_refresh_enabled = True

        snap = self._analytics_latest or {}

        # Chain
        self.analytics_chain_id_var.set(str(snap.get("chain_id") or "-"))
        self.analytics_height_var.set(str(snap.get("height") or "-"))
        self.analytics_catching_up_var.set(str(snap.get("catching_up") if "catching_up" in snap else "-"))
        self.analytics_latest_time_var.set(str(snap.get("latest_block_time") or "-"))
        self.analytics_node_version_var.set(str(snap.get("node_version") or "-"))
        self.analytics_moniker_var.set(str(snap.get("moniker") or "-"))
        latency_ms = snap.get("rpc_latency_ms")
        self.analytics_rpc_latency_var.set(f"{latency_ms:.0f} ms" if isinstance(latency_ms, (int, float)) else "-")

        self.analytics_latest_hash_var.set(str(snap.get("latest_block_hash") or "-"))
        self.analytics_latest_app_hash_var.set(str(snap.get("latest_app_hash") or "-"))

        lag_s = snap.get("block_lag_s")
        self.analytics_block_lag_var.set(f"{lag_s:.1f}s" if isinstance(lag_s, (int, float)) else "-")
        abt = snap.get("avg_block_time_s")
        bpm = snap.get("blocks_per_min")
        if isinstance(abt, (int, float)) and isinstance(bpm, (int, float)):
            self.analytics_avg_block_time_var.set(f"{abt:.2f}s ({bpm:.1f} blk/min)")
        elif isinstance(abt, (int, float)):
            self.analytics_avg_block_time_var.set(f"{abt:.2f}s")
        else:
            self.analytics_avg_block_time_var.set("-")

        self.analytics_node_id_var.set(str(snap.get("node_id") or "-"))
        self.analytics_listen_addr_var.set(str(snap.get("listen_addr") or "-"))
        self.analytics_validator_addr_var.set(str(snap.get("validator_address") or "-"))
        vp = snap.get("validator_voting_power")
        self.analytics_validator_power_var.set(str(vp) if vp is not None else "-")
        vs = snap.get("validator_set_total")
        self.analytics_validator_set_total_var.set(str(vs) if vs is not None else "-")

        abci_app = snap.get("abci_app")
        abci_ver = snap.get("abci_version")
        if abci_app and abci_ver:
            self.analytics_abci_app_var.set(f"{abci_app} / {abci_ver}")
        elif abci_app:
            self.analytics_abci_app_var.set(str(abci_app))
        elif abci_ver:
            self.analytics_abci_app_var.set(str(abci_ver))
        else:
            self.analytics_abci_app_var.set("-")

        self.analytics_tx_index_var.set(str(snap.get("tx_index") or "-"))
        vpk = snap.get("validator_pubkey")
        if isinstance(vpk, str) and len(vpk) > 42:
            self.analytics_validator_pubkey_var.set(vpk[:18] + "..." + vpk[-18:])
        else:
            self.analytics_validator_pubkey_var.set(str(vpk or "-"))

        h = snap.get("rpc_health_ok")
        self.analytics_rpc_health_var.set("OK" if h is True else ("FAIL" if h is False else "-"))

        # Net + mempool
        self.analytics_peers_var.set(str(snap.get("peers") if "peers" in snap else "-"))
        self.analytics_listening_var.set(str(snap.get("listening") if "listening" in snap else "-"))
        self.analytics_mempool_txs_var.set(str(snap.get("mempool_txs") if "mempool_txs" in snap else "-"))
        mem_bytes = snap.get("mempool_bytes")
        self.analytics_mempool_bytes_var.set(_format_bytes(int(mem_bytes)) if isinstance(mem_bytes, (int, float)) else "-")

        # Peers sample
        peers_txt = str(snap.get("peers_sample") or "")
        try:
            self.analytics_peers_text.configure(state="normal")
            self.analytics_peers_text.delete("1.0", tk.END)
            self.analytics_peers_text.insert(tk.END, peers_txt or "(no peers listed)")
            self.analytics_peers_text.configure(state="disabled")
        except Exception:
            pass

        # Host
        lavg = snap.get("loadavg")
        if isinstance(lavg, (tuple, list)) and len(lavg) == 3:
            self.analytics_loadavg_var.set(f"{lavg[0]:.2f} / {lavg[1]:.2f} / {lavg[2]:.2f}")
        else:
            self.analytics_loadavg_var.set("-")

        memh = snap.get("host_mem") or {}
        if memh.get("ok"):
            self.analytics_memhost_var.set(f"{_format_bytes(int(memh.get('avail_bytes', 0)))} / {_format_bytes(int(memh.get('total_bytes', 0)))}")
        else:
            self.analytics_memhost_var.set("-")

        # Process + disk
        proc = snap.get("proc") or {}
        self.analytics_proc_var.set(str(proc.get("status") or "-"))
        cpu = proc.get("cpu")
        rss_mb = proc.get("rss_mb")
        if isinstance(cpu, (int, float)) and isinstance(rss_mb, (int, float)):
            self.analytics_cpu_var.set(f"{cpu:.1f}% / {rss_mb:.0f} MB")
        elif isinstance(cpu, (int, float)):
            self.analytics_cpu_var.set(f"{cpu:.1f}%")
        else:
            self.analytics_cpu_var.set("-")
        self.analytics_uptime_var.set(str(proc.get("uptime") or "-"))

        disk = snap.get("disk") or {}
        if disk.get("ok"):
            self.analytics_disk_var.set(
                f"free {_format_bytes(int(disk.get('free_bytes', 0)))} / total {_format_bytes(int(disk.get('total_bytes', 0)))}"
            )
        else:
            self.analytics_disk_var.set("-")

        data_dir = snap.get("data_dir") or {}
        if data_dir.get("ok"):
            self.analytics_data_dir_var.set(_format_bytes(int(data_dir.get("bytes", 0))))
        else:
            self.analytics_data_dir_var.set(str(data_dir.get("error") or "-"))

        # Footer status
        at = self._analytics_latest_at
        if at:
            age = time.time() - at
            ok = bool(snap.get("ok"))
            self.analytics_status_var.set(("OK" if ok else "RPC error") + f" (updated {age:.1f}s ago)")
        else:
            self.analytics_status_var.set("Waiting for first sample")

        # Alerts summary (quick scan)
        alerts: list[str] = []
        if snap.get("ok") is not True:
            alerts.append("RPC unreachable")
        if snap.get("catching_up") is True:
            alerts.append("catching up")
        lag_s = snap.get("block_lag_s")
        if isinstance(lag_s, (int, float)) and lag_s >= 20.0:
            alerts.append(f"lag {lag_s:.0f}s")
        peers = snap.get("peers")
        if isinstance(peers, int) and peers < 3:
            alerts.append(f"low peers {peers}")
        disk = snap.get("disk") or {}
        if isinstance(disk, dict) and disk.get("ok"):
            try:
                free = float(disk.get("free_bytes") or 0)
                total = float(disk.get("total_bytes") or 0)
                if total > 0:
                    pct = 100.0 * free / total
                    if pct < 10.0:
                        alerts.append(f"disk {pct:.1f}%")
            except Exception:
                pass
        self.analytics_alerts_var.set(", ".join(alerts) if alerts else "No active alerts")

    def _rpc_get_json(self, url: str, timeout_s: float = 2.5) -> tuple[dict | None, float | None, str | None]:
        try:
            start = time.time()
            req = urllib.request.Request(url, headers={"User-Agent": "retrochain-node-manager"})
            with urllib.request.urlopen(req, timeout=timeout_s) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            ms = (time.time() - start) * 1000.0
            return data, ms, None
        except Exception as exc:  # noqa: BLE001
            return None, None, str(exc)

    def _collect_analytics_snapshot(self, rpc_url: str) -> dict:
        rpc = (rpc_url or "").strip().rstrip("/")
        out: dict = {"ok": False}
        if not rpc:
            out["error"] = "missing rpc url"
            return out

        status, ms, err = self._rpc_get_json(f"{rpc}/status")
        if not status:
            out["error"] = err or "failed to fetch /status"
            return out

        out["ok"] = True
        out["rpc_latency_ms"] = ms

        res = status.get("result", {}) if isinstance(status, dict) else {}
        sync = res.get("sync_info", {}) if isinstance(res, dict) else {}
        node = res.get("node_info", {}) if isinstance(res, dict) else {}
        vinfo = res.get("validator_info", {}) if isinstance(res, dict) else {}
        other = node.get("other", {}) if isinstance(node, dict) else {}

        out["height"] = int(sync.get("latest_block_height")) if sync.get("latest_block_height") else None
        out["catching_up"] = sync.get("catching_up")
        out["latest_block_time"] = sync.get("latest_block_time")
        out["latest_block_hash"] = sync.get("latest_block_hash")
        out["latest_app_hash"] = sync.get("latest_app_hash")
        out["earliest_block_height"] = int(sync.get("earliest_block_height")) if sync.get("earliest_block_height") else None
        out["earliest_block_time"] = sync.get("earliest_block_time")
        out["earliest_block_hash"] = sync.get("earliest_block_hash")
        out["chain_id"] = node.get("network")
        out["node_version"] = node.get("version")
        out["moniker"] = (node.get("moniker") or node.get("default_node_info", {}).get("moniker"))
        out["node_id"] = node.get("id") or node.get("default_node_info", {}).get("id")
        out["listen_addr"] = node.get("listen_addr") or node.get("default_node_info", {}).get("listen_addr")

        if isinstance(other, dict):
            out["tx_index"] = other.get("tx_index")

        if isinstance(vinfo, dict):
            out["validator_address"] = vinfo.get("address")
            pub = vinfo.get("pub_key")
            if isinstance(pub, dict):
                out["validator_pubkey"] = pub.get("value") or pub.get("key") or str(pub)
            elif pub is not None:
                out["validator_pubkey"] = str(pub)
            try:
                out["validator_voting_power"] = int(vinfo.get("voting_power")) if vinfo.get("voting_power") is not None else None
            except Exception:
                out["validator_voting_power"] = vinfo.get("voting_power")

        bt = _parse_rfc3339(out.get("latest_block_time"))
        if bt:
            try:
                now = datetime.datetime.now(datetime.timezone.utc)
                out["block_lag_s"] = max(0.0, (now - bt.astimezone(datetime.timezone.utc)).total_seconds())
            except Exception:
                pass

        net, _, _ = self._rpc_get_json(f"{rpc}/net_info")
        if isinstance(net, dict):
            nres = net.get("result", {})
            out["peers"] = int(nres.get("n_peers")) if nres.get("n_peers") is not None else None
            out["listening"] = nres.get("listening")

            # Peer sample
            peers = nres.get("peers")
            lines: list[str] = []
            if isinstance(peers, list):
                for p in peers[:30]:
                    if not isinstance(p, dict):
                        continue
                    ni = p.get("node_info") or {}
                    mon = None
                    if isinstance(ni, dict):
                        mon = ni.get("moniker") or ni.get("default_node_info", {}).get("moniker")
                    pid = p.get("node_id") or (ni.get("id") if isinstance(ni, dict) else None)
                    rip = p.get("remote_ip")
                    outbound = p.get("is_outbound")
                    ver = None
                    if isinstance(ni, dict):
                        ver = ni.get("version")
                    parts = [
                        f"{mon or '-'}",
                        f"id={pid or '-'}",
                        f"ip={rip or '-'}",
                        f"outbound={outbound}" if outbound is not None else "outbound=?",
                    ]
                    if ver:
                        parts.append(f"ver={ver}")
                    lines.append(" ".join(parts))
            out["peers_sample"] = "\n".join(lines)

        mem, _, _ = self._rpc_get_json(f"{rpc}/unconfirmed_txs?limit=200")
        if isinstance(mem, dict):
            mres = mem.get("result", {})
            out["mempool_txs"] = int(mres.get("n_txs")) if mres.get("n_txs") is not None else None
            out["mempool_bytes"] = int(mres.get("total_bytes")) if mres.get("total_bytes") is not None else None

        # /health is a quick liveness probe; treat any successful JSON fetch as OK.
        health, _, _ = self._rpc_get_json(f"{rpc}/health")
        out["rpc_health_ok"] = bool(health is not None)

        abci, _, _ = self._rpc_get_json(f"{rpc}/abci_info")
        if isinstance(abci, dict):
            ares = abci.get("result", {}).get("response", {})
            if isinstance(ares, dict):
                out["abci_app"] = ares.get("data")
                out["abci_version"] = ares.get("version")

        vals, _, _ = self._rpc_get_json(f"{rpc}/validators?per_page=1&page=1")
        if isinstance(vals, dict):
            vres = vals.get("result", {})
            if isinstance(vres, dict) and vres.get("total") is not None:
                try:
                    out["validator_set_total"] = int(vres.get("total"))
                except Exception:
                    out["validator_set_total"] = vres.get("total")

        out["loadavg"] = self._get_loadavg_snapshot()
        out["host_mem"] = self._get_host_mem_snapshot()

        out["proc"] = self._get_retrochaind_process_snapshot()
        out["disk"] = self._get_home_disk_snapshot()
        out["data_dir"] = self._get_data_dir_size_snapshot()
        return out

    def _get_loadavg_snapshot(self) -> tuple[float, float, float] | None:
        try:
            return os.getloadavg()
        except Exception:
            return None

    def _get_host_mem_snapshot(self) -> dict:
        # Linux best-effort via /proc/meminfo.
        try:
            if not os.path.exists("/proc/meminfo"):
                return {"ok": False, "error": "unsupported"}
            total_kb = None
            avail_kb = None
            with open("/proc/meminfo", "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        parts = line.split()
                        if len(parts) >= 2:
                            total_kb = int(parts[1])
                    elif line.startswith("MemAvailable:"):
                        parts = line.split()
                        if len(parts) >= 2:
                            avail_kb = int(parts[1])
                    if total_kb is not None and avail_kb is not None:
                        break
            if total_kb is None or avail_kb is None:
                return {"ok": False, "error": "missing fields"}
            return {"ok": True, "total_bytes": int(total_kb) * 1024, "avail_bytes": int(avail_kb) * 1024}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc)}

    def _get_retrochaind_process_snapshot(self) -> dict:
        # Best-effort process stats for the first retrochaind PID.
        try:
            pids = subprocess.check_output(["pgrep", "-x", "retrochaind"], text=True).strip().split()
            if not pids:
                return {"status": "not running"}
            pid = pids[0]

            # etimes = elapsed seconds since process started
            out = subprocess.check_output(["ps", "-p", pid, "-o", "pid=,pcpu=,rss=,etimes="], text=True).strip()
            parts = out.split()
            cpu = float(parts[1]) if len(parts) > 1 else None
            rss_kb = float(parts[2]) if len(parts) > 2 else None
            etimes = int(parts[3]) if len(parts) > 3 else None

            uptime = "-"
            if etimes is not None:
                days = etimes // 86400
                hrs = (etimes % 86400) // 3600
                mins = (etimes % 3600) // 60
                secs = etimes % 60
                uptime = (f"{days}d " if days else "") + f"{hrs:02d}:{mins:02d}:{secs:02d}"

            return {
                "status": f"running (pid {pid})",
                "cpu": cpu,
                "rss_mb": (rss_kb / 1024.0) if rss_kb is not None else None,
                "uptime": uptime,
            }
        except subprocess.CalledProcessError:
            return {"status": "not running"}
        except Exception as exc:  # noqa: BLE001
            return {"status": f"unknown ({exc})"}

    def _get_home_disk_snapshot(self) -> dict:
        try:
            home = os.path.expanduser(self.home_var.get().strip() or DEFAULT_HOME)
        except Exception:
            home = os.path.expanduser(DEFAULT_HOME)

        try:
            du = shutil.disk_usage(home)
            return {"ok": True, "total_bytes": du.total, "free_bytes": du.free}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc)}

    def _get_data_dir_size_snapshot(self) -> dict:
        try:
            home = os.path.expanduser(self.home_var.get().strip() or DEFAULT_HOME)
        except Exception:
            home = os.path.expanduser(DEFAULT_HOME)

        data_dir = os.path.join(home, "data")
        if not os.path.isdir(data_dir):
            return {"ok": False, "error": f"missing {data_dir}"}
        try:
            # du -sb is fast on ext4/xfs; best-effort.
            out = subprocess.check_output(["du", "-sb", data_dir], text=True).strip()
            size = int(out.split()[0]) if out else 0
            return {"ok": True, "bytes": size}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc)}

    # ----------------------- Scheduled restart (upgrade) -----------------------

    def arm_scheduled_restart(self) -> None:
        raw = self.sched_height_var.get().strip()
        if not raw:
            messagebox.showerror("Scheduled restart", "Provide a target height")
            return
        try:
            target = int(raw)
        except ValueError:
            messagebox.showerror("Scheduled restart", "Target height must be an integer")
            return
        if target <= 0:
            messagebox.showerror("Scheduled restart", "Target height must be > 0")
            return

        self._sched_target_height = target
        self._sched_armed = True
        self.append_node_log(f"\n==> Scheduled restart armed for height {target}\n")

    def disarm_scheduled_restart(self) -> None:
        if self._sched_armed or self._sched_target_height is not None:
            self.append_node_log("\n==> Scheduled restart disarmed\n")
        self._sched_armed = False
        self._sched_target_height = None
        self.sched_status_var.set("Not armed")

    def _fetch_latest_height(self, rpc_url: str) -> int | None:
        # Backwards-compatible wrapper (height only)
        info = self._fetch_latest_height_and_chain_id(rpc_url)
        return info.height if info else None

    class _RpcStatusInfo(NamedTuple):
        height: int
        chain_id: str | None

    def _fetch_latest_height_and_chain_id(self, rpc_url: str) -> _RpcStatusInfo | None:
        rpc_url = (rpc_url or "").strip().rstrip("/")
        if not rpc_url:
            return None
        url = f"{rpc_url}/status"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "retrochain-node-manager"})
            with urllib.request.urlopen(req, timeout=2.5) as resp:
                payload = json.loads(resp.read().decode("utf-8"))

            h = payload.get("result", {}).get("sync_info", {}).get("latest_block_height")
            if h is None:
                return None
            chain_id = payload.get("result", {}).get("node_info", {}).get("network")
            chain_id = str(chain_id) if chain_id is not None else None
            return self._RpcStatusInfo(height=int(h), chain_id=chain_id)
        except Exception:
            return None

    def _maybe_refresh_expected_chain_id(self) -> None:
        """Refresh expected chain-id from the configured --home genesis.json (best-effort)."""
        try:
            home = os.path.expanduser((self.home_var.get() or "").strip() or DEFAULT_HOME)
        except Exception:
            home = os.path.expanduser(DEFAULT_HOME)

        # Avoid re-reading unless home changes.
        if self._sched_expected_chain_id_home == home:
            return
        self._sched_expected_chain_id_home = home

        genesis_path = os.path.join(home, "config", "genesis.json")
        try:
            with open(genesis_path, "r", encoding="utf-8") as f:
                genesis = json.load(f)
            cid = genesis.get("chain_id")
            self._sched_expected_chain_id = str(cid) if cid else None
        except Exception:
            self._sched_expected_chain_id = None

    def _start_scheduled_restart_watcher(self) -> None:
        if self._sched_thread and self._sched_thread.is_alive():
            return

        self._sched_stop_event.clear()

        def _worker() -> None:
            while not self._sched_stop_event.is_set():
                rpc = self._sched_rpc_url
                info = self._fetch_latest_height_and_chain_id(rpc)
                if info is not None:
                    self._sched_latest_height = info.height
                    self._sched_latest_chain_id = info.chain_id
                    now = time.time()
                    self._sched_latest_height_at = now
                    self._sched_latest_chain_id_at = now
                time.sleep(2.0)

        self._sched_thread = threading.Thread(target=_worker, daemon=True)
        self._sched_thread.start()

    def _scheduled_restart_tick(self) -> None:
        self._maybe_refresh_expected_chain_id()

        # Keep thread inputs updated from UI (Tk vars must be accessed on the main thread).
        try:
            self._sched_rpc_url = (self.sched_rpc_var.get().strip() or DEFAULT_SQL_INDEXER_RPC)
        except Exception:
            self._sched_rpc_url = DEFAULT_SQL_INDEXER_RPC

        latest = self._sched_latest_height
        target = self._sched_target_height
        latest_cid = self._sched_latest_chain_id
        expected_cid = self._sched_expected_chain_id

        if not self._sched_armed or target is None:
            if latest is None:
                self.sched_status_var.set("Not armed")
            else:
                cid_txt = f", chain-id {latest_cid}" if latest_cid else ""
                self.sched_status_var.set(f"Not armed (latest {latest}{cid_txt})")
            return

        if latest is None:
            self.sched_status_var.set(f"Armed for {target} (waiting for RPC)")
            return

        cid_txt = f", chain-id {latest_cid}" if latest_cid else ""
        if expected_cid and latest_cid and latest_cid != expected_cid:
            self.sched_status_var.set(f"Armed for {target} (latest {latest}{cid_txt}) [CHAIN-ID MISMATCH]")
            return

        self.sched_status_var.set(f"Armed for {target} (latest {latest}{cid_txt})")

        if latest >= target:
            # Disarm first to ensure we only restart once.
            self._sched_armed = False
            self._sched_target_height = None
            self.sched_status_var.set(f"Triggering restart (reached {latest})")
            self.append_node_log(f"\n==> Scheduled restart triggered at height {latest} (target {target})\n")
            if bool(self.sched_swap_binary_var.get()):
                self._maybe_swap_to_upgraded_binary(reason=f"scheduled restart (target {target})")
            self.restart_node()

    # ----------------------- SQL indexer -----------------------

    def clear_sql_indexer_log(self) -> None:
        self.indexer_log.configure(state="normal")
        self.indexer_log.delete("1.0", tk.END)
        self.indexer_log.configure(state="disabled")

    def browse_indexer_db(self) -> None:
        current = os.path.expanduser(self.indexer_db_var.get().strip() or DEFAULT_SQL_INDEXER_DB)
        initial_dir = os.path.dirname(current) or os.path.expanduser("~")
        initial_file = os.path.basename(current) or "indexer.sqlite"
        path = filedialog.asksaveasfilename(
            title="Select SQLite DB path",
            initialdir=initial_dir,
            initialfile=initial_file,
            defaultextension=".sqlite",
            filetypes=[("SQLite DB", "*.sqlite *.db"), ("All files", "*")],
        )
        if path:
            self.indexer_db_var.set(path)
            self.refresh_indexer_status()

    def _indexer_api_base_url(self) -> str | None:
        listen = self.indexer_api_listen_var.get().strip() or DEFAULT_INDEXER_API_LISTEN
        try:
            host, port_str = listen.rsplit(":", 1)
            int(port_str)
        except Exception:
            return None
        host = host.strip()
        if host in ("0.0.0.0", "::"):
            host = "127.0.0.1"
        return f"http://{host}:{port_str}"

    def open_indexer_api_status(self) -> None:
        base = self._indexer_api_base_url()
        if not base:
            messagebox.showerror("Indexer API", "Invalid listen address; expected host:port")
            return
        webbrowser.open(base + "/v1/status")

    def refresh_indexer_status(self) -> None:
        self._refresh_indexer_status_async(force=True)

    def _indexer_status_tick(self) -> None:
        try:
            if not getattr(self, "indexer_auto_refresh_var", None):
                return
            if not bool(self.indexer_auto_refresh_var.get()):
                return
        except Exception:
            return

        idx_running = bool(self.indexer_thread and self.indexer_thread.is_alive())
        api_running = bool(self.indexer_api_process and self.indexer_api_process.poll() is None)
        if not (idx_running or api_running):
            return

        now = time.time()
        if (now - float(self._indexer_status_last_refresh)) < 2.0:
            return
        self._refresh_indexer_status_async(force=False)

    def _refresh_indexer_status_async(self, force: bool) -> None:
        if self._indexer_status_refresh_in_flight:
            return
        self._indexer_status_refresh_in_flight = True

        rpc_url = (self.indexer_rpc_var.get().strip() or DEFAULT_SQL_INDEXER_RPC).rstrip("/")
        db_path = os.path.expanduser(self.indexer_db_var.get().strip() or DEFAULT_SQL_INDEXER_DB)
        listen = self.indexer_api_listen_var.get().strip() or DEFAULT_INDEXER_API_LISTEN
        cors = (getattr(self, "indexer_api_cors_origins_var", None).get().strip() if getattr(self, "indexer_api_cors_origins_var", None) else "")

        def _runner() -> None:
            idx_running = bool(self.indexer_thread and self.indexer_thread.is_alive())
            api_running = bool(self.indexer_api_process and self.indexer_api_process.poll() is None)

            chain_id: str | None = None
            latest: int | None = None
            rpc_err: str | None = None
            try:
                status_url = rpc_url + "/status"
                with urllib.request.urlopen(status_url, timeout=8) as resp:  # noqa: S310
                    data = json.loads(resp.read().decode("utf-8"))
                result = (data.get("result") or {}) if isinstance(data, dict) else {}
                node_info = (result.get("node_info") or {}) if isinstance(result, dict) else {}
                sync_info = (result.get("sync_info") or {}) if isinstance(result, dict) else {}
                chain_id = node_info.get("network") if isinstance(node_info, dict) else None
                latest_raw = (sync_info.get("latest_block_height") if isinstance(sync_info, dict) else None) or 0
                latest = int(latest_raw)
            except Exception as exc:  # noqa: BLE001
                rpc_err = str(exc)

            db_exists = os.path.exists(db_path)
            last_indexed: int | None = None
            db_chain_id: str | None = None
            blocks_c: int | None = None
            txs_c: int | None = None
            events_c: int | None = None
            db_err: str | None = None

            if db_exists:
                try:
                    with sqlite3.connect(db_path, timeout=5) as conn:
                        row = conn.execute("SELECT value FROM meta WHERE key='last_indexed_height'").fetchone()
                        if row and row[0] is not None:
                            last_indexed = int(row[0])
                        row2 = conn.execute("SELECT value FROM meta WHERE key='chain_id'").fetchone()
                        if row2 and row2[0] is not None:
                            db_chain_id = str(row2[0])

                        blocks_c = int(conn.execute("SELECT COUNT(1) FROM blocks").fetchone()[0])
                        txs_c = int(conn.execute("SELECT COUNT(1) FROM txs").fetchone()[0])
                        events_c = int(conn.execute("SELECT COUNT(1) FROM events").fetchone()[0])
                except Exception as exc:  # noqa: BLE001
                    db_err = str(exc)

            lag: int | None = None
            if latest is not None and last_indexed is not None and latest >= 0 and last_indexed >= 0:
                lag = max(0, int(latest) - int(last_indexed))

            db_size_bytes = 0
            if db_exists:
                for suffix in ["", "-wal", "-shm"]:
                    p = db_path + suffix
                    if os.path.exists(p):
                        try:
                            db_size_bytes += int(os.path.getsize(p))
                        except Exception:
                            pass

            api_base = None
            try:
                host, port_str = listen.rsplit(":", 1)
                int(port_str)
                host = host.strip()
                if host in ("0.0.0.0", "::"):
                    host = "127.0.0.1"
                api_base = f"http://{host}:{port_str}"
            except Exception:
                api_base = None

            lines: list[str] = []
            lines.append(f"Indexer: {'RUNNING' if idx_running else 'stopped'}")
            lines.append(f"API: {'RUNNING' if api_running else 'stopped'} (listen={listen})" + (f" (cors={cors})" if cors else ""))

            if api_base:
                lines.append(f"API URL: {api_base}")

            if rpc_err:
                lines.append(f"RPC: {rpc_url} (ERROR: {rpc_err})")
            else:
                cid = chain_id or "-"
                latest_txt = str(latest) if latest is not None else "-"
                lines.append(f"RPC: {rpc_url} (chain_id={cid}, latest={latest_txt})")

            if not db_exists:
                lines.append(f"DB: {db_path} (missing)")
            elif db_err:
                lines.append(f"DB: {db_path} (ERROR: {db_err})")
            else:
                li = str(last_indexed) if last_indexed is not None else "-"
                lag_txt = str(lag) if lag is not None else "-"
                size_txt = _format_bytes(db_size_bytes)
                counts_txt = "-"
                if blocks_c is not None and txs_c is not None and events_c is not None:
                    counts_txt = f"blocks={blocks_c}, txs={txs_c}, events={events_c}"
                cid_db = db_chain_id or "-"
                lines.append(f"DB: {db_path} (size={size_txt}, chain_id={cid_db}, last_indexed={li}, lag={lag_txt}, {counts_txt})")

            details = "\n".join(lines)

            def _ui() -> None:
                self.indexer_status_details_var.set(details)
                self._indexer_status_last_refresh = time.time()
                self._indexer_status_refresh_in_flight = False

            self.root.after(0, _ui)

        threading.Thread(target=_runner, daemon=True).start()

    # ----------------------- Nginx manager -----------------------

    def refresh_nginx_status(self) -> None:
        self._refresh_nginx_status_async(force=True)

    def _nginx_status_tick(self) -> None:
        try:
            if not getattr(self, "nginx_auto_refresh_var", None):
                return
            if not bool(self.nginx_auto_refresh_var.get()):
                return
        except Exception:
            return

        now = time.time()
        if (now - float(self._nginx_status_last_refresh)) < 2.0:
            return
        self._refresh_nginx_status_async(force=False)

    def _nginx_service_name(self) -> str:
        name = (self.nginx_service_var.get().strip() if getattr(self, "nginx_service_var", None) else "").strip()
        return name or "nginx"

    def _refresh_nginx_status_async(self, force: bool) -> None:
        if self._nginx_status_refresh_in_flight:
            return
        self._nginx_status_refresh_in_flight = True

        service = self._nginx_service_name()
        stub_url = (self.nginx_stub_status_url_var.get().strip() if getattr(self, "nginx_stub_status_url_var", None) else "")

        def _runner() -> None:
            active = "unknown"
            sub = "-"
            main_pid = "-"
            since = "-"
            tasks = "-"
            mem = "-"
            cpu = "-"
            err: str | None = None

            try:
                cmd = [
                    "systemctl",
                    "show",
                    service,
                    "--no-pager",
                    "-p",
                    "ActiveState",
                    "-p",
                    "SubState",
                    "-p",
                    "MainPID",
                    "-p",
                    "ExecMainStartTimestamp",
                    "-p",
                    "TasksCurrent",
                    "-p",
                    "MemoryCurrent",
                    "-p",
                    "CPUUsageNSec",
                ]
                out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True)
                kv: dict[str, str] = {}
                for line in out.splitlines():
                    if "=" in line:
                        k, v = line.split("=", 1)
                        kv[k.strip()] = v.strip()
                active = kv.get("ActiveState", active)
                sub = kv.get("SubState", sub)
                main_pid = kv.get("MainPID", main_pid)
                since = kv.get("ExecMainStartTimestamp", since)
                tasks = kv.get("TasksCurrent", tasks)
                mem_raw = kv.get("MemoryCurrent")
                if mem_raw and mem_raw.isdigit():
                    mem = _format_bytes(int(mem_raw))
                cpu_raw = kv.get("CPUUsageNSec")
                if cpu_raw and cpu_raw.isdigit():
                    # best-effort human readout
                    cpu_s = int(cpu_raw) / 1_000_000_000
                    cpu = f"{cpu_s:.1f}s"
            except Exception as exc:  # noqa: BLE001
                err = str(exc)

            stub_lines: list[str] = []
            if stub_url:
                try:
                    req = urllib.request.Request(stub_url, headers={"Accept": "text/plain"})
                    with urllib.request.urlopen(req, timeout=6) as resp:  # noqa: S310
                        body = resp.read().decode("utf-8", errors="replace")

                    # Typical format:
                    # Active connections: 1
                    # server accepts handled requests
                    #  10 10 20
                    # Reading: 0 Writing: 1 Waiting: 0
                    lines = [ln.strip() for ln in body.splitlines() if ln.strip()]
                    for ln in lines[:6]:
                        stub_lines.append(ln)
                except Exception as exc:  # noqa: BLE001
                    stub_lines.append(f"stub_status ERROR: {exc}")

            status_txt = f"{service}: {active}/{sub}"
            details: list[str] = []
            if err:
                details.append(f"systemctl show ERROR: {err}")
            else:
                details.append(f"MainPID: {main_pid}   Since: {since}")
                details.append(f"Tasks: {tasks}   Mem: {mem}   CPU: {cpu}")
            if stub_url:
                details.append(f"stub_status: {stub_url}")
                details.extend(stub_lines)

            details_txt = "\n".join(details)

            def _ui() -> None:
                self.nginx_status_var.set(status_txt)
                self.nginx_status_details_var.set(details_txt)
                self._nginx_status_last_refresh = time.time()
                self._nginx_status_refresh_in_flight = False

            self.root.after(0, _ui)

        threading.Thread(target=_runner, daemon=True).start()

    def nginx_service_action(self, action: str) -> None:
        service = self._nginx_service_name()
        action = (action or "").strip().lower()
        if action not in ("start", "stop", "restart", "reload"):
            messagebox.showerror("Nginx", f"Unsupported action: {action}")
            return

        cmd = ["systemctl", action, service]
        self._run_command_async(cmd, target_queue=self.nginx_log_queue, start_log_cb=self.append_nginx_log)
        # Force a refresh shortly after issuing the command.
        try:
            self._nginx_status_last_refresh = 0.0
        except Exception:
            pass

    def nginx_test_config(self) -> None:
        cmd = ["nginx", "-t"]
        self._run_command_async(cmd, target_queue=self.nginx_log_queue, start_log_cb=self.append_nginx_log)

    def _nginx_sites_on_select(self) -> None:
        tree = self._nginx_sites_tree
        if not tree:
            return
        sel = tree.selection()
        if not sel:
            try:
                self.nginx_site_details_var.set("(select a site)")
            except Exception:
                pass
            return
        iid = str(sel[0])
        row = self._nginx_sites_rows_by_iid.get(iid)
        if not row:
            return

        lines: list[str] = []
        lines.append(f"Config: {row.get('config_path')}")
        if row.get("realpath") and row.get("realpath") != row.get("config_path"):
            lines.append(f"Realpath: {row.get('realpath')}")
        if row.get("server_name"):
            lines.append(f"server_name: {row.get('server_name')}")
        if row.get("listen"):
            lines.append(f"listen: {row.get('listen')}")
        if row.get("root"):
            lines.append(f"root: {row.get('root')}")
        if row.get("access_log"):
            lines.append(f"access_log: {row.get('access_log')}")
        if row.get("error_log"):
            lines.append(f"error_log: {row.get('error_log')}")
        if row.get("proxy_pass"):
            lines.append(f"proxy_pass: {row.get('proxy_pass')}")
        if row.get("locations"):
            lines.append(f"locations: {row.get('locations')}")

        try:
            self.nginx_site_details_var.set("\n".join(lines) if lines else "(no parsed details)")
        except Exception:
            pass

    def _nginx_set_sites_analytics_text(self, text: str) -> None:
        box = self.nginx_sites_analytics
        if not box:
            return
        try:
            box.configure(state="normal")
            box.delete("1.0", tk.END)
            box.insert(tk.END, text)
            box.see(tk.END)
            box.configure(state="disabled")
        except Exception:
            pass

    def _nginx_enabled_site_config_paths(self) -> list[str]:
        roots = ["/etc/nginx/sites-enabled", "/etc/nginx/conf.d"]
        out: list[str] = []
        for root in roots:
            try:
                if not os.path.isdir(root):
                    continue
                for name in sorted(os.listdir(root)):
                    if name.startswith("."):
                        continue
                    p = os.path.join(root, name)
                    # include symlinks + regular files
                    if os.path.isfile(p) or os.path.islink(p):
                        out.append(p)
            except Exception:
                continue
        return out

    def _nginx_strip_comments(self, text: str) -> str:
        # Best-effort: strip '#' comments outside quotes.
        out_lines: list[str] = []
        for line in text.splitlines():
            in_s = False
            in_d = False
            buf = []
            for ch in line:
                if ch == "'" and not in_d:
                    in_s = not in_s
                elif ch == '"' and not in_s:
                    in_d = not in_d
                if ch == "#" and not in_s and not in_d:
                    break
                buf.append(ch)
            out_lines.append("".join(buf))
        return "\n".join(out_lines)

    def _nginx_extract_server_blocks(self, text: str) -> list[str]:
        blocks: list[str] = []
        t = self._nginx_strip_comments(text)
        pat = re.compile(r"\bserver\b\s*\{", re.IGNORECASE)
        for m in pat.finditer(t):
            start = m.end() - 1  # at '{'
            depth = 0
            end = None
            for i in range(start, len(t)):
                c = t[i]
                if c == "{":
                    depth += 1
                elif c == "}":
                    depth -= 1
                    if depth == 0:
                        end = i + 1
                        break
            if end:
                blocks.append(t[m.start() : end])
        return blocks

    def _nginx_first_match(self, text: str, pattern: str) -> str | None:
        m = re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE)
        if not m:
            return None
        val = (m.group(1) or "").strip()
        return val or None

    def _nginx_all_matches(self, text: str, pattern: str) -> list[str]:
        vals: list[str] = []
        for m in re.finditer(pattern, text, flags=re.IGNORECASE | re.MULTILINE):
            v = (m.group(1) or "").strip()
            if v:
                vals.append(v)
        return vals

    def refresh_nginx_sites(self) -> None:
        tree = self._nginx_sites_tree
        if not tree:
            return

        def _runner() -> None:
            paths = self._nginx_enabled_site_config_paths()
            rows: list[dict] = []

            for cfg_path in paths:
                try:
                    real = os.path.realpath(cfg_path)
                    with open(real, encoding="utf-8", errors="replace") as f:
                        content = f.read()
                except Exception as exc:  # noqa: BLE001
                    rows.append(
                        {
                            "config_path": cfg_path,
                            "realpath": os.path.realpath(cfg_path),
                            "server_name": "(unreadable)",
                            "listen": "-",
                            "type": "-",
                            "access_log": "-",
                            "error": str(exc),
                        }
                    )
                    continue

                blocks = self._nginx_extract_server_blocks(content)
                if not blocks:
                    # still show file as a row for visibility
                    rows.append(
                        {
                            "config_path": cfg_path,
                            "realpath": real,
                            "server_name": "(no server blocks)",
                            "listen": "-",
                            "type": "-",
                            "access_log": "-",
                        }
                    )
                    continue

                for idx, blk in enumerate(blocks):
                    server_name = self._nginx_first_match(blk, r"\bserver_name\s+([^;]+);")
                    listens = self._nginx_all_matches(blk, r"\blisten\s+([^;]+);")
                    root = self._nginx_first_match(blk, r"\broot\s+([^;]+);")
                    access_log = self._nginx_first_match(blk, r"\baccess_log\s+([^;]+);")
                    error_log = self._nginx_first_match(blk, r"\berror_log\s+([^;]+);")
                    proxy_passes = self._nginx_all_matches(blk, r"\bproxy_pass\s+([^;]+);")
                    locations = self._nginx_all_matches(blk, r"\blocation\s+([^\{]+)\{")

                    listen = ", ".join(listens) if listens else "-"
                    typ = "proxy" if proxy_passes else "static"
                    proxy_txt = ", ".join(proxy_passes[:5]) if proxy_passes else ""
                    loc_txt = ", ".join([l.strip() for l in locations[:8]]) if locations else ""

                    rows.append(
                        {
                            "config_path": cfg_path,
                            "realpath": real,
                            "server_index": idx,
                            "server_name": server_name or "-",
                            "listen": listen,
                            "type": typ,
                            "access_log": access_log or "",
                            "error_log": error_log or "",
                            "root": root or "",
                            "proxy_pass": proxy_txt,
                            "locations": loc_txt,
                        }
                    )

            def _ui() -> None:
                try:
                    for iid in tree.get_children():
                        tree.delete(iid)
                except Exception:
                    pass

                self._nginx_sites_rows_by_iid = {}
                for i, r in enumerate(rows):
                    cfg_disp = os.path.basename(str(r.get("config_path") or ""))
                    iid = str(i)
                    self._nginx_sites_rows_by_iid[iid] = r
                    tree.insert(
                        "",
                        "end",
                        iid=iid,
                        values=(
                            cfg_disp,
                            str(r.get("server_name") or ""),
                            str(r.get("listen") or ""),
                            str(r.get("type") or ""),
                            str(r.get("access_log") or ""),
                        ),
                    )

                # Reset details/analytics
                try:
                    self.nginx_site_details_var.set("(select a site)")
                except Exception:
                    pass
                self._nginx_set_sites_analytics_text("")

            self.root.after(0, _ui)

        threading.Thread(target=_runner, daemon=True).start()

    def _nginx_selected_site_row(self) -> dict | None:
        tree = self._nginx_sites_tree
        if not tree:
            return None
        sel = tree.selection()
        if not sel:
            return None
        iid = str(sel[0])
        return self._nginx_sites_rows_by_iid.get(iid)

    def _nginx_tail_lines(self, path: str, max_lines: int) -> list[str]:
        max_lines = max(1, int(max_lines))
        # best-effort: assume avg 250B per line
        max_bytes = min(8 * 1024 * 1024, max(256 * 1024, max_lines * 250))
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(max(0, size - max_bytes), os.SEEK_SET)
            data = f.read()
        lines = data.splitlines()[-max_lines:]
        return [ln.decode("utf-8", errors="replace") for ln in lines]

    def nginx_analyze_selected_site(self) -> None:
        row = self._nginx_selected_site_row()
        if not row:
            messagebox.showinfo("Nginx sites", "Select a site first")
            return

        try:
            minutes = int((self.nginx_sites_minutes_var.get() if self.nginx_sites_minutes_var else "10").strip() or "10")
        except ValueError:
            messagebox.showerror("Nginx sites", "Minutes must be an integer")
            return
        minutes = max(1, min(24 * 60, minutes))

        try:
            max_lines = int((self.nginx_sites_max_lines_var.get() if self.nginx_sites_max_lines_var else "4000").strip() or "4000")
        except ValueError:
            messagebox.showerror("Nginx sites", "Max lines must be an integer")
            return
        max_lines = max(200, min(200_000, max_lines))

        server_name = str(row.get("server_name") or "-")
        cfg_path = str(row.get("config_path") or "-")
        access_log_raw = str(row.get("access_log") or "").strip()

        # Determine log file path.
        log_note: str | None = None
        log_path: str | None = None
        if access_log_raw:
            first = access_log_raw.split()[0].strip().strip("\"")
            if first.lower() == "off":
                log_path = None
                log_note = "access_log is off for this site"
            else:
                log_path = first
        if not log_path:
            log_path = "/var/log/nginx/access.log"
            if not log_note:
                log_note = "using default /var/log/nginx/access.log"

        # If access_log uses variables/syslog, we can't reliably resolve it.
        if log_path and ("$" in log_path or log_path.startswith("syslog:")):
            log_note = f"access_log is dynamic ({log_path}); using default /var/log/nginx/access.log"
            log_path = "/var/log/nginx/access.log"

        def _runner() -> None:
            now = datetime.datetime.now(datetime.timezone.utc)
            cutoff = now - datetime.timedelta(minutes=minutes)

            header: list[str] = []
            header.append(f"Site: {server_name}")
            header.append(f"Config: {cfg_path}")
            header.append(f"Window: last {minutes} min")
            header.append(f"Log: {log_path}")
            if log_note:
                header.append(f"Note: {log_note}")
            header.append("")

            if not log_path:
                body = "\n".join(header + ["No access log available to analyze."])

                def _ui() -> None:
                    self._nginx_set_sites_analytics_text(body)

                self.root.after(0, _ui)
                return

            try:
                lines = self._nginx_tail_lines(log_path, max_lines=max_lines)
            except Exception as exc:  # noqa: BLE001
                body = "\n".join(header + [f"ERROR reading log: {exc}"])

                def _ui() -> None:
                    self._nginx_set_sites_analytics_text(body)

                self.root.after(0, _ui)
                return

            # Nginx combined log best-effort parser.
            log_re = re.compile(
                r'^(?P<ip>\S+)\s+\S+\s+\S+\s+\[(?P<time>[^\]]+)\]\s+"(?P<req>[^"]*)"\s+(?P<status>\d{3})\s+(?P<size>\S+)\s+"(?P<ref>[^"]*)"\s+"(?P<ua>[^"]*)"'
            )

            total = 0
            matched = 0
            in_window = 0
            bad_time = 0

            status_cls = Counter()
            status_codes = Counter()
            paths = Counter()
            ips = Counter()
            uas = Counter()
            methods = Counter()

            earliest: datetime.datetime | None = None
            latest: datetime.datetime | None = None

            for line in lines:
                total += 1
                m = log_re.match(line)
                if not m:
                    continue
                matched += 1
                ip = m.group("ip")
                time_local = m.group("time")
                req = m.group("req")
                status = m.group("status")
                ua = m.group("ua")

                try:
                    dt = datetime.datetime.strptime(time_local, "%d/%b/%Y:%H:%M:%S %z")
                    dt_utc = dt.astimezone(datetime.timezone.utc)
                except Exception:
                    bad_time += 1
                    continue

                if dt_utc < cutoff:
                    continue

                in_window += 1
                if earliest is None or dt_utc < earliest:
                    earliest = dt_utc
                if latest is None or dt_utc > latest:
                    latest = dt_utc

                try:
                    sc = int(status)
                except Exception:
                    sc = 0

                status_codes[status] += 1
                if 200 <= sc < 300:
                    status_cls["2xx"] += 1
                elif 300 <= sc < 400:
                    status_cls["3xx"] += 1
                elif 400 <= sc < 500:
                    status_cls["4xx"] += 1
                elif 500 <= sc < 600:
                    status_cls["5xx"] += 1
                else:
                    status_cls["other"] += 1

                ips[ip] += 1
                uas[ua] += 1

                if req and req != "-":
                    parts = req.split()
                    if len(parts) >= 2:
                        methods[parts[0]] += 1
                        paths[parts[1]] += 1

            out: list[str] = []
            out.extend(header)
            out.append(f"Lines scanned: {total} (parsed={matched}, bad_time={bad_time})")
            out.append(f"Requests in window: {in_window}")
            if earliest and latest:
                out.append(f"Observed window: {earliest.isoformat()} .. {latest.isoformat()}")
            out.append("")

            if in_window == 0:
                out.append("No recent requests found in the selected time window.")
            else:
                out.append("Status classes: " + ", ".join(f"{k}={v}" for k, v in status_cls.most_common()))
                out.append("Top statuses: " + ", ".join(f"{k}={v}" for k, v in status_codes.most_common(8)))
                if methods:
                    out.append("Methods: " + ", ".join(f"{k}={v}" for k, v in methods.most_common(6)))
                out.append("")
                out.append("Top paths:")
                for pth, c in paths.most_common(10):
                    out.append(f"  {c:>5}  {pth}")
                out.append("Top IPs:")
                for ip, c in ips.most_common(10):
                    out.append(f"  {c:>5}  {ip}")
                out.append("Top user agents:")
                for ua, c in uas.most_common(5):
                    ua_s = ua
                    if len(ua_s) > 110:
                        ua_s = ua_s[:107] + "..."
                    out.append(f"  {c:>5}  {ua_s}")

            body = "\n".join(out) + "\n"

            def _ui() -> None:
                self._nginx_set_sites_analytics_text(body)

            self.root.after(0, _ui)

        self._nginx_set_sites_analytics_text("Analyzing...\n")
        threading.Thread(target=_runner, daemon=True).start()

    def start_sql_indexer(self) -> None:
        if self.indexer_thread and self.indexer_thread.is_alive():
            messagebox.showinfo("SQL Indexer", "Indexer already running")
            return

        rpc = self.indexer_rpc_var.get().strip() or DEFAULT_SQL_INDEXER_RPC
        db_path = os.path.expanduser(self.indexer_db_var.get().strip() or DEFAULT_SQL_INDEXER_DB)

        try:
            poll_s = float(self.indexer_poll_var.get().strip() or DEFAULT_SQL_INDEXER_POLL_SECONDS)
        except ValueError:
            messagebox.showerror("SQL Indexer", "Poll seconds must be a number")
            return
        poll_s = max(0.5, poll_s)

        start_height_raw = self.indexer_start_height_var.get().strip()
        start_height: int | None = None
        if start_height_raw:
            try:
                start_height = int(start_height_raw)
            except ValueError:
                messagebox.showerror("SQL Indexer", "Start height must be an integer")
                return

        self.append_indexer_log("\n==> Starting built-in SQL indexer\n")
        self.indexer_stop_event.clear()
        self.indexer_status_var.set("Indexer running")

        cfg = IndexerConfig(rpc_url=rpc, db_path=db_path, poll_seconds=poll_s, start_height=start_height)
        self.sql_indexer = SqlIndexer(cfg)

        def _log(line: str) -> None:
            self.indexer_log_queue.put(line)

        def _run() -> None:
            try:
                self.sql_indexer.open()
                self.sql_indexer.run_forever(self.indexer_stop_event, _log)
            except Exception as exc:  # noqa: BLE001
                self.indexer_log_queue.put(f"ERROR running indexer: {exc}\n")
            finally:
                try:
                    if self.sql_indexer:
                        self.sql_indexer.close()
                except Exception:
                    pass
                self.sql_indexer = None

                def _ui_done() -> None:
                    self.indexer_status_var.set("Indexer stopped")
                    # Force a refresh so status reflects final DB height, etc.
                    try:
                        self._indexer_status_last_refresh = 0.0
                    except Exception:
                        pass

                self.root.after(0, _ui_done)

        self.indexer_thread = threading.Thread(target=_run, daemon=True)
        self.indexer_thread.start()

    # ----------------------- Setup helpers -----------------------

    def clear_setup_log(self) -> None:
        self.setup_log.configure(state="normal")
        self.setup_log.delete("1.0", tk.END)
        self.setup_log.configure(state="disabled")

    def _setup_append(self, msg: str) -> None:
        self.setup_log_queue.put(msg)

    def _node_cmd_base(self) -> tuple[str, str]:
        binary_raw = self.bin_var.get().strip() or DEFAULT_BINARY
        binary = self._resolve_binary(binary_raw, [DEFAULT_BINARY, _repo_retrochaind_build()]) or binary_raw
        home = os.path.expanduser(self.home_var.get().strip() or DEFAULT_HOME)
        return binary, home

    def _config_paths(self) -> tuple[str, str, str]:
        _, home = self._node_cmd_base()
        cfg_dir = os.path.join(home, "config")
        return (
            cfg_dir,
            os.path.join(cfg_dir, "config.toml"),
            os.path.join(cfg_dir, "app.toml"),
        )

    def _toml_quote(self, s: str) -> str:
        return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'

    def _set_toml_kv(self, file_path: str, key: str, value_literal: str, section: str | None = None) -> None:
        """Best-effort TOML key update by line-editing.

        - Updates first matching `key = ...` line.
        - If section is provided, edits within that [section] block.
        - If key not found, appends it at end of the section (or file).
        """

        if not os.path.exists(file_path):
            raise FileNotFoundError(file_path)

        with open(file_path, encoding="utf-8") as f:
            lines = f.read().splitlines(True)

        key_re = re.compile(rf"^\\s*{re.escape(key)}\\s*=\\s*.*$")

        start_idx = 0
        end_idx = len(lines)
        if section:
            sec_re = re.compile(rf"^\\s*\\[{re.escape(section)}\\]\\s*$")
            next_sec_re = re.compile(r"^\s*\[.*\]\s*$")
            found = False
            for i, line in enumerate(lines):
                if sec_re.match(line.strip()):
                    start_idx = i + 1
                    found = True
                    break
            if found:
                for j in range(start_idx, len(lines)):
                    if next_sec_re.match(lines[j].strip()):
                        end_idx = j
                        break
            else:
                # Create the section at end
                if lines and not lines[-1].endswith("\n"):
                    lines[-1] += "\n"
                lines.append(f"\n[{section}]\n")
                start_idx = len(lines)
                end_idx = len(lines)

        # Replace if present
        for i in range(start_idx, end_idx):
            if key_re.match(lines[i]):
                prefix = "" if lines[i].endswith("\n") else "\n"
                lines[i] = f"{key} = {value_literal}{prefix}"
                with open(file_path, "w", encoding="utf-8") as f:
                    f.writelines(lines)
                return

        # Append
        insert_at = end_idx
        lines.insert(insert_at, f"{key} = {value_literal}\n")
        with open(file_path, "w", encoding="utf-8") as f:
            f.writelines(lines)

    def setup_init_node(self) -> None:
        binary, home = self._node_cmd_base()
        chain_id = (self.setup_chain_id_var.get().strip() or DEFAULT_SETUP_CHAIN_ID)
        moniker = (self.setup_moniker_var.get().strip() or "retro-node")
        cmd = [binary, "init", moniker, "--chain-id", chain_id, "--home", home]
        self._run_command_async(cmd, target_queue=self.setup_log_queue, start_log_cb=self.append_setup_log)

    def setup_download_genesis(self) -> None:
        url = self.setup_genesis_url_var.get().strip()
        if not url:
            messagebox.showinfo("Genesis", "Set a Genesis URL (optional) first.")
            return

        cfg_dir, _, _ = self._config_paths()
        os.makedirs(cfg_dir, exist_ok=True)
        dst = os.path.join(cfg_dir, "genesis.json")

        def _runner() -> None:
            self._setup_append(f"\n==> Downloading genesis: {url}\n")
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "retrochain-node-manager"})
                with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
                    data = resp.read()
                with open(dst, "wb") as f:
                    f.write(data)
                self._setup_append(f"==> Wrote: {dst} ({len(data)} bytes)\n")
            except urllib.error.URLError as exc:
                self._setup_append(f"ERROR downloading genesis: {exc}\n")
            except Exception as exc:  # noqa: BLE001
                self._setup_append(f"ERROR downloading genesis: {exc}\n")

        threading.Thread(target=_runner, daemon=True).start()

    def setup_apply_basic_config(self) -> None:
        chain_id = (self.setup_chain_id_var.get().strip() or DEFAULT_SETUP_CHAIN_ID)
        seeds = self.setup_seeds_var.get().strip()
        peers = self.setup_persistent_peers_var.get().strip()
        min_gas = self.setup_min_gas_prices_var.get().strip() or DEFAULT_SETUP_MIN_GAS_PRICES

        _, config_toml, app_toml = self._config_paths()

        def _runner() -> None:
            self._setup_append("\n==> Applying basic config\n")
            try:
                if seeds:
                    self._set_toml_kv(config_toml, "seeds", self._toml_quote(seeds), section="p2p")
                if peers:
                    self._set_toml_kv(config_toml, "persistent_peers", self._toml_quote(peers), section="p2p")

                # Keep a visible chain-id in the client config if present.
                client_toml = os.path.join(os.path.dirname(config_toml), "client.toml")
                if os.path.exists(client_toml):
                    self._set_toml_kv(client_toml, "chain-id", self._toml_quote(chain_id))

                # app.toml: minimum gas prices
                if os.path.exists(app_toml):
                    self._set_toml_kv(app_toml, "minimum-gas-prices", self._toml_quote(min_gas))

                    # Ensure API + gRPC are enabled for explorer/dev tooling.
                    # Operators can still override these in app.toml.
                    self._set_toml_kv(app_toml, "enable", "true", section="api")
                    self._set_toml_kv(app_toml, "swagger", "true", section="api")
                    self._set_toml_kv(app_toml, "enable", "true", section="grpc")

                self._setup_append("==> Done\n")
            except Exception as exc:  # noqa: BLE001
                self._setup_append(f"ERROR applying config: {exc}\n")

        threading.Thread(target=_runner, daemon=True).start()

    def _rpc_first_server(self) -> str | None:
        raw = self.setup_statesync_rpc_servers_var.get().strip()
        if not raw:
            return None
        parts = [p.strip() for p in raw.split(",") if p.strip()]
        return parts[0] if parts else None

    def setup_autofill_trust(self) -> None:
        rpc = self._rpc_first_server()
        if not rpc:
            messagebox.showerror("State Sync", "Enter at least one RPC server URL (comma-separated).")
            return

        def _runner() -> None:
            try:
                self._setup_append(f"\n==> Fetching trust params from {rpc}\n")
                status_url = rpc.rstrip("/") + "/status"
                with urllib.request.urlopen(status_url, timeout=10) as resp:  # noqa: S310
                    status = json.loads(resp.read().decode("utf-8"))
                latest = int(status["result"]["sync_info"]["latest_block_height"])
                trust_height = max(1, latest - 2000)
                block_url = rpc.rstrip("/") + f"/block?height={trust_height}"
                with urllib.request.urlopen(block_url, timeout=10) as resp:  # noqa: S310
                    blk = json.loads(resp.read().decode("utf-8"))
                trust_hash = blk["result"]["block_id"]["hash"]

                self.setup_statesync_trust_height_var.set(str(trust_height))
                self.setup_statesync_trust_hash_var.set(trust_hash)
                self._setup_append(f"==> trust_height={trust_height}\n==> trust_hash={trust_hash}\n")
            except Exception as exc:  # noqa: BLE001
                self._setup_append(f"ERROR auto-filling trust params: {exc}\n")

        threading.Thread(target=_runner, daemon=True).start()

    def setup_apply_rpc_config(self) -> None:
        public_rpc = bool(self.setup_public_rpc_var.get())
        statesync_enable = bool(self.setup_statesync_enable_var.get())

        rpc_servers = self.setup_statesync_rpc_servers_var.get().strip()
        trust_height = self.setup_statesync_trust_height_var.get().strip()
        trust_hash = self.setup_statesync_trust_hash_var.get().strip()

        _, config_toml, _ = self._config_paths()

        def _runner() -> None:
            self._setup_append("\n==> Applying RPC node config\n")
            try:
                # Explorer/indexer performance: enable tx indexing by default.
                # Required for /tx_search and event/attribute queries.
                self._set_toml_kv(config_toml, "indexer", self._toml_quote("kv"), section="tx_index")

                # Allow the hosted explorer frontend to call CometBFT RPC from browsers.
                cors = '["https://retrochain.ddns.net", "http://retrochain.ddns.net"]'
                self._set_toml_kv(config_toml, "cors_allowed_origins", cors, section="rpc")

                if public_rpc:
                    self._set_toml_kv(config_toml, "laddr", self._toml_quote("tcp://0.0.0.0:26657"), section="rpc")

                # State sync (optional)
                self._set_toml_kv(config_toml, "enable", "true" if statesync_enable else "false", section="statesync")
                if statesync_enable:
                    if rpc_servers:
                        self._set_toml_kv(config_toml, "rpc_servers", self._toml_quote(rpc_servers), section="statesync")
                    if trust_height:
                        self._set_toml_kv(config_toml, "trust_height", trust_height, section="statesync")
                    if trust_hash:
                        self._set_toml_kv(config_toml, "trust_hash", self._toml_quote(trust_hash), section="statesync")

                self._setup_append("==> Done\n")
            except Exception as exc:  # noqa: BLE001
                self._setup_append(f"ERROR applying RPC config: {exc}\n")

        threading.Thread(target=_runner, daemon=True).start()

    def setup_create_validator_key(self) -> None:
        binary, home = self._node_cmd_base()
        backend = self.keyring_backend_var.get().strip() or DEFAULT_KEYRING_BACKEND
        key_name = self.setup_val_key_name_var.get().strip() or "validator"
        cmd = [binary, "keys", "add", key_name, "--home", home, "--keyring-backend", backend]
        # This will prompt on stdin in the terminal normally; here we just run and stream output.
        # Users can use the Keyring menu if they need mnemonic import.
        self._run_command_async(cmd, target_queue=self.setup_log_queue, start_log_cb=self.append_setup_log)

    def setup_show_validator_pubkey(self) -> None:
        binary, home = self._node_cmd_base()
        cmd = [binary, "tendermint", "show-validator", "--home", home]
        self._run_command_async(cmd, target_queue=self.setup_log_queue, start_log_cb=self.append_setup_log)

    def _build_create_validator_cmd(self) -> list[str]:
        binary, home = self._node_cmd_base()
        chain_id = (self.setup_chain_id_var.get().strip() or DEFAULT_SETUP_CHAIN_ID)
        moniker = (self.setup_moniker_var.get().strip() or "retro-node")
        key_name = self.setup_val_key_name_var.get().strip() or "validator"
        amount = self.setup_val_amount_var.get().strip() or "1000000uretro"
        fees = self.setup_val_fees_var.get().strip() or "5000uretro"

        comm = (self.setup_val_commission_var.get().strip() or "0.10/0.20/0.01").split("/")
        rate = comm[0] if len(comm) > 0 else "0.10"
        max_rate = comm[1] if len(comm) > 1 else "0.20"
        max_change = comm[2] if len(comm) > 2 else "0.01"
        min_self = self.setup_val_min_self_del_var.get().strip() or "1"

        # pubkey via: retrochaind tendermint show-validator
        pubkey_cmd = [binary, "tendermint", "show-validator", "--home", home]
        try:
            pubkey = subprocess.check_output(pubkey_cmd, text=True).strip()
        except Exception:
            pubkey = ""

        cmd = [
            binary,
            "tx",
            "staking",
            "create-validator",
            "--amount",
            amount,
            "--pubkey",
            pubkey or "<run: retrochaind tendermint show-validator>",
            "--moniker",
            moniker,
            "--chain-id",
            chain_id,
            "--commission-rate",
            rate,
            "--commission-max-rate",
            max_rate,
            "--commission-max-change-rate",
            max_change,
            "--min-self-delegation",
            min_self,
            "--from",
            key_name,
            "--fees",
            fees,
            "--home",
            home,
        ]
        backend = self.keyring_backend_var.get().strip() or DEFAULT_KEYRING_BACKEND
        cmd += ["--keyring-backend", backend]
        return cmd

    def setup_generate_create_validator_cmd(self) -> None:
        cmd = self._build_create_validator_cmd()
        self._setup_append("\n==> Create-validator command (review before running):\n")
        self._setup_append(" ".join(shlex.quote(x) for x in cmd) + "\n")

    def setup_broadcast_create_validator(self) -> None:
        if not messagebox.askyesno(
            "Broadcast create-validator",
            "This will broadcast a staking create-validator tx from the selected key. Continue?",
        ):
            return

        cmd = self._build_create_validator_cmd()
        self._run_command_async(cmd, target_queue=self.setup_log_queue, start_log_cb=self.append_setup_log)

    def stop_sql_indexer(self) -> None:
        if self.indexer_thread and self.indexer_thread.is_alive():
            self.append_indexer_log("\n==> Stopping indexer\n")
            self.indexer_stop_event.set()
            self.indexer_status_var.set("Indexer stopping...")
            return
        self.append_indexer_log("\n==> No indexer thread found\n")
        self.indexer_status_var.set("Indexer idle")

    def reset_sql_indexer_db(self) -> None:
        # Always stop first (best effort)
        if self.indexer_thread and self.indexer_thread.is_alive():
            if not messagebox.askyesno(
                "Reset DB",
                "Indexer appears to be running. Stop it and reset the database?",
            ):
                return
            self.stop_sql_indexer()

        sqlite_path = os.path.expanduser(self.indexer_db_var.get().strip() or DEFAULT_SQL_INDEXER_DB)
        if not os.path.exists(sqlite_path):
            messagebox.showinfo("Reset DB", f"SQLite DB not found (nothing to reset):\n{sqlite_path}")
            return

        if not messagebox.askyesno(
            "Reset DB",
            "This will reset your SQLite index database by renaming it to a timestamped backup.\n\n"
            f"DB: {sqlite_path}\n\nProceed?",
        ):
            return

        ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_path = f"{sqlite_path}.bak-{ts}"

        try:
            os.makedirs(os.path.dirname(sqlite_path) or ".", exist_ok=True)
            self.append_indexer_log(f"\n==> Resetting SQLite DB: {sqlite_path}\n")
            shutil.move(sqlite_path, backup_path)
            # Also clean up WAL/SHM if present
            for suffix in ["-wal", "-shm"]:
                sidecar = sqlite_path + suffix
                if os.path.exists(sidecar):
                    try:
                        os.remove(sidecar)
                    except Exception:
                        pass
            self.append_indexer_log(f"==> Moved to: {backup_path}\n")
            messagebox.showinfo("Reset DB", f"Database reset. Backup saved as:\n{backup_path}")
        except Exception as exc:  # noqa: BLE001
            self.append_indexer_log(f"ERROR resetting DB: {exc}\n")
            messagebox.showerror("Reset DB", f"Failed to reset DB: {exc}")

    def start_indexer_api(self) -> None:
        if self.indexer_api_process and self.indexer_api_process.poll() is None:
            messagebox.showinfo("Indexer API", "API already running")
            return

        db_path = os.path.expanduser(self.indexer_db_var.get().strip() or DEFAULT_SQL_INDEXER_DB)
        if not os.path.isfile(db_path):
            messagebox.showerror("Indexer API", f"DB not found: {db_path}")
            return

        listen = self.indexer_api_listen_var.get().strip() or DEFAULT_INDEXER_API_LISTEN
        script_path = os.path.join(os.path.dirname(__file__), "indexer_api.py")
        cmd_list = [sys.executable, script_path, "--db", db_path, "--listen", listen]
        cors = (getattr(self, "indexer_api_cors_origins_var", None).get().strip() if getattr(self, "indexer_api_cors_origins_var", None) else "")
        if cors:
            cmd_list += ["--cors-origins", cors]

        self.append_indexer_log(
            f"\n==> Starting indexer API: {' '.join(shlex.quote(x) for x in cmd_list)}\n"
        )
        self.indexer_api_status_var.set(f"API running ({listen})")

        try:
            # Start in a new session so we can stop the whole process group reliably.
            self.indexer_api_process = subprocess.Popen(
                cmd_list,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                start_new_session=True,
            )
        except Exception as exc:  # noqa: BLE001
            self.append_indexer_log(f"ERROR starting indexer api: {exc}\n")
            self.indexer_api_status_var.set("API stopped")
            self.indexer_api_process = None
            return

        def _run() -> None:
            try:
                proc = self.indexer_api_process
                if not proc:
                    return
                for line in proc.stdout or []:
                    self.indexer_log_queue.put(line)
                proc.wait()
                self.indexer_log_queue.put(f"\n==> indexer api exited with code {proc.returncode}\n")
            except Exception as exc:  # noqa: BLE001
                self.indexer_log_queue.put(f"ERROR running indexer api: {exc}\n")
            finally:
                # Tk vars are not thread-safe; schedule UI update on main thread.
                def _ui_done() -> None:
                    self.indexer_api_status_var.set("API stopped")
                    self.indexer_api_process = None

                self.root.after(0, _ui_done)

        self.indexer_api_thread = threading.Thread(target=_run, daemon=True)
        self.indexer_api_thread.start()

    def stop_indexer_api(self) -> None:
        proc = self.indexer_api_process
        if proc and proc.poll() is None:
            self.append_indexer_log("\n==> Stopping indexer API (SIGTERM)\n")
            self.indexer_api_status_var.set("API stopping...")

            # Best-effort: terminate the whole process group.
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except Exception:
                try:
                    proc.terminate()
                except Exception:
                    pass

            def _escalate_if_needed() -> None:
                p = self.indexer_api_process
                if not p or p.poll() is not None:
                    return
                self.append_indexer_log("==> Indexer API still running; sending SIGKILL\n")
                try:
                    os.killpg(p.pid, signal.SIGKILL)
                except Exception:
                    try:
                        p.kill()
                    except Exception:
                        pass
                # Fallback: if something re-spawned or detached, try pkill by script name.
                try:
                    subprocess.run(["pkill", "-f", "tools/indexer_api.py"], check=False)
                except Exception:
                    pass

            # Give it a moment to exit cleanly, then escalate.
            self.root.after(1500, _escalate_if_needed)
            return

        self.append_indexer_log("\n==> No indexer API process found\n")
        self.indexer_api_status_var.set("API idle")

    # ----------------------- Modules helpers -----------------------

    def _binary_and_home(self) -> tuple[str | None, str]:
        binary_raw = self.bin_var.get().strip() or DEFAULT_BINARY
        binary = self._resolve_binary(binary_raw, [DEFAULT_BINARY, _repo_retrochaind_build()])
        home = os.path.expanduser(self.home_var.get().strip() or DEFAULT_HOME)
        return binary, home

    def refresh_modules(self) -> None:
        """Populate query/tx module dropdowns from `retrochaind ... --help` output."""

        def _parse_modules(help_text: str) -> list[str]:
            mods: list[str] = []
            in_section = False
            for line in help_text.splitlines():
                if line.strip() == "Available Commands:":
                    in_section = True
                    continue
                if in_section:
                    if not line.strip():
                        continue
                    if line.lstrip().startswith("Flags:") or line.lstrip().startswith("Global Flags:"):
                        break
                    # command name is first token
                    parts = line.strip().split()
                    if not parts:
                        continue
                    name = parts[0]
                    desc = " ".join(parts[1:]).lower()
                    # Keep only module subcommands (filters out 'txs', 'block', etc.)
                    if " module" not in desc:
                        continue
                    if name and name not in mods:
                        mods.append(name)
            return mods

        binary, home = self._binary_and_home()
        if not binary:
            self.module_log_queue.put("ERROR: retrochaind binary not found. Set the correct binary path on the Node tab.\n")
            return

        def _runner() -> None:
            try:
                q_help = subprocess.check_output([binary, "query", "--help"], text=True)
                t_help = subprocess.check_output([binary, "tx", "--help"], text=True)
                query_mods = sorted(_parse_modules(q_help))
                tx_mods = sorted(_parse_modules(t_help))

                # Always include custom modules so they're visible even if they lack CLI commands yet.
                for name in ["arcade", "burn", "retrochain"]:
                    if name not in query_mods:
                        query_mods.append(name)
                    if name not in tx_mods:
                        tx_mods.append(name)
                query_mods = sorted(set(query_mods))
                tx_mods = sorted(set(tx_mods))

                def _apply() -> None:
                    self.modules_bin_status_var.set(f"binary: {binary}")
                    self.available_query_modules = query_mods
                    self.available_tx_modules = tx_mods
                    self.query_module_combo["values"] = query_mods
                    self.tx_module_combo["values"] = tx_mods
                    if self.query_module_var.get() not in query_mods and query_mods:
                        self.query_module_var.set(query_mods[0])
                    if self.tx_module_var.get() not in tx_mods and tx_mods:
                        self.tx_module_var.set(tx_mods[0])
                    self.module_log_queue.put(
                        f"==> Modules refreshed (query={len(query_mods)}, tx={len(tx_mods)}, home={home})\n"
                    )

                self.root.after(0, _apply)
            except Exception as exc:  # noqa: BLE001
                self.module_log_queue.put(f"ERROR refreshing modules: {exc}\n")

        threading.Thread(target=_runner, daemon=True).start()

    def run_module_command(self) -> None:
        """Run an arbitrary retrochaind command (space-separated)."""
        cmd = self.module_cmd_var.get().strip()
        if not cmd:
            return
        binary, home = self._binary_and_home()
        if not binary:
            messagebox.showerror("Modules", "retrochaind binary not found. Update the binary path on the Node tab.")
            return
        cmd_list = [binary] + shlex.split(cmd) + ["--home", home]
        self._run_command_async(cmd_list, target_queue=self.module_log_queue, start_log_cb=self.append_module_log)

    def list_query_commands(self) -> None:
        binary, home = self._binary_and_home()
        mod = self.query_module_var.get().strip()
        if not binary or not mod:
            return
        cmd_list = [binary, "query", mod, "--help", "--home", home]
        self._run_command_async(cmd_list, target_queue=self.module_log_queue, start_log_cb=self.append_module_log)

    def query_selected_params(self) -> None:
        binary, home = self._binary_and_home()
        mod = self.query_module_var.get().strip()
        if not binary or not mod:
            return
        if mod not in self.available_query_modules:
            self.module_log_queue.put(f"ERROR: module '{mod}' is not available in this binary's query commands.\n")
            return
        if mod == "burn":
            self.module_log_queue.put(
                "NOTE: burn currently has no CLI query commands in this binary (GetQueryCmd returns nil).\n"
            )
        cmd_list = [binary, "query", mod, "params", "--output", "json", "--home", home]
        self._run_command_async(cmd_list, target_queue=self.module_log_queue, start_log_cb=self.append_module_log)

    def list_tx_commands(self) -> None:
        binary, home = self._binary_and_home()
        mod = self.tx_module_var.get().strip()
        if not binary or not mod:
            return
        cmd_list = [binary, "tx", mod, "--help", "--home", home]
        self._run_command_async(cmd_list, target_queue=self.module_log_queue, start_log_cb=self.append_module_log)

    def _resolve_binary(self, name: str, extra_paths: list[str] | None = None) -> str | None:
        """Find an executable by name or explicit path, with optional fallbacks."""
        # Prefer the locally-built binary when the user asks for "retrochaind".
        # This prevents the GUI from accidentally launching an older installed binary in $PATH.
        if (name or "").strip() == "retrochaind":
            local_build = _repo_retrochaind_build()
            if os.path.isfile(local_build) and os.access(local_build, os.X_OK):
                return local_build

        if name:
            if os.path.isfile(name) and os.access(name, os.X_OK):
                return name
            found = shutil.which(name)
            if found:
                return found
        for candidate in extra_paths or []:
            path = os.path.expanduser(candidate)
            if os.path.isfile(path) and os.access(path, os.X_OK):
                return path
        return None

    def _find_running_node_cmds_for_home(self, home: str) -> list[str]:
        """Return matching running node commandlines for this --home (best-effort)."""
        home = os.path.expanduser(home)
        needles = [f"--home {home}", f"--home={home}"]
        matches: list[str] = []
        for pat in ("retrochaind", "cosmovisor"):
            try:
                out = subprocess.check_output(["pgrep", "-fa", pat], text=True)
            except subprocess.CalledProcessError:
                continue
            except Exception:
                continue
            for ln in out.splitlines():
                if " start" not in ln:
                    continue
                if any(n in ln for n in needles):
                    matches.append(ln.strip())
        return matches

    def _detect_home_db_locks(self, home: str) -> list[str]:
        """Detect active file locks on data/**/LOCK (Linux/Unix best-effort)."""
        if fcntl is None:
            return []
        try:
            home = os.path.expanduser(home)
        except Exception:
            return []
        data_dir = os.path.join(home, "data")
        if not os.path.isdir(data_dir):
            return []

        locked: list[str] = []
        try:
            for root, dirs, files in os.walk(data_dir):
                # Avoid extremely deep walks; the DB dirs are shallow.
                rel = os.path.relpath(root, data_dir)
                if rel.count(os.sep) >= 3:
                    dirs[:] = []
                    continue
                if "LOCK" not in files:
                    continue
                lock_path = os.path.join(root, "LOCK")
                try:
                    fd = os.open(lock_path, os.O_RDWR)
                except Exception:
                    continue
                try:
                    try:
                        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        fcntl.flock(fd, fcntl.LOCK_UN)
                    except OSError:
                        locked.append(lock_path)
                finally:
                    try:
                        os.close(fd)
                    except Exception:
                        pass
        except Exception:
            return locked
        return locked

    def start_node(self) -> None:
        if self.process and self.process.poll() is None:
            messagebox.showinfo("retrochaind", "Node already running")
            return

        binary_raw = self.bin_var.get().strip() or DEFAULT_BINARY
        binary = self._resolve_binary(binary_raw, [DEFAULT_BINARY, _repo_retrochaind_build()])
        if not binary:
            messagebox.showerror(
                "retrochaind",
                f"retrochaind binary not found.\n\nTried: {binary_raw}\nAlso checked: {_repo_retrochaind_build()} and PATH",
            )
            return
        home = os.path.expanduser(self.home_var.get().strip() or DEFAULT_HOME)
        extra_args = self.args_var.get().strip()

        # Preflight: prevent the classic LevelDB "resource temporarily unavailable" by detecting locks.
        running = self._find_running_node_cmds_for_home(home)
        locked = self._detect_home_db_locks(home)
        if running or locked:
            details = []
            if running:
                details.append("Detected running process(es) using this --home:\n" + "\n".join(running))
            if locked:
                details.append("Detected active DB lock(s):\n" + "\n".join(locked[:12]))
                if len(locked) > 12:
                    details.append(f"(and {len(locked) - 12} more)")
            details.append("\nFix: Stop the running node (or change --home), then try again.")
            messagebox.showerror("retrochaind", "\n\n".join(details))
            return

        cmd_str = f"{shlex.quote(binary)} start --home {shlex.quote(home)} {extra_args}"
        self.append_node_log(f"\n==> Starting: {cmd_str}\n")
        self.append_node_log(f"==> Resolved binary: {binary}\n")
        self.status_var.set("Starting...")
        self.stop_event.clear()

        def _run() -> None:
            try:
                # Use shell=False for safety; split command
                cmd_list = shlex.split(cmd_str)
                self.process = subprocess.Popen(
                    cmd_list,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                )
                try:
                    self.root.after(0, lambda: self.status_var.set("Running"))
                except Exception:
                    pass
                for line in self.process.stdout:  # type: ignore[arg-type]
                    if self.stop_event.is_set():
                        break
                    self.node_log_queue.put(line)
                self.process.wait()
                self.node_log_queue.put(f"\n==> retrochaind exited with code {self.process.returncode}\n")
            except FileNotFoundError:
                self.node_log_queue.put("ERROR: retrochaind binary not found. Update the path and try again.\n")
            except Exception as exc:  # noqa: BLE001
                self.node_log_queue.put(f"ERROR: {exc}\n")
            finally:
                try:
                    self.root.after(0, lambda: self.status_var.set("Stopped"))
                except Exception:
                    pass
                self.process = None

        self.reader_thread = threading.Thread(target=_run, daemon=True)
        self.reader_thread.start()
        self.status_var.set("Starting...")

    def start_testnet_node(self) -> None:
        if self.testnet_process and self.testnet_process.poll() is None:
            messagebox.showinfo("retrochaind (testnet)", "Testnet node already running")
            return

        binary_raw = self.test_bin_var.get().strip() or DEFAULT_BINARY
        binary = self._resolve_binary(binary_raw, [DEFAULT_BINARY, _repo_retrochaind_build()])
        if not binary:
            messagebox.showerror(
                "retrochaind (testnet)",
                f"retrochaind binary not found.\n\nTried: {binary_raw}\nAlso checked: {_repo_retrochaind_build()} and PATH",
            )
            return

        home = os.path.expanduser(self.test_home_var.get().strip() or DEFAULT_TESTNET_HOME)
        extra_args = self.test_args_var.get().strip()

        cmd_str = f"{shlex.quote(binary)} start --home {shlex.quote(home)} {extra_args}"
        self.testnet_log_queue.put(f"\n==> Starting: {cmd_str}\n")
        self.testnet_log_queue.put(f"==> Resolved binary: {binary}\n")
        self.testnet_status_var.set("Starting...")
        self.testnet_stop_event.clear()

        def _run() -> None:
            try:
                cmd_list = shlex.split(cmd_str)
                self.testnet_process = subprocess.Popen(
                    cmd_list,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                )
                for line in self.testnet_process.stdout:  # type: ignore[arg-type]
                    if self.testnet_stop_event.is_set():
                        break
                    self.testnet_log_queue.put(line)
                self.testnet_process.wait()
                self.testnet_log_queue.put(
                    f"\n==> retrochaind (testnet) exited with code {self.testnet_process.returncode}\n"
                )
            except FileNotFoundError:
                self.testnet_log_queue.put("ERROR: retrochaind binary not found. Update the path and try again.\n")
            except Exception as exc:  # noqa: BLE001
                self.testnet_log_queue.put(f"ERROR: {exc}\n")
            finally:
                self.testnet_status_var.set("Stopped")
                self.testnet_process = None

        self.testnet_reader_thread = threading.Thread(target=_run, daemon=True)
        self.testnet_reader_thread.start()
        self.testnet_status_var.set("Running")

    def _stop_tail_process(self) -> None:
        if self.tail_process and self.tail_process.poll() is None:
            try:
                self.tail_process.terminate()
            except Exception:
                pass
        self.tail_process = None
        self.tail_stop_event.set()

    def backup_node(self) -> None:
        """Create a compressed backup of the current home directory."""
        home = os.path.expanduser(self.home_var.get().strip() or DEFAULT_HOME)
        if not os.path.isdir(home):
            messagebox.showerror("Backup", f"Home not found: {home}")
            return

        ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        default_name = f"retrochain-backup-{ts}.tar.gz"
        dest = filedialog.asksaveasfilename(
            title="Save backup as",
            initialfile=default_name,
            defaultextension=".tar.gz",
            filetypes=[("Tar Gzip", "*.tar.gz"), ("All files", "*.*")],
        )
        if not dest:
            return

        cmd = ["tar", "-czf", dest, "-C", home, "."]
        self.append_node_log(f"\n==> Creating backup: {dest}\n")

        def _on_success() -> None:
            messagebox.showinfo("Backup", f"Backup created:\n{dest}")

        self._run_command_async(cmd, success_cb=_on_success)

    def start_tail(self) -> None:
        logfile = os.path.expanduser(self.logfile_var.get().strip())
        if not logfile:
            messagebox.showinfo("Tail", "Provide a log file path first")
            return
        if not os.path.isfile(logfile):
            messagebox.showerror("Tail", f"Log file not found: {logfile}")
            return
        self._stop_tail_process()
        self.tail_stop_event.clear()
        self.append_node_log(f"\n==> Tailing {logfile}\n")

        def _tail() -> None:
            try:
                self.tail_process = subprocess.Popen(
                    ["tail", "-F", logfile],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                )
                for line in self.tail_process.stdout:  # type: ignore[arg-type]
                    if self.tail_stop_event.is_set():
                        break
                    self.node_log_queue.put(line)
            except Exception as exc:  # noqa: BLE001
                self.node_log_queue.put(f"ERROR tailing log: {exc}\n")
            finally:
                self._stop_tail_process()

        self.tail_thread = threading.Thread(target=_tail, daemon=True)
        self.tail_thread.start()

    def stop_tail(self) -> None:
        self.append_node_log("\n==> Stopping tail\n")
        self._stop_tail_process()

    def start_hermes(self) -> None:
        if self.hermes_process and self.hermes_process.poll() is None:
            messagebox.showinfo("Hermes", "Hermes already running")
            return
        resolved = self._hermes_resolve_binary_and_env()
        if not resolved:
            return
        binary, config_path, env = resolved
        cmd_list = [binary, "start"]
        self.append_hermes_log(f"\n==> Starting Hermes: {' '.join(shlex.quote(x) for x in cmd_list)} (HERMES_CONFIG={config_path})\n")
        self.hermes_stop_event.clear()
        self.hermes_status_var.set("Hermes running")

        def _run() -> None:
            try:
                self.hermes_process = subprocess.Popen(
                    cmd_list,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    env=env,
                    start_new_session=True,
                )
                for line in self.hermes_process.stdout or []:
                    if self.hermes_stop_event.is_set():
                        break
                    self.hermes_log_queue.put(line)
                self.hermes_process.wait()
                self.hermes_log_queue.put(f"\n==> hermes exited with code {self.hermes_process.returncode}\n")
            except FileNotFoundError:
                self.hermes_log_queue.put("ERROR: hermes binary not found.\n")
            except Exception as exc:  # noqa: BLE001
                self.hermes_log_queue.put(f"ERROR running hermes: {exc}\n")
            finally:
                def _ui_done() -> None:
                    self.hermes_status_var.set("Hermes stopped")
                    self.hermes_process = None

                self.root.after(0, _ui_done)

        self.hermes_thread = threading.Thread(target=_run, daemon=True)
        self.hermes_thread.start()

    def stop_hermes(self) -> None:
        if self.hermes_process and self.hermes_process.poll() is None:
            self.append_hermes_log("\n==> Stopping Hermes (SIGTERM)\n")
            self.hermes_stop_event.set()
            proc = self.hermes_process

            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except Exception:
                try:
                    proc.terminate()
                except Exception:
                    pass
            self.hermes_status_var.set("Hermes stopping...")

            def _escalate_if_needed() -> None:
                p = self.hermes_process
                if not p or p.poll() is not None:
                    return
                self.append_hermes_log("==> Hermes still running; sending SIGKILL\n")
                try:
                    os.killpg(p.pid, signal.SIGKILL)
                except Exception:
                    try:
                        p.kill()
                    except Exception:
                        pass

            self.root.after(1500, _escalate_if_needed)
            return
        self.append_hermes_log("\n==> No Hermes process found\n")
        self.hermes_status_var.set("Hermes idle")

    def hermes_health_check(self) -> None:
        resolved = self._hermes_resolve_binary_and_env(require_config=True)
        if not resolved:
            return
        binary, config_path, env = resolved
        cmd_list = [binary, "health-check"]

        def _run_health() -> None:
            try:
                self.append_hermes_log(f"\n==> Hermes health-check (HERMES_CONFIG={config_path})\n")
                proc = subprocess.Popen(
                    cmd_list,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    env=env,
                )
                for line in proc.stdout or []:
                    self.hermes_log_queue.put(line)
                proc.wait()
                self.hermes_log_queue.put(f"==> exit {proc.returncode}\n")
                if proc.returncode == 0:
                    self.root.after(0, lambda: self.hermes_status_var.set("Hermes healthy"))
            except FileNotFoundError:
                self.hermes_log_queue.put("ERROR: hermes binary not found.\n")
            except Exception as exc:  # noqa: BLE001
                self.hermes_log_queue.put(f"ERROR running hermes health-check: {exc}\n")

        threading.Thread(target=_run_health, daemon=True).start()

    def browse_hermes_binary(self) -> None:
        path = filedialog.askopenfilename(title="Select hermes binary")
        if path:
            self.hermes_bin_var.set(path)

    def browse_hermes_config(self) -> None:
        current = os.path.expanduser(self.hermes_config_var.get().strip() or DEFAULT_HERMES_CONFIG)
        initial_dir = os.path.dirname(current) or os.path.expanduser("~")
        path = filedialog.askopenfilename(
            title="Select Hermes config.toml",
            initialdir=initial_dir,
            filetypes=[("TOML", "*.toml"), ("All files", "*")],
        )
        if path:
            self.hermes_config_var.set(path)
            self.refresh_hermes_config_info()

    def _hermes_resolve_binary_and_env(self, require_config: bool = True) -> tuple[str, str, dict] | None:
        binary_raw = self.hermes_bin_var.get().strip() or DEFAULT_HERMES_BINARY
        binary = self._resolve_binary(binary_raw, ["~/.local/bin/hermes", "/usr/local/bin/hermes", "/usr/bin/hermes"])
        if not binary:
            messagebox.showerror("Hermes", "Hermes binary not found. Update the path (e.g. ~/.local/bin/hermes) and retry.")
            return None

        config_path = os.path.expanduser(self.hermes_config_var.get().strip() or DEFAULT_HERMES_CONFIG)
        if require_config and not os.path.isfile(config_path):
            messagebox.showerror("Hermes", f"Config not found: {config_path}")
            return None

        env = {**os.environ, "HERMES_CONFIG": config_path}
        return binary, config_path, env

    def _hermes_chain_ids_from_config_text(self, text: str) -> list[str]:
        # Best-effort TOML scanning; no external deps.
        out: list[str] = []
        seen = set()
        in_chain = False
        for raw in text.splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("[[") and line.endswith("]]"):
                in_chain = (line.lower() == "[[chains]]")
                continue
            if in_chain:
                m = re.match(r'^id\s*=\s*"([^"]+)"\s*$', line)
                if m:
                    cid = m.group(1).strip()
                    if cid and cid not in seen:
                        seen.add(cid)
                        out.append(cid)
        return out

    def refresh_hermes_config_info(self) -> None:
        cfg_path = os.path.expanduser(self.hermes_config_var.get().strip() or DEFAULT_HERMES_CONFIG)
        if not os.path.isfile(cfg_path):
            try:
                self.hermes_config_info_var.set(f"config: missing ({cfg_path})")
            except Exception:
                pass
            try:
                if getattr(self, "hermes_chain_combo", None):
                    self.hermes_chain_combo["values"] = []
            except Exception:
                pass
            return

        try:
            with open(cfg_path, encoding="utf-8", errors="replace") as f:
                text = f.read()
        except Exception as exc:  # noqa: BLE001
            self.hermes_config_info_var.set(f"config: ERROR reading ({exc})")
            return

        chains = self._hermes_chain_ids_from_config_text(text)
        chains_txt = ", ".join(chains[:8]) + ("..." if len(chains) > 8 else "")
        self.hermes_config_info_var.set(f"config: ok (chains={len(chains)}: {chains_txt})")

        try:
            if getattr(self, "hermes_chain_combo", None):
                self.hermes_chain_combo["values"] = chains
        except Exception:
            pass

        try:
            if getattr(self, "hermes_ibc_from_combo", None):
                self.hermes_ibc_from_combo["values"] = chains
            if getattr(self, "hermes_ibc_to_combo", None):
                self.hermes_ibc_to_combo["values"] = chains
        except Exception:
            pass

        # If chain is empty, set first.
        try:
            if chains and not (self.hermes_chain_var.get() or "").strip():
                self.hermes_chain_var.set(chains[0])
        except Exception:
            pass

    def _run_hermes_command_async(self, args_list: list[str], title: str | None = None) -> None:
        resolved = self._hermes_resolve_binary_and_env(require_config=True)
        if not resolved:
            return
        binary, config_path, env = resolved
        cmd_list = [binary] + args_list

        def _runner() -> None:
            try:
                t = title or "hermes"
                self.hermes_log_queue.put(f"\n==> {t}: {' '.join(shlex.quote(x) for x in cmd_list)} (HERMES_CONFIG={config_path})\n")
                proc = subprocess.Popen(
                    cmd_list,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    env=env,
                )
                for line in proc.stdout or []:
                    self.hermes_log_queue.put(line)
                proc.wait()
                self.hermes_log_queue.put(f"==> exit {proc.returncode}\n")
            except FileNotFoundError:
                self.hermes_log_queue.put("ERROR: hermes binary not found.\n")
            except Exception as exc:  # noqa: BLE001
                self.hermes_log_queue.put(f"ERROR running hermes: {exc}\n")

        threading.Thread(target=_runner, daemon=True).start()

    def _hermes_run_capture(self, args_list: list[str]) -> tuple[int, str] | None:
        resolved = self._hermes_resolve_binary_and_env(require_config=True)
        if not resolved:
            return None
        binary, config_path, env = resolved
        cmd_list = [binary] + args_list
        try:
            proc = subprocess.run(
                cmd_list,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env=env,
                check=False,
            )
            out = proc.stdout or ""
            self.hermes_log_queue.put(
                f"\n==> capture: {' '.join(shlex.quote(x) for x in cmd_list)} (HERMES_CONFIG={config_path})\n"
            )
            self.hermes_log_queue.put(out)
            self.hermes_log_queue.put(f"==> exit {proc.returncode}\n")
            return proc.returncode, out
        except FileNotFoundError:
            self.hermes_log_queue.put("ERROR: hermes binary not found.\n")
            return None
        except Exception as exc:  # noqa: BLE001
            self.hermes_log_queue.put(f"ERROR running hermes: {exc}\n")
            return None

    def _hermes_parse_connections_output(self, text: str) -> list[dict[str, str]]:
        entries: list[dict[str, str]] = []
        for raw_block in re.split(r"\n\s*\n", (text or "").strip()):
            block = raw_block.strip()
            if not block:
                continue
            m_local = re.search(r"\bconnection-\d+\b", block)
            if not m_local:
                continue
            local_id = m_local.group(0)
            m_cp = re.search(r"counterparty[^\n]*\b(connection-\d+)\b", block, flags=re.IGNORECASE)
            cp_id = m_cp.group(1) if m_cp else ""
            m_state = re.search(r"\bstate\b\s*[:=]\s*([A-Za-z0-9_\-]+)", block)
            state = m_state.group(1) if m_state else ""
            entries.append({"connection_id": local_id, "counterparty_connection_id": cp_id, "state": state})
        return entries

    def _hermes_parse_channels_output(self, text: str) -> list[dict[str, str]]:
        entries: list[dict[str, str]] = []
        for raw_block in re.split(r"\n\s*\n", (text or "").strip()):
            block = raw_block.strip()
            if not block:
                continue
            m_chan = re.search(r"\bchannel-\d+\b", block)
            if not m_chan:
                continue
            channel_id = m_chan.group(0)
            m_port = re.search(r"\bport_id\b\s*[:=]\s*([A-Za-z0-9._\-]+)", block)
            port_id = m_port.group(1) if m_port else ""

            # Prefer connection_hops context when present.
            hop = ""
            m_hops = re.search(r"connection_hops[^\n]*\b(connection-\d+)\b", block, flags=re.IGNORECASE)
            if m_hops:
                hop = m_hops.group(1)
            else:
                m_any_conn = re.search(r"\bconnection-\d+\b", block)
                hop = m_any_conn.group(0) if m_any_conn else ""

            m_cp_chan = re.search(r"counterparty[^\n]*\b(channel-\d+)\b", block, flags=re.IGNORECASE)
            cp_channel_id = m_cp_chan.group(1) if m_cp_chan else ""
            m_cp_port = re.search(r"counterparty[^\n]*\bport\b[^\n]*[:=]\s*([A-Za-z0-9._\-]+)", block, flags=re.IGNORECASE)
            cp_port_id = m_cp_port.group(1) if m_cp_port else ""

            entries.append(
                {
                    "port_id": port_id,
                    "channel_id": channel_id,
                    "connection_hop": hop,
                    "counterparty_port_id": cp_port_id,
                    "counterparty_channel_id": cp_channel_id,
                }
            )
        return entries

    def hermes_refresh_ibc_links(self) -> None:
        from_chain = (self.hermes_ibc_from_var.get() if getattr(self, "hermes_ibc_from_var", None) else "").strip()
        to_chain = (self.hermes_ibc_to_var.get() if getattr(self, "hermes_ibc_to_var", None) else "").strip()
        if not from_chain or not to_chain:
            messagebox.showerror("Hermes", "Select both 'from' and 'to' chains")
            return

        def _update_summary(text: str) -> None:
            try:
                self.hermes_ibc_summary.configure(state="normal")
                self.hermes_ibc_summary.delete("1.0", tk.END)
                self.hermes_ibc_summary.insert(tk.END, text)
                self.hermes_ibc_summary.configure(state="disabled")
            except Exception:
                pass

        def _runner() -> None:
            self.hermes_log_queue.put(f"\n==> IBC links refresh: {from_chain} <-> {to_chain}\n")

            from_conn = self._hermes_run_capture(["query", "connections", "--chain", from_chain])
            from_chan = self._hermes_run_capture(["query", "channels", "--chain", from_chain])
            to_conn = self._hermes_run_capture(["query", "connections", "--chain", to_chain])
            to_chan = self._hermes_run_capture(["query", "channels", "--chain", to_chain])
            if not (from_conn and from_chan and to_conn and to_chan):
                self.root.after(0, lambda: _update_summary("ERROR: failed to run one or more Hermes queries (see log).\n"))
                return

            _rc_fc, out_fc = from_conn
            _rc_fch, out_fch = from_chan
            _rc_tc, out_tc = to_conn
            _rc_tch, out_tch = to_chan

            from_conns = self._hermes_parse_connections_output(out_fc)
            to_conns = self._hermes_parse_connections_output(out_tc)
            from_chans = self._hermes_parse_channels_output(out_fch)
            to_chans = self._hermes_parse_channels_output(out_tch)

            # Pair connections via counterparty connection id (best-effort).
            to_conn_ids = {e.get("connection_id", "") for e in to_conns if e.get("connection_id")}
            conn_pairs: list[str] = []
            for e in from_conns:
                local_id = e.get("connection_id", "")
                cp_id = e.get("counterparty_connection_id", "")
                if local_id and cp_id and cp_id in to_conn_ids:
                    conn_pairs.append(f"{local_id} <-> {cp_id}")

            # Pair channels by counterparty channel+port.
            to_chan_lookup: set[tuple[str, str]] = set()
            for e in to_chans:
                c = e.get("channel_id", "")
                p = e.get("port_id", "")
                if c and p:
                    to_chan_lookup.add((p, c))
            chan_pairs: list[str] = []
            for e in from_chans:
                cp_c = e.get("counterparty_channel_id", "")
                cp_p = e.get("counterparty_port_id", "")
                if cp_c and cp_p and (cp_p, cp_c) in to_chan_lookup:
                    chan_pairs.append(f"{e.get('port_id','')}/{e.get('channel_id','')} <-> {cp_p}/{cp_c}")

            def _group_by_hop(chans: list[dict[str, str]]) -> dict[str, list[str]]:
                grouped: dict[str, list[str]] = {}
                for e in chans:
                    hop = e.get("connection_hop", "") or "(unknown)"
                    label = f"{e.get('port_id','')}/{e.get('channel_id','')}"
                    grouped.setdefault(hop, []).append(label)
                for k in list(grouped.keys()):
                    grouped[k] = sorted(set(grouped[k]))
                return grouped

            from_by_hop = _group_by_hop(from_chans)
            to_by_hop = _group_by_hop(to_chans)

            lines: list[str] = []
            lines.append(f"IBC links summary ({datetime.datetime.now().isoformat(timespec='seconds')})\n")
            lines.append(f"from: {from_chain}\n")
            lines.append(f"to:   {to_chain}\n\n")

            lines.append("Connection pairs (best-effort):\n")
            if conn_pairs:
                for s in sorted(set(conn_pairs))[:20]:
                    lines.append(f"- {s}\n")
            else:
                lines.append("- (none detected; see raw Hermes output in log)\n")

            lines.append("\nChannel pairs (best-effort):\n")
            if chan_pairs:
                for s in sorted(set(chan_pairs))[:40]:
                    lines.append(f"- {s}\n")
            else:
                lines.append("- (none detected; see raw Hermes output in log)\n")

            lines.append("\nChannels by connection hop (from):\n")
            for hop, chs in sorted(from_by_hop.items()):
                lines.append(f"- {hop}: {len(chs)}\n")
                for c in chs[:12]:
                    lines.append(f"  {c}\n")
                if len(chs) > 12:
                    lines.append("  ...\n")

            lines.append("\nChannels by connection hop (to):\n")
            for hop, chs in sorted(to_by_hop.items()):
                lines.append(f"- {hop}: {len(chs)}\n")
                for c in chs[:12]:
                    lines.append(f"  {c}\n")
                if len(chs) > 12:
                    lines.append("  ...\n")

            self.root.after(0, lambda: _update_summary("".join(lines)))

        threading.Thread(target=_runner, daemon=True).start()

    def hermes_version(self) -> None:
        # Support both `hermes --version` and `hermes version` across releases.
        resolved = self._hermes_resolve_binary_and_env(require_config=False)
        if not resolved:
            return
        binary, _cfg, env = resolved

        def _runner() -> None:
            for args in (["--version"], ["version"]):
                try:
                    self.hermes_log_queue.put(f"\n==> hermes {' '.join(args)}\n")
                    proc = subprocess.Popen(
                        [binary] + args,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        bufsize=1,
                        env=env,
                    )
                    for line in proc.stdout or []:
                        self.hermes_log_queue.put(line)
                    proc.wait()
                    self.hermes_log_queue.put(f"==> exit {proc.returncode}\n")
                    if proc.returncode == 0:
                        return
                except Exception:
                    continue
            self.hermes_log_queue.put("ERROR: could not determine hermes version (unsupported command?)\n")

        threading.Thread(target=_runner, daemon=True).start()

    def hermes_validate_config(self) -> None:
        # Best-effort; Hermes versions differ. We'll try common validate commands.
        def _runner() -> None:
            candidates = [
                (["config", "validate"], "validate config"),
                (["validate"], "validate"),
            ]
            for args, title in candidates:
                resolved = self._hermes_resolve_binary_and_env(require_config=True)
                if not resolved:
                    return
                binary, config_path, env = resolved
                cmd_list = [binary] + args
                try:
                    self.hermes_log_queue.put(
                        f"\n==> {title}: {' '.join(shlex.quote(x) for x in cmd_list)} (HERMES_CONFIG={config_path})\n"
                    )
                    proc = subprocess.Popen(
                        cmd_list,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        bufsize=1,
                        env=env,
                    )
                    out_lines: list[str] = []
                    for line in proc.stdout or []:
                        out_lines.append(line)
                        self.hermes_log_queue.put(line)
                    proc.wait()
                    self.hermes_log_queue.put(f"==> exit {proc.returncode}\n")
                    # Heuristic: if command not recognized, try next.
                    joined = "".join(out_lines).lower()
                    if "unknown" in joined and "subcommand" in joined:
                        continue
                    return
                except Exception as exc:  # noqa: BLE001
                    self.hermes_log_queue.put(f"ERROR validating config: {exc}\n")
                    return

        threading.Thread(target=_runner, daemon=True).start()

    def _hermes_selected_chain(self) -> str | None:
        c = (self.hermes_chain_var.get() if getattr(self, "hermes_chain_var", None) else "").strip()
        return c or None

    def hermes_keys_list(self) -> None:
        chain = self._hermes_selected_chain()
        if not chain:
            messagebox.showerror("Hermes", "Select a chain first (Load chains)")
            return
        self._run_hermes_command_async(["keys", "list", "--chain", chain], title=f"keys list ({chain})")

    def hermes_query_channels(self) -> None:
        chain = self._hermes_selected_chain()
        if not chain:
            messagebox.showerror("Hermes", "Select a chain first (Load chains)")
            return
        self._run_hermes_command_async(["query", "channels", "--chain", chain], title=f"query channels ({chain})")

    def hermes_query_clients(self) -> None:
        chain = self._hermes_selected_chain()
        if not chain:
            messagebox.showerror("Hermes", "Select a chain first (Load chains)")
            return
        self._run_hermes_command_async(["query", "clients", "--chain", chain], title=f"query clients ({chain})")

    def hermes_query_connections(self) -> None:
        chain = self._hermes_selected_chain()
        if not chain:
            messagebox.showerror("Hermes", "Select a chain first (Load chains)")
            return
        self._run_hermes_command_async(["query", "connections", "--chain", chain], title=f"query connections ({chain})")

    def hermes_run_args(self) -> None:
        raw = (self.hermes_cmd_args_var.get() if getattr(self, "hermes_cmd_args_var", None) else "").strip()
        if not raw:
            messagebox.showinfo("Hermes", "Enter args to run (example: query channels --chain osmosis-1)")
            return
        try:
            args = shlex.split(raw)
        except Exception:
            messagebox.showerror("Hermes", "Could not parse args (check quotes)")
            return
        self._run_hermes_command_async(args, title="custom")

    def stop_node(self) -> None:
        if self.process and self.process.poll() is None:
            self.append_node_log("\n==> Stopping node (SIGTERM)\n")
            self.stop_event.set()
            try:
                self.process.terminate()
            except Exception:
                pass
            self.status_var.set("Stopping...")
            return

        # Fallback: kill any running retrochaind
        try:
            home = os.path.expanduser(self.home_var.get().strip() or DEFAULT_HOME)
            # Match retrochaind, retrochaind-pre-*, or cosmovisor-managed commandlines.
            subprocess.run(["pkill", "-f", f"(retrochaind|cosmovisor).* start .*--home[= ]{re.escape(home)}"], check=False)
            self.append_node_log("\n==> Sent pkill to node processes (scoped to this --home)\n")
        except Exception as exc:  # noqa: BLE001
            self.append_node_log(f"ERROR stopping process: {exc}\n")
        self.status_var.set("Stopped")

    def stop_testnet_node(self) -> None:
        if self.testnet_process and self.testnet_process.poll() is None:
            self.testnet_log_queue.put("\n==> Stopping testnet node (SIGTERM)\n")
            self.testnet_stop_event.set()
            try:
                self.testnet_process.terminate()
            except Exception:
                pass
            self.testnet_status_var.set("Stopping...")
            return

        try:
            home = os.path.expanduser(self.test_home_var.get().strip() or DEFAULT_TESTNET_HOME)
            subprocess.run(["pkill", "-f", f"(retrochaind|cosmovisor).* start .*--home[= ]{re.escape(home)}"], check=False)
            self.testnet_log_queue.put("\n==> Sent pkill to node processes (testnet, scoped to this --home)\n")
        except Exception as exc:  # noqa: BLE001
            self.testnet_log_queue.put(f"ERROR stopping testnet process: {exc}\n")
        self.testnet_status_var.set("Stopped")

    def restart_testnet_node(self) -> None:
        self.stop_testnet_node()
        self.root.after(800, self.start_testnet_node)

    def show_testnet_status(self) -> None:
        home = os.path.expanduser(self.test_home_var.get().strip() or DEFAULT_TESTNET_HOME)
        try:
            out = subprocess.check_output(["pgrep", "-fl", "retrochaind"], text=True)
            matches = [ln for ln in out.splitlines() if f"--home {home}" in ln]
            if matches:
                msg = "Running processes:\n" + "\n".join(matches)
                self.testnet_status_var.set("Running")
            else:
                msg = "retrochaind (testnet) not running"
                self.testnet_status_var.set("Stopped")
        except subprocess.CalledProcessError:
            msg = "retrochaind (testnet) not running"
            self.testnet_status_var.set("Stopped")
        self.testnet_log_queue.put(f"\n==> Status: {msg}\n")
        messagebox.showinfo("Status (testnet)", msg)

    def clone_mainnet_config_to_testnet(self) -> None:
        """Copy main home config into testnet home (does not copy data/)."""
        src_home = os.path.expanduser(self.home_var.get().strip() or DEFAULT_HOME)
        dst_home = os.path.expanduser(self.test_home_var.get().strip() or DEFAULT_TESTNET_HOME)
        src_cfg = os.path.join(src_home, "config")
        dst_cfg = os.path.join(dst_home, "config")

        if not os.path.isdir(src_cfg):
            messagebox.showerror("Clone config", f"Source config not found: {src_cfg}")
            return

        os.makedirs(dst_cfg, exist_ok=True)
        copied: list[str] = []
        for name in ("app.toml", "config.toml", "client.toml", "genesis.json", "addrbook.json"):
            s = os.path.join(src_cfg, name)
            d = os.path.join(dst_cfg, name)
            if os.path.exists(s):
                shutil.copy2(s, d)
                copied.append(name)

        self.testnet_log_queue.put(f"\n==> Cloned config files to: {dst_cfg}\n")
        if copied:
            self.testnet_log_queue.put("==> Copied: " + ", ".join(copied) + "\n")
        else:
            self.testnet_log_queue.put("==> Nothing copied (no known config files found)\n")

    def apply_testnet_ports(self) -> None:
        """Write port overrides into the testnet home's TOML files."""
        home = os.path.expanduser(self.test_home_var.get().strip() or DEFAULT_TESTNET_HOME)
        cfg_dir = os.path.join(home, "config")
        config_toml = os.path.join(cfg_dir, "config.toml")
        app_toml = os.path.join(cfg_dir, "app.toml")

        if not os.path.isdir(cfg_dir):
            messagebox.showerror("Testnet ports", f"Config dir not found: {cfg_dir}\nRun init/setup first (or clone config).")
            return

        try:
            rpc_laddr = self.test_rpc_laddr_var.get().strip() or DEFAULT_TESTNET_RPC_LADDR
            p2p_laddr = self.test_p2p_laddr_var.get().strip() or DEFAULT_TESTNET_P2P_LADDR
            api_addr = self.test_api_addr_var.get().strip() or DEFAULT_TESTNET_API_ADDR
            grpc_addr = self.test_grpc_addr_var.get().strip() or DEFAULT_TESTNET_GRPC_ADDR

            if os.path.exists(config_toml):
                self._set_toml_kv(config_toml, "laddr", self._toml_quote(rpc_laddr), section="rpc")
                self._set_toml_kv(config_toml, "laddr", self._toml_quote(p2p_laddr), section="p2p")

            if os.path.exists(app_toml):
                self._set_toml_kv(app_toml, "address", self._toml_quote(api_addr), section="api")
                self._set_toml_kv(app_toml, "address", self._toml_quote(grpc_addr), section="grpc")

            self.testnet_log_queue.put("\n==> Applied testnet port overrides\n")
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Testnet ports", f"Failed to apply ports: {exc}")

    def restart_node(self) -> None:
        self.stop_node()
        self.root.after(800, self.start_node)

    def show_status(self) -> None:
        try:
            out = subprocess.check_output(["pgrep", "-fl", "retrochaind"], text=True)
            if out.strip():
                msg = f"Running processes:\n{out.strip()}"
                self.status_var.set("Running")
            else:
                msg = "retrochaind not running"
                self.status_var.set("Stopped")
        except subprocess.CalledProcessError:
            msg = "retrochaind not running"
            self.status_var.set("Stopped")
        self.append_node_log(f"\n==> Status: {msg}\n")
        messagebox.showinfo("Status", msg)

    def apply_mainnet_preset(self) -> None:
        self.bin_var.set(DEFAULT_BINARY)
        self.home_var.set(os.path.expanduser("~/.retrochain"))
        self.args_var.set("--log_no_color")
        self.logfile_var.set(os.path.expanduser("~/.retrochain/logs/retrochaind.log"))
        self.append_node_log("\n==> Applied Mainnet preset\n")

    def apply_local_preset(self) -> None:
        self.bin_var.set(DEFAULT_BINARY)
        self.home_var.set(os.path.expanduser("~/.retrochain-local"))
        self.args_var.set("--log_no_color --trace".strip())
        self.logfile_var.set(os.path.expanduser("~/.retrochain-local/logs/retrochaind.log"))
        self.append_node_log("\n==> Applied Local preset\n")

    # ----------------------- Keyring helpers -----------------------

    def _keyring_cmd_base(self) -> list[str]:
        binary = self.bin_var.get().strip() or DEFAULT_BINARY
        home = os.path.expanduser(self.home_var.get().strip() or DEFAULT_HOME)
        backend = self.keyring_backend_var.get().strip() or DEFAULT_KEYRING_BACKEND
        return [binary, "keys", "--home", home, "--keyring-backend", backend]

    def refresh_keys(self) -> None:
        cmd = self._keyring_cmd_base() + ["list", "--output", "json"]

        def _on_success(output: str) -> None:
            try:
                data = json.loads(output)
            except json.JSONDecodeError:
                messagebox.showerror("keys list", "Failed to parse keys output")
                return
            self.keys_data = data if isinstance(data, list) else []
            for item in self.keys_tree.get_children():
                self.keys_tree.delete(item)
            for entry in self.keys_data:
                values = (
                    entry.get("name", ""),
                    entry.get("type", ""),
                    entry.get("address", ""),
                    entry.get("algo", ""),
                )
                self.keys_tree.insert("", tk.END, values=values)

        self._run_keys_capture(cmd, _on_success)

    def _run_keys_capture(self, cmd_list: list[str], on_success, input_text: str | None = None) -> None:
        binary = cmd_list[0]
        passphrase = self.keyring_pass_var.get()

        def _runner() -> None:
            try:
                self.append_node_log(f"\n==> {' '.join(shlex.quote(x) for x in cmd_list)}\n")
                proc = subprocess.Popen(
                    cmd_list,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    stdin=subprocess.PIPE if (input_text or passphrase) else None,
                )
                if proc.stdin and (input_text or passphrase):
                    proc.stdin.write(input_text if input_text is not None else passphrase + "\n")
                    proc.stdin.flush()
                    proc.stdin.close()
                output_lines: list[str] = []
                for line in proc.stdout or []:
                    output_lines.append(line)
                proc.wait()
                output = "".join(output_lines)
                if proc.returncode == 0:
                    on_success(output)
                else:
                    self.node_log_queue.put(output or f"command failed (exit {proc.returncode})\n")
            except FileNotFoundError:
                self.node_log_queue.put(f"ERROR: {binary} not found.\n")
            except Exception as exc:  # noqa: BLE001
                self.node_log_queue.put(f"ERROR: {exc}\n")

        threading.Thread(target=_runner, daemon=True).start()

    def _selected_key_name(self) -> str | None:
        selection = self.keys_tree.selection()
        if not selection:
            messagebox.showinfo("Keyring", "Select a key first")
            return None
        item = self.keys_tree.item(selection[0])
        values = item.get("values", [])
        return values[0] if values else None

    def show_selected_address(self) -> None:
        name = self._selected_key_name()
        if not name:
            return
        cmd = self._keyring_cmd_base() + ["show", name, "--address"]
        self._run_command_async(cmd)

    def show_selected_pubkey(self) -> None:
        name = self._selected_key_name()
        if not name:
            return
        cmd = self._keyring_cmd_base() + ["show", name, "--pubkey"]
        self._run_command_async(cmd)

    def add_key(self) -> None:
        name = simpledialog.askstring("Add key", "Key name:", parent=self.root)
        if not name:
            return
        cmd = self._keyring_cmd_base() + ["add", name]

        passphrase = self.keyring_pass_var.get()
        input_text = None
        if passphrase:
            # keys add prompts twice for passphrase
            input_text = f"{passphrase}\n{passphrase}\n"

        self._run_command_async(cmd, input_text, success_cb=self.refresh_keys)

    def import_mnemonic(self) -> None:
        name = simpledialog.askstring("Import mnemonic", "Key name:", parent=self.root)
        if not name:
            return
        mnemonic = simpledialog.askstring(
            "Import mnemonic",
            "Enter 12/24-word mnemonic:",
            parent=self.root,
            show="*",
        )
        if not mnemonic:
            return

        cmd = self._keyring_cmd_base() + ["add", name, "--recover"]
        passphrase = self.keyring_pass_var.get()
        input_parts = []
        if passphrase:
            input_parts.append(passphrase)
            input_parts.append(passphrase)
        input_parts.append(mnemonic.strip())
        input_text = "\n".join(input_parts) + "\n"

        self._run_command_async(cmd, input_text, success_cb=self.refresh_keys)

    def create_key_with_mnemonic(self) -> None:
        name = simpledialog.askstring("Create key", "Key name:", parent=self.root)
        if not name:
            return

        cmd = self._keyring_cmd_base() + ["add", name, "--output", "json"]
        passphrase = self.keyring_pass_var.get()
        input_text = None
        if passphrase:
            # keys add prompts twice for passphrase
            input_text = f"{passphrase}\n{passphrase}\n"

        def _on_success(output: str) -> None:
            mnemonic = self._extract_mnemonic(output)
            if mnemonic:
                messagebox.showinfo(
                    "Key created",
                    f"Name: {name}\n\nSave this mnemonic securely:\n{mnemonic}",
                )
            else:
                messagebox.showwarning(
                    "Key created",
                    "Key added, but mnemonic could not be parsed. Check the log for details.",
                )
            self.refresh_keys()

        self._run_keys_capture(cmd, _on_success, input_text=input_text)

    def delete_key(self) -> None:
        name = self._selected_key_name()
        if not name:
            return
        if not messagebox.askyesno("Delete key", f"Delete key '{name}'? This cannot be undone."):
            return
        cmd = self._keyring_cmd_base() + ["delete", name, "--force"]
        passphrase = self.keyring_pass_var.get()
        input_text = f"{passphrase}\n" if passphrase else None
        self._run_command_async(cmd, input_text, success_cb=self.refresh_keys)

    def show_about(self) -> None:
        about_msg = (
            "Retrochain Node Manager\n"
            "Shaunware Solutions\n\n"
            "Manage retrochaind, view logs, and handle keyring wallets."
        )
        messagebox.showinfo("About", about_msg)

    def systemd_action(self, action: str) -> None:
        service = self.service_var.get().strip()
        if not service:
            messagebox.showinfo("systemd", "Provide a service name")
            return
        self.append_node_log(f"\n==> systemctl {action} {service}\n")
        try:
            out = subprocess.check_output(["systemctl", action, service], stderr=subprocess.STDOUT, text=True)
            self.append_node_log(out + "\n")
            messagebox.showinfo("systemd", out if out.strip() else f"systemctl {action} ok")
        except subprocess.CalledProcessError as exc:
            self.append_node_log(exc.output + "\n")
            messagebox.showerror("systemd", exc.output or exc.args)

    def _extract_mnemonic(self, output: str) -> str | None:
        try:
            data = json.loads(output)
            if isinstance(data, dict):
                mnemonic = data.get("mnemonic") or data.get("Mnemonic")
                if mnemonic:
                    return str(mnemonic).strip()
        except json.JSONDecodeError:
            pass

        for line in output.splitlines():
            if "mnemonic" in line.lower():
                parts = line.split(":", 1)
                if len(parts) == 2:
                    candidate = parts[1].strip().strip('"')
                    if len(candidate.split()) >= 12:
                        return candidate
        return None


def main() -> None:
    root = tk.Tk()
    NodeManagerGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
