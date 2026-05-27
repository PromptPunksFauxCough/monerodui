"""Shared mutable application state for the web UI.

All UI components read from the module-level `state` singleton via
NiceGUI `@ui.refreshable` functions; background tasks (process state
callbacks, stats poller) write to it. Mutation is plain attribute
assignment — no observers.

There are no deployment-specific Configuration Variables in this file;
all values are runtime-derived from config + system probes.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

# Imported from the existing libs package (which has zero Kivy deps).
# Importing the type here keeps `state.last_stats` correctly typed even
# though M1 never sets it (poll is M2).
from monerodui.libs import NodeStats  # noqa: F401  (re-exported via type hint)


@dataclass
class AppState:
    """Singleton holding all UI-observable state.

    Lifecycle of each field:
      - process_owned / external_node_running / node_state / last_stats /
        last_poll_time / last_poll_error:
            written by the stats poller / process_adapter (M2).
      - binary_version / update_status:
            written by VersionChecker / UpdateChecker (M4). M1/M2 leave
            them at defaults (M2 renders banners conditionally).
      - arch_*, binary_*, storage_*, device_ip:
            populated once at startup by `main.initialize()` (M1).

    `node_is_running` is a *derived* property: true if EITHER we own the
    process OR an external monerod is reachable via RPC. Use the two
    underlying flags to drive UI affordances (e.g. disable Stop when
    external-only).
    """

    # ---- Node lifecycle (M2) ----
    # Did *we* spawn this monerod? Drives whether Stop is enabled.
    process_owned: bool = False
    # Is there an RPC-reachable monerod we did NOT spawn? Surfaces as
    # "Running (external)" in the UI; Stop is disabled in this case
    # because killing a process we didn't start is out of scope.
    external_node_running: bool = False
    # Human-readable state string for status_card State row.
    node_state: str = "Stopped"
    # Last completed poll result (or None if never polled / offline).
    last_stats: Optional[NodeStats] = None
    # Timestamp (time.time()) of the most recent successful poll —
    # used for "staleness" display in the UI.
    last_poll_time: Optional[float] = None
    # Latest poll error message (or None if last poll succeeded). Shown
    # in the offline banner so the user can see *why* the node looks
    # offline (connection refused vs. timeout vs. RPC error).
    last_poll_error: Optional[str] = None
    # Generic "last error" (start-failure message etc.) — populated by
    # process_adapter on failed start/stop.
    last_error: Optional[str] = None

    # ---- Live service references (M2 populates from main.initialize) ----
    # Typed as Any to avoid an import cycle; concrete types are
    # monerodui.libs.ProcessManager, NodeStatsPoller, VersionChecker,
    # UpdateChecker.
    process_manager: Optional[Any] = None
    node_stats_poller: Optional[Any] = None
    version_checker: Optional[Any] = None
    update_checker: Optional[Any] = None

    # ---- Binary metadata (M4 writes, M1/M2 leave defaults) ----
    binary_version: Optional[str] = None
    update_status: Optional[Any] = None  # UpdateStatus from libs.update_checker

    # ---- Arch / binary readiness (M1 populates) ----
    arch_supported: bool = False
    arch_name: str = "Unknown"
    binary_path: Optional[Path] = None
    binary_ready: bool = False

    # ---- Storage check (M1 populates) ----
    storage_path: Optional[str] = None
    storage_free_gib: float = 0.0
    storage_ok: bool = False
    # M4: one-shot flag so the low-storage warning toast fires exactly
    # once across the server's lifetime — first browser to connect to
    # the dashboard sees it; subsequent reloads / tabs do not. Reset
    # to False if you want it to re-fire (e.g. after a config change
    # that lowers free space).
    storage_warning_shown: bool = False

    # ---- Network (M1 populates) ----
    device_ip: str = "Unknown"

    # ---- UI toggles (M5) ----
    # True = status card body hidden, only header + summary shown.
    # Toggled by the chevron button in the status card header.
    status_card_collapsed: bool = False
    # User-dismissed banners. Each banner has an "X" button that flips
    # the corresponding flag and refreshes the stats card. Flags are
    # process-lifetime (reset by `service monerodui-web restart` since
    # AppState is re-instantiated at server startup); they intentionally
    # don't persist across restarts.
    version_banner_dismissed: bool = False
    update_banner_dismissed: bool = False

    # ---- Derived ----

    @property
    def node_is_running(self) -> bool:
        """True if a node is responding — owned OR external."""
        return self.process_owned or self.external_node_running


# Module-level singleton — imported as `from monerodui_web.core import state`.
state: AppState = AppState()
