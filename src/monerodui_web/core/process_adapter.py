"""External-monerod detection helpers.

Historically (M2 first draft) this file held a `ScreenedMonerod` class
that wrapped `monerodui.libs.ProcessManager` to launch monerod inside
`screen -dmS monerod`. That was dropped per user decision: ProcessManager
already auto-appends `--log-file <data_dir>/monerod.log` (see
`monerodui/libs/process_manager.py:186-189`), which gives the user the
same observability `screen -r` would (`tail -f
/root/.bitmonero/monerod.log`). Dropping the wrapper eliminates pid
discovery, screen-session-collision handling, and ~250 lines of code.

What's left here is only the *external*-monerod detection helper used
by the dashboard's polling loop and the startup probe. It does NOT
manage any process — it just checks whether *any* monerod is running
on the system regardless of who launched it.

Filename retained as `process_adapter.py` for import-path stability
(callers still do `from monerodui_web.core.process_adapter import
discover_external_monerod_pid`).

No deployment-specific Configuration Variables in this file.
"""

from __future__ import annotations

import logging
import subprocess
from typing import Optional

logger = logging.getLogger(__name__)


def discover_external_monerod_pid() -> Optional[int]:
    """Return any running `monerod` pid, or None.

    Used in two places:

      1. Startup probe (`main._initial_state_probe_and_autostart`) —
         cheap pgrep to short-circuit auto-start when an external
         daemon is already running.
      2. Per-tick reconciler (`dashboard._apply_poll_result`) —
         distinguishes "RPC responding because we spawned it" from
         "RPC responding because someone else's monerod is up".

    Uses `pgrep -x monerod` (basename match, not full-command). This
    deliberately matches *any* monerod regardless of binary path, since
    the goal is to detect daemons we did not spawn (which by definition
    can have any launch path).
    """
    try:
        out = subprocess.run(
            ["pgrep", "-x", "monerod"],
            capture_output=True,
            text=True,
            timeout=2,
        )
    except Exception as e:
        logger.debug(f"pgrep failed: {e}")
        return None
    pids = [int(p) for p in out.stdout.split() if p.strip().isdigit()]
    return pids[0] if pids else None
