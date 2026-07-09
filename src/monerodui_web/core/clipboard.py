"""Browser clipboard helper.

`navigator.clipboard.writeText()` only works in secure contexts
(HTTPS or localhost). When the UI is accessed via a LAN IP over
plain HTTP (e.g. `http://10.0.0.3:8085`), navigator.clipboard is
undefined and a naive check like `navigator.clipboard && ...` short-
circuits silently — the JS does nothing, the Python `ui.notify` runs
anyway, and the user is told the copy succeeded with an empty
clipboard.

This module wraps the two-tier approach: try navigator.clipboard
first, fall back to a hidden-textarea + execCommand('copy') (which
works in any context, modern browsers still support it as a
deprecated-but-functional API). Caller handles its own user-facing
notification.
"""

from __future__ import annotations

import json

from nicegui import ui


def copy_text(text: str) -> None:
    """Copy `text` to the browser clipboard.

    Async fire-and-forget — we don't await the JS, so we can't
    distinguish success from failure server-side. The fallback path
    has been reliable in major browsers for many years; in practice
    a real failure is rare enough that the caller can assume success
    for notify purposes.
    """
    # json.dumps gives a guaranteed-valid JS string literal for any
    # input, including special characters that Python's `repr()`
    # might encode in non-JS-compatible ways.
    text_js = json.dumps(text)
    js = f"""
    (async function() {{
        const text = {text_js};
        if (navigator.clipboard && window.isSecureContext) {{
            try {{
                await navigator.clipboard.writeText(text);
                return;
            }} catch (e) {{
                // fall through to legacy path
            }}
        }}
        const ta = document.createElement('textarea');
        ta.value = text;
        ta.style.position = 'fixed';
        ta.style.opacity = '0';
        ta.style.pointerEvents = 'none';
        document.body.appendChild(ta);
        ta.focus();
        ta.select();
        try {{ document.execCommand('copy'); }} catch (e) {{}}
        document.body.removeChild(ta);
    }})();
    """
    ui.run_javascript(js)
