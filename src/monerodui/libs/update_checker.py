"""Remote update checking via MoneroPulse DNS."""

import json
import logging
import urllib.request
import urllib.error
from dataclasses import dataclass
from typing import Optional, Tuple

import os
if 'ANDROID_ROOT' in os.environ:
    os.environ['SSL_CERT_FILE'] = '/etc/security/cacerts'

from .version_checker import VersionChecker

logger = logging.getLogger(__name__)


@dataclass
class UpdateStatus:
    local_version: str = ""
    remote_version: str = ""
    remote_hash: str = ""
    update_available: bool = False
    error: str = ""

    @property
    def current_version(self) -> str:
        return self.local_version

    @property
    def latest_version(self) -> str:
        return self.remote_version


class UpdateChecker:
    """Checks for updates via MoneroPulse DNS-over-HTTPS."""
    
    DNS_URL = "https://dns.google/resolve?name=updates.moneropulse.org&type=TXT"
    
    def __init__(self, version_checker: VersionChecker, is_android: bool = False, arch: str = "amd64"):
        self._version_checker = version_checker
        self._is_android = is_android
        self._arch = arch
        self._cached_status: Optional[UpdateStatus] = None
    
    def check(self, force: bool = False) -> UpdateStatus:
        if self._cached_status and not force:
            return self._cached_status
        
        status = UpdateStatus()
        
        local = self._version_checker.cached_version
        if not local or not local.version:
            status.error = "Local version unavailable"
            logger.warning(status.error)
            return status
        
        status.local_version = local.version
        
        remote = self._fetch_remote_version()
        if not remote:
            status.error = "Failed to fetch remote version"
            return status
        
        status.remote_version, status.remote_hash = remote
        status.update_available = self._compare(status.local_version, status.remote_version)
        
        if status.update_available:
            logger.info(f"Update available: {status.local_version} -> {status.remote_version}")
        else:
            logger.debug(f"Up to date: {status.local_version} >= {status.remote_version}")
        
        self._cached_status = status
        return status
    
    def _get_dns_target(self) -> str:
        if self._is_android:
            if self._arch == "arm64":
                return "monero:android-armv8:"
            else:
                return "monero:android-armv7:"
        return "monero:linux-x64:"

    def _fetch_remote_version(self) -> Optional[Tuple[str, str]]:
            if self._is_android:
                from jnius import autoclass
                URL = autoclass('java.net.URL')
                
                url = URL("https://dns.google/resolve?name=updates.moneropulse.org&type=TXT")
                conn = url.openConnection()
                stream = conn.getInputStream()
                reader = autoclass('java.io.BufferedReader')(autoclass('java.io.InputStreamReader')(stream))
                response = reader.readLine()
                reader.close()

                data = json.loads(response)

                answers = data.get("Answer", [])
                if not answers:
                    logger.warning("No DNS TXT records returned")
                    return None

                target = self._get_dns_target()
                for answer in answers:
                    raw = answer.get("data", "").strip('"')
                    if raw.startswith(target):
                        parts = raw.split(":")
                        if len(parts) == 4:
                            return parts[2], parts[3]

                logger.warning(f"No matching platform in DNS records for {target}")
                return None

            else:
                try:
                    req = urllib.request.Request(self.DNS_URL, headers={"Accept": "application/json"})
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        data = json.loads(resp.read().decode())
                    
                    answers = data.get("Answer", [])
                    if not answers:
                        logger.warning("No DNS TXT records returned")
                        return None
                    
                    target = self._get_dns_target()
                    for answer in answers:
                        raw = answer.get("data", "").strip('"')
                        if raw.startswith(target):
                            parts = raw.split(":")
                            if len(parts) == 4:
                                return parts[2], parts[3]
                    
                    logger.warning(f"No matching platform in DNS records for {target}")
                    return None
                
                except (urllib.error.URLError, TimeoutError) as e:
                    logger.error(f"DNS fetch failed: {e}")
                    return None
        
                except (json.JSONDecodeError, KeyError, ValueError) as e:
                    logger.error(f"DNS parse failed: {e}")
                    return None

    def _compare(self, local: str, remote: str) -> bool:
        try:
            local_t = tuple(map(int, local.split(".")))
            remote_t = tuple(map(int, remote.split(".")))
            return local_t < remote_t
        except ValueError:
            logger.warning(f"Version parse failed: local={local}, remote={remote}")
            return False
