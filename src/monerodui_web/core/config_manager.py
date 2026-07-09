"""INI config loader/saver shared with the Kivy app.

The on-disk format is `configparser` INI at
`~/.config/monerodui/monerodui.ini`. The defaults dict and the
`get_extra_args()` translator are ported verbatim from the Kivy
`monerodui.main.monerodUIApp` so the two apps produce identical
monerod command lines from identical config files.

Configuration Variables
-----------------------
The only deployment-specific path baked in here is the config file
location. To redirect for testing or non-standard deployments, change:

    CONFIG_DIR  = Path.home() / ".config" / "monerodui"   # <<USER MUST SET if non-default>>
    CONFIG_FILE = CONFIG_DIR / "monerodui.ini"            # <<USER MUST SET if non-default>>

The Kivy app uses the same location (see
`src/monerodui/main.py:131-133`). Changing one side without the other
breaks shared-config behavior.
"""

from __future__ import annotations

import configparser
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# --- Configuration Variables ----------------------------------------------
CONFIG_DIR: Path = Path.home() / ".config" / "monerodui"
CONFIG_FILE: Path = CONFIG_DIR / "monerodui.ini"
# --------------------------------------------------------------------------


class ConfigManager:
    """Thin wrapper around `configparser.ConfigParser`.

    Differs from the Kivy `ConfigParser` wrapper in that there is no
    notify-on-change behavior — UI refresh is driven separately by the
    NiceGUI `@ui.refreshable` mechanism.
    """

    def __init__(self, config_path: Path = CONFIG_FILE) -> None:
        self.config_path: Path = config_path
        # `interpolation=None` matches Kivy's parser (avoids `%` issues
        # in values like log filenames and access-control-origins).
        self.config: configparser.ConfigParser = configparser.ConfigParser(
            interpolation=None
        )

    # ---- Load / save ----------------------------------------------------

    def load(self) -> None:
        """Read INI from disk if present, then apply defaults for any
        missing section/key. Writes back if anything was added."""
        if self.config_path.exists():
            try:
                self.config.read(self.config_path, encoding="utf-8")
                logger.info(f"Loaded config: {self.config_path}")
            except (OSError, configparser.Error) as e:
                logger.error(f"Failed to read config {self.config_path}: {e}")

        dirty = self._apply_defaults()
        if dirty:
            self.save()
            logger.info("Config repaired with default values and saved")

    def save(self) -> None:
        """Write current config to disk. Creates parent directory."""
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, "w", encoding="utf-8") as fp:
                self.config.write(fp)
        except OSError as e:
            logger.error(f"Failed to save config {self.config_path}: {e}")

    def _apply_defaults(self) -> bool:
        """Ensure every default section/key exists. Returns True if any
        value was inserted."""
        defaults = self.get_all_defaults()
        dirty = False
        for section, options in defaults.items():
            if not self.config.has_section(section):
                self.config.add_section(section)
                dirty = True
            for key, value in options.items():
                if not self.config.has_option(section, key):
                    self.config.set(section, key, value)
                    dirty = True
        return dirty

    # ---- Typed accessors ------------------------------------------------

    def get(
        self,
        section: str,
        key: str,
        fallback: Optional[str] = None,
    ) -> str:
        try:
            return self.config.get(section, key, fallback=fallback)
        except (configparser.NoSectionError, configparser.NoOptionError):
            return fallback if fallback is not None else ""

    def getint(self, section: str, key: str, fallback: int = 0) -> int:
        try:
            return self.config.getint(section, key, fallback=fallback)
        except (configparser.NoSectionError, configparser.NoOptionError, ValueError):
            return fallback

    def getboolean(self, section: str, key: str, fallback: bool = False) -> bool:
        # The INI uses "0"/"1" rather than True/False, so route through
        # the string getter for portability with the Kivy app's writes.
        raw = self.get(section, key, fallback="1" if fallback else "0")
        return str(raw).strip().lower() in ("1", "true", "yes", "on")

    def set(self, section: str, key: str, value: str) -> None:
        if not self.config.has_section(section):
            self.config.add_section(section)
        self.config.set(section, key, str(value))

    # ---- Defaults dict (ported verbatim from Kivy main.py) -------------

    def get_all_defaults(self) -> dict[str, dict[str, str]]:
        """Return the canonical defaults dict.

        Ported verbatim from `monerodui.main.monerodUIApp.build_config`
        (src/monerodui/main.py:148-263) and merged with the slightly
        differing `_ensure_config_integrity` dict (lines 571-626). The
        only divergence between the two Kivy methods is `storage`:
            build_config:             "min_free_gib": "10.0"
            _ensure_config_integrity: "min_free_gib": "50.0"
        We follow `_ensure_config_integrity` because that is the value
        the Kivy app rewrites on every startup (it overwrites the
        `build_config` value at on_start).
        """
        return {
            "network": {
                "network_type": "mainnet",
                "offline": "0",
                "no_sync": "0",
                "public_node": "0",
                "sync_pruned_blocks": "1",
                "pad_transactions": "0",
            },
            "p2p": {
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
                "ban_list": "",
            },
            "bandwidth": {
                "limit_rate_up": "8192",
                "limit_rate_down": "32768",
            },
            "rpc": {
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
                "disable_ban": "0",
            },
            "rpcssl": {
                "mode": "autodetect",
                "private_key": "",
                "certificate": "",
                "ca_certificates": "",
                "allow_any_cert": "0",
                "allow_chained": "0",
            },
            "zmq": {
                "disabled": "0",
                "bind_ip": "127.0.0.1",
                "bind_port": "18082",
                "pub": "",
            },
            "proxy": {
                "address": "",
                "allow_dns_leaks": "0",
                "tx_proxy": "",
                "anonymous_inbound": "",
            },
            "bootstrap": {
                "address": "",
                "login": "",
                "proxy": "",
            },
            "blockchain": {
                "prune": "1",
                "fast_block_sync": "1",
                "db_sync_mode": "fast:async:250000000bytes",
                "db_salvage": "0",
                "block_sync_size": "0",
                "keep_alt_blocks": "0",
                "max_txpool_weight": "648000000",
            },
            "dns": {
                "enforce_checkpoints": "0",
                "disable_checkpoints": "0",
                "enable_blocklist": "0",
                "check_updates": "notify",
            },
            "nat": {
                "igd": "delayed",
            },
            "mining": {
                "address": "",
                "threads": "0",
                "bg_enable": "0",
                "bg_ignore_battery": "0",
                "bg_idle_threshold": "0",
                "bg_miner_target": "0",
            },
            "logging": {
                "file": "",
                "level": "0",
                "max_file_size": "104850000",
                "max_files": "50",
            },
            "performance": {
                "max_concurrency": "0",
                "prep_blocks_threads": "4",
            },
            "notify": {
                "block_enabled": "0",
                "reorg_enabled": "0",
            },
            "advanced": {
                "config_file": "",
                "data_dir": "",
                "non_interactive": "1",
                "extra_messages_file": "",
            },
            "runtime": {
                "extra_flags": "",
                "auto_start": "0",
                "enable_boot": "0",
            },
            "storage": {
                "min_free_gib": "50.0",
                "preferred_path": "",
            },
            "state": {
                "was_running": "0",
            },
        }

    # ---- monerod CLI args translator ------------------------------------

    def get_extra_args(self) -> list[str]:
        """Translate the loaded config into monerod CLI arguments.

        Ported verbatim from `monerodui.main.monerodUIApp._get_extra_args`
        (src/monerodui/main.py:894-1165). The only difference is that
        `self.config` here is a plain `configparser.ConfigParser` rather
        than Kivy's wrapper. Every section translation and every flag
        is preserved so the two apps produce identical monerod
        command lines from the same INI file.
        """
        args: list[str] = []

        args.append("--non-interactive")

        # ---- network ----
        net_type = self.get("network", "network_type")
        if net_type == "testnet":
            args.append("--testnet")
        elif net_type == "stagenet":
            args.append("--stagenet")

        if self.get("network", "offline") == "1":
            args.append("--offline")
        if self.get("network", "no_sync") == "1":
            args.append("--no-sync")
        if self.get("network", "public_node") == "1":
            args.append("--public-node")
        if self.get("network", "sync_pruned_blocks") == "1":
            args.append("--sync-pruned-blocks")
        if self.get("network", "pad_transactions") == "1":
            args.append("--pad-transactions")

        # ---- p2p ----
        bind_ip = self.get("p2p", "bind_ip")
        if bind_ip and bind_ip != "0.0.0.0":
            args.extend(["--p2p-bind-ip", bind_ip])

        bind_port = self.get("p2p", "bind_port")
        if bind_port and bind_port != "18080":
            args.extend(["--p2p-bind-port", bind_port])

        if self.get("p2p", "use_ipv6") == "1":
            args.append("--p2p-use-ipv6")

        ext_port = self.get("p2p", "external_port")
        if ext_port and ext_port != "0":
            args.extend(["--p2p-external-port", ext_port])

        out_peers = self.get("p2p", "out_peers")
        if out_peers and out_peers != "-1":
            args.extend(["--out-peers", out_peers])

        in_peers = self.get("p2p", "in_peers")
        if in_peers and in_peers != "-1":
            args.extend(["--in-peers", in_peers])

        max_conns = self.get("p2p", "max_connections_per_ip")
        if max_conns and max_conns != "1":
            args.extend(["--max-connections-per-ip", max_conns])

        if self.get("p2p", "hide_my_port") == "1":
            args.append("--hide-my-port")
        if self.get("p2p", "allow_local_ip") == "1":
            args.append("--allow-local-ip")

        priority_nodes = self.get("p2p", "priority_nodes")
        if priority_nodes:
            for node in priority_nodes.split(","):
                if node.strip():
                    args.extend(["--add-priority-node", node.strip()])

        exclusive_nodes = self.get("p2p", "exclusive_nodes")
        if exclusive_nodes:
            for node in exclusive_nodes.split(","):
                if node.strip():
                    args.extend(["--add-exclusive-node", node.strip()])

        seed_nodes = self.get("p2p", "seed_nodes")
        if seed_nodes:
            args.extend(["--seed-node", seed_nodes])

        ban_list = self.get("p2p", "ban_list")
        if ban_list:
            args.extend(["--ban-list", ban_list])

        # ---- bandwidth ----
        limit_up = self.get("bandwidth", "limit_rate_up")
        if limit_up and limit_up != "8192":
            args.extend(["--limit-rate-up", limit_up])

        limit_down = self.get("bandwidth", "limit_rate_down")
        if limit_down and limit_down != "32768":
            args.extend(["--limit-rate-down", limit_down])

        # ---- rpc ----
        rpc_bind_ip = self.get("rpc", "bind_ip")
        if rpc_bind_ip:
            args.extend(["--rpc-bind-ip", rpc_bind_ip])

        rpc_bind_port = self.get("rpc", "bind_port")
        if rpc_bind_port:
            args.extend(["--rpc-bind-port", rpc_bind_port])

        res_bind_ip = self.get("rpc", "restricted_bind_ip")
        if res_bind_ip and res_bind_ip != "127.0.0.1":
            args.extend(["--rpc-restricted-bind-ip", res_bind_ip])

        res_bind_port = self.get("rpc", "restricted_bind_port")
        if res_bind_port and res_bind_port != "0":
            args.extend(["--rpc-restricted-bind-port", res_bind_port])

        if self.get("rpc", "restricted") == "1":
            args.append("--restricted-rpc")
        if self.get("rpc", "use_ipv6") == "1":
            args.append("--rpc-use-ipv6")

        rpc_login = self.get("rpc", "login")
        if rpc_login:
            args.extend(["--rpc-login", rpc_login])

        if self.get("rpc", "confirm_external_bind") == "1":
            args.append("--confirm-external-bind")

        cors = self.get("rpc", "access_control_origins")
        if cors:
            args.extend(["--rpc-access-control-origins", cors])

        if self.get("rpc", "disable_ban") == "1":
            args.append("--disable-rpc-ban")

        # ---- rpcssl ----
        ssl_mode = self.get("rpcssl", "mode")
        if ssl_mode == "enabled":
            args.extend(["--rpc-ssl", "enabled"])
        elif ssl_mode == "disabled":
            args.extend(["--rpc-ssl", "disabled"])

        ssl_key = self.get("rpcssl", "private_key")
        if ssl_key:
            args.extend(["--rpc-ssl-private-key", ssl_key])

        ssl_cert = self.get("rpcssl", "certificate")
        if ssl_cert:
            args.extend(["--rpc-ssl-certificate", ssl_cert])

        ca_certs = self.get("rpcssl", "ca_certificates")
        if ca_certs:
            args.extend(["--rpc-ssl-ca-certificates", ca_certs])

        if self.get("rpcssl", "allow_any_cert") == "1":
            args.append("--rpc-ssl-allow-any-cert")
        if self.get("rpcssl", "allow_chained") == "1":
            args.append("--rpc-ssl-allow-chained")

        # ---- zmq ----
        if self.get("zmq", "disabled") == "1":
            args.append("--no-zmq")
        else:
            zmq_ip = self.get("zmq", "bind_ip")
            zmq_port = self.get("zmq", "bind_port")
            if zmq_ip and zmq_port:
                args.extend(
                    ["--zmq-rpc-bind-ip", zmq_ip, "--zmq-rpc-bind-port", zmq_port]
                )

            zmq_pub = self.get("zmq", "pub")
            if zmq_pub:
                args.extend(["--zmq-pub", zmq_pub])

        # ---- proxy ----
        proxy = self.get("proxy", "address")
        if proxy:
            args.extend(["--proxy", proxy])

        if self.get("proxy", "allow_dns_leaks") == "1":
            args.append("--allow-dns-leaks")

        tx_proxy = self.get("proxy", "tx_proxy")
        if tx_proxy:
            args.extend(["--tx-proxy", tx_proxy])

        anon_inbound = self.get("proxy", "anonymous_inbound")
        if anon_inbound:
            args.extend(["--anonymous-inbound", anon_inbound])

        # ---- bootstrap ----
        boot_addr = self.get("bootstrap", "address")
        if boot_addr:
            args.extend(["--bootstrap-daemon-address", boot_addr])

        boot_login = self.get("bootstrap", "login")
        if boot_login:
            args.extend(["--bootstrap-daemon-login", boot_login])

        boot_proxy = self.get("bootstrap", "proxy")
        if boot_proxy:
            args.extend(["--bootstrap-daemon-proxy", boot_proxy])

        # ---- blockchain ----
        if self.get("blockchain", "prune") == "1":
            args.append("--prune-blockchain")

        db_sync = self.get("blockchain", "db_sync_mode")
        if db_sync:
            args.extend(["--db-sync-mode", db_sync])

        if self.get("blockchain", "db_salvage") == "1":
            args.append("--db-salvage")

        if self.get("blockchain", "fast_block_sync") == "1":
            args.append("--fast-block-sync=1")
        else:
            args.append("--fast-block-sync=0")

        if self.get("blockchain", "keep_alt_blocks") == "1":
            args.append("--keep-alt-blocks")

        max_txpool_weight = self.get("blockchain", "max_txpool_weight")
        if max_txpool_weight and max_txpool_weight != "648000000":
            args.extend(["--max-txpool-weight", max_txpool_weight])

        # ---- dns ----
        if self.get("dns", "enforce_checkpoints") == "1":
            args.append("--enforce-dns-checkpoints")
        if self.get("dns", "disable_checkpoints") == "1":
            args.append("--disable-dns-checkpoints")
        if self.get("dns", "enable_blocklist") == "1":
            args.append("--enable-dns-blocklist")

        check_updates = self.get("dns", "check_updates")
        if check_updates:
            args.extend(["--check-updates", check_updates])

        # ---- nat ----
        igd = self.get("nat", "igd")
        if igd:
            args.extend(["--igd", igd])

        # ---- mining ----
        mine_addr = self.get("mining", "address")
        mine_threads = self.get("mining", "threads")
        if mine_addr and mine_threads and mine_threads != "0":
            args.extend(
                ["--start-mining", mine_addr, "--mining-threads", mine_threads]
            )

        if self.get("mining", "bg_enable") == "1":
            args.append("--bg-mining-enable")
        if self.get("mining", "bg_ignore_battery") == "1":
            args.append("--bg-mining-ignore-battery")

        bg_threshold = self.get("mining", "bg_idle_threshold")
        if bg_threshold and bg_threshold != "0":
            args.extend(["--bg-mining-miner-target", bg_threshold])

        bg_target = self.get("mining", "bg_miner_target")
        if bg_target and bg_target != "0":
            args.extend(["--bg-mining-miner-target", bg_target])

        # ---- logging ----
        log_level = self.get("logging", "level")
        if log_level:
            args.extend(["--log-level", log_level])

        max_log_size = self.get("logging", "max_file_size")
        if max_log_size and max_log_size != "104850000":
            args.extend(["--max-log-file-size", max_log_size])

        max_logs = self.get("logging", "max_files")
        if max_logs and max_logs != "50":
            args.extend(["--max-log-files", max_logs])

        # ---- performance ----
        prep_threads = self.get("performance", "prep_blocks_threads")
        if prep_threads and prep_threads != "4":
            args.extend(["--prep-blocks-threads", prep_threads])

        max_concurrency = self.get("performance", "max_concurrency")
        if max_concurrency and max_concurrency != "0":
            args.extend(["--max-concurrency", max_concurrency])

        # ---- advanced ----
        config_file = self.get("advanced", "config_file")
        if config_file:
            args.extend(["--config-file", config_file])

        data_dir = self.get("advanced", "data_dir")
        if data_dir:
            args.extend(["--data-dir", data_dir])

        extra_messages = self.get("advanced", "extra_messages_file")
        if extra_messages:
            args.extend(["--extra-messages-file", extra_messages])

        # ---- runtime extras ----
        extra_flags = self.get("runtime", "extra_flags")
        if extra_flags:
            args.extend(extra_flags.split())

        return args


# Module-level singleton — imported as `from monerodui_web.core import config`.
config: ConfigManager = ConfigManager()
