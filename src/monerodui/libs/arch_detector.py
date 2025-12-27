"""CPU architecture detection for binary selection."""

import platform
import os
import sys
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class ArchDetector:
    """Detects CPU architecture and resolves appropriate binary."""
    
    ARCH_MAP = {
        # ARM 32-bit
        "armv7l": "arm32", "armv7": "arm32", "armv8l": "arm32",
        "armeabi-v7a": "arm32", "armeabi": "arm32",
        # ARM 64-bit
        "aarch64": "arm64", "arm64": "arm64", "arm64-v8a": "arm64",
        # x86_64
        "x86_64": "amd64", "AMD64": "amd64", "x64": "amd64",
    }
    
    def __init__(self, bin_dir: Path | str = None):
        self._bin_dir = Path(bin_dir) if bin_dir else None
        self._detected_arch: Optional[str] = None
        self._binary_path: Optional[Path] = None
        self._is_android = self._check_android()
    
    def _check_android(self) -> bool:
        """Check if running on Android."""
        try:
            from android import mActivity
            return True
        except ImportError:
            return 'ANDROID_ROOT' in os.environ
    
    @property
    def is_android(self) -> bool:
        return self._is_android
    
    @property
    def raw_arch(self) -> str:
        """Raw architecture string from platform."""
        arch = platform.machine()
        
        if self._is_android and (not arch or arch == "unknown"):
            arch = self._get_android_arch()
        
        return arch or "unknown"
    
    @property
    def detected_arch(self) -> Optional[str]:
        """Normalized architecture identifier."""
        if self._detected_arch is None:
            raw = self.raw_arch.lower()
            
            self._detected_arch = self.ARCH_MAP.get(raw)
            
            if self._detected_arch is None:
                if "arm64" in raw or "aarch64" in raw:
                    self._detected_arch = "arm64"
                elif "arm" in raw:
                    self._detected_arch = "arm32"
                elif "x86_64" in raw or "amd64" in raw:
                    self._detected_arch = "amd64"
            
            logger.info(f"Detected architecture: {raw} -> {self._detected_arch}")
        
        return self._detected_arch
    
    def _get_android_arch(self) -> str:
        """Get architecture on Android."""
        try:
            import subprocess
            result = subprocess.run(
                ["getprop", "ro.product.cpu.abi"],
                capture_output=True, text=True, timeout=5
            )
            if result.stdout.strip():
                return result.stdout.strip()
        except Exception as e:
            logger.debug(f"getprop failed: {e}")
        
        import struct
        return "arm64" if struct.calcsize("P") * 8 == 64 else "arm32"
    
    @property
    def binary_path(self) -> Optional[Path]:
        """Full path to architecture-appropriate binary."""
        if self._binary_path is None:
            self._binary_path = self._resolve_binary()
        return self._binary_path
    
    def _resolve_binary(self) -> Optional[Path]:
        """Locate the correct binary."""
        if self._is_android:
            return self._resolve_android_binary()
        else:
            return self._resolve_desktop_binary()
    
    def _resolve_android_binary(self) -> Optional[Path]:
        """Resolve binary on Android."""
        arch = self.detected_arch
        if not arch:
            return None
        
        search_paths = []
        try:
            from android import mActivity
            context = mActivity.getApplicationContext()
            native_lib_dir = context.getApplicationInfo().nativeLibraryDir
            if native_lib_dir:
                search_paths.append(Path(native_lib_dir))
        except Exception as e:
            logger.warning(f"Could not get Android lib dir: {e}")
        
        binary_name = f"libmonerod_{arch}.so"
        
        for search_path in search_paths:
            binary_path = search_path / binary_name
            if binary_path.exists():
                self._ensure_executable(binary_path)
                logger.info(f"Found Android binary: {binary_path}")
                return binary_path
        
        logger.error(f"Android binary not found: {binary_name}")
        return None

    def _resolve_desktop_binary(self) -> Optional[Path]:
        """Resolve binary on desktop (Briefcase/Linux)."""
        
        if self._bin_dir and self._bin_dir.exists():
            binary_path = self._bin_dir / "monerod"
            if binary_path.exists():
                self._ensure_executable(binary_path)
                logger.info(f"Found desktop binary in bin_dir: {binary_path}")
                return binary_path
        
        project_root = Path(__file__).resolve().parent.parent
        binary_path = project_root / "monerod"
        if binary_path.exists():
            self._ensure_executable(binary_path)
            logger.info(f"Found desktop binary in project root: {binary_path}")
            return binary_path
        
        current_file = Path(__file__).resolve()
        app_root = current_file.parent.parent.parent
        binary_path = app_root / "monerod"
        
        if binary_path.exists():
            self._ensure_executable(binary_path)
            logger.info(f"Found desktop binary: {binary_path}")
            return binary_path
        
        logger.error(f"Desktop binary not found")
        return None

    def _ensure_executable(self, path: Path):
        """Ensure binary is executable."""
        if not os.access(path, os.X_OK):
            try:
                path.chmod(path.stat().st_mode | 0o755)
            except (OSError, PermissionError) as e:
                logger.warning(f"Could not chmod {path}: {e}")
    
    def is_supported(self) -> bool:
        """Check if current architecture is supported."""
        return self.detected_arch is not None
    
    def is_ready(self) -> bool:
        """Check if binary is available and executable."""
        path = self.binary_path
        return path is not None and path.exists() and os.access(path, os.X_OK)
    
    def refresh(self):
        """Clear cache and re-detect."""
        self._detected_arch = None
        self._binary_path = None
    
    def get_status(self) -> dict:
        """Return status dict for UI consumption."""
        return {
            "raw_arch": self.raw_arch,
            "detected_arch": self.detected_arch,
            "supported": self.is_supported(),
            "binary_path": str(self.binary_path) if self.binary_path else None,
            "ready": self.is_ready(),
            "is_android": self._is_android,
        }
