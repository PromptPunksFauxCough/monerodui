"""Main application screen."""

import os
import logging
from pathlib import Path
from kivy.lang import Builder
from kivy.properties import ObjectProperty

from kivymd.uix.screen import MDScreen
from kivymd.uix.dialog import (
    MDDialog,
    MDDialogIcon,
    MDDialogHeadlineText,
    MDDialogSupportingText,
    MDDialogButtonContainer,
)
from kivymd.uix.button import MDButton, MDButtonText

logger = logging.getLogger(__name__)

from monerodui.components.status_card import StatusCard, StatusRow
from monerodui.components.node_stats_card import (
    NodeStatsCard, StatItem, SmallStatItem,
    SyncProgressBar, UpdateBanner, VersionBanner, OfflineMessage
)

Builder.load_file(str(Path(__file__).parent.parent / "ui/screens/main.kv"))


class MainScreen(MDScreen):
    """Primary application screen."""
    
    def on_kv_post(self, base_widget):
        self.ids.status_card.bind(on_storage_tapped=self._on_storage_tapped)

    def _on_storage_tapped(self, *args):
        app = self.get_app()
        if app._file_manager is not None:
            return
        app._launch_directory_picker()

    def refresh_status(self):
        app = self.get_app()
        card = self.ids.status_card
        
        arch = app.arch_detector.get_status()
        card.update_arch(
            raw=arch["raw_arch"],
            detected=arch["detected_arch"] or "Unknown",
            supported=arch["supported"],
        )
        
        card.update_binary(
            path=arch["binary_path"],
            ready=arch["ready"],
        )
        
        data_dir = app.config.get("advanced", "data_dir")
        if data_dir and Path(data_dir).exists():
            try:
                stat = os.statvfs(data_dir)
                free_gib = (stat.f_bavail * stat.f_frsize) / (1024 ** 3)
                card.update_storage(
                    path=data_dir,
                    free_gib=free_gib,
                    valid=True,
                    message="OK",
                )
            except OSError:
                card.update_storage(
                    path=data_dir,
                    free_gib=0,
                    valid=False,
                    message="Cannot read storage",
                )
        else:
            card.update_storage(
                path="Not configured",
                free_gib=0,
                valid=False,
                message="Select a data directory",
            )
        
        card.update_state(
            state=app.node_state,
            is_running=app.node_is_running,
        )
        
        self._update_button(app.node_is_running)
    
    
    def update_node_stats(self, stats):
        self.ids.node_stats_card.update_stats(stats)
    
    def set_node_offline(self):
        self.ids.node_stats_card.set_offline()
    
    def _update_button(self, is_running: bool):
        self.ids.start_stop_text.text = "Stop" if is_running else "Start"
    
    def on_start_stop(self):
        app = self.get_app()
        app.toggle_process()

    def get_app(self):
        from kivymd.app import MDApp
        return MDApp.get_running_app()

