"""Status card — the system-status panel.

Mirrors the Kivy `StatusCard` (src/monerodui/components/status_card.py
+ src/monerodui/ui/components/status_card.kv). Five rows:
Architecture, Device IP, Binary, Storage, State. Color coding follows
the Kivy theme: orange #ff6600 for OK, theme error red for problems.

Live state-text updates drive off `AppState` mutated by the polling
tick in dashboard.py; call `build_status_card.refresh()` to re-render.
Start/Stop button lives separately in the dashboard footer (not in
this card). Storage row's chevron always navigates to `/settings` so
the user can change `advanced.data_dir`.

No deployment-specific Configuration Variables in this file.
"""

from __future__ import annotations

from nicegui import ui

from monerodui_web.core import state

# Color palette — matches the Kivy theme.
OK_COLOR = "#ff6600"        # orange primary (Kivy [1, 0.4, 0, 1])
ERR_COLOR = "#cf6679"       # Material dark error
DIM_COLOR = "#999999"        # row labels (Kivy [0.6, 0.6, 0.6, 1])
TEXT_COLOR = "#ffffff"
SUMMARY_DIM = "#b3b3b3"


def _status_row(
    icon: str,
    label: str,
    value: str,
    is_ok: bool,
    *,
    trailing_icon: str | None = None,
    trailing_disabled: bool = False,
    trailing_on_click=None,
) -> None:
    """Render one Architecture/IP/Binary/Storage/State row."""
    color = OK_COLOR if is_ok else ERR_COLOR
    with ui.row().classes("items-center w-full no-wrap").style(
        "padding: 8px 0; gap: 12px;"
    ):
        ui.icon(icon).style(f"color: {color}; font-size: 24px;")
        ui.label(label).style(
            f"color: {DIM_COLOR}; width: 40%; "
            "overflow: hidden; text-overflow: ellipsis; white-space: nowrap;"
        )
        ui.label(value).style(
            f"color: {TEXT_COLOR}; font-weight: 600; flex: 1; "
            "overflow: hidden; text-overflow: ellipsis; white-space: nowrap;"
        )
        if trailing_icon is not None:
            btn = ui.button(icon=trailing_icon, on_click=trailing_on_click).props(
                "flat round dense color=white"
            )
            if trailing_disabled:
                btn.disable()


@ui.refreshable
def build_status_card() -> None:
    """Build the status card from current `AppState`.

    Call `build_status_card.refresh()` from anywhere to re-render
    after `state` mutates (M2/M4).
    """
    # Card matches Kivy: black background, no border, outlined-look.
    with ui.card().classes("w-full").style(
        "background-color: #000000; border: 1px solid #1a1a1a; "
        "padding: 16px; border-radius: 8px;"
    ):
        # ---- Header ----
        with ui.row().classes("items-center w-full no-wrap").style("gap: 8px;"):
            ui.label("System Status").style(
                f"color: {TEXT_COLOR}; font-size: 18px; font-weight: 600;"
            )
            ui.space()
            # Right-aligned summary text: when running, show storage path;
            # when stopped, show "Stopped" so a collapsed card still has
            # state context in its header.
            if state.node_is_running:
                ui.label(
                    f"[ Running • {state.storage_path or '--'} ]"
                ).style(f"color: {SUMMARY_DIM}; font-size: 12px;")
            elif state.status_card_collapsed:
                ui.label("[ Stopped ]").style(
                    f"color: {SUMMARY_DIM}; font-size: 12px;"
                )
            # Collapse/expand toggle. Icon mirrors current state so the
            # user can predict what clicking will do.
            ui.button(
                icon=(
                    "expand_more" if state.status_card_collapsed
                    else "expand_less"
                ),
                on_click=_toggle_status_card_collapsed,
            ).props("flat round dense color=white")

        # Body — hidden when collapsed. The separator + rows are the
        # collapsible part; the header stays visible regardless.
        if state.status_card_collapsed:
            return

        ui.separator().style("background-color: #333333; margin: 8px 0;")

        # ---- Rows ----

        # 1. Architecture
        arch_ok = state.arch_supported
        arch_display = state.arch_name if arch_ok else f"{state.arch_name} (unsupported)"
        _status_row("memory", "Architecture", arch_display, arch_ok)

        # 2. Device IP (with copy button)
        ip_ok = state.device_ip not in ("Unknown", "No Ext Net", "")
        _status_row(
            "lan",
            "Device IP",
            state.device_ip,
            ip_ok,
            trailing_icon="content_copy",
            trailing_disabled=not ip_ok,
            trailing_on_click=(
                (lambda: _copy_to_clipboard(state.device_ip)) if ip_ok else None
            ),
        )

        # 3. Binary
        if state.binary_ready and state.binary_path:
            bin_display = "Ready"
        elif state.binary_path:
            bin_display = "Not Executable"
        else:
            bin_display = "Not Found"
        _status_row(
            "settings_applications",
            "Binary",
            bin_display,
            state.binary_ready,
        )

        # 4. Storage (clickable when node is stopped — picker lands in M3)
        if state.storage_ok and state.storage_path:
            storage_display = (
                f"{state.storage_path} ({state.storage_free_gib:.1f} GiB free)"
            )
        elif state.storage_path:
            storage_display = f"{state.storage_path} - low free space"
        else:
            storage_display = "Not configured"
        # Chevron always navigates to /settings (Advanced section, where
        # the data-dir picker lives). M3 ships a proper picker; changes
        # take effect on the next daemon restart. Always-clickable so the
        # affordance isn't a lie when a daemon happens to be running.
        _status_row(
            "storage",
            "Storage",
            storage_display,
            state.storage_ok,
            trailing_icon="chevron_right",
            trailing_disabled=False,
            # Land on the Advanced section with the data_dir input
            # briefly flashed — much more useful than dumping the user
            # at the top of the settings page. See settings_route() for
            # the focus query-param handling.
            trailing_on_click=lambda: ui.navigate.to(
                "/settings?focus=advanced.data_dir"
            ),
        )

        # 5. State — tri-state, distinguishes owned vs external monerod.
        # The Stop button in the dashboard footer keys off the same
        # process_owned / external_node_running flags.
        if state.process_owned:
            state_text = "Running"
            state_icon = "play_circle"
            state_ok = True
        elif state.external_node_running:
            state_text = "Running (external)"
            state_icon = "play_circle"
            state_ok = True
        elif state.external_node_busy:
            # External monerod is alive (pgrep found it) but its RPC is
            # unresponsive — usually means it's busy syncing. Not an
            # error state, so don't paint red. If we managed to parse
            # an ETA from monerod's log, append it to the label.
            if state.sync_eta_minutes is not None:
                blocks_part = (
                    f", {state.sync_blocks_left:,} blocks left"
                    if state.sync_blocks_left is not None else ""
                )
                state_text = (
                    f"Running (syncing — ~{state.sync_eta_minutes:.0f}m"
                    f"{blocks_part})"
                )
            else:
                state_text = "Running (syncing)"
            state_icon = "sync"
            state_ok = True
        else:
            state_text = "Stopped"
            state_icon = "stop_circle"
            state_ok = False
        _status_row(state_icon, "State", state_text, state_ok)


def _toggle_status_card_collapsed() -> None:
    """Flip the collapsed flag and re-render the card."""
    state.status_card_collapsed = not state.status_card_collapsed
    build_status_card.refresh()


def _copy_to_clipboard(text: str) -> None:
    """Copy `text` to the browser clipboard via JS."""
    # navigator.clipboard requires a secure context (localhost counts).
    js = (
        "navigator.clipboard && navigator.clipboard.writeText("
        f"{text!r}"
        ")"
    )
    ui.run_javascript(js)
    ui.notify(f"Copied: {text}", type="positive")
