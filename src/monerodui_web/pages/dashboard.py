"""Dashboard page (`/`) — the main view.

Layout (top to bottom):
  - Header row: title + gear icon (gear navigates to `/settings`).
  - Scrollable body: status card + node-stats card.
  - Page-level footnote explaining the `*` markers in the node-stats
    card (Connections / Known Peers / Bandwidth are redacted under
    monerod's `--restricted-rpc` mode).
  - Footer: Start / Stop button (tri-state — owned / external / stopped).

Polling:
  - A NiceGUI `ui.timer(POLL_INTERVAL_SECS, _poll_stats_tick)` runs per
    browser connection. The first tick fires after 1 s (matching the
    Kivy `Clock.schedule_once(poll, 1)` from main.py:1205), subsequent
    ticks every 10 s.
  - The poll itself runs in a thread executor because
    `NodeStatsPoller.poll()` is synchronous and may block up to 30 s.
  - On each tick we ALSO check whether the daemon we (might have)
    spawned is still alive — see external-detection logic in
    `_apply_poll_result()`.

Configuration Variables
-----------------------
    POLL_INTERVAL_SECS   = 10   # matches Kivy main.py:1206
    FIRST_POLL_DELAY_SECS = 1   # matches Kivy main.py:1205
"""

from __future__ import annotations

import asyncio
import logging
import re
import socket
import time
from pathlib import Path
from typing import Optional

from nicegui import ui

from monerodui_web.components import build_node_stats_card, build_status_card
from monerodui_web.core import config, state
from monerodui_web.core.process_adapter import discover_external_monerod_pid
from monerodui.libs import NodeStats
from monerodui.libs.process_manager import ProcessState

logger = logging.getLogger(__name__)


# --- Configuration Variables ---------------------------------------------
POLL_INTERVAL_SECS: int = 10
FIRST_POLL_DELAY_SECS: float = 1.0
# --------------------------------------------------------------------------


def build_dashboard() -> None:
    """Build the dashboard UI inside the active NiceGUI page context."""
    # M4: low-storage warning toast. Fires once across the server's
    # lifetime (state.storage_warning_shown is the latch). We deliver
    # it from here rather than from main.initialize() because ui.notify
    # is only valid inside a NiceGUI client context — calling it from
    # an `app.on_startup` hook is a no-op (no connected client to push
    # to).
    if not state.storage_ok and not state.storage_warning_shown:
        try:
            min_free_gib = float(
                config.get("storage", "min_free_gib", fallback="10.0")
            )
        except ValueError:
            min_free_gib = 10.0
        path = state.storage_path or "(not configured)"
        ui.notify(
            f"Low storage: {path} has {state.storage_free_gib:.1f} GiB "
            f"free, below {min_free_gib:.0f} GiB threshold.",
            type="warning",
            timeout=10000,
        )
        state.storage_warning_shown = True

    # Page-level full-height column with dark body bg.
    with ui.column().classes("w-full").style(
        "max-width: 900px; margin: 0 auto; padding: 16px; gap: 16px;"
    ):
        # ---- Header ----
        with ui.row().classes("items-center w-full no-wrap").style("gap: 8px;"):
            ui.label("monerod UI").style(
                "color: #ff6600; font-size: 24px; font-weight: 700;"
            )
            ui.space()
            ui.button(
                icon="settings",
                on_click=lambda: ui.navigate.to("/settings"),
            ).props("flat round color=white").tooltip("Settings")

        # ---- Scrollable body ----
        with ui.scroll_area().classes("w-full").style(
            "height: calc(100vh - 240px);"
        ):
            with ui.column().classes("w-full").style("gap: 16px;"):
                build_status_card()
                build_node_stats_card()

        # ---- Restricted-RPC footnote (page-level, always shown) ----
        # Sits outside the cards so the explanation for any "*" markers
        # in the Node Statistics card is visible regardless of scroll
        # position. Subtle dim italic; negative margin-top pulls it up
        # against the bottom of the cards (the parent column has
        # gap: 16px between children, which we counteract here so the
        # footnote visually attaches to the box above it).
        ui.label(
            "* Connections, Known Peers, and Bandwidth are redacted by "
            "monerod's --restricted-rpc mode. The daemon still has that "
            "data; it just intentionally doesn't share it over RPC."
        ).style(
            "color: #999999; font-size: 10px; font-style: italic; "
            "text-align: center; padding: 0 16px; margin-top: -12px;"
        )

        # ---- Footer: Start / Stop button (tri-state) ----
        with ui.row().classes("items-center w-full justify-center").style(
            "padding-top: 8px;"
        ):
            build_start_stop_button()

    # ---- Polling timer ----
    # First poll immediately (1s delay, matches Kivy main.py:1205) so
    # the user doesn't stare at "node not running" for 10 s.
    ui.timer(FIRST_POLL_DELAY_SECS, _poll_stats_tick, once=True)
    ui.timer(POLL_INTERVAL_SECS, _poll_stats_tick)


# ---- Start / Stop button -------------------------------------------------


@ui.refreshable
def build_start_stop_button() -> None:
    """Tri-state Start/Stop. Refresh after state changes."""
    # Hide the button entirely when an external monerod is syncing —
    # nothing the user can do here (Stop is a no-op on processes we
    # didn't spawn, Start would just collide with the live daemon).
    # The status card already shows "Running (syncing — ~Xm)" so the
    # state is visible without a useless greyed-out button.
    if state.external_node_busy and not state.process_owned:
        return

    if state.process_owned:
        ui.button(
            "Stop",
            icon="stop_circle",
            on_click=_on_stop_click,
        ).props("color=orange unelevated")
    elif state.external_node_running:
        # External monerod with responsive RPC — show greyed-out Stop
        # with a tooltip explaining why it's disabled.
        btn = ui.button(
            "Stop (external)",
            icon="stop_circle",
        ).props("color=grey unelevated")
        btn.disable()
        btn.tooltip(
            "monerod was not spawned by monerodui — stop it from "
            "wherever it was launched (e.g. `screen -r monerod` then "
            "Ctrl-C if you started it that way, or `kill <pid>`)."
        )
    else:
        # Stopped — show Start. Disabled if prerequisites missing.
        can_start = (
            state.binary_ready
            and state.binary_path is not None
            and state.storage_path is not None
            and state.process_manager is not None
        )
        btn = ui.button(
            "Start",
            icon="play_circle",
            on_click=_on_start_click if can_start else None,
        ).props("color=orange unelevated")
        if not can_start:
            btn.disable()
            reason = "Cannot start: "
            if not state.binary_ready:
                reason += "binary not ready. "
            elif not state.storage_path:
                reason += "data dir not configured. "
            elif state.process_manager is None:
                reason += "process manager not initialized. "
            btn.tooltip(reason.strip())


async def _on_start_click() -> None:
    """Configure + start monerod via ProcessManager."""
    pm = state.process_manager
    if pm is None:
        ui.notify("Process manager not initialized", type="negative")
        return
    if state.binary_path is None:
        ui.notify("monerod binary not resolved", type="negative")
        return

    data_dir = config.get("advanced", "data_dir", fallback="")
    if not data_dir:
        ui.notify("data_dir is not configured", type="negative")
        return

    # Pre-check: refuse to start if the RPC port is already bound. This
    # prevents the silent-crash UX where monerod spawns, fails to bind
    # RPC within ~1s, and the UI just blips back to Stopped with an
    # opaque last_poll_error. Common case: user's external monerod is
    # already holding the port.
    rpc_ip = config.get("rpc", "bind_ip", fallback="127.0.0.1")
    try:
        rpc_port = int(config.get("rpc", "bind_port", fallback="18081"))
    except ValueError:
        rpc_port = 18081
    if _port_in_use(rpc_ip, rpc_port):
        ui.notify(
            f"Port {rpc_ip}:{rpc_port} is already in use — "
            f"stop the existing daemon first (e.g. `screen -r monerod` "
            f"+ Ctrl-C, or `kill <pid>`).",
            type="negative",
            timeout=10000,
        )
        return

    ui.notify("Starting monerod...", type="info")

    def _do_start() -> bool:
        try:
            extra_args = config.get_extra_args()
            from pathlib import Path as _P
            pm.configure(
                binary_path=state.binary_path,
                working_dir=_P(data_dir),
                extra_args=extra_args,
                on_state_change=_on_process_state_change,
            )
            return pm.start()
        except Exception as e:
            logger.error(f"start failed: {e}", exc_info=True)
            state.last_error = str(e)
            return False

    loop = asyncio.get_event_loop()
    ok = await loop.run_in_executor(None, _do_start)

    if ok:
        # ProcessManager._monitor() thread will fire _on_process_state_change
        # when the daemon exits, flipping process_owned back to False.
        state.process_owned = True
        state.node_state = "Running"
        ui.notify("monerod started", type="positive")
    else:
        err = pm.last_error or state.last_error or "unknown"
        ui.notify(f"Start failed: {err}", type="negative")

    build_start_stop_button.refresh()
    build_status_card.refresh()
    # Trigger an immediate poll so stats appear ASAP.
    await _poll_stats_tick()


async def _on_stop_click() -> None:
    pm = state.process_manager
    if pm is None:
        ui.notify("Process manager not initialized", type="negative")
        return
    if not state.process_owned:
        ui.notify("Cannot stop a process we didn't start", type="warning")
        return

    ui.notify("Stopping monerod...", type="info")
    loop = asyncio.get_event_loop()
    ok = await loop.run_in_executor(None, pm.stop)
    if ok:
        state.process_owned = False
        state.node_state = "Stopped"
        state.last_stats = None
        ui.notify("monerod stopped", type="positive")
    else:
        err = pm.last_error or "unknown"
        ui.notify(f"Stop failed: {err}", type="negative")

    build_start_stop_button.refresh()
    build_status_card.refresh()
    build_node_stats_card.refresh()


def _on_process_state_change(ps: ProcessState) -> None:
    """Adapter callback. Runs in the watcher thread — no UI calls here.

    We just mutate AppState; the next polling tick (on the asyncio loop)
    will pick up the change and call .refresh() on the components. This
    avoids cross-thread NiceGUI calls — refreshable components can only
    be safely refreshed from the asyncio loop, not from arbitrary
    background threads spawned by ProcessManager.
    """
    logger.info(f"process state change: {ps.name}")
    if ps == ProcessState.RUNNING:
        state.process_owned = True
        state.node_state = "Running"
    elif ps in (ProcessState.STOPPED, ProcessState.ERROR):
        state.process_owned = False
        state.node_state = "Stopped" if ps == ProcessState.STOPPED else "Error"


# ---- monerod log sync-progress parser -----------------------------------

# Matches lines like:
#   Synced 3683092/3683298 (99%, 206 left, 16% of total synced, estimated 28.0 minutes left)
# monerod writes one of these to bitmonero.log every ~2-3 min during catch-up.
_SYNC_LINE_RE = re.compile(
    r"Synced (\d+)/(\d+)\s+\(\d+%,\s+(\d+) left,.+estimated\s+([\d.]+)\s+minutes left"
)


def _parse_latest_sync_progress(log_path: Path) -> Optional[dict]:
    """Tail the last ~64 KB of monerod's log and return the most recent
    sync-progress info (blocks remaining + ETA minutes). Returns None if
    the log is unreadable or contains no sync line in the tail window.

    Used only when external_node_busy is True (i.e. RPC is unresponsive
    and we need an alternate source for sync status). Cheap — bounded
    read + regex over a small window.
    """
    try:
        with open(log_path, "rb") as f:
            f.seek(0, 2)  # end
            size = f.tell()
            offset = max(0, size - 65536)
            f.seek(offset)
            tail = f.read().decode("utf-8", errors="replace")
    except OSError:
        return None

    matches = list(_SYNC_LINE_RE.finditer(tail))
    if not matches:
        return None
    m = matches[-1]
    return {
        "blocks_left": int(m.group(3)),
        "eta_minutes": float(m.group(4)),
    }


# ---- Port pre-check helper ----------------------------------------------


def _port_in_use(host: str, port: int) -> bool:
    """True if (host, port) is already bound by another process.

    Tries to bind a fresh socket; if it fails the port is taken. For
    `0.0.0.0` we pass empty string (Linux convention for "all interfaces").
    """
    bind_host = "" if host in ("0.0.0.0", "::") else host
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((bind_host, port))
            return False
        except OSError:
            return True


# ---- Polling -------------------------------------------------------------


async def _poll_stats_tick() -> None:
    """ui.timer callback. Poll node + reconcile owned/external flags."""
    poller = state.node_stats_poller
    if poller is None:
        # initialize() hasn't finished yet — first-tick can race startup.
        logger.info("poll tick fired but poller not yet wired")
        return

    loop = asyncio.get_event_loop()
    result: Optional[NodeStats] = None
    err: Optional[str] = None
    try:
        result = await loop.run_in_executor(None, poller.poll)
    except Exception as e:
        err = str(e)
        logger.error(f"poll failed: {e}", exc_info=True)

    _apply_poll_result(result, err)

    build_status_card.refresh()
    build_node_stats_card.refresh()
    build_start_stop_button.refresh()


def _apply_poll_result(result: Optional[NodeStats], err: Optional[str]) -> None:
    """Reconcile poll result with process_owned / external_node_running.

    Truth table:
      poll succeeded (status != offline)  AND we own a live pid    -> owned
      poll succeeded                      AND we DON'T own a pid   -> external
      poll failed/offline                 AND we own a live pid    -> owned but RPC down (rare)
      poll failed/offline                 AND we DON'T own a pid   -> stopped
    """
    now = time.time()
    pm = state.process_manager

    rpc_reachable = (
        result is not None and result.status != "offline"
    )
    we_have_live_pid = bool(pm is not None and pm.is_running)

    if rpc_reachable:
        state.last_stats = result
        state.last_poll_time = now
        state.last_poll_error = None
        # Any RPC success clears the busy/syncing flag and its enriched
        # fields — the daemon is responding, no longer "alive but
        # unresponsive".
        state.external_node_busy = False
        state.sync_blocks_left = None
        state.sync_eta_minutes = None
        if we_have_live_pid:
            state.process_owned = True
            state.external_node_running = False
            state.node_state = "Running"
        else:
            state.process_owned = False
            state.external_node_running = True
            state.node_state = "Running (external)"
    else:
        # No RPC. If we still own a pid, the daemon may be alive but
        # not yet accepting RPC (startup) — keep state but stash error.
        state.last_poll_error = err or (
            result.status if result is not None else "no response"
        )
        if we_have_live_pid:
            state.process_owned = True
            state.external_node_running = False
            state.external_node_busy = False
            state.sync_blocks_left = None
            state.sync_eta_minutes = None
            # Keep node_state "Running" so the UI doesn't flicker.
            # last_stats is stale but the offline banner only triggers
            # when last_stats is None — so leave it.
        else:
            state.process_owned = False
            state.external_node_running = False
            # No owned process AND no RPC. Use pgrep to disambiguate:
            #   - pgrep finds monerod → daemon is alive but RPC is
            #     unresponsive (almost always "busy syncing after a
            #     downtime"; monerod deprioritizes RPC during catch-up).
            #     Surface as "Running (syncing)" so the user knows
            #     it's transient, not a real outage.
            #   - pgrep finds nothing → truly stopped.
            ext_pid = discover_external_monerod_pid()
            if ext_pid is not None:
                state.external_node_busy = True
                state.node_state = "Running (syncing)"
                # Best-effort: parse the latest sync line from
                # monerod's log to enrich the label with an ETA. RPC
                # is unresponsive during sync, so the log is the only
                # path to this info while we're in the busy state.
                data_dir = config.get("advanced", "data_dir", fallback="")
                info = None
                if data_dir:
                    info = _parse_latest_sync_progress(
                        Path(data_dir) / "bitmonero.log"
                    )
                if info is not None:
                    state.sync_blocks_left = info["blocks_left"]
                    state.sync_eta_minutes = info["eta_minutes"]
                else:
                    state.sync_blocks_left = None
                    state.sync_eta_minutes = None
            else:
                state.external_node_busy = False
                state.sync_blocks_left = None
                state.sync_eta_minutes = None
                state.last_stats = None
                state.node_state = "Stopped"
