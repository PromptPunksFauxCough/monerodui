import sys
from pathlib import Path

if __name__ == '__main__':
    sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import traceback
import logging

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

class AndroidLogger(object):
    def __init__(self, filename="full_app_log.txt", original_stream=sys.stdout):
        self.terminal = original_stream
        if 'ANDROID_ROOT' in os.environ:
            log_dir = '/storage/emulated/0/Download/'
            if not os.path.exists(log_dir):
                try:
                    os.makedirs(log_dir)
                except:
                    pass
            self.log_file = os.path.join(log_dir, filename)
            try:
                self.log = open(self.log_file, "a", encoding="utf-8")
            except:
                self.log = None
        else:
            self.log = None

    def write(self, message):
        self.terminal.write(message)
        if self.log:
            try:
                self.log.write(message)
                self.log.flush()
            except:
                pass

    def flush(self):
        self.terminal.flush()
        if self.log:
            try:
                self.log.flush()
            except:
                pass

if 'ANDROID_ROOT' in os.environ:
    sys.stdout = AndroidLogger(original_stream=sys.stdout)
    sys.stderr = sys.stdout

def final_excepthook(t, v, tb):
    sys.__excepthook__(t, v, tb) 
    logger.error(f"Application terminated with UNCAUGHT EXCEPTION: {t.__name__}")

sys.excepthook = final_excepthook

"""monerod UI - Main Application Entry."""

from pathlib import Path
from urllib.parse import unquote

from kivy.clock import Clock, mainthread
from kivy.properties import ObjectProperty, StringProperty, BooleanProperty
from kivy.utils import platform

from kivymd.app import MDApp
from kivymd.uix.snackbar import MDSnackbar, MDSnackbarText
from kivymd.uix.dialog import (
    MDDialog,
    MDDialogIcon,
    MDDialogHeadlineText,
    MDDialogSupportingText,
    MDDialogButtonContainer,
)
from kivymd.uix.button import MDButton, MDButtonText

from monerodui.libs import (
    ArchDetector,
    ProcessManager,
    ProcessState,
    NodeStatsPoller,
    VersionChecker,
    UpdateChecker,
)

REQUEST_CODE_DATA_DIR = 1001


class monerodUIApp(MDApp):
    """Main application class."""
    
    arch_detector = ObjectProperty(None)
    process_manager = ObjectProperty(None)
    node_stats_poller = ObjectProperty(None)
    version_checker = ObjectProperty(None)
    
    node_state = StringProperty("Stopped")
    node_is_running = BooleanProperty(False)

    # 1. Kivy Lifecycle
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        if 'ANDROID_ROOT' in os.environ:
            self.title = "monerod UI (Android)"
            self._is_android = True
        else:
            self.title = "monerod UI (Desktop)"
            self._is_android = False
            
        self.main_screen = None
        self._stats_poll_event = None
        self._insufficient_storage_dialog = None
        self._data_dir_dialog = None
        self._file_manager = None
        self._last_notified_height = 0
        
        base_path = Path(__file__).parent
        self.arch_detector = ArchDetector(bin_dir=base_path / "assets" / "bin")
        self.process_manager = ProcessManager()
        self.node_stats_poller = NodeStatsPoller()
        self.version_checker = VersionChecker()
        self.update_checker = UpdateChecker(self.version_checker,is_android=self._is_android,arch=self.arch_detector.detected_arch or "amd64")
  
    def get_application_config(self, defaultpath='%(appdir)s/%(appname)s.ini'):
        if self._is_android:
            return super().get_application_config(defaultpath)
        else:
            config_dir = Path.home() / ".config" / "monerodui"
            config_dir.mkdir(parents=True, exist_ok=True)
            return str(config_dir / "monerodui.ini")

    def build(self):
        self.theme_cls.theme_style = "Dark"
        self.theme_cls.primary_palette = "Orange"
        self.theme_cls.backgroundColor = [0, 0, 0, 1]
        self.theme_cls.surfaceColor = [0.2, 0.2, 0.2, 1]
        self.theme_cls.surfaceContainerColor = [0.2, 0.2, 0.2, 1]
        self.theme_cls.surfaceContainerHighColor = [0.25, 0.25, 0.25, 1]
        self.theme_cls.surfaceContainerLowColor = [0.15, 0.15, 0.15, 1]

        from monerodui.screens.main_screen import MainScreen
        self.main_screen = MainScreen()
        return self.main_screen

    def build_config(self, config):
        config.setdefaults("network", {
            "network_type": "mainnet", 
            "offline": "0",
            "no_sync": "0",
            "public_node": "0",
            "sync_pruned_blocks": "1",
            "pad_transactions": "0"
        })
        config.setdefaults("p2p", {
            "bind_ip": "0.0.0.0", 
            "bind_port": "18080",
            "use_ipv6": "0",
            "external_port": "0",
            "out_peers": "-1",
            "in_peers": "-1",
            "max_connections_per_ip": "1",
            "hide_my_port": "0",
            "allow_local_ip": "0",
            "priority_nodes": "",
            "exclusive_nodes": "",
            "seed_nodes": "",
            "ban_list": ""
        })
        config.setdefaults("bandwidth", {
            "limit_rate_up": "8192", 
            "limit_rate_down": "32768"
        })
        config.setdefaults("rpc", {
            "bind_ip": "127.0.0.1", 
            "bind_port": "18081",
            "restricted_bind_ip": "127.0.0.1",
            "restricted_bind_port": "0",
            "restricted": "0",
            "use_ipv6": "0",
            "login": "",
            "confirm_external_bind": "0",
            "access_control_origins": "",
            "max_connections": "100",
            "disable_ban": "0"
        })
        config.setdefaults("rpcssl", {
            "mode": "autodetect",
            "private_key": "",
            "certificate": "",
            "ca_certificates": "",
            "allow_any_cert": "0",
            "allow_chained": "0"
        })
        config.setdefaults("zmq", {
            "disabled": "0",
            "bind_ip": "127.0.0.1", 
            "bind_port": "18082",
            "pub": ""
        })
        config.setdefaults("proxy", {
            "address": "",
            "allow_dns_leaks": "0",
            "tx_proxy": "",
            "anonymous_inbound": ""
        })
        config.setdefaults("bootstrap", {
            "address": "",
            "login": "",
            "proxy": ""
        })
        config.setdefaults("blockchain", {
            "prune": "1", 
            "fast_block_sync": "1",
            "db_sync_mode": "fast:async:250000000bytes",
            "db_salvage": "0",
            "block_sync_size": "0",
            "keep_alt_blocks": "0",
            "max_txpool_weight": "648000000"
        })
        config.setdefaults("dns", {
            "enforce_checkpoints": "0",
            "disable_checkpoints": "0",
            "enable_blocklist": "0",
            "check_updates": "notify"
        })
        config.setdefaults("nat", {
            "igd": "delayed"
        })
        config.setdefaults("mining", {
            "address": "",
            "threads": "0",
            "bg_enable": "0",
            "bg_ignore_battery": "0",
            "bg_idle_threshold": "0",
            "bg_miner_target": "0"
        })
        config.setdefaults("logging", {
            "file": "",
            "level": "0",
            "max_file_size": "104850000",
            "max_files": "50"
        })
        config.setdefaults("performance", {
            "max_concurrency": "0",
            "prep_blocks_threads": "4"
        })
        config.setdefaults("notify", {
            "block_enabled": "0",
            "reorg_enabled": "0"
        })
        config.setdefaults("advanced", {
            "config_file": "",
            "data_dir": "",
            "non_interactive": "1",
            "extra_messages_file": ""
        })
        config.setdefaults("runtime", {"extra_flags": "", "auto_start": "0", "enable_boot": "0"})
        config.setdefaults("storage", {"min_free_gib": "10.0", "preferred_path": ""})
        config.setdefaults('state', {'was_running': '0'})
        
        return super().build_config(config)
    
    def build_settings(self, settings):
        settings.add_json_panel("monerod UI", self.config, filename=str(Path(__file__).parent / "settings" / "settings_schema.json"))


    def on_start(self):
        ini_path = self.get_application_config()
        self.config.read(ini_path)
        self._ensure_config_integrity()
    
        if platform == 'android':
            self._request_notification_permission()
            self._bind_activity_result()
    
        if self._needs_data_dir():
            Clock.schedule_once(lambda dt: self._show_data_dir_prompt(), 0.5)
        else:
            Clock.schedule_once(self._initialize, 0.5)

    def on_resume(self):
        logger.info("on_resume called")
        
        if platform == 'android':
            try:
                self._stop_android_service()
            except Exception as e:
                logger.warning(f"Failed to stop service: {e}")
        
        if hasattr(self, 'process_manager') and self.process_manager.is_running:
            self._start_stats_polling()

    def on_pause(self):
        logger.info("on_pause called")
        if platform == 'android' and self.process_manager.is_running:
            self._start_android_service()
            logger.info("Started background service")
        return True

    def on_stop(self):
        logger.info("=== APPLICATION STOPPING ===")
        self._stop_stats_polling()
        
        is_running = self.process_manager.is_running
        if not self.config.has_section("state"):
            self.config.add_section("state")
        self.config.set("state", "was_running", "1" if is_running else "0")
        self.config.write()
        logger.info(f"Saved was_running state: {is_running}")
        
        if is_running:
            logger.info("Leaving monerod running in background")

    # 2. Data Directory Selection (SAF)
    def _needs_data_dir(self) -> bool:
        """Check if user needs to select a data directory."""
        data_dir = self.config.get("advanced", "data_dir")
        if not data_dir:
            return True
        return not Path(data_dir).exists()

    def _bind_activity_result(self):
        """Bind to activity result callback."""
        from android import activity
        activity.bind(on_activity_result=self._on_activity_result)

    def _show_data_dir_prompt(self):
        """Show dialog explaining directory selection."""
        self._data_dir_dialog = MDDialog(
            MDDialogIcon(
                icon="folder-plus",
                theme_text_color="Custom",
                text_color=[1, 0.4, 0, 1]
            ),
            MDDialogHeadlineText(text="Select Data Directory"),
            MDDialogSupportingText(
                text="Choose a folder to store blockchain data.\n\n"
                     "This folder will persist even if you reinstall the app.\n\n"
                     "Tip: Create a new folder like 'monerod' in your home directory."
            ),
            MDDialogButtonContainer(
                MDButton(
                    MDButtonText(text="Select Folder"),
                    style="filled",
                    md_bg_color=[1, 0.4, 0, 1],
                    on_release=lambda x: self._launch_directory_picker()
                ),
            ),
            theme_bg_color="Custom",
            md_bg_color=[0.2, 0.2, 0.2, 1],
        )
        self._data_dir_dialog.open()

    def _launch_directory_picker(self):
        """Launch platform-appropriate directory picker."""
        if self._data_dir_dialog:
            self._data_dir_dialog.dismiss()
            self._data_dir_dialog = None
    
        if self._is_android:
            self._launch_directory_picker_android()
        else:
            self._launch_directory_picker_desktop()

    def _launch_directory_picker_android(self):
        """Launch SAF directory picker on Android."""
        from jnius import autoclass
        
        Intent = autoclass('android.content.Intent')
        PythonActivity = autoclass('org.kivy.android.PythonActivity')
        
        intent = Intent(Intent.ACTION_OPEN_DOCUMENT_TREE)
        intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        intent.addFlags(Intent.FLAG_GRANT_WRITE_URI_PERMISSION)
        intent.addFlags(Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION)
        
        PythonActivity.mActivity.startActivityForResult(intent, REQUEST_CODE_DATA_DIR)

    def _launch_directory_picker_desktop(self):
        """Launch KivyMD file manager on desktop."""
        from kivymd.uix.filemanager import MDFileManager
        
        is_onboarding = not self.config.get("advanced", "data_dir")

        def on_select(path):
            if self._file_manager is None:
                return
            fm = self._file_manager
            self._file_manager = None
            fm.close()
            
            if Path(path).exists() and Path(path).is_dir():
                data_path = Path(path) / ".monerod"
                data_path.mkdir(parents=True, exist_ok=True)
                self.config.set("advanced", "data_dir", str(data_path))
                self.config.write()
                logger.info(f"Saved data_dir: {data_path}")
                if is_onboarding:
                    Clock.schedule_once(self._initialize, 0.3)
                else:
                    self.main_screen.refresh_status()
            else:
                logger.error(f"Invalid directory: {path}")
                if is_onboarding:
                    Clock.schedule_once(lambda dt: self._show_data_dir_required_dialog(), 0.3)
        
        def on_cancel(*args):
            if self._file_manager is None:
                return
            fm = self._file_manager
            self._file_manager = None
            fm.close()
            if is_onboarding:
                Clock.schedule_once(lambda dt: self._show_data_dir_required_dialog(), 0.3)

        self._file_manager = MDFileManager(
            exit_manager=on_cancel,
            select_path=on_select,
            selector="folder",
            background_color_selection_button=[1, 0.4, 0, 1],
            icon_color=[1, 0.4, 0, 1],
            icon_selection_button="check",
        )
        self._file_manager.show(str(Path.home()))

    def _on_activity_result(self, request_code, result_code, intent):
        """Handle SAF picker result."""
        if request_code != REQUEST_CODE_DATA_DIR:
            return
        
        from jnius import autoclass
        
        Activity = autoclass('android.app.Activity')
        Intent = autoclass('android.content.Intent')
        
        if result_code != Activity.RESULT_OK or intent is None:
            Clock.schedule_once(lambda dt: self._show_data_dir_required_dialog(), 0.3)
            return
        
        uri = intent.getData()
        
        # Take persistable permission
        PythonActivity = autoclass('org.kivy.android.PythonActivity')
        content_resolver = PythonActivity.mActivity.getContentResolver()
        flags = Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_GRANT_WRITE_URI_PERMISSION
        content_resolver.takePersistableUriPermission(uri, flags)
        
        # Convert to filesystem path
        path = self._uri_to_path(uri)
        logger.info(f"SAF URI: {uri.toString()}")
        logger.info(f"Converted path: {path}")
        
        if path and Path(path).exists():
            self.config.set("advanced", "data_dir", path)
            self.config.write()
            logger.info(f"Saved data_dir: {path}")
            Clock.schedule_once(self._initialize, 0.3)
        else:
            logger.error(f"Invalid path from URI: {path}")
            Clock.schedule_once(lambda dt: self._show_data_dir_required_dialog(), 0.3)

    def _uri_to_path(self, uri) -> str:
        """Convert SAF URI to filesystem path."""
        uri_str = uri.toString()
        
        # Tree URIs look like: content://com.android.externalstorage.documents/tree/primary%3AMyFolder
        if "primary" in uri_str:
            encoded_path = uri_str.split("primary")[-1]
            if encoded_path.startswith("%3A"):
                encoded_path = encoded_path[3:]
            elif encoded_path.startswith(":"):
                encoded_path = encoded_path[1:]
            
            decoded_path = unquote(encoded_path)
            return f"/storage/emulated/0/{decoded_path}"
        
        # Handle SD card: content://...../tree/XXXX-XXXX%3Afolder
        if "/tree/" in uri_str:
            parts = uri_str.split("/tree/")[1]
            if "%3A" in parts:
                volume_id, encoded_path = parts.split("%3A", 1)
            elif ":" in parts:
                volume_id, encoded_path = parts.split(":", 1)
            else:
                return None
            
            decoded_path = unquote(encoded_path)
            
            for mount in [f"/storage/{volume_id}", f"/mnt/media_rw/{volume_id}"]:
                if Path(mount).exists():
                    return f"{mount}/{decoded_path}"
        
        return None

    def _show_data_dir_required_dialog(self):
        """Show dialog when user must select a directory."""
        dialog = MDDialog(
            MDDialogIcon(
                icon="folder-alert",
                theme_text_color="Custom",
                text_color=[1, 0.4, 0, 1]
            ),
            MDDialogHeadlineText(text="Directory Required"),
            MDDialogSupportingText(
                text="A data directory is required for monerod to store blockchain data.\n\n"
                     "Please select a folder to continue."
            ),
            MDDialogButtonContainer(
                MDButton(
                    MDButtonText(text="Exit"),
                    style="text",
                    on_release=lambda x: self.stop()
                ),
                MDButton(
                    MDButtonText(text="Select Folder"),
                    style="filled",
                    md_bg_color=[1, 0.4, 0, 1],
                    on_release=lambda x: self._dismiss_and_retry(dialog)
                ),
            ),
            theme_bg_color="Custom",
            md_bg_color=[0.2, 0.2, 0.2, 1],
        )
        dialog.open()

    def _dismiss_and_retry(self, dialog):
        dialog.dismiss()
        self._launch_directory_picker()

    # 3. Notifications
    def _request_notification_permission(self):
        """Request notification permission on Android 13+."""
        if platform != 'android':
            return
        
        from jnius import autoclass
        
        PythonActivity = autoclass('org.kivy.android.PythonActivity')
        Context = autoclass('android.content.Context')
        NotificationChannel = autoclass('android.app.NotificationChannel')
        NotificationManager = autoclass('android.app.NotificationManager')
        
        context = PythonActivity.mActivity
        channel_id = "monerodui_default"
        
        channel = NotificationChannel(channel_id, "monerod UI", NotificationManager.IMPORTANCE_DEFAULT)
        nm = context.getSystemService(Context.NOTIFICATION_SERVICE)
        nm.createNotificationChannel(channel)

    # 4. Initialization
    def _initialize(self, *args):
        logger.info("=== INITIALIZATION START ===")
        arch_status = self.arch_detector.get_status()
        logger.info(f"Architecture: {arch_status}")
        
        if not self.arch_detector.is_supported():
            self.show_snackbar(f"Unsupported architecture: {self.arch_detector.raw_arch}")
            return
        
        if not self.arch_detector.is_ready():
            self.show_snackbar("Binary not found or not executable")
        else:
            self._check_binary_version()
        
        self._check_existing_process()
        self._complete_initialization()

    def _ensure_config_integrity(self):
        defaults = {
            "network": {
                "network_type": "mainnet", "offline": "0", "no_sync": "0",
                "public_node": "0", "sync_pruned_blocks": "1", "pad_transactions": "0"
            },
            "p2p": {
                "bind_ip": "0.0.0.0", "bind_port": "18080", "use_ipv6": "0", 
                "external_port": "0", "out_peers": "-1", "in_peers": "-1", 
                "max_connections_per_ip": "1", "hide_my_port": "0", 
                "allow_local_ip": "0", "priority_nodes": "", 
                "exclusive_nodes": "", "seed_nodes": "", "ban_list": ""
            },
            "bandwidth": {"limit_rate_up": "8192", "limit_rate_down": "32768"},
            "rpc": {
                "bind_ip": "127.0.0.1", "bind_port": "18081", 
                "restricted_bind_ip": "127.0.0.1", "restricted_bind_port": "0",
                "restricted": "0", "use_ipv6": "0", "login": "", 
                "confirm_external_bind": "0", "access_control_origins": "",
                "max_connections": "100", "disable_ban": "0"
            },
            "rpcssl": {
                "mode": "autodetect", "private_key": "", "certificate": "", 
                "ca_certificates": "", "allow_any_cert": "0", "allow_chained": "0"
            },
            "zmq": {"disabled": "0", "bind_ip": "127.0.0.1", "bind_port": "18082", "pub": ""},
            "proxy": {"address": "", "allow_dns_leaks": "0", "tx_proxy": "", "anonymous_inbound": ""},
            "bootstrap": {"address": "", "login": "", "proxy": ""},
            "blockchain": {
                "prune": "1", "db_sync_mode": "fast:async:250000000bytes", 
                "db_salvage": "0", "block_sync_size": "0", 
                "fast_block_sync": "1", "keep_alt_blocks": "0", 
                "max_txpool_weight": "648000000"
            },
            "dns": {
                "enforce_checkpoints": "0", "disable_checkpoints": "0", 
                "enable_blocklist": "0", "check_updates": "notify"
            },
            "nat": {"igd": "delayed"},
            "mining": {
                "address": "", "threads": "0", "bg_enable": "0", 
                "bg_ignore_battery": "0", "bg_idle_threshold": "0", "bg_miner_target": "0"
            },
            "logging": {
                "file": "", "level": "0", "max_file_size": "104850000", "max_files": "50"
            },
            "performance": {"max_concurrency": "0", "prep_blocks_threads": "4"},
            "notify": {"block_enabled": "0", "reorg_enabled": "0"},
            "advanced": {
                "config_file": "", "data_dir": "", 
                "non_interactive": "1", "extra_messages_file": ""
            },
            "runtime": {"extra_flags": "", "auto_start": "0", "enable_boot": "0"},
            "storage": {"min_free_gib": "50.0", "preferred_path": ""},
            "state": {"was_running": "0"},
        }

        dirty = False
        for section, options in defaults.items():
            if not self.config.has_section(section):
                self.config.add_section(section)
                dirty = True
            
            for key, value in options.items():
                if not self.config.has_option(section, key):
                    self.config.set(section, key, value)
                    dirty = True
        
        if dirty:
            self.config.write()
            logger.info("Config repaired and saved")

    def _check_existing_process(self):
        """Check if monerod is already running (from previous session or external)."""
        if self.process_manager.is_running:
            logger.info("Detected existing node via ProcessManager")
            self._update_ui_state(running=True)
            return
        
        stats = self.node_stats_poller.poll()
        if stats.status != "offline":
            logger.info("Detected existing node via RPC")
            self._update_ui_state(running=True)
        else:
            self._update_ui_state(running=False)
    
    def _check_binary_version(self):
        if self.arch_detector.binary_path:
            self.version_checker.set_binary_path(self.arch_detector.binary_path)
            version = self.version_checker.get_version()
            if version:
                Clock.schedule_once(lambda dt: self._set_binary_version(version), 1.0)

    def _set_binary_version(self, version):
        """Set binary version in UI once it's ready."""
        if self.main_screen and hasattr(self.main_screen, 'ids'):
            if 'node_stats_card' in self.main_screen.ids:
                self.main_screen.ids.node_stats_card.set_binary_version(version)

    def _get_working_directory(self) -> Path:
        """Get working directory from config."""
        data_dir = self.config.get("advanced", "data_dir")
        if data_dir:
            return Path(data_dir)
        return None

    def _complete_initialization(self):
        logger.info("=== COMPLETING INITIALIZATION ===")
        
        working_dir = self._get_working_directory()
        
        if not working_dir:
            logger.error("No working directory configured")
            self.show_snackbar("No data directory configured")
            return
        
        if not self._check_storage():
            return
        
        logger.info(f"Working directory: {working_dir}")
        logger.info(f"Binary path: {self.arch_detector.binary_path}")
        
        if self.arch_detector.binary_path and working_dir:
            logger.info("Configuring ProcessManager...")
            self.process_manager.configure(
                binary_path=self.arch_detector.binary_path,
                working_dir=working_dir,
                on_state_change=self._on_process_state_change,
            )
            logger.info("ProcessManager configured successfully")
            
            boot_start_enabled = False
            if platform == 'android':
                try:
                    from jnius import autoclass
                    PythonActivity = autoclass('org.kivy.android.PythonActivity')
                    Context = autoclass('android.content.Context')
                    context = PythonActivity.mActivity.getApplicationContext()
                    prefs = context.getSharedPreferences("monerodui", Context.MODE_PRIVATE)
                    boot_start_enabled = prefs.getBoolean("enable_boot", False)
                    logger.info(f"Read enable_boot from SharedPreferences: {boot_start_enabled}")
                except Exception as e:
                    logger.error(f"Failed to read SharedPreferences: {e}")
            
            if self.process_manager.is_running:
                logger.info("Detected monerod already running from service")
                self._update_ui_state(True)
            else:
                last_running = self.config.get("state", "was_running", fallback="0")
                was_running = last_running in ("1", "True", "true")
                
                config_auto_start = self.config.get("runtime", "auto_start", fallback="0")
                user_auto_start = config_auto_start in ("1", "True", "true")
                
                should_start = False
                start_reason = ""
                
                if self._is_android:
                    if was_running:
                        should_start = True
                        start_reason = "Resuming previous state"
                    elif user_auto_start or boot_start_enabled:
                        should_start = True
                        start_reason = "Auto-start setting enabled"
                else:
                    if user_auto_start:
                        should_start = True
                        start_reason = "Auto-start setting enabled"
    
                logger.info(f"Auto-start check: was_running={was_running}, user_setting={user_auto_start}, boot_enabled={boot_start_enabled} -> {should_start}")
                
                if should_start:
                    logger.info(f"Triggering auto-start: {start_reason}")
                    extra_args = self._get_extra_args()
                    
                    self.process_manager.configure(
                        binary_path=self.arch_detector.binary_path,
                        working_dir=working_dir,
                        extra_args=extra_args,
                        on_state_change=self._on_process_state_change,
                    )
                    
                    if self.process_manager.start():
                        logger.info("Auto-start succeeded")
                        self._update_ui_state(True)
                    else:
                        logger.error(f"Auto-start failed: {self.process_manager.last_error}")
                        if not self.config.has_section("state"):
                            self.config.add_section("state")
                        self.config.set("state", "was_running", "0")
                        self.config.write()
                        self._update_ui_state(False)
        else:
            logger.error(f"Cannot configure ProcessManager - binary={self.arch_detector.binary_path}, working_dir={working_dir}")
        
        self.main_screen.refresh_status()

    # 5. Storage
    def _check_storage(self) -> bool:
        """Check if data directory has sufficient free space."""
        data_dir = self.config.get("advanced", "data_dir")
        if not data_dir or not Path(data_dir).exists():
            return False
        
        try:
            stat = os.statvfs(data_dir)
            free_gib = (stat.f_bavail * stat.f_frsize) / (1024 ** 3)
            min_free_gib = float(self.config.get("storage", "min_free_gib", fallback="10.0"))
            
            if free_gib < min_free_gib:
                self._show_insufficient_storage_dialog(
                    f"Only {free_gib:.1f} GiB free, {min_free_gib:.1f} GiB required."
                )
                return False
            return True
        except OSError:
            return False

    def _show_insufficient_storage_dialog(self, message: str):
        self._insufficient_storage_dialog = MDDialog(
            MDDialogIcon(icon="harddisk-remove", theme_text_color="Custom", text_color=[1, 0.4, 0, 1]),
            MDDialogHeadlineText(text="Insufficient Storage"),
            MDDialogSupportingText(text=f"{message}\n\nRequires sufficient free space for blockchain data."),
            MDDialogButtonContainer(
                MDButton(
                    MDButtonText(text="Change Location", theme_text_color="Custom", text_color=[1, 0.4, 0, 1]),
                    style="text",
                    on_release=lambda x: self._dismiss_and_pick_new()
                ),
                MDButton(
                    MDButtonText(text="OK", theme_text_color="Custom", text_color=[1, 1, 1, 1]),
                    style="filled",
                    md_bg_color=[1, 0.4, 0, 1],
                    on_release=lambda x: self._insufficient_storage_dialog.dismiss()
                ),
            ),
            theme_bg_color="Custom",
            md_bg_color=[0.2, 0.2, 0.2, 1],
        )
        self._insufficient_storage_dialog.open()

    def _dismiss_and_pick_new(self):
        """Dismiss storage dialog and launch directory picker."""
        if self._insufficient_storage_dialog:
            self._insufficient_storage_dialog.dismiss()
        self._launch_directory_picker()

    # 6. Process Management
    def _validate_ready(self) -> bool:
        """Validate system is ready to start node."""
        logger.info("Validating readiness...")
        if not self.arch_detector.is_ready():
            logger.warning("Binary not available")
            self.show_snackbar("Binary not available")
            return False
        
        data_dir = self.config.get("advanced", "data_dir")
        if not data_dir or not Path(data_dir).exists():
            logger.warning("Data directory not set or doesn't exist")
            self.show_snackbar("Data directory not configured")
            return False
        
        logger.info("Validation passed")
        return True

    def toggle_process(self):
        logger.info("=== TOGGLE_PROCESS CALLED ===")
        
        if not self._validate_ready():
            logger.warning("Validation failed, aborting toggle")
            return
        
        is_running = self.node_is_running
        logger.info(f"node_is_running={is_running}")
        
        if is_running:
            logger.info("=== STOPPING MONEROD ===")
            if self.process_manager.is_running:
                logger.info("ProcessManager reports running, calling stop()")
                result = self.process_manager.stop()
                logger.info(f"Stop result: {result}")
            else:
                logger.warning("ProcessManager reports NOT running")
            self._update_ui_state(False)
        else:
            logger.info("=== STARTING MONEROD ===")
            if not self._check_storage():
                logger.warning("Storage check failed, aborting start")
                return
            
            working_dir = self._get_working_directory()
            binary_path = self.arch_detector.binary_path
            extra_args = self._get_extra_args()
            
            logger.info(f"Binary: {binary_path}")
            logger.info(f"Working dir: {working_dir}")
            logger.info(f"Extra args: {extra_args}")
            
            try:
                logger.info("Calling ProcessManager.configure()...")
                self.process_manager.configure(
                    binary_path=binary_path,
                    working_dir=working_dir,
                    extra_args=extra_args,
                    on_state_change=self._on_process_state_change,
                )
                logger.info("ProcessManager configured")
                
                logger.info("Calling ProcessManager.start()...")
                start_result = self.process_manager.start()
                logger.info(f"Start result: {start_result}")
                
                if not start_result:
                    error = self.process_manager.last_error
                    logger.error(f"Start FAILED: {error}")
                    self.show_snackbar(f"Failed to start: {error}")
                else:
                    logger.info("Start succeeded")
                    
            except Exception as e:
                logger.error(f"EXCEPTION during start: {e}", exc_info=True)
                self.show_snackbar(f"Error: {e}")

    def _get_extra_args(self) -> list[str]:
        """Translate app configuration into monerod command-line arguments."""
        args = []
        
        args.append("--non-interactive")
        
        net_type = self.config.get("network", "network_type")
        if net_type == "testnet":
            args.append("--testnet")
        elif net_type == "stagenet":
            args.append("--stagenet")
            
        if self.config.get("network", "offline") == "1":
            args.append("--offline")
        if self.config.get("network", "no_sync") == "1":
            args.append("--no-sync")
        if self.config.get("network", "public_node") == "1":
            args.append("--public-node")
        if self.config.get("network", "sync_pruned_blocks") == "1":
            args.append("--sync-pruned-blocks")
        if self.config.get("network", "pad_transactions") == "1":
            args.append("--pad-transactions")

        bind_ip = self.config.get("p2p", "bind_ip")
        if bind_ip and bind_ip != "0.0.0.0":
            args.extend(["--p2p-bind-ip", bind_ip])
            
        bind_port = self.config.get("p2p", "bind_port")
        if bind_port and bind_port != "18080":
            args.extend(["--p2p-bind-port", bind_port])
            
        if self.config.get("p2p", "use_ipv6") == "1":
            args.append("--p2p-use-ipv6")
            
        ext_port = self.config.get("p2p", "external_port")
        if ext_port and ext_port != "0":
            args.extend(["--p2p-external-port", ext_port])
            
        out_peers = self.config.get("p2p", "out_peers")
        if out_peers and out_peers != "-1":
            args.extend(["--out-peers", out_peers])
            
        in_peers = self.config.get("p2p", "in_peers")
        if in_peers and in_peers != "-1":
            args.extend(["--in-peers", in_peers])
            
        max_conns = self.config.get("p2p", "max_connections_per_ip")
        if max_conns and max_conns != "1":
            args.extend(["--max-connections-per-ip", max_conns])
            
        if self.config.get("p2p", "hide_my_port") == "1":
            args.append("--hide-my-port")
        if self.config.get("p2p", "allow_local_ip") == "1":
            args.append("--allow-local-ip")
            
        priority_nodes = self.config.get("p2p", "priority_nodes")
        if priority_nodes:
            for node in priority_nodes.split(","):
                if node.strip():
                    args.extend(["--add-priority-node", node.strip()])
                    
        exclusive_nodes = self.config.get("p2p", "exclusive_nodes")
        if exclusive_nodes:
            for node in exclusive_nodes.split(","):
                if node.strip():
                    args.extend(["--add-exclusive-node", node.strip()])
                    
        seed_nodes = self.config.get("p2p", "seed_nodes")
        if seed_nodes:
            args.extend(["--seed-node", seed_nodes])
            
        ban_list = self.config.get("p2p", "ban_list")
        if ban_list:
            args.extend(["--ban-list", ban_list])

        limit_up = self.config.get("bandwidth", "limit_rate_up")
        if limit_up and limit_up != "8192":
            args.extend(["--limit-rate-up", limit_up])
            
        limit_down = self.config.get("bandwidth", "limit_rate_down")
        if limit_down and limit_down != "32768":
            args.extend(["--limit-rate-down", limit_down])

        rpc_bind_ip = self.config.get("rpc", "bind_ip")
        if rpc_bind_ip:
            args.extend(["--rpc-bind-ip", rpc_bind_ip])
            
        rpc_bind_port = self.config.get("rpc", "bind_port")
        if rpc_bind_port:
            args.extend(["--rpc-bind-port", rpc_bind_port])
            
        res_bind_ip = self.config.get("rpc", "restricted_bind_ip")
        if res_bind_ip and res_bind_ip != "127.0.0.1":
            args.extend(["--rpc-restricted-bind-ip", res_bind_ip])
            
        res_bind_port = self.config.get("rpc", "restricted_bind_port")
        if res_bind_port and res_bind_port != "0":
            args.extend(["--rpc-restricted-bind-port", res_bind_port])
            
        if self.config.get("rpc", "restricted") == "1":
            args.append("--restricted-rpc")
        if self.config.get("rpc", "use_ipv6") == "1":
            args.append("--rpc-use-ipv6")
            
        rpc_login = self.config.get("rpc", "login")
        if rpc_login:
            args.extend(["--rpc-login", rpc_login])
            
        if self.config.get("rpc", "confirm_external_bind") == "1":
            args.append("--confirm-external-bind")
            
        cors = self.config.get("rpc", "access_control_origins")
        if cors:
            args.extend(["--rpc-access-control-origins", cors])
            
        if self.config.get("rpc", "disable_ban") == "1":
            args.append("--disable-rpc-ban")

        ssl_mode = self.config.get("rpcssl", "mode")
        if ssl_mode == "enabled":
            args.extend(["--rpc-ssl", "enabled"])
        elif ssl_mode == "disabled":
            args.extend(["--rpc-ssl", "disabled"])
        
        ssl_key = self.config.get("rpcssl", "private_key")
        if ssl_key:
            args.extend(["--rpc-ssl-private-key", ssl_key])
            
        ssl_cert = self.config.get("rpcssl", "certificate")
        if ssl_cert:
            args.extend(["--rpc-ssl-certificate", ssl_cert])
            
        ca_certs = self.config.get("rpcssl", "ca_certificates")
        if ca_certs:
            args.extend(["--rpc-ssl-ca-certificates", ca_certs])
            
        if self.config.get("rpcssl", "allow_any_cert") == "1":
            args.append("--rpc-ssl-allow-any-cert")
        if self.config.get("rpcssl", "allow_chained") == "1":
            args.append("--rpc-ssl-allow-chained")

        if self.config.get("zmq", "disabled") == "1":
            args.append("--no-zmq")
        else:
            zmq_ip = self.config.get("zmq", "bind_ip")
            zmq_port = self.config.get("zmq", "bind_port")
            if zmq_ip and zmq_port:
                args.extend(["--zmq-rpc-bind-ip", zmq_ip, "--zmq-rpc-bind-port", zmq_port])
            
            zmq_pub = self.config.get("zmq", "pub")
            if zmq_pub:
                args.extend(["--zmq-pub", zmq_pub])

        proxy = self.config.get("proxy", "address")
        if proxy:
            args.extend(["--proxy", proxy])
            
        if self.config.get("proxy", "allow_dns_leaks") == "1":
            args.append("--allow-dns-leaks")
            
        tx_proxy = self.config.get("proxy", "tx_proxy")
        if tx_proxy:
            args.extend(["--tx-proxy", tx_proxy])
            
        anon_inbound = self.config.get("proxy", "anonymous_inbound")
        if anon_inbound:
            args.extend(["--anonymous-inbound", anon_inbound])

        boot_addr = self.config.get("bootstrap", "address")
        if boot_addr:
            args.extend(["--bootstrap-daemon-address", boot_addr])
            
        boot_login = self.config.get("bootstrap", "login")
        if boot_login:
            args.extend(["--bootstrap-daemon-login", boot_login])
            
        boot_proxy = self.config.get("bootstrap", "proxy")
        if boot_proxy:
            args.extend(["--bootstrap-daemon-proxy", boot_proxy])

        if self.config.get("blockchain", "prune") == "1":
            args.append("--prune-blockchain")
            
        db_sync = self.config.get("blockchain", "db_sync_mode")
        if db_sync:
            args.extend(["--db-sync-mode", db_sync])
            
        if self.config.get("blockchain", "db_salvage") == "1":
            args.append("--db-salvage")
            
        if self.config.get("blockchain", "fast_block_sync") == "1":
            args.append("--fast-block-sync=1")
        else:
            args.append("--fast-block-sync=0")
            
        if self.config.get("blockchain", "keep_alt_blocks") == "1":
            args.append("--keep-alt-blocks")
            
        max_txpool_weight = self.config.get("blockchain", "max_txpool_weight")
        if max_txpool_weight and max_txpool_weight != "648000000":
            args.extend(["--max-txpool-weight", max_txpool_weight])

        if self.config.get("dns", "enforce_checkpoints") == "1":
            args.append("--enforce-dns-checkpoints")
        if self.config.get("dns", "disable_checkpoints") == "1":
            args.append("--disable-dns-checkpoints")
        if self.config.get("dns", "enable_blocklist") == "1":
            args.append("--enable-dns-blocklist")
        
        check_updates = self.config.get("dns", "check_updates")
        if check_updates:
            args.extend(["--check-updates", check_updates])

        igd = self.config.get("nat", "igd")
        if igd:
            args.extend(["--igd", igd])

        mine_addr = self.config.get("mining", "address")
        mine_threads = self.config.get("mining", "threads")
        if mine_addr and mine_threads and mine_threads != "0":
            args.extend(["--start-mining", mine_addr, "--mining-threads", mine_threads])
            
        if self.config.get("mining", "bg_enable") == "1":
            args.append("--bg-mining-enable")
        if self.config.get("mining", "bg_ignore_battery") == "1":
            args.append("--bg-mining-ignore-battery")
            
        bg_threshold = self.config.get("mining", "bg_idle_threshold")
        if bg_threshold and bg_threshold != "0":
            args.extend(["--bg-mining-miner-target", bg_threshold])
            
        bg_target = self.config.get("mining", "bg_miner_target")
        if bg_target and bg_target != "0":
            args.extend(["--bg-mining-miner-target", bg_target])

        log_level = self.config.get("logging", "level")
        if log_level:
            args.extend(["--log-level", log_level])
            
        max_log_size = self.config.get("logging", "max_file_size")
        if max_log_size and max_log_size != "104850000":
            args.extend(["--max-log-file-size", max_log_size])
            
        max_logs = self.config.get("logging", "max_files")
        if max_logs and max_logs != "50":
            args.extend(["--max-log-files", max_logs])
            
        prep_threads = self.config.get("performance", "prep_blocks_threads")
        if prep_threads and prep_threads != "4":
            args.extend(["--prep-blocks-threads", prep_threads])
            
        max_concurrency = self.config.get("performance", "max_concurrency")
        if max_concurrency and max_concurrency != "0":
            args.extend(["--max-concurrency", max_concurrency])

        config_file = self.config.get("advanced", "config_file")
        if config_file:
            args.extend(["--config-file", config_file])
            
        data_dir = self.config.get("advanced", "data_dir")
        if data_dir:
            args.extend(["--data-dir", data_dir])
            
        extra_messages = self.config.get("advanced", "extra_messages_file")
        if extra_messages:
            args.extend(["--extra-messages-file", extra_messages])

        extra_flags = self.config.get("runtime", "extra_flags")
        if extra_flags:
            args.extend(extra_flags.split())

        return args

    def _on_process_state_change(self, state: ProcessState):
        logger.info(f"=== PROCESS STATE CHANGE: {state.name} ===")
        if state == ProcessState.RUNNING:
            self._update_ui_state(True)
        elif state in (ProcessState.STOPPED, ProcessState.ERROR):
            self._update_ui_state(False)

    @mainthread
    def _update_ui_state(self, running: bool):
        logger.info(f"Updating UI state: running={running}")
        self.node_is_running = running
        self.node_state = "Running" if running else "Stopped"
        
        if self._is_android:
            if running:
                self._start_android_service()
            elif not running:
                self._stop_android_service()
        
        if self.main_screen:
            self.main_screen.refresh_status()
            
            if hasattr(self.main_screen, 'ids') and 'status_card' in self.main_screen.ids:
                self.main_screen.ids.status_card.is_running = running
                
                if running:
                    self._start_stats_polling()
                    self.main_screen.ids.status_card.collapse()
                else:
                    self._stop_stats_polling()
                    self.main_screen.set_node_offline()
                    self.main_screen.ids.status_card.expand()
                    if self.version_checker.cached_version and 'node_stats_card' in self.main_screen.ids:
                        self.main_screen.ids.node_stats_card.set_binary_version(self.version_checker.cached_version)

    # 7. Stats Polling
    def _start_stats_polling(self):
        if self._stats_poll_event is None:
            Clock.schedule_once(lambda dt: self._poll_stats(), 1)
            self._stats_poll_event = Clock.schedule_interval(lambda dt: self._poll_stats(), 10)
            Clock.schedule_once(lambda dt: self._check_for_updates(), 10)
  
    def _stop_stats_polling(self):
        if self._stats_poll_event is not None:
            self._stats_poll_event.cancel()
            self._stats_poll_event = None

    def _poll_stats(self):
        """Poll node stats in background thread."""
        import threading
        
        def _do_poll():
            stats = self.node_stats_poller.poll()
            
            process_running = self.process_manager.is_running
            
            if process_running != self.node_is_running:
                logger.info(f"Process state mismatch: process_running={process_running}, node_is_running={self.node_is_running}")
                self._update_ui_state(process_running)
            
            if stats.status != "offline":
                self._check_notify_events(stats)
                from kivy.clock import Clock
                Clock.schedule_once(lambda dt: self.main_screen.update_node_stats(stats))
        
        threading.Thread(target=_do_poll, daemon=True).start()

    # 8. Config Changes
    def on_config_change(self, config, section, key, value):
        if section == "runtime" and key == "enable_boot":
            self._save_boot_preference(value in ("1", "True", "true"))

    # 9. Notifications & Events
    def _check_for_updates(self):
        logger.info(f"Update check starting - cached_version: {self.version_checker.cached_version}")
        status = self.update_checker.check()
        if status.error:
            logger.warning(f"Update check failed: {status.error}")
            return
        if status.update_available:
            logger.info(f"Update available: {status.local_version} -> {status.remote_version}")
            self._update_version_ui(status)
            if self._is_android:
                self._send_notification("Update Available", f"v{status.remote_version} available")
        else:
            logger.info(f"Up to date: {status.local_version}")

    @mainthread
    def _update_version_ui(self, status):
        if hasattr(self.main_screen, 'ids') and 'node_stats_card' in self.main_screen.ids:
            self.main_screen.ids.node_stats_card.update_version_info(status)

    @mainthread
    def _update_version_ui(self, status):
        if hasattr(self.main_screen, 'ids') and 'node_stats_card' in self.main_screen.ids:
            self.main_screen.ids.node_stats_card.update_version_info(status)
   
    def _check_notify_events(self, stats):
        """Check for notification-worthy events."""
        if not self._is_android:
            return
        
        if self.config.get("notify", "block_enabled") == "1":
            if stats.height > self._last_notified_height and self._last_notified_height > 0:
                self._notify_block(stats.height)
            self._last_notified_height = stats.height

    def _notify_block(self, height):
        """Send notification for new block."""
        try:
            self._send_notification("New Block", f"Block #{height:,}")
            logger.info(f"Sent block notification for height {height}")
        except Exception as e:
            logger.error(f"Failed to send notification: {e}")

    def _notify_reorg(self, split_height, new_height):
        """Send notification for chain reorg."""
        try:
            self._send_notification("Chain Reorganization", f"Split at {split_height:,}, new height {new_height:,}")
            logger.info(f"Sent reorg notification")
        except Exception as e:
            logger.error(f"Failed to send notification: {e}")

    @mainthread
    def show_snackbar(self, text):
        MDSnackbar(MDSnackbarText(text=text), y="24dp", pos_hint={"center_x": 0.5}, size_hint_x=0.9).open()

    def _send_notification(self, title: str, message: str):
        """Send notification using Android API directly."""
        if platform != 'android':
            return
        
        from jnius import autoclass
        
        PythonActivity = autoclass('org.kivy.android.PythonActivity')
        Context = autoclass('android.content.Context')
        NotificationBuilder = autoclass('android.app.Notification$Builder')
        NotificationChannel = autoclass('android.app.NotificationChannel')
        NotificationManager = autoclass('android.app.NotificationManager')
        PendingIntent = autoclass('android.app.PendingIntent')
        Intent = autoclass('android.content.Intent')
        
        context = PythonActivity.mActivity
        channel_id = "monerodui_default"
        
        channel = NotificationChannel(channel_id, "monerod UI", NotificationManager.IMPORTANCE_DEFAULT)
        nm = context.getSystemService(Context.NOTIFICATION_SERVICE)
        nm.createNotificationChannel(channel)
        
        intent = Intent(context, PythonActivity)
        pending = PendingIntent.getActivity(context, 0, intent, 67108864)
        
        notification = NotificationBuilder(context, channel_id) \
            .setContentTitle(title) \
            .setContentText(message) \
            .setSmallIcon(context.getApplicationInfo().icon) \
            .setContentIntent(pending) \
            .setAutoCancel(True) \
            .build()
        
        nm.notify(1, notification)

    # 10. Android Service
    def _start_android_service(self):
        """Start the background service."""
        try:
            from jnius import autoclass
            service = autoclass('org.monerodui.monerodui.ServiceMonerodui')
            mActivity = autoclass('org.kivy.android.PythonActivity').mActivity
            service.start(mActivity, '')
        except Exception as e:
            logger.error(f"Failed to start service: {e}")

    def _stop_android_service(self):
        from android import mActivity
        from jnius import autoclass
        
        context = mActivity.getApplicationContext()
        service_name = str(context.getPackageName()) + '.Service' + 'Monerodui'
        
        Intent = autoclass('android.content.Intent')
        intent = Intent(
            context,
            autoclass(service_name)
        )
        context.stopService(intent)

    def _save_boot_preference(self, enabled: bool):
        """Save boot preference to SharedPreferences."""
        if platform != 'android':
            return
        try:
            from jnius import autoclass
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            Context = autoclass('android.content.Context')
            
            context = PythonActivity.mActivity.getApplicationContext()
            prefs = context.getSharedPreferences("monerodui", Context.MODE_PRIVATE)
            editor = prefs.edit()
            editor.putBoolean("enable_boot", enabled)
            editor.apply()
            logger.info(f"Saved enable_boot preference: {enabled}")
        except Exception as e:
            logger.error(f"Failed to save boot preference: {e}")


def main():
    monerodUIApp().run()


if __name__ == "__main__":
    main()
