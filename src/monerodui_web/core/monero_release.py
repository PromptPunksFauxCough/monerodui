"""Small helpers around Monero releases (download URL construction).

Lives in `core/` so both `main.py` (for the JSON API) and the UI
components (`node_stats_card.py`'s update banner) can share one
source of truth for the URL pattern.
"""

from __future__ import annotations

from typing import Optional


def construct_download_url(arch: str, version: str) -> Optional[str]:
    """Build the canonical downloads.getmonero.org URL for this arch +
    version.

    Matches the URL monerod itself logs when an update is available
    (bitmonero.log lines like "Version X.Y.Z of monero for linux-x64
    is available: https://downloads.getmonero.org/...").

    `arch` values come from `ArchDetector.detected_arch` — see
    `src/monerodui/libs/arch_detector.py` ARCH_MAP. Returns None for
    unrecognized arch (caller can hide the URL row / field).
    """
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
