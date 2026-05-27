"""Settings page (`/settings`) — full parity with the Kivy
`MDApp.open_settings()` panel.

SETTINGS_SCHEMA mirrors `src/monerodui/settings/settings_schema.json`
field-for-field: 17 group separators + 82 editable fields across 17 INI
sections (verified 2026-05-27). The schema is duplicated here as Python
data — not loaded from JSON at runtime — so this file is self-contained
and the structure is greppable in source.

Layout:
  - Header row: Back button + title + Save button.
  - Section accordion (`ui.expansion`): commonly-edited sections
    (Network, P2P, RPC, Blockchain, Advanced) are open by default; the
    other 15 are collapsed but one click away.
  - Floating Save button at the bottom for long pages.

Save handler reads each rendered widget's current value, coerces to the
INI-friendly string format (`"0"`/`"1"` for booleans, str-of-number for
numerics), and writes via `config.set()` + `config.save()`. The Kivy
app reads the same file with identical key/section names, so a "Save"
here is immediately visible there too.

Data Directory picker:
  - The `advanced.data_dir` field gets a special inline row: a text
    input plus a "folder_open" icon button. The button opens a
    `ui.dialog()` with: a typeable path input, a "../" parent button,
    and a list of subdirectories (read via `os.scandir`). Clicking a
    subdirectory navigates into it; "Select this directory" writes the
    path back to the main input.

Configuration Variables
-----------------------
    EXPANDED_BY_DEFAULT: sections rendered open in the accordion.
    INI_KEYS_WITHOUT_CLI_CONSUMER: documented fields that don't map to
        a monerod CLI flag in `get_extra_args()` but are read elsewhere
        (Android-only, runtime/state/storage bookkeeping, or future-use).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from nicegui import ui

from monerodui_web.core import config

logger = logging.getLogger(__name__)


# --- Configuration Variables --------------------------------------------------

# Sections rendered open by default — the ones a user is most likely to
# touch. Everything else starts collapsed (clearly labelled, one click).
EXPANDED_BY_DEFAULT: set[str] = {"network", "p2p", "rpc", "blockchain", "advanced"}

# Fields whose INI key is intentionally NOT translated to a CLI flag by
# config.get_extra_args(). They are still rendered so that:
#   - the INI stays compatible with the Kivy app's reader
#   - future versions may wire them up
#   - the user can still see/edit their stored values
# Each entry: (section, key) -> reason
INI_KEYS_WITHOUT_CLI_CONSUMER: dict[tuple[str, str], str] = {
    ("runtime", "auto_start"): "consumed by web startup logic (main.py)",
    ("runtime", "enable_boot"): "Android-only (boot receiver); no-op on web",
    ("notify", "block_enabled"): "Android-only (notifications); no-op on web",
    ("notify", "reorg_enabled"): "Android-only (notifications); no-op on web",
    ("advanced", "non_interactive"): "implicit — --non-interactive is always passed",
    ("blockchain", "block_sync_size"): (
        "schema-defined but no CLI flag emitted by get_extra_args() "
        "(Kivy's translator omits it too); stored for future use"
    ),
    ("rpc", "max_connections"): (
        "schema-defined but Kivy's _get_extra_args() does not emit "
        "--rpc-max-connections; stored for future use"
    ),
    ("logging", "file"): (
        "schema-defined but Kivy's _get_extra_args() does not emit "
        "--log-file (ProcessManager auto-appends --log-file pointing at "
        "data_dir/monerod.log); stored for future use"
    ),
}

# -----------------------------------------------------------------------------


# Field-for-field mirror of src/monerodui/settings/settings_schema.json.
# Restructured from the flat JSON (with "title" group separators) into a
# nested list-of-sections keyed by the INI section name. This keeps the
# save loop trivial and lets us drive the accordion directly.
SETTINGS_SCHEMA: list[dict[str, Any]] = [
    {
        "section_key": "runtime",
        "title": "Launcher",
        "fields": [
            {"key": "extra_flags", "title": "Extra Flags", "type": "string",
             "desc": "Additional raw command-line flags (advanced)"},
            {"key": "auto_start", "title": "Auto Start", "type": "bool",
             "desc": "Automatically start daemon when app launches"},
            {"key": "enable_boot", "title": "Start on Boot", "type": "bool",
             "desc": "Android only — start node when device restarts"},
        ],
    },
    {
        "section_key": "notify",
        "title": "Notifications (Android)",
        "fields": [
            {"key": "block_enabled", "title": "Block Notifications", "type": "bool",
             "desc": "Android only — notification on new block"},
            {"key": "reorg_enabled", "title": "Reorg Notifications", "type": "bool",
             "desc": "Android only — notification on chain reorganization"},
        ],
    },
    {
        "section_key": "proxy",
        "title": "Proxy / Tor",
        "fields": [
            {"key": "address", "title": "Proxy", "type": "string",
             "desc": "SOCKS proxy for network traffic (ip:port, e.g. 127.0.0.1:9050)"},
            {"key": "allow_dns_leaks", "title": "Allow DNS Leaks", "type": "bool",
             "desc": "Allow DNS queries outside of proxy"},
            {"key": "tx_proxy", "title": "TX Proxy", "type": "string",
             "desc": "Proxy for local txs: tor,ip:port[,max_conn][,disable_noise]"},
            {"key": "anonymous_inbound", "title": "Anonymous Inbound", "type": "string",
             "desc": "Hidden service: address,bind:port[,max_conn]"},
        ],
    },
    {
        "section_key": "network",
        "title": "Network",
        "fields": [
            {"key": "network_type", "title": "Network Type", "type": "options",
             "options": ["mainnet", "testnet", "stagenet"],
             "desc": "Select which network to connect to"},
            {"key": "offline", "title": "Offline Mode", "type": "bool",
             "desc": "Do not listen for peers, nor connect to any"},
            {"key": "no_sync", "title": "No Sync", "type": "bool",
             "desc": "Don't synchronize the blockchain with other peers"},
            {"key": "public_node", "title": "Public Node", "type": "bool",
             "desc": "Allow others to use this node as a remote (restricted RPC, view-only)"},
            {"key": "sync_pruned_blocks", "title": "Sync Pruned Blocks", "type": "bool",
             "desc": "Allow syncing from nodes with only pruned blocks"},
            {"key": "pad_transactions", "title": "Pad Transactions", "type": "bool",
             "desc": "Pad relayed transactions to defend against traffic volume analysis"},
        ],
    },
    {
        "section_key": "blockchain",
        "title": "Blockchain",
        "fields": [
            {"key": "prune", "title": "Prune Blockchain", "type": "bool",
             "desc": "Enable blockchain pruning to save disk space"},
            {"key": "db_sync_mode", "title": "DB Sync Mode", "type": "options",
             "options": ["fast:async:250000000bytes", "safe:sync", "fastest:async"],
             "desc": "Database sync mode (safe is slower but safer)"},
            {"key": "db_salvage", "title": "DB Salvage", "type": "bool",
             "desc": "Try to salvage corrupted blockchain database"},
            {"key": "block_sync_size", "title": "Block Sync Size", "type": "numeric",
             "desc": "Blocks to sync at once (0 = adaptive)"},
            {"key": "fast_block_sync", "title": "Fast Block Sync", "type": "bool",
             "desc": "Use embedded block hashes for faster sync"},
            {"key": "keep_alt_blocks", "title": "Keep Alt Blocks", "type": "bool",
             "desc": "Keep alternative blocks on restart"},
            {"key": "max_txpool_weight", "title": "Max Txpool Weight (bytes)",
             "type": "numeric",
             "desc": "Maximum transaction pool weight (default: 648000000)"},
        ],
    },
    {
        "section_key": "rpc",
        "title": "RPC Server",
        "fields": [
            {"key": "bind_ip", "title": "RPC Bind IP", "type": "string",
             "desc": "IP address for RPC server (default: 127.0.0.1)"},
            {"key": "bind_port", "title": "RPC Bind Port", "type": "numeric",
             "desc": "Port for RPC server (default: 18081)"},
            {"key": "restricted_bind_ip", "title": "Restricted RPC Bind IP", "type": "string",
             "desc": "IP for restricted RPC server"},
            {"key": "restricted_bind_port", "title": "Restricted RPC Port", "type": "numeric",
             "desc": "Port for restricted RPC server"},
            {"key": "restricted", "title": "Restricted RPC", "type": "bool",
             "desc": "Restrict RPC to view-only commands, hide sensitive data"},
            {"key": "use_ipv6", "title": "Use IPv6", "type": "bool",
             "desc": "Allow IPv6 for RPC connections"},
            {"key": "login", "title": "RPC Login", "type": "string",
             "desc": "username:password for RPC authentication"},
            {"key": "confirm_external_bind", "title": "Confirm External Bind", "type": "bool",
             "desc": "Confirm binding RPC to non-loopback address (required for external access)"},
            {"key": "access_control_origins", "title": "CORS Origins", "type": "string",
             "desc": "Comma-separated origins for cross-origin resource sharing"},
            {"key": "max_connections", "title": "Max Connections", "type": "numeric",
             "desc": "Maximum total RPC connections permitted (default: 100)"},
            {"key": "disable_ban", "title": "Disable RPC Ban", "type": "bool",
             "desc": "Do not ban hosts on RPC errors"},
        ],
    },
    {
        "section_key": "p2p",
        "title": "P2P Settings",
        "fields": [
            {"key": "bind_ip", "title": "P2P Bind IP (IPv4)", "type": "string",
             "desc": "Interface for p2p network protocol"},
            {"key": "bind_port", "title": "P2P Bind Port", "type": "numeric",
             "desc": "Port for p2p network protocol (default: 18080)"},
            {"key": "use_ipv6", "title": "Use IPv6", "type": "bool",
             "desc": "Enable IPv6 for p2p connections"},
            {"key": "external_port", "title": "External Port", "type": "numeric",
             "desc": "External port for p2p if using NAT/port forwarding (0 = disabled)"},
            {"key": "out_peers", "title": "Max Out Peers", "type": "numeric",
             "desc": "Maximum number of outgoing peer connections (-1 = default)"},
            {"key": "in_peers", "title": "Max In Peers", "type": "numeric",
             "desc": "Maximum number of incoming peer connections (-1 = default)"},
            {"key": "max_connections_per_ip", "title": "Max Connections Per IP",
             "type": "numeric",
             "desc": "Maximum p2p connections allowed from same IP address"},
            {"key": "hide_my_port", "title": "Hide My Port", "type": "bool",
             "desc": "Do not announce yourself as peerlist candidate"},
            {"key": "allow_local_ip", "title": "Allow Local IP", "type": "bool",
             "desc": "Allow local IP addresses in peer list (debug)"},
            {"key": "priority_nodes", "title": "Add Priority Nodes", "type": "string",
             "desc": "Peers to connect to and keep open (comma-separated)"},
            {"key": "exclusive_nodes", "title": "Add Exclusive Nodes", "type": "string",
             "desc": "Connect ONLY to these peers (comma-separated, overrides other peer options)"},
            {"key": "seed_nodes", "title": "Seed Nodes", "type": "string",
             "desc": "Nodes to retrieve peer addresses from (comma-separated)"},
            {"key": "ban_list", "title": "Ban List File", "type": "string",
             "desc": "Path to file containing banned IPs (one per line)"},
        ],
    },
    {
        "section_key": "bandwidth",
        "title": "Bandwidth Limits",
        "fields": [
            {"key": "limit_rate_up", "title": "Upload Limit (kB/s)", "type": "numeric",
             "desc": "Maximum upload rate in kB/s (default: 8192)"},
            {"key": "limit_rate_down", "title": "Download Limit (kB/s)", "type": "numeric",
             "desc": "Maximum download rate in kB/s (default: 32768)"},
        ],
    },
    {
        "section_key": "rpcssl",
        "title": "RPC SSL",
        "fields": [
            {"key": "mode", "title": "SSL Mode", "type": "options",
             "options": ["autodetect", "enabled", "disabled"],
             "desc": "Enable SSL on RPC connections"},
            {"key": "private_key", "title": "SSL Private Key", "type": "string",
             "desc": "Path to PEM format private key"},
            {"key": "certificate", "title": "SSL Certificate", "type": "string",
             "desc": "Path to PEM format certificate"},
            {"key": "ca_certificates", "title": "CA Certificates", "type": "string",
             "desc": "Path to file with CA certificate(s) to replace system CAs"},
            {"key": "allow_any_cert", "title": "Allow Any Cert", "type": "bool",
             "desc": "Allow any peer certificate (insecure)"},
            {"key": "allow_chained", "title": "Allow Chained", "type": "bool",
             "desc": "Allow user chain certificates"},
        ],
    },
    {
        "section_key": "zmq",
        "title": "ZMQ",
        "fields": [
            {"key": "disabled", "title": "Disable ZMQ", "type": "bool",
             "desc": "Disable ZMQ RPC server"},
            {"key": "bind_ip", "title": "ZMQ Bind IP", "type": "string",
             "desc": "IP for ZMQ RPC server (default: 127.0.0.1)"},
            {"key": "bind_port", "title": "ZMQ Bind Port", "type": "numeric",
             "desc": "Port for ZMQ RPC server (default: 18082)"},
            {"key": "pub", "title": "ZMQ Pub Address", "type": "string",
             "desc": "Address for ZMQ pub (tcp://ip:port or ipc://path)"},
        ],
    },
    {
        "section_key": "bootstrap",
        "title": "Bootstrap Daemon",
        "fields": [
            {"key": "address", "title": "Bootstrap Address", "type": "string",
             "desc": "URL of bootstrap daemon for wallets while syncing ('auto' for public nodes)"},
            {"key": "login", "title": "Bootstrap Login", "type": "string",
             "desc": "username:password for bootstrap daemon"},
            {"key": "proxy", "title": "Bootstrap Proxy", "type": "string",
             "desc": "SOCKS proxy for bootstrap connections (ip:port)"},
        ],
    },
    {
        "section_key": "dns",
        "title": "DNS & Checkpoints",
        "fields": [
            {"key": "enforce_checkpoints", "title": "Enforce DNS Checkpoints", "type": "bool",
             "desc": "Enforce checkpoints retrieved from DNS"},
            {"key": "disable_checkpoints", "title": "Disable DNS Checkpoints", "type": "bool",
             "desc": "Do not retrieve checkpoints from DNS"},
            {"key": "enable_blocklist", "title": "Enable DNS Blocklist", "type": "bool",
             "desc": "Apply realtime blocklist from DNS"},
            {"key": "check_updates", "title": "Check Updates", "type": "options",
             "options": ["notify", "disabled", "download", "update"],
             "desc": "How to handle new version notifications"},
        ],
    },
    {
        "section_key": "nat",
        "title": "UPnP / NAT",
        "fields": [
            {"key": "igd", "title": "UPnP Mode", "type": "options",
             "options": ["delayed", "enabled", "disabled"],
             "desc": "UPnP port mapping behavior"},
        ],
    },
    {
        "section_key": "mining",
        "title": "Mining",
        "fields": [
            {"key": "address", "title": "Mining Address", "type": "string",
             "desc": "Wallet address to mine to"},
            {"key": "threads", "title": "Mining Threads", "type": "numeric",
             "desc": "Number of mining threads"},
            {"key": "bg_enable", "title": "Background Mining", "type": "bool",
             "desc": "Enable background mining"},
            {"key": "bg_ignore_battery", "title": "Ignore Battery", "type": "bool",
             "desc": "Mine on battery (assume plugged in if status unknown)"},
            {"key": "bg_idle_threshold", "title": "Idle Threshold (%)", "type": "numeric",
             "desc": "Minimum idle percentage to start background mining"},
            {"key": "bg_miner_target", "title": "Miner CPU Target (%)", "type": "numeric",
             "desc": "Maximum CPU usage for background miner"},
        ],
    },
    {
        "section_key": "logging",
        "title": "Logging",
        "fields": [
            {"key": "file", "title": "Log File", "type": "string",
             "desc": "Path to log file (leave empty for default)"},
            {"key": "level", "title": "Log Level", "type": "options",
             "options": ["0", "1", "2", "3", "4"],
             "desc": "Logging verbosity"},
            {"key": "max_file_size", "title": "Max Log Size (bytes)", "type": "numeric",
             "desc": "Maximum log file size before rotation (default: 104850000)"},
            {"key": "max_files", "title": "Max Log Files", "type": "numeric",
             "desc": "Maximum rotated log files to keep (0 = unlimited)"},
        ],
    },
    {
        "section_key": "performance",
        "title": "Performance",
        "fields": [
            {"key": "max_concurrency", "title": "Max Concurrency", "type": "numeric",
             "desc": "Max threads for parallel jobs (0 = auto)"},
            {"key": "prep_blocks_threads", "title": "Prep Blocks Threads", "type": "numeric",
             "desc": "Threads for preparing block hashes (default: 4)"},
        ],
    },
    {
        "section_key": "advanced",
        "title": "Advanced",
        "fields": [
            {"key": "config_file", "title": "Config File", "type": "string",
             "desc": "Path to external config file"},
            # data_dir gets special rendering (text input + folder picker).
            {"key": "data_dir", "title": "Data Directory", "type": "path",
             "desc": "Custom data directory path"},
            {"key": "non_interactive", "title": "Non-Interactive", "type": "bool",
             "desc": "Run in non-interactive mode (always implicitly enabled by the web launcher)"},
            {"key": "extra_messages_file", "title": "Extra Messages File", "type": "string",
             "desc": "File with extra messages for coinbase transactions"},
        ],
    },
]


# ---- helpers ----------------------------------------------------------------


def _coerce_to_str(value: Any, field_type: str) -> str:
    """Convert a widget value into the INI string representation.

    bools become "0"/"1" to match the Kivy app's format (its
    `ConfigParser` reads with `getboolean` which accepts both, but
    Kivy's writer always emits "0"/"1"). Numerics become str(int) when
    the float is whole, else str(float). Strings pass through unchanged.
    """
    if field_type == "bool":
        return "1" if bool(value) else "0"
    if field_type == "numeric":
        if value is None or value == "":
            return "0"
        try:
            f = float(value)
            if f.is_integer():
                return str(int(f))
            return str(f)
        except (TypeError, ValueError):
            return str(value)
    # string / options / path
    return "" if value is None else str(value)


# ---- Data directory picker dialog ------------------------------------------


def _open_dir_picker(data_dir_input: ui.input) -> None:
    """Open a modal dialog with a server-side directory browser.

    The user is on the same machine as the server (localhost-or-LAN),
    so a typeable path field plus a simple list-based navigator covers
    the common cases without a full tree widget.
    """
    # Anchor the starting path: current value, else $HOME.
    start_raw = (data_dir_input.value or "").strip()
    start_path = Path(start_raw) if start_raw else Path.home()
    # Walk up until we find an existing dir (handles "user typed garbage").
    while not start_path.exists() and start_path != start_path.parent:
        start_path = start_path.parent
    if not start_path.exists():
        start_path = Path.home()

    # Mutable holder so inner closures can rebind without `nonlocal` games.
    current: dict[str, Path] = {"path": start_path.resolve()}

    with ui.dialog() as dialog, ui.card().style("min-width: 600px; max-width: 90vw;"):
        ui.label("Select Data Directory").classes("text-h6")

        path_label = ui.label(f"Current: {current['path']}").style(
            "font-family: monospace; word-break: break-all;"
        )

        # Editable path — user can type directly.
        path_input = ui.input(
            label="Path",
            value=str(current["path"]),
        ).classes("w-full")

        # Subdirectory list container — rebuilt on every navigation.
        list_container = ui.column().classes("w-full").style(
            "max-height: 320px; overflow-y: auto; gap: 4px;"
        )

        def refresh_listing() -> None:
            list_container.clear()
            path = current["path"]
            path_label.set_text(f"Current: {path}")
            path_input.set_value(str(path))

            with list_container:
                # Parent navigation row.
                if path.parent != path:
                    ui.button(
                        ".. (parent)",
                        icon="arrow_upward",
                        on_click=lambda: navigate_to(path.parent),
                    ).props("flat align=left").classes("w-full")

                # Subdirectories.
                try:
                    entries = sorted(
                        (e for e in os.scandir(path) if e.is_dir()),
                        key=lambda e: e.name.lower(),
                    )
                except (OSError, PermissionError) as e:
                    ui.label(f"Cannot list directory: {e}").style("color: #ff6666;")
                    return

                if not entries:
                    ui.label("(no subdirectories)").style("color: #888;")
                    return

                for entry in entries:
                    sub = Path(entry.path)
                    ui.button(
                        entry.name,
                        icon="folder",
                        on_click=lambda _e=None, p=sub: navigate_to(p),
                    ).props("flat align=left").classes("w-full")

        def navigate_to(p: Path) -> None:
            try:
                resolved = p.resolve()
                if resolved.exists() and resolved.is_dir():
                    current["path"] = resolved
                    refresh_listing()
                else:
                    ui.notify(f"Not a directory: {p}", type="warning")
            except (OSError, RuntimeError) as e:
                ui.notify(f"Cannot navigate: {e}", type="warning")

        def go_typed() -> None:
            """Honor whatever the user typed into the path input."""
            typed = (path_input.value or "").strip()
            if typed:
                navigate_to(Path(typed))

        path_input.on("blur", lambda _e: go_typed())
        path_input.on("keydown.enter", lambda _e: go_typed())

        def select_current() -> None:
            data_dir_input.set_value(str(current["path"]))
            dialog.close()

        with ui.row().classes("w-full justify-end").style("gap: 8px; padding-top: 8px;"):
            ui.button("Cancel", on_click=dialog.close).props("flat")
            ui.button(
                "Select this directory",
                on_click=select_current,
                icon="check",
            ).props("color=orange unelevated")

        refresh_listing()

    dialog.open()


# ---- Page builder -----------------------------------------------------------


def build_settings_page() -> None:
    """Render the `/settings` route inside the active NiceGUI page."""
    # Maps (section_key, field_key) -> widget reference, so the Save
    # handler can read every current value uniformly.
    widget_refs: dict[tuple[str, str], Any] = {}

    with ui.column().classes("w-full").style(
        "max-width: 900px; margin: 0 auto; padding: 16px; gap: 16px;"
    ):
        # ---- Header ----
        with ui.row().classes("items-center w-full no-wrap").style("gap: 8px;"):
            ui.button(
                icon="arrow_back",
                on_click=lambda: ui.navigate.to("/"),
            ).props("flat round color=white").tooltip("Back to dashboard")
            ui.label("Settings").style(
                "color: #ff6600; font-size: 24px; font-weight: 700;"
            )
            ui.space()
            ui.button(
                "Save",
                icon="save",
                on_click=lambda: _on_save(widget_refs),
            ).props("color=orange unelevated")

        ui.label(
            f"Config file: {config.config_path}"
        ).style("color: #888; font-size: 12px; font-family: monospace;")

        # ---- Sections ----
        for section in SETTINGS_SCHEMA:
            section_key: str = section["section_key"]
            title: str = section["title"]
            fields: list[dict[str, Any]] = section["fields"]

            expanded = section_key in EXPANDED_BY_DEFAULT
            with ui.expansion(
                title,
                icon="settings",
                value=expanded,
            ).classes("w-full").props("header-class=text-orange") as exp:
                # Tighten internal layout.
                exp.style("background: #1f1f1f; border: 1px solid #333; border-radius: 6px;")
                with ui.column().classes("w-full").style("padding: 8px 12px; gap: 8px;"):
                    for field in fields:
                        _render_field(section_key, field, widget_refs)

        # ---- Floating Save (footer) ----
        with ui.row().classes("w-full justify-end").style("padding-top: 16px;"):
            ui.button(
                "Save",
                icon="save",
                on_click=lambda: _on_save(widget_refs),
            ).props("color=orange unelevated size=lg")


def _render_field(
    section_key: str,
    field: dict[str, Any],
    widget_refs: dict[tuple[str, str], Any],
) -> None:
    """Render one INI field, wire it into the widget_refs map."""
    field_type: str = field["type"]
    field_key: str = field["key"]
    field_title: str = field["title"]
    desc: str = field.get("desc", "")

    # Honor existing INI value over schema default. ConfigManager
    # already backfills defaults at load(), so `config.get(...)`
    # should never return empty for keys defined in get_all_defaults.
    raw_value = config.get(section_key, field_key, fallback="")

    annotation = ""
    if (section_key, field_key) in INI_KEYS_WITHOUT_CLI_CONSUMER:
        annotation = f"  ({INI_KEYS_WITHOUT_CLI_CONSUMER[(section_key, field_key)]})"

    if field_type == "bool":
        # Accept "1"/"true"/"yes"/"on" as truthy (Kivy's writer uses "0"/"1").
        current_bool = str(raw_value).strip().lower() in ("1", "true", "yes", "on")
        widget = ui.switch(text=field_title, value=current_bool)
        widget_refs[(section_key, field_key)] = widget
        if desc or annotation:
            ui.label(f"{desc}{annotation}").style("color: #888; font-size: 12px;")

    elif field_type == "numeric":
        try:
            current_num: float = float(raw_value) if raw_value not in ("", None) else 0.0
        except (TypeError, ValueError):
            current_num = 0.0
        widget = ui.number(label=field_title, value=current_num).classes("w-full")
        widget_refs[(section_key, field_key)] = widget
        if desc or annotation:
            ui.label(f"{desc}{annotation}").style("color: #888; font-size: 12px;")

    elif field_type == "options":
        options: list[str] = field.get("options", [])
        current_val = str(raw_value) if raw_value else (options[0] if options else "")
        if current_val not in options and options:
            current_val = options[0]
        widget = ui.select(
            options=options,
            label=field_title,
            value=current_val,
        ).classes("w-full")
        widget_refs[(section_key, field_key)] = widget
        if desc or annotation:
            ui.label(f"{desc}{annotation}").style("color: #888; font-size: 12px;")

    elif field_type == "path":
        # Text input + Browse button, side by side.
        with ui.row().classes("items-end w-full no-wrap").style("gap: 8px;"):
            widget = ui.input(label=field_title, value=str(raw_value or "")).classes(
                "flex-grow"
            )
            ui.button(
                icon="folder_open",
                on_click=lambda _e=None, w=widget: _open_dir_picker(w),
            ).props("flat round color=orange").tooltip("Browse directories")
        widget_refs[(section_key, field_key)] = widget
        if desc or annotation:
            ui.label(f"{desc}{annotation}").style("color: #888; font-size: 12px;")

    else:  # "string" or anything unrecognized — default to text input
        widget = ui.input(label=field_title, value=str(raw_value or "")).classes("w-full")
        widget_refs[(section_key, field_key)] = widget
        if desc or annotation:
            ui.label(f"{desc}{annotation}").style("color: #888; font-size: 12px;")


def _on_save(widget_refs: dict[tuple[str, str], Any]) -> None:
    """Write every rendered field's current value into the INI."""
    written = 0
    try:
        for section in SETTINGS_SCHEMA:
            section_key: str = section["section_key"]
            for field in section["fields"]:
                field_key: str = field["key"]
                field_type: str = field["type"]
                widget = widget_refs.get((section_key, field_key))
                if widget is None:
                    continue
                value = widget.value
                config.set(
                    section_key,
                    field_key,
                    _coerce_to_str(value, field_type),
                )
                written += 1
        config.save()
        logger.info(f"Settings saved: {written} fields written to {config.config_path}")
        ui.notify(
            f"Saved {written} settings. Restart monerod for them to take effect.",
            type="positive",
            timeout=5000,
        )
    except Exception as e:
        logger.error(f"Save failed: {e}", exc_info=True)
        ui.notify(f"Save failed: {e}", type="negative", timeout=8000)
