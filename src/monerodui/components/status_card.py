"""Status card component displaying system state."""

import os
from pathlib import Path
from kivy.lang import Builder
from kivy.properties import StringProperty, BooleanProperty
from kivymd.uix.card import MDCard
from kivymd.uix.boxlayout import MDBoxLayout

Builder.load_file(str(Path(__file__).parent.parent / "ui/components/status_card.kv"))


class StatusRow(MDBoxLayout):
    icon = StringProperty("help-circle")
    label = StringProperty("Label")
    value = StringProperty("--")
    is_ok = BooleanProperty(False)


class StatusCard(MDCard):
    arch_value = StringProperty("Detecting...")
    arch_ok = BooleanProperty(False)
    binary_value = StringProperty("Checking...")
    binary_ok = BooleanProperty(False)
    storage_value = StringProperty("Scanning...")
    storage_ok = BooleanProperty(False)
    state_value = StringProperty("Stopped")
    is_running = BooleanProperty(False)
    is_expanded = BooleanProperty(True)
    summary_text = StringProperty("Ready")
    all_ok = BooleanProperty(False)
    
    def __init__(self, *args, **kwargs):
        self.register_event_type("on_storage_tapped")
        super().__init__(*args, **kwargs)
    
    def on_storage_tapped(self):
        pass
    
    def toggle_expanded(self):
        self.is_expanded = not self.is_expanded
    
    def collapse(self):
        self.is_expanded = False
    
    def expand(self):
        self.is_expanded = True
    
    def _update_summary(self):
        self.all_ok = self.arch_ok and self.binary_ok and self.storage_ok
        if self.is_running:
            self.summary_text = f"Running • {self.storage_value}"
        else:
            self.summary_text = f"Ready • {self.storage_value}"

    def update_arch(self, raw, detected, supported):
        self.arch_value = f"{detected}"
        self.arch_ok = supported
        self._update_summary()
    
    def update_binary(self, path, ready):
        self.binary_value = "Ready" if ready else "Not Ready"
        self.binary_ok = ready
        self._update_summary()

    def update_storage(self, path, free_gib, valid, message):
        if valid and path:
            if 'ANDROID_ROOT' in os.environ:
                self.storage_value = f"{free_gib:.1f} GiB free"
            else:
                self.storage_value = f"{path} ({free_gib:.1f} GiB free)"

        elif path:
            self.storage_value = f"{path} - {message}"
        else:
            self.storage_value = message
        self.storage_ok = valid
        self._update_summary()
        
    def update_state(self, state, is_running):
        self.state_value = state
        self.is_running = is_running
        self._update_summary()
