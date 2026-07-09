"""NiceGUI app entrypoint for monerodui_web.

Run with:
    python -m monerodui_web          # via __main__.py
    monerodui-web                    # via console-script (after install)

Configuration Variables
-----------------------
The following deployment-specific values are baked in here. Edit
before deploying to a different host/port:

    WEB_HOST = "0.0.0.0"     # LAN-accessible (per user request 2026-05-26)
    WEB_PORT = 8085          # <<USER MUST SET if port conflict>>

NOTE: WEB_HOST changed from "127.0.0.1" to "0.0.0.0" on 2026-05-26 at
user request to allow LAN access from 10.0.0.0/24 clients. There is
currently NO authentication on the web UI — anyone able to reach
http://<apollo-ip>:8085 can start/stop monerod and edit its config.
If untrusted devices may join the LAN, add auth (e.g. nginx basic
auth in front, or NiceGUI's storage_secret + a login page) before
relying on this.
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict

from nicegui import app, ui

from monerodui.libs import (
    ArchDetector,
    NetworkInfo,
    NodeStatsPoller,
    ProcessManager,
    UpdateChecker,
    VersionChecker,
)
from monerodui_web.core import config, state
from monerodui_web.core.monero_release import construct_download_url
from monerodui_web.core.process_adapter import discover_external_monerod_pid
from monerodui_web.pages import build_dashboard, build_settings_page

# --- Configuration Variables ---------------------------------------------
WEB_HOST: str = "0.0.0.0"
WEB_PORT: int = 8085
WEB_TITLE: str = "monerod UI"
# Highest-priority binary search path. On apollo, /root/monero is a
# symlink the user maintains pointing at the current desired Monero
# release (currently v0.18.4.5). On other hosts this typically doesn't
# exist and the search falls through to ArchDetector + shutil.which.
PREFERRED_BINARY: Path = Path("/root/monero/monerod")
# Monero's own default data dir is ~/.bitmonero/. If the INI's
# advanced.data_dir is empty on startup, we backfill this value so the
# Kivy ProcessManager's "--data-dir required" check passes without
# making the user configure anything.
DEFAULT_DATA_DIR: Path = Path.home() / ".bitmonero"
# --------------------------------------------------------------------------

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

# Inject global CSS to match the Kivy theme: orange #ff6600 primary,
# dark backgrounds (#000000 card bg, #333333 body), Quasar primary
# override via CSS custom properties.
_GLOBAL_CSS = """
<style>
  :root {
    --q-primary: #ff6600;
    --q-dark: #000000;
  }
  body {
    background-color: #1a1a1a;
    color: #ffffff;
  }
  .nicegui-content {
    background-color: #1a1a1a;
  }
  .q-card {
    background-color: #000000;
    color: #ffffff;
  }
  .q-btn[color="orange"] {
    background-color: #ff6600 !important;
    color: #ffffff !important;
  }
</style>
"""


def _resolve_bin_dir() -> Path:
    """Mirror the Kivy app's `bin_dir` (Briefcase layout).

    The Kivy app uses `Path(__file__).parent / "assets" / "bin"` from
    inside `src/monerodui/main.py`. We compute the equivalent path
    relative to the *Kivy* package so a shared binary install works
    for both apps. If the directory doesn't exist, `ArchDetector` will
    just fall through to its project-root / app-root searches and
    finally to our `shutil.which("monerod")` fallback in initialize().
    """
    # /root/monerodui/src/monerodui_web/main.py
    #   .parent           -> .../monerodui_web/
    #   .parent.parent    -> .../src/
    #   / "monerodui" / "assets" / "bin"
    return Path(__file__).parent.parent / "monerodui" / "assets" / "bin"


def initialize() -> None:
    """Run once at server startup (via `app.on_startup`).

    Order:
      1. Load config (creates default INI if missing).
      2. Arch detection + binary resolution (Kivy search + `which` fallback).
      3. Device IP probe.
      4. Storage check on configured data_dir.
    """
    logger.info("=== monerodui_web INITIALIZATION ===")

    # 1. Config
    config.load()

    # Backfill empty data_dir with Monero's own default (~/.bitmonero).
    # The Kivy ProcessManager requires --data-dir to be passed; without
    # this the user would have to configure it before the first Start.
    existing_data_dir = config.get("advanced", "data_dir", fallback="")
    if not existing_data_dir:
        config.set("advanced", "data_dir", str(DEFAULT_DATA_DIR))
        config.save()
        logger.info(f"Backfilled advanced.data_dir = {DEFAULT_DATA_DIR}")

    # 2. Arch detection (always — we want state.arch_name even if the
    # binary is resolved outside ArchDetector below).
    bin_dir = _resolve_bin_dir()
    logger.info(f"Using bin_dir: {bin_dir} (exists={bin_dir.exists()})")
    try:
        detector = ArchDetector(bin_dir=bin_dir)
        state.arch_name = detector.detected_arch or detector.raw_arch or "Unknown"
        state.arch_supported = detector.is_supported()
        kivy_binary_path = detector.binary_path
        kivy_binary_ready = detector.is_ready()
    except Exception as e:
        logger.error(f"ArchDetector failed: {e}", exc_info=True)
        state.arch_name = "Unknown"
        state.arch_supported = False
        kivy_binary_path = None
        kivy_binary_ready = False

    # Binary resolution priority (per user decision 2026-05-26):
    #   1. PREFERRED_BINARY (/root/monero/monerod — apollo's symlink)
    #   2. Kivy ArchDetector search (Briefcase layout, project root, app root)
    #   3. shutil.which("monerod") on PATH
    if PREFERRED_BINARY.exists() and os.access(PREFERRED_BINARY, os.X_OK):
        state.binary_path = PREFERRED_BINARY
        state.binary_ready = True
        logger.info(f"Resolved monerod via PREFERRED_BINARY: {PREFERRED_BINARY}")
    elif kivy_binary_path is not None:
        state.binary_path = kivy_binary_path
        state.binary_ready = kivy_binary_ready
        logger.info(f"Resolved monerod via ArchDetector: {kivy_binary_path}")
    else:
        which_result = shutil.which("monerod")
        if which_result:
            which_path = Path(which_result)
            state.binary_path = which_path
            state.binary_ready = which_path.exists() and os.access(which_path, os.X_OK)
            logger.info(f"Resolved monerod via PATH: {which_path}")
        else:
            state.binary_path = None
            state.binary_ready = False
            logger.warning(
                f"monerod binary not found at {PREFERRED_BINARY}, "
                f"in bin_dir {bin_dir}, or on PATH"
            )

    # 3. Device IP
    try:
        ip = NetworkInfo().get_device_ip()
        state.device_ip = ip if ip else "No Ext Net"
    except Exception as e:
        logger.error(f"NetworkInfo failed: {e}", exc_info=True)
        state.device_ip = "Unknown"

    # 4. Storage check — port of _check_storage() from src/monerodui/main.py:769-787.
    _check_storage_for_state()

    # 5. Wire live service references onto AppState.
    _wire_services()

    # 6. External-detection probe + auto-start.
    # Port of _complete_initialization (src/monerodui/main.py:677-766).
    _initial_state_probe_and_autostart()

    logger.info(
        f"Init done — arch={state.arch_name} supported={state.arch_supported} "
        f"binary_ready={state.binary_ready} ip={state.device_ip} "
        f"storage_ok={state.storage_ok} "
        f"process_owned={state.process_owned} "
        f"external_node_running={state.external_node_running}"
    )


def _wire_services() -> None:
    """Instantiate the long-lived service objects and put them on state.

    These live for the server's lifetime. The dashboard page reads them
    via `state.process_manager` / `state.node_stats_poller` etc.
    """
    # RPC poller — host/port come from config (defaults 127.0.0.1:18081).
    rpc_host = config.get("rpc", "bind_ip", fallback="127.0.0.1")
    try:
        rpc_port = int(config.get("rpc", "bind_port", fallback="18081"))
    except ValueError:
        rpc_port = 18081
    # Poller binds to 127.0.0.1 even if monerod is bound to 0.0.0.0 — RPC
    # access from the same host always works on loopback. Override only
    # if the configured bind_ip is a specific non-0.0.0.0 address.
    poll_host = "127.0.0.1" if rpc_host in ("0.0.0.0", "", "127.0.0.1") else rpc_host

    state.node_stats_poller = NodeStatsPoller(host=poll_host, port=rpc_port)
    state.process_manager = ProcessManager()
    state.version_checker = VersionChecker()
    # UpdateChecker takes (version_checker, is_android, arch). Server is
    # never android; arch falls back to 'amd64' if detection failed.
    arch = state.arch_name if state.arch_supported else "amd64"
    state.update_checker = UpdateChecker(
        state.version_checker,
        is_android=False,
        arch=arch,
    )
    logger.info(
        f"Wired services: poller=http://{poll_host}:{rpc_port} "
        f"process_manager=ProcessManager arch={arch}"
    )


def _initial_state_probe_and_autostart() -> None:
    """One-shot startup: detect external monerod, optionally auto-start.

    Port of `_complete_initialization` (src/monerodui/main.py:677-766)
    minus the Android-only boot-preference and was_running paths.

    Decision order:
      1. If `pgrep -x monerod` finds a daemon AND its RPC responds ->
         mark external_node_running, skip auto-start.
      2. Else if runtime.auto_start = 1 AND prerequisites pass ->
         configure + start via ProcessManager (direct subprocess; monerod's
         own `--log-file` writes to data_dir/monerod.log, which the user
         can `tail -f` for the same observability `screen -r` would give).
      3. Else leave state stopped.
    """
    # Probe for external monerod via pgrep (cheap) + RPC poll.
    ext_pid = discover_external_monerod_pid()
    if ext_pid is not None:
        logger.info(f"External monerod pid {ext_pid} detected via pgrep")
        try:
            stats = state.node_stats_poller.poll()
            if stats.status != "offline":
                state.external_node_running = True
                state.process_owned = False
                state.node_state = "Running (external)"
                state.last_stats = stats
                import time as _t
                state.last_poll_time = _t.time()
                logger.info("External monerod is RPC-responsive; skipping auto-start")
                return
            else:
                logger.info(
                    f"pgrep found monerod {ext_pid} but RPC unreachable — "
                    f"treating as not-running for UI purposes"
                )
        except Exception as e:
            logger.warning(f"Initial RPC probe failed: {e}")

    # Auto-start path (desktop equivalent of main.py:736-762).
    auto_start_raw = config.get("runtime", "auto_start", fallback="0")
    auto_start = auto_start_raw in ("1", "True", "true")
    if not auto_start:
        logger.info("auto_start disabled in config; node remains stopped")
        return

    if not state.binary_ready or state.binary_path is None:
        logger.warning("auto_start requested but binary not ready; skipping")
        return

    data_dir = config.get("advanced", "data_dir", fallback="")
    if not data_dir:
        logger.warning("auto_start requested but data_dir not set; skipping")
        return

    logger.info("Auto-start: configuring ProcessManager and launching")
    try:
        extra_args = config.get_extra_args()
        # Import here to avoid a top-level cycle with dashboard.py.
        from monerodui_web.pages.dashboard import _on_process_state_change
        state.process_manager.configure(
            binary_path=state.binary_path,
            working_dir=Path(data_dir),
            extra_args=extra_args,
            on_state_change=_on_process_state_change,
        )
        ok = state.process_manager.start()
        if ok:
            state.process_owned = True
            state.node_state = "Running"
            logger.info("Auto-start succeeded")
        else:
            err = state.process_manager.last_error
            logger.error(f"Auto-start failed: {err}")
    except Exception as e:
        logger.error(f"Auto-start raised: {e}", exc_info=True)


def _check_storage_for_state() -> None:
    """Populate `state.storage_*` from config + os.statvfs.

    Ported from `monerodui.main.monerodUIApp._check_storage`
    (src/monerodui/main.py:769-787). The Kivy version returns bool and
    opens a dialog on failure; we just record the result.
    """
    data_dir = config.get("advanced", "data_dir")
    if not data_dir or not Path(data_dir).exists():
        state.storage_path = data_dir or None
        state.storage_free_gib = 0.0
        state.storage_ok = False
        return

    try:
        stat = os.statvfs(data_dir)
        free_gib = (stat.f_bavail * stat.f_frsize) / (1024 ** 3)
        try:
            min_free_gib = float(
                config.get("storage", "min_free_gib", fallback="10.0")
            )
        except ValueError:
            min_free_gib = 10.0

        state.storage_path = data_dir
        state.storage_free_gib = free_gib
        state.storage_ok = free_gib >= min_free_gib
    except OSError as e:
        logger.error(f"statvfs failed for {data_dir}: {e}")
        state.storage_path = data_dir
        state.storage_free_gib = 0.0
        state.storage_ok = False


# ---- Background version + update checks ---------------------------------


async def _kick_off_version_and_update_checks() -> None:
    """Fire-and-forget chain: version check, then update check.

    Runs once at startup as an asyncio task scheduled by `app.on_startup`.
    Both checks are sync I/O (subprocess for version, urllib HTTPS for
    update), so each goes through `run_in_executor` to avoid blocking
    NiceGUI's event loop. Each task writes its result onto AppState; the
    next stats-poll tick triggers the per-tab refresh that picks up the
    new state (so no cross-thread NiceGUI calls are needed here — same
    pattern as ProcessManager's `on_state_change` callback: mutate
    state on the worker, let the polling tick on the asyncio loop
    handle the UI refresh).

    Sequencing matters: UpdateChecker.check() reads
    `version_checker.cached_version.version` (libs/update_checker.py:53),
    so the version check MUST complete first or the update check will
    return an empty UpdateStatus with `error="Local version unavailable"`.
    """
    if state.version_checker is None or state.update_checker is None:
        logger.warning("version/update checkers not wired; skipping checks")
        return
    if not state.binary_ready or state.binary_path is None:
        logger.info("binary not ready; skipping version+update checks")
        return

    loop = asyncio.get_event_loop()

    # ---- Version check ----
    # VersionChecker.get_version() takes no path arg; binary_path must be
    # set on the instance first (libs/version_checker.py:51-53).
    state.version_checker.set_binary_path(state.binary_path)
    try:
        binary_version = await loop.run_in_executor(
            None, state.version_checker.get_version
        )
    except Exception as e:
        logger.error(f"version check raised: {e}", exc_info=True)
        binary_version = None

    if binary_version is not None and binary_version.version:
        state.binary_version = binary_version.display_string
        logger.info(f"version check ok: {state.binary_version}")
    else:
        logger.warning("version check returned no version string")

    # ---- Update check ----
    # Depends on cached_version being populated above. Even if the
    # version check failed, attempt the update check — UpdateStatus
    # will just carry a populated `error` field that the banner
    # condition (update_available) will treat as no-update.
    try:
        update_status = await loop.run_in_executor(
            None, state.update_checker.check
        )
    except Exception as e:
        logger.error(f"update check raised: {e}", exc_info=True)
        update_status = None

    if update_status is not None:
        state.update_status = update_status
        if update_status.update_available:
            logger.info(
                f"update available: {update_status.local_version} -> "
                f"{update_status.remote_version}"
            )
        elif update_status.error:
            logger.warning(f"update check error: {update_status.error}")
        else:
            logger.info(
                f"up to date: {update_status.local_version} "
                f">= {update_status.remote_version}"
            )


# ---- NiceGUI page route -------------------------------------------------

ui.add_head_html(_GLOBAL_CSS, shared=True)


@ui.page("/")
def index() -> None:
    """Render the dashboard for each browser connection."""
    ui.dark_mode().enable()
    build_dashboard()


@ui.page("/settings")
def settings_route(focus: str = "") -> None:
    """Render the full settings page.

    Optional `?focus=<section>.<field>` query param: after the page
    renders, scrolls to the named section and briefly flashes the
    named field. Used by the Storage-row chevron in the status card
    to land users directly on `advanced.data_dir`.
    """
    ui.dark_mode().enable()
    build_settings_page(focus=focus)


# ---- JSON API endpoint ---------------------------------------------------
# NiceGUI exposes the underlying FastAPI `app`, so we can register a plain
# REST route alongside the @ui.page UI routes. This mirrors the dashboard's
# visible data as machine-readable JSON for scripts / monitoring.
#
# GET /api/status — returns everything the dashboard shows. Same security
# posture as the UI (no auth; reachable from anything on 10.0.0.0/24).


@app.get("/api/status")
def api_status() -> Dict[str, Any]:
    """JSON mirror of the dashboard. Snapshot at request time.

    Updated server-side every POLL_INTERVAL_SECS by the dashboard's
    polling tick; clients see whatever was in `state` when the GET landed.
    """
    # Config-derived flag — authoritative, no heuristic.
    restricted_rpc = config.getboolean("rpc", "restricted", fallback=False)

    # System status block (everything in the status card).
    system_status: Dict[str, Any] = {
        "architecture": state.arch_name,
        "architecture_supported": state.arch_supported,
        "device_ip": state.device_ip,
        "binary_path": str(state.binary_path) if state.binary_path else None,
        "binary_ready": state.binary_ready,
        "binary_version": state.binary_version,
        "storage_path": state.storage_path,
        "storage_free_gib": round(state.storage_free_gib, 3),
        "storage_ok": state.storage_ok,
        "state": state.node_state,
        "process_owned": state.process_owned,
        "external_node_running": state.external_node_running,
        # external_node_busy: pgrep finds monerod but RPC times out —
        # usually means the daemon is busy syncing. When True, the
        # `sync_blocks_left` and `sync_eta_minutes` fields below are
        # best-effort parses from monerod's log (may be None if not
        # available); otherwise both are None.
        "external_node_busy": state.external_node_busy,
        "sync_blocks_left": state.sync_blocks_left,
        "sync_eta_minutes": state.sync_eta_minutes,
        "node_is_running": state.node_is_running,
    }

    # Update banner block (None when no check has run or no update).
    # Mirrors the UI banner: includes the SHA256 (`remote_hash`) and the
    # constructed download URL so script consumers don't have to know
    # the downloads.getmonero.org URL pattern themselves.
    update_status_block: Any = None
    if state.update_status is not None:
        remote_version = getattr(state.update_status, "remote_version", None)
        download_url = (
            construct_download_url(state.arch_name, remote_version)
            if remote_version
            else None
        )
        update_status_block = {
            "update_available": getattr(state.update_status, "update_available", False),
            "local_version": getattr(state.update_status, "local_version", None),
            "remote_version": remote_version,
            "remote_hash": getattr(state.update_status, "remote_hash", None) or None,
            "download_url": download_url,
        }

    # Node stats block (None when poller hasn't returned a result yet).
    node_stats_block: Any = None
    if state.last_stats is not None:
        s = state.last_stats
        # asdict() gives a flat dict of all NodeStats fields; we shape
        # it into the same sections the UI uses for clarity.
        target_h = getattr(s, "target_height", 0) or 0
        progress = (
            (s.height / target_h) if (target_h > 0 and s.height <= target_h)
            else 1.0 if s.synchronized
            else 0.0
        )
        node_stats_block = {
            "nettype": s.nettype,
            "sync": {
                "synchronized": s.synchronized,
                "height": s.height,
                "target_height": target_h,
                "progress_fraction": round(progress, 6),
                "busy_syncing": s.busy_syncing,
            },
            "overview": {
                "connections_total": s.incoming_connections + s.outgoing_connections,
                "connections_incoming": s.incoming_connections,
                "connections_outgoing": s.outgoing_connections,
                "block_height": s.height,
                "free_space_gib": round(state.storage_free_gib, 3),
            },
            "network": {
                "hashrate": s.hashrate,
                "difficulty": s.difficulty,
                "peerlist_white": s.white_peerlist_size,
                "peerlist_grey": s.grey_peerlist_size,
                "peerlist_total": s.white_peerlist_size + s.grey_peerlist_size,
            },
            "blockchain": {
                "tx_count": s.tx_count,
                "tx_pool_size": s.tx_pool_size,
                "block_reward_atomic": s.block_reward,
                "fee_estimate_atomic": s.fee_estimate,
                "database_size_bytes": s.database_size,
            },
            "resources": {
                "bytes_in_mib": round(s.bytes_in_mib, 3),
                "bytes_out_mib": round(s.bytes_out_mib, 3),
            },
            # True if monerod is running with --restricted-rpc. When True,
            # several fields above will be 0 (connections, peerlists,
            # bandwidth) because monerod redacts them at the RPC layer —
            # NOT because the values are actually zero.
            "restricted_rpc": restricted_rpc,
            "status": s.status,
        }

    return {
        "system_status": system_status,
        "update_status": update_status_block,
        "node_stats": node_stats_block,
        "polling": {
            "last_poll_time": state.last_poll_time,
            "last_poll_error": state.last_poll_error,
            "poll_interval_secs": 10,
        },
    }


# ---- Console-script entry ------------------------------------------------


def main() -> None:
    """Console-script entry. Registers startup hook and runs the server."""
    # initialize() runs first (sync): config, arch, binary, storage,
    # services, external probe, auto-start.
    app.on_startup(initialize)
    # Then the async chain: version + update checks. Registered as a
    # separate startup hook so it runs *after* initialize() has wired
    # state.version_checker / state.update_checker. NiceGUI awaits each
    # hook in registration order on the asyncio loop.
    app.on_startup(_kick_off_version_and_update_checks)
    ui.run(
        host=WEB_HOST,
        port=WEB_PORT,
        title=WEB_TITLE,
        dark=True,
        reload=False,
        show=False,
    )


if __name__ == "__main__":
    main()
