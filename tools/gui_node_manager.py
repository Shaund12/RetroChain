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
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, simpledialog, ttk

from sql_indexer import IndexerConfig, SqlIndexer


DEFAULT_BINARY = "retrochaind"
DEFAULT_HOME = os.path.expanduser("~/.retrochain")
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


class NodeManagerGUI:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Retrochain Node Manager - Shaunware Solutions")
        self.process: subprocess.Popen | None = None
        self.node_log_queue: queue.Queue[str] = queue.Queue()
        self.hermes_log_queue: queue.Queue[str] = queue.Queue()
        self.module_log_queue: queue.Queue[str] = queue.Queue()
        self.indexer_log_queue: queue.Queue[str] = queue.Queue()
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

        self.keys_data: list[dict] = []

        self.available_query_modules: list[str] = []
        self.available_tx_modules: list[str] = []

        # Scheduled restart (upgrade) watcher state
        self._sched_stop_event = threading.Event()
        self._sched_thread: threading.Thread | None = None
        self._sched_latest_height: int | None = None
        self._sched_latest_height_at: float | None = None
        self._sched_target_height: int | None = None
        self._sched_armed: bool = False
        self._sched_rpc_url: str = DEFAULT_SQL_INDEXER_RPC

        self._build_ui()
        self._start_scheduled_restart_watcher()
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
        setup_tab = ttk.Frame(notebook, padding=4)
        hermes_tab = ttk.Frame(notebook, padding=4)
        modules_tab = ttk.Frame(notebook, padding=4)
        indexer_tab = ttk.Frame(notebook, padding=4)
        notebook.add(node_tab, text="Node")
        notebook.add(setup_tab, text="Setup")
        notebook.add(hermes_tab, text="Hermes")
        notebook.add(modules_tab, text="Modules")
        notebook.add(indexer_tab, text="SQL Indexer")

        ttk.Label(node_tab, text="retrochaind binary").grid(row=0, column=0, sticky="w")
        self.bin_var = tk.StringVar(value=DEFAULT_BINARY)
        ttk.Entry(node_tab, textvariable=self.bin_var, width=50).grid(row=0, column=1, sticky="ew", padx=6)

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

        sched_btns = ttk.Frame(sched)
        sched_btns.grid(row=1, column=0, columnspan=4, sticky="w", pady=(6, 0))
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
        ttk.Entry(hermes_tab, textvariable=self.hermes_bin_var, width=32).grid(row=0, column=1, sticky="ew", padx=4)
        ttk.Label(hermes_tab, text="config").grid(row=0, column=2, sticky="w")
        self.hermes_config_var = tk.StringVar(value=DEFAULT_HERMES_CONFIG)
        ttk.Entry(hermes_tab, textvariable=self.hermes_config_var, width=42).grid(row=0, column=3, sticky="ew", padx=4)

        btns = ttk.Frame(hermes_tab)
        btns.grid(row=1, column=0, columnspan=4, pady=6, sticky="w")
        ttk.Button(btns, text="Start", command=self.start_hermes).grid(row=0, column=0, padx=4)
        ttk.Button(btns, text="Stop", command=self.stop_hermes).grid(row=0, column=1, padx=4)
        ttk.Button(btns, text="Health", command=self.hermes_health_check).grid(row=0, column=2, padx=4)
        self.hermes_status_var = tk.StringVar(value="Hermes idle")
        ttk.Label(btns, textvariable=self.hermes_status_var, foreground="green").grid(row=0, column=3, padx=8)

        self.hermes_log = scrolledtext.ScrolledText(hermes_tab, height=24, wrap=tk.WORD, state="disabled")
        self.hermes_log.grid(row=2, column=0, columnspan=4, sticky="nsew")
        hermes_tab.rowconfigure(2, weight=1)

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
        indexer_tab.rowconfigure(5, weight=1)

        ttk.Label(indexer_tab, text="RPC URL").grid(row=0, column=0, sticky="w")
        self.indexer_rpc_var = tk.StringVar(value=DEFAULT_SQL_INDEXER_RPC)
        ttk.Entry(indexer_tab, textvariable=self.indexer_rpc_var).grid(row=0, column=1, sticky="ew", padx=6)

        ttk.Label(indexer_tab, text="DB path (SQLite)").grid(row=1, column=0, sticky="w")
        self.indexer_db_var = tk.StringVar(value=DEFAULT_SQL_INDEXER_DB)
        ttk.Entry(indexer_tab, textvariable=self.indexer_db_var).grid(row=1, column=1, sticky="ew", padx=6)

        ttk.Label(indexer_tab, text="Poll seconds").grid(row=2, column=0, sticky="w")
        self.indexer_poll_var = tk.StringVar(value=DEFAULT_SQL_INDEXER_POLL_SECONDS)
        ttk.Entry(indexer_tab, textvariable=self.indexer_poll_var, width=10).grid(row=2, column=1, sticky="w", padx=6)

        ttk.Label(indexer_tab, text="Start height (optional)").grid(row=3, column=0, sticky="w")
        self.indexer_start_height_var = tk.StringVar(value="")
        ttk.Entry(indexer_tab, textvariable=self.indexer_start_height_var, width=14).grid(row=3, column=1, sticky="w", padx=6)

        ttk.Label(indexer_tab, text="Explorer API listen").grid(row=4, column=0, sticky="w")
        self.indexer_api_listen_var = tk.StringVar(value=DEFAULT_INDEXER_API_LISTEN)
        ttk.Entry(indexer_tab, textvariable=self.indexer_api_listen_var, width=18).grid(row=4, column=1, sticky="w", padx=6)

        idx_btns = ttk.Frame(indexer_tab)
        idx_btns.grid(row=5, column=0, columnspan=3, sticky="w", pady=6)
        ttk.Button(idx_btns, text="Start indexer", command=self.start_sql_indexer).grid(row=0, column=0, padx=4)
        ttk.Button(idx_btns, text="Stop indexer", command=self.stop_sql_indexer).grid(row=0, column=1, padx=4)
        ttk.Button(idx_btns, text="Reset DB", command=self.reset_sql_indexer_db).grid(row=0, column=2, padx=4)
        ttk.Button(idx_btns, text="Clear log", command=self.clear_sql_indexer_log).grid(row=0, column=3, padx=4)
        self.indexer_status_var = tk.StringVar(value="Indexer idle")
        ttk.Label(idx_btns, textvariable=self.indexer_status_var, foreground="green").grid(row=0, column=4, padx=10)

        api_btns = ttk.Frame(indexer_tab)
        api_btns.grid(row=6, column=0, columnspan=3, sticky="w", pady=(0, 6))
        ttk.Button(api_btns, text="Start API", command=self.start_indexer_api).grid(row=0, column=0, padx=4)
        ttk.Button(api_btns, text="Stop API", command=self.stop_indexer_api).grid(row=0, column=1, padx=4)
        self.indexer_api_status_var = tk.StringVar(value="API idle")
        ttk.Label(api_btns, textvariable=self.indexer_api_status_var, foreground="green").grid(row=0, column=2, padx=10)

        hint2 = (
            "Built-in indexer: pulls blocks + txs + ABCI events from CometBFT RPC and stores them in SQLite.\n"
            "It indexes begin_block/end_block events and tx events (from /block_results).\n"
            "Leave Start height empty to resume from the last indexed height in the DB."
        )
        ttk.Label(indexer_tab, text=hint2, foreground="gray").grid(row=7, column=0, columnspan=3, sticky="w", pady=(0, 6))

        self.indexer_log = scrolledtext.ScrolledText(indexer_tab, height=20, wrap=tk.WORD, state="disabled")
        self.indexer_log.grid(row=8, column=0, columnspan=3, sticky="nsew")
        indexer_tab.rowconfigure(8, weight=1)

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

    def append_hermes_log(self, line: str) -> None:
        self.hermes_log.configure(state="normal")
        self.hermes_log.insert(tk.END, line)
        self.hermes_log.see(tk.END)
        self.hermes_log.configure(state="disabled")

    def append_module_log(self, line: str) -> None:
        self.module_log.configure(state="normal")
        self.module_log.insert(tk.END, line)
        self.module_log.see(tk.END)
        self.module_log.configure(state="disabled")

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
                line = self.setup_log_queue.get_nowait()
                self.append_setup_log(line)
        except queue.Empty:
            pass

        self._scheduled_restart_tick()
        self.root.after(150, self._poll_log_queues)

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
            return int(h)
        except Exception:
            return None

    def _start_scheduled_restart_watcher(self) -> None:
        if self._sched_thread and self._sched_thread.is_alive():
            return

        self._sched_stop_event.clear()

        def _worker() -> None:
            while not self._sched_stop_event.is_set():
                rpc = self._sched_rpc_url
                h = self._fetch_latest_height(rpc)
                if h is not None:
                    self._sched_latest_height = h
                    self._sched_latest_height_at = time.time()
                time.sleep(2.0)

        self._sched_thread = threading.Thread(target=_worker, daemon=True)
        self._sched_thread.start()

    def _scheduled_restart_tick(self) -> None:
        # Keep thread inputs updated from UI (Tk vars must be accessed on the main thread).
        try:
            self._sched_rpc_url = (self.sched_rpc_var.get().strip() or DEFAULT_SQL_INDEXER_RPC)
        except Exception:
            self._sched_rpc_url = DEFAULT_SQL_INDEXER_RPC

        latest = self._sched_latest_height
        target = self._sched_target_height

        if not self._sched_armed or target is None:
            if latest is None:
                self.sched_status_var.set("Not armed")
            else:
                self.sched_status_var.set(f"Not armed (latest {latest})")
            return

        if latest is None:
            self.sched_status_var.set(f"Armed for {target} (waiting for RPC)")
            return

        self.sched_status_var.set(f"Armed for {target} (latest {latest})")

        if latest >= target:
            # Disarm first to ensure we only restart once.
            self._sched_armed = False
            self._sched_target_height = None
            self.sched_status_var.set(f"Triggering restart (reached {latest})")
            self.append_node_log(f"\n==> Scheduled restart triggered at height {latest} (target {target})\n")
            self.restart_node()

    # ----------------------- SQL indexer -----------------------

    def clear_sql_indexer_log(self) -> None:
        self.indexer_log.configure(state="normal")
        self.indexer_log.delete("1.0", tk.END)
        self.indexer_log.configure(state="disabled")

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
                self.indexer_status_var.set("Indexer stopped")

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
        binary = self.bin_var.get().strip() or DEFAULT_BINARY
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

        self.append_indexer_log(
            f"\n==> Starting indexer API: {' '.join(shlex.quote(x) for x in cmd_list)}\n"
        )
        self.indexer_api_status_var.set(f"API running ({listen})")

        def _run() -> None:
            try:
                self.indexer_api_process = subprocess.Popen(
                    cmd_list,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                )
                for line in self.indexer_api_process.stdout or []:
                    self.indexer_log_queue.put(line)
                self.indexer_api_process.wait()
                self.indexer_log_queue.put(f"\n==> indexer api exited with code {self.indexer_api_process.returncode}\n")
            except Exception as exc:  # noqa: BLE001
                self.indexer_log_queue.put(f"ERROR running indexer api: {exc}\n")
            finally:
                self.indexer_api_status_var.set("API stopped")
                self.indexer_api_process = None

        self.indexer_api_thread = threading.Thread(target=_run, daemon=True)
        self.indexer_api_thread.start()

    def stop_indexer_api(self) -> None:
        if self.indexer_api_process and self.indexer_api_process.poll() is None:
            self.append_indexer_log("\n==> Stopping indexer API (SIGTERM)\n")
            try:
                self.indexer_api_process.terminate()
            except Exception:
                pass
            self.indexer_api_status_var.set("API stopping...")
            return
        self.append_indexer_log("\n==> No indexer API process found\n")
        self.indexer_api_status_var.set("API idle")

    # ----------------------- Modules helpers -----------------------

    def _binary_and_home(self) -> tuple[str | None, str]:
        binary_raw = self.bin_var.get().strip() or DEFAULT_BINARY
        binary = self._resolve_binary(binary_raw)
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

    def start_node(self) -> None:
        if self.process and self.process.poll() is None:
            messagebox.showinfo("retrochaind", "Node already running")
            return

        binary = self.bin_var.get().strip() or DEFAULT_BINARY
        home = os.path.expanduser(self.home_var.get().strip() or DEFAULT_HOME)
        extra_args = self.args_var.get().strip()

        cmd_str = f"{shlex.quote(binary)} start --home {shlex.quote(home)} {extra_args}"
        self.append_node_log(f"\n==> Starting: {cmd_str}\n")
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
                self.status_var.set("Stopped")
                self.process = None

        self.reader_thread = threading.Thread(target=_run, daemon=True)
        self.reader_thread.start()
        self.status_var.set("Running")

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
        binary_raw = self.hermes_bin_var.get().strip() or DEFAULT_HERMES_BINARY
        binary = self._resolve_binary(binary_raw, ["~/.local/bin/hermes", "/usr/local/bin/hermes", "/usr/bin/hermes"])
        if not binary:
            messagebox.showerror("Hermes", "Hermes binary not found. Update the path (e.g. ~/.local/bin/hermes) and retry.")
            return
        config_path = os.path.expanduser(self.hermes_config_var.get().strip() or DEFAULT_HERMES_CONFIG)
        if not os.path.isfile(config_path):
            messagebox.showerror("Hermes", f"Config not found: {config_path}")
            return
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
                    env={**os.environ, "HERMES_CONFIG": config_path},
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
                self.hermes_status_var.set("Hermes stopped")
                self.hermes_process = None

        self.hermes_thread = threading.Thread(target=_run, daemon=True)
        self.hermes_thread.start()

    def stop_hermes(self) -> None:
        if self.hermes_process and self.hermes_process.poll() is None:
            self.append_hermes_log("\n==> Stopping Hermes (SIGTERM)\n")
            self.hermes_stop_event.set()
            try:
                self.hermes_process.terminate()
            except Exception:
                pass
            self.hermes_status_var.set("Hermes stopping...")
            return
        self.append_hermes_log("\n==> No Hermes process found\n")
        self.hermes_status_var.set("Hermes idle")

    def hermes_health_check(self) -> None:
        binary_raw = self.hermes_bin_var.get().strip() or DEFAULT_HERMES_BINARY
        binary = self._resolve_binary(binary_raw, ["~/.local/bin/hermes", "/usr/local/bin/hermes", "/usr/bin/hermes"])
        if not binary:
            messagebox.showerror("Hermes", "Hermes binary not found. Update the path (e.g. ~/.local/bin/hermes) and retry.")
            return
        config_path = os.path.expanduser(self.hermes_config_var.get().strip() or DEFAULT_HERMES_CONFIG)
        cmd_list = [binary, "health-check"]
        env = {**os.environ, "HERMES_CONFIG": config_path}

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
                    self.hermes_status_var.set("Hermes healthy")
            except FileNotFoundError:
                self.hermes_log_queue.put("ERROR: hermes binary not found.\n")
            except Exception as exc:  # noqa: BLE001
                self.hermes_log_queue.put(f"ERROR running hermes health-check: {exc}\n")

        threading.Thread(target=_run_health, daemon=True).start()

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
            subprocess.run(["pkill", "-f", "retrochaind"], check=False)
            self.append_node_log("\n==> Sent pkill to retrochaind\n")
        except Exception as exc:  # noqa: BLE001
            self.append_node_log(f"ERROR stopping process: {exc}\n")
        self.status_var.set("Stopped")

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
        self.bin_var.set("retrochaind")
        self.home_var.set(os.path.expanduser("~/.retrochain"))
        self.args_var.set("--log_no_color")
        self.logfile_var.set(os.path.expanduser("~/.retrochain/logs/retrochaind.log"))
        self.append_node_log("\n==> Applied Mainnet preset\n")

    def apply_local_preset(self) -> None:
        self.bin_var.set("retrochaind")
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
