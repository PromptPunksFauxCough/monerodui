"""Node statistics card — live view of monerod's RPC-reported state.

Mirrors `src/monerodui/components/node_stats_card.py` +
`src/monerodui/ui/components/node_stats_card.kv`. Driven by
`AppState.last_stats` (a `monerodui.libs.NodeStats` dataclass).

Sections (top to bottom):
  1. Header row: title + (right-aligned) network-type tag.
  2. Version banner (M4 populates; rendered conditionally).
  3. Update banner (M4 populates; rendered conditionally).
  4. Offline message (when last_stats is None / status == 'offline').
  5. Sync status line + linear progress bar.
  6. OVERVIEW grid (3 cols): Connections, Block Height, Free Space.
  7. NETWORK grid (3 cols): Hashrate, Difficulty, Known Peers.
  8. BLOCKCHAIN grid (5 cols): Total TXs, TX Pool, Block Reward,
     Est. Fee, Database Size.
  9. RESOURCES grid (2 cols): Bandwidth in, Bandwidth out.

Color logic mirrors the Kivy KV's `is_ok` flag — orange #ff6600 for
healthy, error red for unhealthy/zero. See `_stat_cell()`.

No deployment-specific Configuration Variables.
"""

from __future__ import annotations

from typing import Optional

from nicegui import ui

from monerodui.libs import NodeStats
from monerodui_web.core import state


# Color palette — matches Kivy theme & status_card.py.
OK_COLOR = "#ff6600"      # orange primary (Kivy [1, 0.4, 0, 1])
ERR_COLOR = "#cf6679"     # Material dark error
DIM_COLOR = "#999999"     # row labels (Kivy [0.6, 0.6, 0.6, 1])
TEXT_COLOR = "#ffffff"
HEADER_COLOR = "#ff6600"  # SECTION headers
BANNER_BG_VERSION = "#262626"
BANNER_BG_UPDATE = "rgba(204, 51, 51, 0.20)"
BANNER_BG_OFFLINE = "#1a1a1a"


# ---- Humanize helpers (module-private) -----------------------------------


def _fmt_hashrate(hps: int) -> str:
    """Bytes-style scaling for hash/s. Mirrors NodeStats.hashrate_display."""
    if hps >= 1_000_000_000:
        return f"{hps / 1_000_000_000:.2f} GH/s"
    if hps >= 1_000_000:
        return f"{hps / 1_000_000:.2f} MH/s"
    if hps >= 1_000:
        return f"{hps / 1_000:.2f} KH/s"
    return f"{hps} H/s"


def _fmt_difficulty(d: int) -> str:
    """Mirrors NodeStats.difficulty_display."""
    if d >= 1_000_000_000_000:
        return f"{d / 1_000_000_000_000:.2f} TH"
    if d >= 1_000_000_000:
        return f"{d / 1_000_000_000:.2f} GH"
    if d >= 1_000_000:
        return f"{d / 1_000_000:.2f} MH"
    return f"{d:,}"


def _fmt_bytes_gib(n: int) -> str:
    """Bytes -> GiB with 2 decimals."""
    return f"{n / (1024 ** 3):.2f} GiB"


def _fmt_atomic_xmr(atomic: int, decimals: int = 4) -> str:
    """Monero atomic units (1e-12 XMR) -> XMR string. Mirrors NodeStats."""
    if atomic == 0:
        return "--"
    xmr = atomic / 1_000_000_000_000
    if xmr < 0.0001:
        return f"{xmr:.8f}"
    return f"{xmr:.{decimals}f}"


# ---- Sub-builders --------------------------------------------------------


def _section_header(text: str) -> None:
    ui.label(text).style(
        f"color: {HEADER_COLOR}; font-size: 12px; font-weight: 700; "
        "letter-spacing: 1px; padding: 8px 0 4px 0;"
    )


def _stat_cell(value: str, label: str, is_ok: bool = True) -> None:
    """OVERVIEW grid cell: bold colored value + dim label below."""
    color = OK_COLOR if is_ok else ERR_COLOR
    with ui.column().classes("items-center").style(
        "gap: 2px; padding: 4px 8px; flex: 1;"
    ):
        ui.label(value).style(
            f"color: {color}; font-size: 18px; font-weight: 700; "
            "text-align: center;"
        )
        ui.label(label).style(
            f"color: {DIM_COLOR}; font-size: 11px; text-align: center;"
        )


def _small_stat_cell(value: str, label: str) -> None:
    """NETWORK/BLOCKCHAIN/RESOURCES grid cell: white value + dim label."""
    with ui.column().classes("items-center").style(
        "gap: 2px; padding: 4px 8px; flex: 1;"
    ):
        ui.label(value).style(
            f"color: {TEXT_COLOR}; font-size: 14px; font-weight: 600; "
            "text-align: center;"
        )
        ui.label(label).style(
            f"color: {DIM_COLOR}; font-size: 11px; text-align: center;"
        )


def _dismiss_version_banner() -> None:
    """Hide the version banner for the rest of this server process."""
    state.version_banner_dismissed = True
    build_node_stats_card.refresh()


def _dismiss_update_banner() -> None:
    """Hide the update banner for the rest of this server process."""
    state.update_banner_dismissed = True
    build_node_stats_card.refresh()


def _version_banner(version_text: str) -> None:
    """Top-of-card banner showing the local monerod binary version."""
    with ui.row().classes("items-center w-full no-wrap").style(
        f"background-color: {BANNER_BG_VERSION}; "
        "padding: 8px 12px; border-radius: 8px; gap: 8px;"
    ):
        ui.icon("info").style(f"color: {DIM_COLOR}; font-size: 18px;")
        ui.label(version_text).style(
            f"color: #e6e6e6; font-size: 13px;"
        )
        ui.space()
        ui.label("monerod").style(f"color: {DIM_COLOR}; font-size: 11px;")
        ui.button(
            icon="close", on_click=_dismiss_version_banner
        ).props("flat dense round size=sm color=white").tooltip(
            "Dismiss (returns on next service restart)"
        )


def _construct_download_url(arch: str, version: str) -> Optional[str]:
    """Build the canonical downloads.getmonero.org URL for this arch +
    version. Matches the URL monerod itself logs when an update is
    available (see bitmonero.log lines like "Version X.Y.Z of monero
    for linux-x64 is available: https://downloads.getmonero.org/...").

    Arch values come from `ArchDetector` ("amd64" / "arm64" / "armhf").
    Returns None for unrecognized arch — banner will hide the URL row.
    """
    # arch values from ArchDetector.detected_arch — see
    # src/monerodui/libs/arch_detector.py ARCH_MAP.
    platform_map = {
        "amd64": "linux-x64",
        "arm64": "linux-armv8",
        "arm32": "linux-armv7",
    }
    platform = platform_map.get(arch)
    if platform is None:
        return None
    return (
        f"https://downloads.getmonero.org/cli/"
        f"monero-{platform}-v{version}.tar.bz2"
    )


def _copy_to_clipboard(text: str, label: str) -> None:
    """Copy `text` to the browser clipboard and notify."""
    js = (
        "navigator.clipboard && navigator.clipboard.writeText("
        f"{text!r}"
        ")"
    )
    ui.run_javascript(js)
    ui.notify(f"{label} copied", type="positive")


def _update_banner(
    local: str,
    remote: str,
    remote_hash: str,
    download_url: Optional[str],
) -> None:
    """Banner shown when UpdateChecker reports an update is available.

    Includes:
      - Version delta ("Current: X.Y.Z --> Latest: A.B.C")
      - Download URL (clickable, opens in new tab) + copy button
      - SHA256 hash + copy button

    Mirrors the info monerod itself logs to bitmonero.log on update
    availability, so the user has everything they need to verify and
    install the new release without leaving the page.
    """
    with ui.row().classes("items-start w-full no-wrap").style(
        f"background-color: {BANNER_BG_UPDATE}; "
        "padding: 12px; border-radius: 8px; gap: 8px;"
    ):
        ui.icon("error").style(
            "color: #ff4d4d; font-size: 20px; margin-top: 2px;"
        )
        with ui.column().classes("w-full").style("gap: 4px;"):
            with ui.row().classes("items-center w-full no-wrap").style(
                "gap: 4px;"
            ):
                ui.label("Update Available").style(
                    "color: #ffcccc; font-size: 13px; font-weight: 700;"
                )
                ui.space()
                ui.button(
                    icon="close", on_click=_dismiss_update_banner
                ).props("flat dense round size=sm color=white").tooltip(
                    "Dismiss (returns on next service restart)"
                )
            ui.label(f"Current: {local}  -->  Latest: {remote}").style(
                "color: #ffcccc; font-size: 12px;"
            )
            if download_url:
                with ui.row().classes("items-center w-full no-wrap").style(
                    "gap: 6px; margin-top: 4px;"
                ):
                    ui.label("Download:").style(
                        "color: #ffaaaa; font-size: 11px; font-weight: 600; "
                        "min-width: 70px;"
                    )
                    ui.link(download_url, download_url, new_tab=True).style(
                        "color: #ffe066; font-size: 11px; "
                        "word-break: break-all; text-decoration: underline;"
                    )
                    ui.button(
                        icon="content_copy",
                        on_click=lambda u=download_url: _copy_to_clipboard(u, "URL"),
                    ).props("flat dense round size=sm color=white").tooltip(
                        "Copy URL"
                    )
            if remote_hash:
                with ui.row().classes("items-center w-full no-wrap").style(
                    "gap: 6px;"
                ):
                    ui.label("SHA256:").style(
                        "color: #ffaaaa; font-size: 11px; font-weight: 600; "
                        "min-width: 70px;"
                    )
                    ui.label(remote_hash).style(
                        "color: #ffe066; font-size: 11px; "
                        "font-family: monospace; word-break: break-all;"
                    )
                    ui.button(
                        icon="content_copy",
                        on_click=lambda h=remote_hash: _copy_to_clipboard(h, "SHA256"),
                    ).props("flat dense round size=sm color=white").tooltip(
                        "Copy hash"
                    )


def _offline_banner(error: Optional[str]) -> None:
    with ui.column().classes("items-center w-full").style(
        f"background-color: {BANNER_BG_OFFLINE}; padding: 24px; "
        "border-radius: 8px; gap: 4px;"
    ):
        ui.label("Node is not running").style(
            f"color: {DIM_COLOR}; font-size: 14px;"
        )
        if error:
            ui.label(f"Last poll: {error}").style(
                f"color: {DIM_COLOR}; font-size: 11px; font-style: italic;"
            )


def _sync_section(stats: NodeStats) -> None:
    """Sync status text + linear progress bar."""
    # Status text (mirror Kivy logic).
    if stats.synchronized:
        status_text = "Fully synchronized"
    elif stats.busy_syncing:
        status_text = (
            f"Syncing... {stats.height:,} / {stats.target_height:,} "
            f"({stats.sync_progress:.1f}%) — "
            f"{stats.blocks_remaining:,} blocks remaining"
        )
    else:
        status_text = "Waiting for sync..."

    with ui.column().classes("w-full").style("gap: 4px;"):
        ui.label(status_text).style(
            f"color: {DIM_COLOR}; font-size: 12px;"
        )
        # ui.linear_progress takes 0.0-1.0. NodeStats.sync_progress is 0-100.
        ui.linear_progress(
            value=stats.sync_progress / 100.0,
            show_value=False,
        ).props("color=orange instant-feedback").style("height: 16px;")


# ---- Main refreshable builder --------------------------------------------


@ui.refreshable
def build_node_stats_card() -> None:
    """Build the node-stats card from current `AppState`."""
    stats = state.last_stats
    is_offline = stats is None or stats.status == "offline"

    with ui.card().classes("w-full").style(
        "background-color: #000000; border: 1px solid #1a1a1a; "
        "padding: 16px; border-radius: 8px; gap: 12px;"
    ):
        # ---- Header row ----
        with ui.row().classes("items-center w-full no-wrap").style("gap: 8px;"):
            ui.label("Node Statistics").style(
                f"color: {TEXT_COLOR}; font-size: 18px; font-weight: 600;"
            )
            ui.space()
            if not is_offline and stats is not None:
                ui.label(stats.nettype.upper()).style(
                    f"color: {OK_COLOR}; font-size: 11px; font-weight: 700; "
                    "letter-spacing: 1px;"
                )

        ui.separator().style("background-color: #333333;")

        # ---- Version banner (M4 populates state.binary_version) ----
        # state.version_banner_dismissed is set when the user clicks the
        # banner's X — persists for the rest of this server process.
        if state.binary_version and not state.version_banner_dismissed:
            _version_banner(state.binary_version)

        # ---- Update banner (M4 populates state.update_status) ----
        # state.update_banner_dismissed gates this the same way.
        upd = state.update_status
        if (
            upd is not None
            and getattr(upd, "update_available", False)
            and not state.update_banner_dismissed
        ):
            local = getattr(upd, "local_version", None) or "?"
            remote = getattr(upd, "remote_version", None) or "?"
            remote_hash = getattr(upd, "remote_hash", "") or ""
            # Construct the same download URL monerod itself logs to
            # bitmonero.log when an update is available. Falls back to
            # None (hides the URL row) if arch is unrecognized.
            download_url = _construct_download_url(state.arch_name, remote)
            _update_banner(local, remote, remote_hash, download_url)

        # ---- Offline message OR live grids ----
        if is_offline:
            _offline_banner(state.last_poll_error)
            return

        assert stats is not None  # narrowed by is_offline check
        _sync_section(stats)

        # OVERVIEW (3 cols)
        _section_header("OVERVIEW")
        with ui.row().classes("w-full no-wrap").style("gap: 4px;"):
            # incoming_connections_count + outgoing_connections_count are
            # both redacted to 0 by --restricted-rpc. The daemon may have
            # plenty of real peers (verifiable via `lsof -iTCP:18080`);
            # show "*" so the UI is honest about not knowing rather than
            # claiming "0 peers" misleadingly. The footnote in
            # dashboard.py (between the scroll area and Start/Stop button)
            # explains the asterisk.
            if stats.total_connections == 0:
                conn_value = "*"
                conn_ok = True  # don't paint red — we just don't know
            else:
                conn_value = f"{stats.total_connections}"
                conn_ok = stats.total_connections > 0
            _stat_cell(conn_value, "Connections", is_ok=conn_ok)
            _stat_cell(
                f"{stats.height:,}",
                "Block Height",
                is_ok=stats.synchronized,
            )
            # Prefer state.storage_free_gib (set from os.statvfs at init)
            # over stats.free_space_gib — they should be close, but the
            # config-derived path is what the user is actually using.
            free_gib = (
                state.storage_free_gib
                if state.storage_free_gib > 0
                else stats.free_space_gib
            )
            _stat_cell(
                f"{free_gib:.1f} GiB",
                "Free Space",
                is_ok=free_gib > 1.0,
            )

        # NETWORK (3 cols)
        _section_header("NETWORK")
        with ui.row().classes("w-full no-wrap").style("gap: 4px;"):
            _small_stat_cell(_fmt_hashrate(stats.hashrate), "Hashrate")
            _small_stat_cell(_fmt_difficulty(stats.difficulty), "Difficulty")
            # white_peerlist_size + grey_peerlist_size both redacted to 0
            # under --restricted-rpc. Show "*" instead of misleading "0";
            # page-level footnote in dashboard.py explains.
            peers_total = stats.white_peerlist_size + stats.grey_peerlist_size
            peers_value = "*" if peers_total == 0 else f"{peers_total:,}"
            _small_stat_cell(peers_value, "Known Peers")

        # BLOCKCHAIN (5 cols)
        _section_header("BLOCKCHAIN")
        with ui.row().classes("w-full no-wrap").style("gap: 4px;"):
            _small_stat_cell(f"{stats.tx_count:,}", "Total TXs")
            _small_stat_cell(f"{stats.tx_pool_size:,}", "TX Pool")
            _small_stat_cell(_fmt_atomic_xmr(stats.block_reward), "Block Reward")
            _small_stat_cell(_fmt_atomic_xmr(stats.fee_estimate, 8), "Est. Fee (XMR)")
            _small_stat_cell(_fmt_bytes_gib(stats.database_size), "Database Size")

        # RESOURCES (2 cols)
        _section_header("RESOURCES")
        with ui.row().classes("w-full no-wrap").style("gap: 4px;"):
            # bytes_in_mib / bytes_out_mib are both 0 when --restricted-rpc
            # blocks GET /get_net_stats (returns 404; the poller swallows
            # the error and reports 0). Render "*" so the user knows the
            # data is unavailable, not literally zero; page-level footnote
            # in dashboard.py explains.
            if stats.bytes_in_mib == 0.0 and stats.bytes_out_mib == 0.0:
                bw_down_value = "*"
                bw_up_value = "*"
            else:
                bw_down_value = f"{stats.bytes_in_mib:.1f} MiB"
                bw_up_value = f"{stats.bytes_out_mib:.1f} MiB"
            _small_stat_cell(bw_down_value, "Bandwidth Down")
            _small_stat_cell(bw_up_value, "Bandwidth Up")
