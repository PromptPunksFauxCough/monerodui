"""monerodui_web — NiceGUI-based web UI for monerod.

A drop-in replacement for the KivyMD desktop UI, intended to run as a
local web server on the same machine as monerod. Shares the same INI
config file (`~/.config/monerodui/monerodui.ini`) and reuses the
hardware-/process-/RPC-facing library code from `monerodui.libs`.

This package is independent of the existing `monerodui` (Kivy) package
and does not import any Kivy/KivyMD modules.

NOTE: `main` is intentionally *not* re-exported at package level so that
`import monerodui_web.core` works without NiceGUI installed (useful for
testing config / state in isolation). Import the entry point directly:

    from monerodui_web.main import main
"""

