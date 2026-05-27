# monerod UI — Web

A browser-accessible port of the [monerod UI](../../README.md) Kivy desktop app, built on **[NiceGUI](https://nicegui.io/)** 3.x (FastAPI + Quasar/Vue under the hood). The Kivy app keeps working unchanged; this is a parallel package that shares the same configuration, the same monerod-management library code, and the same on-disk INI file — only the UI layer is reimplemented.

If you already have the Kivy app installed and configured, the web UI picks up its settings automatically.

## Why a web UI?

- **Remote access**: control monerod from any device on your LAN — phones, tablets, other laptops, anything with a browser. The Kivy app only works on the machine running it.
- **No display required**: runs headless on a server or VPS. No X11, no Wayland, no GPU.
- **Same UX language**: dark theme, orange accents, same five status rows and stats grid as the Kivy desktop app. The layout is a 1:1 port, not a redesign.
- **Coexists with the desktop app**: both packages live under `src/`; both read and write the same `~/.config/monerodui/monerodui.ini`. Run whichever is convenient — just don't run both at the same time against the same daemon.

## Requirements

- **Linux** (Ubuntu 22.04+ or similar). Android is not a target for this package — the parent Kivy app at `src/monerodui/` is what gets bundled into the APK; `monerodui_web/` is in `source.exclude_dirs` in `buildozer.spec`.
- Python 3.10+.
- monerod binary somewhere on the system (see [Binary discovery](#binary-discovery) below).
- A browser. No special version needed — anything from the last few years works.

## Quick start

```bash
cd /path/to/monerodui

# One-time setup: create a venv and install with the [web] extra
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[web]"

# Run
monerodui-web
```

Open `http://127.0.0.1:8085` in a browser. That's it.

To stop the server: `Ctrl-C` in the terminal, or `kill <pid>`.

## Network access

By default the server binds to `0.0.0.0:8085`, meaning **anything on your LAN can reach it** (subject to your router/firewall). There is **no authentication** in v1 — anyone who can reach the URL can start/stop monerod and change its config.

That's safe if:
- Your LAN is trusted (your own devices only), AND
- Your router doesn't port-forward 8085 to the internet.

If either of those changes, put the UI behind a reverse proxy with auth (nginx basic auth, Caddy with basicauth, Tailscale, etc.) before exposing it further.

To restrict to localhost only, edit the `WEB_HOST` constant near the top of `main.py`:

```python
WEB_HOST: str = "127.0.0.1"   # was "0.0.0.0"
```

To change the port, edit `WEB_PORT` in the same block.

## Architecture

```
src/monerodui_web/
├── __init__.py            # Package marker
├── __main__.py            # Enables `python -m monerodui_web`
├── main.py                # NiceGUI entrypoint: ui.run(), startup hooks,
│                          # /api/status JSON endpoint, route registration
├── core/
│   ├── __init__.py        # Re-exports the `state` and `config` singletons
│   ├── app_state.py       # Single shared AppState dataclass (the
│   │                      # source of truth for everything the UI shows)
│   ├── config_manager.py  # ConfigManager: wraps configparser, port of
│   │                      # the Kivy _get_extra_args() (~270 lines that
│   │                      # translate INI → monerod CLI args)
│   └── process_adapter.py # discover_external_monerod_pid() helper
├── pages/
│   ├── __init__.py        # Re-exports build_dashboard, build_settings_page
│   ├── dashboard.py       # `/` route — status card + stats card +
│   │                      # Start/Stop button + polling loop
│   └── settings.py        # `/settings` route — 82-field settings form
│                          # mirroring the Kivy settings panel
└── components/
    ├── __init__.py
    ├── status_card.py     # Architecture / IP / Binary / Storage / State
    │                      # (collapsible)
    └── node_stats_card.py # Version + update banners, sync progress,
                           # OVERVIEW / NETWORK / BLOCKCHAIN / RESOURCES
```

### Shared with the Kivy app (read-only — never modify from here)

The web UI imports several modules from the Kivy package as pure libraries. None of these have Kivy dependencies:

- `monerodui.libs.arch_detector` — CPU architecture detection
- `monerodui.libs.process_manager` — monerod subprocess lifecycle
- `monerodui.libs.node_stats` — RPC poll → `NodeStats` dataclass
- `monerodui.libs.version_checker` — extracts version from `monerod --version`
- `monerodui.libs.update_checker` — checks DNS TXT for newer releases
- `monerodui.libs.network_info` — device IP detection
- `monerodui.settings.settings_schema.json` — source of truth for the 82 settings fields

### Why these design choices

- **Polling, not websockets, for node stats.** Every browser tab runs a `ui.timer(10s)` that hits monerod's RPC, stores the result in the shared `AppState`, and refreshes the `@ui.refreshable` components. Simpler than push, and 10s granularity matches what humans care about for blockchain stats.
- **One shared `AppState` singleton.** All pages and refreshable components read from `state` (`monerodui_web/core/app_state.py`). Background tasks write to it. No observers, no event bus — just plain attribute assignment plus `.refresh()` calls.
- **ProcessManager runs monerod directly, no `screen` wrapper.** The Kivy `ProcessManager` auto-appends `--log-file <data_dir>/monerod.log`, which gives the same observability as `screen -r monerod` (just `tail -f /root/.bitmonero/monerod.log`).
- **External-daemon detection.** If you're already running monerod outside the UI (e.g. in `screen`), the dashboard detects it via `pgrep -x monerod` plus an RPC poll, surfaces it as "Running (external)", and disables the Stop button (the UI never kills a process it didn't spawn).

## Configuration

The web UI shares **`~/.config/monerodui/monerodui.ini`** with the Kivy app. No conversion, no migration — the same file works for both.

If the file doesn't exist on first run, defaults are written. The web UI also backfills `advanced.data_dir = ~/.bitmonero` if empty, matching Monero's own default.

Settings can be edited two ways:
1. The web UI's **Settings** page (gear icon, top right) — full form for all 82 fields across 17 INI sections.
2. Hand-editing the INI file — useful for bulk changes or scripted setup.

Changes take effect on **next monerod restart**, not live (matches Kivy behavior).

### Binary discovery

The web UI looks for `monerod` in this order:

1. **`/root/monero/monerod`** (`PREFERRED_BINARY` in `main.py`). On the apollo dev machine this is a symlink the user maintains pointing at the current Monero release.
2. The Kivy `ArchDetector` search path (Briefcase-layout `desktop/binary/`, project root, app root).
3. `shutil.which('monerod')` — anything on `PATH`.

Edit `PREFERRED_BINARY` in `main.py` if your preferred location is different.

## JSON API: `/api/status`

Every field on the dashboard is also exposed as machine-readable JSON:

```bash
curl -sS http://127.0.0.1:8085/api/status
```

Returns a single snapshot at request time. The server's polling loop refreshes the underlying data every 10 seconds. Same security posture as the UI itself — no auth, reachable from anything on the LAN.

### Response shape

```json
{
  "system_status": {
    "architecture": "amd64",
    "architecture_supported": true,
    "device_ip": "10.0.0.3",
    "binary_path": "/root/monero/monerod",
    "binary_ready": true,
    "binary_version": "'Fluorine Fermi' (v0.18.4.5-release)",
    "storage_path": "/root/.bitmonero",
    "storage_free_gib": 5587.401,
    "storage_ok": true,
    "state": "Running (external)",
    "process_owned": false,
    "external_node_running": true,
    "node_is_running": true
  },
  "update_status": {
    "update_available": true,
    "local_version": "0.18.4.5",
    "remote_version": "0.18.5.0",
    "remote_hash": "423b49f3658e29f70a1d971667dec924c7ee7a107cfc93440456e28500b471a6",
    "download_url": "https://downloads.getmonero.org/cli/monero-linux-x64-v0.18.5.0.tar.bz2"
  },
  "node_stats": {
    "nettype": "mainnet",
    "sync": {
      "synchronized": true,
      "height": 3682974,
      "target_height": 3682974,
      "progress_fraction": 1.0,
      "busy_syncing": false
    },
    "overview": {
      "connections_total": 0,
      "connections_incoming": 0,
      "connections_outgoing": 0,
      "block_height": 3682974,
      "free_space_gib": 5587.401
    },
    "network": {
      "hashrate": 6117779053,
      "difficulty": 734133486418,
      "peerlist_white": 0,
      "peerlist_grey": 0,
      "peerlist_total": 0
    },
    "blockchain": {
      "tx_count": 60814079,
      "tx_pool_size": 61,
      "block_reward_atomic": 602031860000,
      "fee_estimate_atomic": 20000,
      "database_size_bytes": 279172874240
    },
    "resources": {
      "bytes_in_mib": 0.0,
      "bytes_out_mib": 0.0
    },
    "restricted_rpc": true,
    "status": "OK"
  },
  "polling": {
    "last_poll_time": 1779860213.436604,
    "last_poll_error": null,
    "poll_interval_secs": 10
  }
}
```

### Field notes

- **`update_status`** is `null` until the startup version+update check completes (a few seconds after server start). If you're up-to-date, `update_available` is `false` and the banner is hidden in the UI. `download_url` is `null` for unrecognized arches (only `amd64` / `arm64` / `arm32` desktop builds are mapped).
- **`node_stats`** is `null` until the first successful poll lands (1 second after the first page load). If the poll fails (daemon offline, RPC unreachable), `node_stats` stays at its last good value and `polling.last_poll_error` carries the error string.
- **`restricted_rpc: true`** indicates monerod is running with `--restricted-rpc`. When true, these fields are **redacted to 0 by monerod itself**, not actually zero:
  - `node_stats.overview.connections_*`
  - `node_stats.network.peerlist_*`
  - `node_stats.resources.bytes_*_mib`
  
  The data exists on the daemon; it just intentionally doesn't share it over RPC. The Kivy app and the web UI both show `*` for these in the visible UI; consumers of the JSON should treat zeros under `restricted_rpc: true` as "unknown".
- **`*_atomic`** values are in atomic units (1 XMR = 10¹² atomic). Divide by 1e12 for XMR.
- **`last_poll_time`** is a Unix timestamp (seconds, fractional). Clients can compute staleness as `now() - last_poll_time`.

### Example: monitor sync height from a script

```bash
while true; do
  curl -sS http://127.0.0.1:8085/api/status \
    | jq -r '.node_stats.sync | "height=\(.height) sync=\(.synchronized)"'
  sleep 30
done
```

## Development

### Local iteration loop

```bash
source .venv/bin/activate
# Edit a file...
# Restart by Ctrl-C'ing the running server and re-running:
monerodui-web
```

There's no hot-reload — NiceGUI's `reload=True` doesn't play well with our startup hooks. Manual restart is the path.

### Validating imports without launching the server

```bash
.venv/bin/python -c "import monerodui_web.main; print('OK')"
```

Catches syntax errors and missing imports without firing up the HTTP server.

### Running both the Kivy app and the web UI simultaneously?

**Don't.** Both read and write the same `~/.config/monerodui/monerodui.ini` — there's no file locking, so a race would lose writes. They'd also both try to spawn monerod subprocesses if either decided to auto-start. Run one or the other.

### Tests

There aren't any (yet). The end-to-end "test" is launch + browse. Settings parity vs the Kivy `settings_schema.json` was verified manually during the port; if you add a setting in either place, audit the other.

## Known quirks

- **`--restricted-rpc` redactions show as `*` in the UI** with an always-visible footnote explaining why. See the JSON API section above for the full list of affected fields.
- **The version banner uses Monero's full release name** (`'Fluorine Fermi' (v0.18.4.5-release)`), not the short form (`v0.18.4.5`). Matches what the Kivy app shows.
- **Status card collapse is a UI-only toggle**, not persisted to config. Reopening the page resets it to expanded.

## Related files

- [`../../README.md`](../../README.md) — main monerodui README (covers the Kivy app, Android builds, and general project info).
- [`../monerodui/settings/settings_schema.json`](../monerodui/settings/settings_schema.json) — source of truth for the settings page schema.
