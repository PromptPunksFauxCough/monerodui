"""Node statistics fetcher via RPC."""

import json
import logging
import urllib.request
import urllib.error
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class NodeStats:
    """Current node statistics."""
    incoming_connections: int = 0
    outgoing_connections: int = 0
    height: int = 0
    target_height: int = 0
    synchronized: bool = False
    database_size: int = 0
    free_space: int = 0
    version: str = ""
    update_available: bool = False
    nettype: str = "mainnet"
    difficulty: int = 0
    tx_count: int = 0
    tx_pool_size: int = 0
    bytes_in: int = 0
    bytes_out: int = 0
    busy_syncing: bool = False
    status: str = "offline"
    white_peerlist_size: int = 0
    grey_peerlist_size: int = 0
    block_reward: int = 0
    block_time: int = 0
    hashrate: int = 0
    fee_estimate: int = 0
    
    @property
    def total_connections(self) -> int:
        return self.incoming_connections + self.outgoing_connections
    
    @property
    def sync_progress(self) -> float:
        if self.target_height == 0:
            return 0.0
        if self.synchronized:
            return 100.0
        return (self.height / self.target_height) * 100
    
    @property
    def blocks_remaining(self) -> int:
        if self.synchronized:
            return 0
        return max(0, self.target_height - self.height)
    
    @property
    def database_size_gib(self) -> float:
        return self.database_size / (1024 ** 3)
    
    @property
    def free_space_gib(self) -> float:
        return self.free_space / (1024 ** 3)
    
    @property
    def bytes_in_mib(self) -> float:
        return self.bytes_in / (1024 ** 2)
    
    @property
    def bytes_out_mib(self) -> float:
        return self.bytes_out / (1024 ** 2)
    
    @property
    def difficulty_display(self) -> str:
        if self.difficulty >= 1_000_000_000_000:
            return f"{self.difficulty / 1_000_000_000_000:.2f} TH"
        elif self.difficulty >= 1_000_000_000:
            return f"{self.difficulty / 1_000_000_000:.2f} GH"
        elif self.difficulty >= 1_000_000:
            return f"{self.difficulty / 1_000_000:.2f} MH"
        else:
            return f"{self.difficulty:,}"
    
    @property
    def hashrate_display(self) -> str:
        if self.hashrate >= 1_000_000_000:
            return f"{self.hashrate / 1_000_000_000:.2f} GH/s"
        elif self.hashrate >= 1_000_000:
            return f"{self.hashrate / 1_000_000:.2f} MH/s"
        elif self.hashrate >= 1_000:
            return f"{self.hashrate / 1_000:.2f} KH/s"
        else:
            return f"{self.hashrate} H/s"
    
    @property
    def fee_display(self) -> str:
        if self.fee_estimate == 0:
            return "--"
        xmr = self.fee_estimate / 1_000_000_000_000
        if xmr < 0.0001:
            return f"{xmr:.8f}"
        return f"{xmr:.6f}"
    
    @property
    def block_reward_display(self) -> str:
        if self.block_reward == 0:
            return "--"
        xmr = self.block_reward / 1_000_000_000_000
        return f"{xmr:.4f}"


@dataclass
class VersionInfo:
    """Version information from daemon."""
    current_version: str = ""
    update_available: bool = False
    latest_version: str = ""
    download_url: str = ""


class NodeStatsPoller:
    """Polls node RPC for statistics."""
    
    BLOCK_TIME_TARGET = 120
    
    def __init__(self, host: str = "127.0.0.1", port: int = 18081):
        self.host = host
        self.port = port
        self._last_stats: Optional[NodeStats] = None
        self._version_info: Optional[VersionInfo] = None
    
    @property
    def rpc_url(self) -> str:
        return f"http://{self.host}:{self.port}/json_rpc"
    
    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"
    
    def _rpc_call(self, method: str, params: dict = None) -> Optional[dict]:
        payload = {
            "jsonrpc": "2.0",
            "id": "0",
            "method": method,
        }
        if params:
            payload["params"] = params
        
        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                self.rpc_url,
                data=data,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                return result.get("result")
        except urllib.error.URLError as e:
            logger.debug(f"RPC connection error: {e}")
            return None
        except TimeoutError:
            logger.debug("RPC timeout")
            return None
        except json.JSONDecodeError as e:
            logger.warning(f"Invalid JSON response: {e}")
            return None
    
    def _http_call(self, endpoint: str) -> Optional[dict]:
        try:
            url = f"{self.base_url}/{endpoint}"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as e:
            logger.debug(f"HTTP connection error for {endpoint}: {e}")
            return None
        except TimeoutError:
            logger.debug(f"HTTP timeout for {endpoint}")
            return None
        except json.JSONDecodeError as e:
            logger.warning(f"Invalid JSON response from {endpoint}: {e}")
            return None

    def poll(self) -> NodeStats:
        stats = NodeStats()
        
        info = self._rpc_call("get_info")
        if info:
            stats.status = info.get("status", "unknown")
            stats.height = info.get("height", 0)
            stats.target_height = info.get("target_height", 0) or stats.height
            stats.incoming_connections = info.get("incoming_connections_count", 0)
            stats.outgoing_connections = info.get("outgoing_connections_count", 0)
            stats.synchronized = info.get("synchronized", False)
            stats.busy_syncing = info.get("busy_syncing", False)
            stats.database_size = info.get("database_size", 0)
            stats.free_space = info.get("free_space", 0)
            stats.version = info.get("version", "")
            stats.update_available = info.get("update_available", False)
            stats.nettype = info.get("nettype", "mainnet")
            stats.difficulty = info.get("difficulty", 0)
            stats.tx_count = info.get("tx_count", 0)
            stats.tx_pool_size = info.get("tx_pool_size", 0)
            stats.white_peerlist_size = info.get("white_peerlist_size", 0)
            stats.grey_peerlist_size = info.get("grey_peerlist_size", 0)
            
            if stats.difficulty > 0:
                stats.hashrate = stats.difficulty // self.BLOCK_TIME_TARGET
        else:
            stats.status = "offline"
            self._last_stats = stats
            return stats
        
        if not stats.busy_syncing:
            net_stats = self._http_call("get_net_stats")
            if net_stats:
                stats.bytes_in = net_stats.get("total_bytes_in", 0)
                stats.bytes_out = net_stats.get("total_bytes_out", 0)
            
            last_header = self._rpc_call("get_last_block_header")
            if last_header and "block_header" in last_header:
                header = last_header["block_header"]
                stats.block_reward = header.get("reward", 0)
                stats.block_time = header.get("timestamp", 0)
            
            fee_info = self._rpc_call("get_fee_estimate")
            if fee_info:
                stats.fee_estimate = fee_info.get("fee", 0)
        
        self._last_stats = stats
        return stats
    
    def check_update(self) -> VersionInfo:
        version_info = VersionInfo()
        
        info = self._rpc_call("get_info")
        if info:
            version_info.current_version = info.get("version", "")
            version_info.update_available = info.get("update_available", False)
        
        update_info = self._rpc_call("get_update", {"command": "check"})
        if update_info:
            version_info.update_available = update_info.get("update", False)
            version_info.latest_version = update_info.get("version", "")
            version_info.download_url = update_info.get("user_uri", "")
        
        self._version_info = version_info
        return version_info
    
    @property
    def last_stats(self) -> Optional[NodeStats]:
        return self._last_stats
    
    @property
    def version_info(self) -> Optional[VersionInfo]:
        return self._version_info
