"""Process management for binary execution."""

import subprocess
import threading
import os
import shutil
import platform
import logging
from pathlib import Path
from typing import Optional, Callable
from enum import Enum, auto

logger = logging.getLogger(__name__)

class ProcessState(Enum):
    """Binary process states."""
    STOPPED = auto()
    STARTING = auto()
    RUNNING = auto()
    STOPPING = auto()
    ERROR = auto()


class ProcessManager:
    """Manages binary process lifecycle."""
    
    def __init__(self):
        self._process: Optional[subprocess.Popen] = None
        self._state = ProcessState.STOPPED
        self._binary_path: Optional[Path] = None
        self._working_dir: Optional[Path] = None
        self._extra_args: list[str] = []
        self._stdout_thread: Optional[threading.Thread] = None
        self._stderr_thread: Optional[threading.Thread] = None
        self._on_state_change: Optional[Callable[[ProcessState], None]] = None
        self._last_error: Optional[str] = None
        self._is_android = self._check_android()
    
    def _check_android(self) -> bool:
        """Check if running on Android."""
        try:
            from android import mActivity
            return True
        except ImportError:
            return 'ANDROID_ROOT' in os.environ
    
    @property
    def state(self) -> ProcessState:
        return self._state
    
    @property
    def is_running(self) -> bool:
        return self._state == ProcessState.RUNNING
    
    @property
    def last_error(self) -> Optional[str]:
        return self._last_error
    
    def configure(
        self,
        binary_path: Path,
        working_dir: Path,
        extra_args: Optional[list[str]] = None,
        on_state_change: Optional[Callable[[ProcessState], None]] = None,
    ):
        """Configure the process manager."""
        self._binary_path = binary_path
        self._working_dir = working_dir
        self._extra_args = extra_args or []
        self._on_state_change = on_state_change
        self._process = None
        self._state = ProcessState.STOPPED
    
    def _set_state(self, state: ProcessState):
        self._state = state
        if self._on_state_change:
            self._on_state_change(state)
    
    def _stream_output(self, stream, prefix: str):
        """Stream process output to logger."""
        try:
            for line in iter(stream.readline, b''):
                if line:
                    logger.info(f"{prefix}: {line.decode('utf-8', errors='replace').rstrip()}")
        except Exception as e:
            logger.error(f"Stream error: {e}")
        finally:
            try:
                stream.close()
            except:
                pass
   
    def _prepare_executable(self) -> Optional[Path]:
        """Prepare executable for running (Android needs special handling)."""
        if self._binary_path is None:
            return None
        
        if not self._is_android:
            return self._binary_path
        
        try:
            try:
                from android import mActivity
                context = mActivity.getApplicationContext()
                private_dir = context.getFilesDir().getAbsolutePath()
            except:
                private_dir = os.environ.get("ANDROID_PRIVATE", "/data/data/org.monerodroid/files")
            
            internal_bin_dir = Path(private_dir) / "bin"
            internal_bin_dir.mkdir(parents=True, exist_ok=True)
            
            exec_path = internal_bin_dir / "monerod"
            
            need_copy = True
            if exec_path.exists():
                if exec_path.stat().st_size == self._binary_path.stat().st_size:
                    need_copy = False
            
            if need_copy:
                logger.info(f"Copying binary: {self._binary_path} -> {exec_path}")
                shutil.copy(str(self._binary_path), str(exec_path))
            
            exec_path.chmod(0o755)
            
            if not os.access(str(exec_path), os.X_OK):
                logger.error(f"Failed to make {exec_path} executable")
                return None
            
            return exec_path
                
        except Exception as e:
            logger.error(f"Error preparing executable: {e}", exc_info=True)
            return None
    
    def start(self) -> bool:
        """Start the binary process."""
        if self._state in (ProcessState.RUNNING, ProcessState.STARTING):
            logger.warning("Process already running or starting")
            return False
        
        if self._binary_path is None:
            self._last_error = "Configuration missing"
            self._set_state(ProcessState.ERROR)
            return False
        
        # Extract data-dir from args - required
        data_dir = None
        for i, arg in enumerate(self._extra_args):
            if arg == "--data-dir" and i + 1 < len(self._extra_args):
                data_dir = self._extra_args[i + 1]
                break
        
        if not data_dir:
            self._last_error = "No --data-dir specified"
            self._set_state(ProcessState.ERROR)
            return False
        
        self._set_state(ProcessState.STARTING)
        self._last_error = None
        
        try:
            executable = self._prepare_executable()
            if executable is None:
                raise Exception("Failed to prepare executable binary")
            
            Path(data_dir).mkdir(parents=True, exist_ok=True)
            
            cmd = []
            
            if self._is_android:
                arch = platform.machine().lower()
                if "aarch64" in arch or "arm64" in arch or "v8" in arch:
                    linker = "/system/bin/linker64"
                else:
                    linker = "/system/bin/linker"
                
                if os.path.exists(linker):
                    cmd = [linker, str(executable)]
                else:
                    cmd = [str(executable)]
            else:
                cmd = [str(executable)]
            
            cmd.extend(self._extra_args)
            
            args_str = ' '.join(self._extra_args)
            if "--log-file" not in args_str:
                log_file = Path(data_dir) / "monerod.log"
                cmd.extend(["--log-file", str(log_file)])
            
            logger.info(f"Executing: {' '.join(cmd)}")
            
            env = os.environ.copy()
            env['HOME'] = data_dir
            
            if self._is_android and self._binary_path:
                lib_dir = str(self._binary_path.parent)
                current_ld = env.get('LD_LIBRARY_PATH', '')
                env['LD_LIBRARY_PATH'] = f"{lib_dir}:{current_ld}"
            
            self._process = subprocess.Popen(
                cmd,
                cwd=data_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                env=env,
            )
            
            logger.info(f"Started PID: {self._process.pid}")
            
            self._stdout_thread = threading.Thread(
                target=self._stream_output, 
                args=(self._process.stdout, "monerod"), 
                daemon=True
            )
            self._stderr_thread = threading.Thread(
                target=self._stream_output, 
                args=(self._process.stderr, "monerod-err"), 
                daemon=True
            )
            self._stdout_thread.start()
            self._stderr_thread.start()
            
            threading.Thread(target=self._monitor, daemon=True).start()
            
            self._set_state(ProcessState.RUNNING)
            return True
            
        except Exception as e:
            self._last_error = str(e)
            logger.error(f"Startup failed: {e}", exc_info=True)
            self._set_state(ProcessState.ERROR)
            return False

    def stop(self) -> bool:
        """Stop the binary process."""
        if self._process is None:
            logger.warning("No process to stop")
            return False
        
        self._set_state(ProcessState.STOPPING)
        try:
            logger.info("Terminating process")
            self._process.terminate()
            try:
                self._process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                logger.warning("Process didn't terminate, killing")
                self._process.kill()
                self._process.wait(timeout=2)
            self._process = None
            self._set_state(ProcessState.STOPPED)
            return True
        except Exception as e:
            self._last_error = str(e)
            logger.error(f"Stop failed: {e}")
            self._set_state(ProcessState.ERROR)
            return False
    
    def _monitor(self):
        """Monitor process and update state when it exits."""
        if self._process:
            rc = self._process.wait()
            logger.info(f"Process exited with code: {rc}")
            if self._state == ProcessState.RUNNING:
                if rc != 0:
                    self._last_error = f"Exited with code {rc}"
                    self._set_state(ProcessState.ERROR)
                else:
                    self._set_state(ProcessState.STOPPED)
            self._process = None
    
    def get_status(self) -> dict:
        """Return current process status."""
        return {
            "state": self._state.name,
            "is_running": self.is_running,
            "last_error": self._last_error
        }


