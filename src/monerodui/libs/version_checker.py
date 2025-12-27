"""Binary version checking."""

import subprocess
import re
import os
import logging
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class BinaryVersion:
    version: str = ""
    release_name: str = ""
    build_tag: str = ""
    is_release: bool = False
    raw_output: str = ""
    
    @property
    def display_string(self) -> str:
        if self.release_name and self.version:
            return f"'{self.release_name}' (v{self.version}{self.build_tag})"
        elif self.version:
            return f"v{self.version}{self.build_tag}"
        return "Unknown"


class VersionChecker:
    """Checks binary version."""
    
    VERSION_PATTERN = re.compile(
        r"Monero '([^']+)' \(v([0-9.]+)(-\w+)?\)"
    )
    
    def __init__(self, binary_path: Optional[Path] = None):
        self.binary_path = binary_path
        self._cached_version: Optional[BinaryVersion] = None
        self._is_android = self._check_android()
    
    def _check_android(self) -> bool:
        """Check if running on Android."""
        try:
            from android import mActivity
            return True
        except ImportError:
            return 'ANDROID_ROOT' in os.environ
    
    def set_binary_path(self, path: Path):
        self.binary_path = path
        self._cached_version = None
    
    def get_version(self, force_refresh: bool = False) -> Optional[BinaryVersion]:
        if self._cached_version and not force_refresh:
            return self._cached_version
        
        if not self.binary_path or not self.binary_path.exists():
            logger.warning("Binary path not set or doesn't exist")
            return None
        
        try:
            result = subprocess.run(
                [str(self.binary_path), "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            
            output = result.stdout.strip() or result.stderr.strip()
            if output:
                version = self._parse_version(output)
                version.raw_output = output
                self._cached_version = version
                logger.info(f"Detected version: {version.display_string}")
                return version
            else:
                logger.warning("Binary returned no version output")
            
        except subprocess.TimeoutExpired:
            logger.error("Version check timed out")
        except Exception as e:
            logger.error(f"Error checking version: {e}")
        
        return None
    
    def _parse_version(self, output: str) -> BinaryVersion:
        version = BinaryVersion()
        match = self.VERSION_PATTERN.search(output)
        if match:
            version.release_name = match.group(1)
            version.version = match.group(2)
            version.build_tag = match.group(3) or ""
            version.is_release = "-release" in version.build_tag
        else:
            simple_match = re.search(r'v?(\d+\.\d+\.\d+(?:\.\d+)?)', output)
            if simple_match:
                version.version = simple_match.group(1)
        return version
    
    @property
    def cached_version(self) -> Optional[BinaryVersion]:
        return self._cached_version
