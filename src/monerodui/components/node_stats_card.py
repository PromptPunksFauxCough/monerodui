"""Node statistics display card."""

from pathlib import Path
from kivy.lang import Builder
from kivy.properties import StringProperty, NumericProperty, BooleanProperty
from kivymd.uix.card import MDCard
from kivymd.uix.boxlayout import MDBoxLayout

Builder.load_file(str(Path(__file__).parent.parent / "ui/components/node_stats_card.kv"))


class StatItem(MDBoxLayout):
    value = StringProperty("--")
    label = StringProperty("Label")
    is_ok = BooleanProperty(True)


class SmallStatItem(MDBoxLayout):
    value = StringProperty("--")
    label = StringProperty("Label")


class SyncProgressBar(MDBoxLayout):
    progress = NumericProperty(0)


class UpdateBanner(MDBoxLayout):
    update_text = StringProperty("")


class VersionBanner(MDBoxLayout):
    version_text = StringProperty("")


class OfflineMessage(MDBoxLayout):
    pass


class SectionHeader(MDBoxLayout):
    text = StringProperty("Section")


class NodeStatsCard(MDCard):
    # Primary stats
    connections_text = StringProperty("--")
    has_connections = BooleanProperty(False)
    height_text = StringProperty("--")
    is_synced = BooleanProperty(False)
    storage_text = StringProperty("--")
    has_storage = BooleanProperty(True)
    
    # Sync
    sync_progress = NumericProperty(0)
    sync_status_text = StringProperty("Sync Progress")
    
    # State
    is_offline = BooleanProperty(True)
    update_available = BooleanProperty(False)
    update_text = StringProperty("")
    version_text = StringProperty("")
    network_text = StringProperty("MAINNET")
    
    # Network stats
    difficulty_text = StringProperty("--")
    hashrate_text = StringProperty("--")
    peers_text = StringProperty("--")
    
    # Chain stats
    tx_pool_text = StringProperty("--")
    tx_count_text = StringProperty("--")
    block_reward_text = StringProperty("--")
    fee_text = StringProperty("--")
    
    # Resource stats
    bandwidth_text = StringProperty("-- / --")
    db_size_text = StringProperty("--")
    
    def update_stats(self, stats):
        if stats is None or stats.status == "offline":
            self.is_offline = True
            return
        
        self.is_offline = False
        
        # Primary stats
        self.connections_text = f"{stats.total_connections}"
        self.has_connections = stats.total_connections > 0
        self.height_text = f"{stats.height:,}"
        self.is_synced = stats.synchronized
        self.storage_text = f"{stats.free_space_gib:.1f} GB"
        self.has_storage = stats.free_space_gib > 1.0
        
        # Network stats
        self.difficulty_text = stats.difficulty_display
        self.hashrate_text = stats.hashrate_display
        self.peers_text = f"{stats.white_peerlist_size + stats.grey_peerlist_size:,}"
        
        # Chain stats
        self.tx_pool_text = f"{stats.tx_pool_size:,}"
        self.tx_count_text = f"{stats.tx_count:,}"
        self.block_reward_text = stats.block_reward_display
        self.fee_text = stats.fee_display
        
        # Resource stats
        self.bandwidth_text = f"{stats.bytes_in_mib:.1f} / {stats.bytes_out_mib:.1f} MB"
        self.db_size_text = f"{stats.database_size_gib:.1f} GB"
        
        # Network and sync
        self.network_text = stats.nettype.upper()
        self.sync_progress = stats.sync_progress
        
        if stats.synchronized:
            self.sync_status_text = "Fully synchronized"
        elif stats.busy_syncing:
            self.sync_status_text = f"Syncing... {stats.blocks_remaining:,} blocks remaining"
        else:
            self.sync_status_text = "Waiting for sync..."
        
        if not self.version_text or self.version_text == "":
            if stats.version:
                self.version_text = stats.version
        
        if not self.update_available:
            self.update_available = stats.update_available

    def update_version_info(self, version_info):
        if version_info is None:
            return
        self.update_available = version_info.update_available
        if version_info.update_available:
            if version_info.latest_version:
                self.update_text = f"Current: {version_info.current_version}\nLatest: {version_info.latest_version}"
            else:
                self.update_text = f"Current: {version_info.current_version}"
    
    def set_binary_version(self, binary_version):
        if binary_version:
            self.version_text = binary_version.display_string
    
    def set_offline(self):
        self.is_offline = True
        self.connections_text = "--"
        self.height_text = "--"
        self.storage_text = "--"
        self.sync_progress = 0
        self.sync_status_text = "Sync Progress"
        self.update_available = False
        self.difficulty_text = "--"
        self.hashrate_text = "--"
        self.tx_pool_text = "--"
        self.bandwidth_text = "-- / --"
        self.block_reward_text = "--"
        self.fee_text = "--"
        self.peers_text = "--"
        self.tx_count_text = "--"
        self.db_size_text = "--"
        self.network_text = "MAINNET"
