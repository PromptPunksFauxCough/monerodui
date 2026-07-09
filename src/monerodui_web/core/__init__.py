"""Core (non-UI) state and config for monerodui_web."""

from .app_state import AppState, state
from .config_manager import ConfigManager, config

__all__ = [
    "AppState",
    "state",
    "ConfigManager",
    "config",
]
