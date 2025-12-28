"""Network interface detection for RPC/ZMQ binding."""

import logging
import os
import socket
from typing import Optional

logger = logging.getLogger(__name__)


class NetworkInfo:
    
    INTERFACE_PRIORITY = [
        # Linux eth
        "eth", "enp", "eno", "ens",
        # Linux wifi
        "wlan", "wlp",
        # Android mobile data
        "rmnet", "ccmni",
    ]
    
    def __init__(self):
        self._is_android = self._check_android()
        self._cached_ip: Optional[str] = None
    
    def _check_android(self) -> bool:
        try:
            from android import mActivity
            return True
        except ImportError:
            return 'ANDROID_ROOT' in os.environ
    
    @property
    def is_android(self) -> bool:
        return self._is_android
    
    def get_device_ip(self) -> Optional[str]:
        if self._cached_ip is not None:
            return self._cached_ip
        
        if self._is_android:
            ip = self._get_android_ip()
        else:
            ip = self._get_desktop_ip()
        
        self._cached_ip = ip
        logger.info(f"Detected device IP: {ip}")
        return ip
    
    def _get_desktop_ip(self) -> Optional[str]:
        try:
            import netifaces
            return self._get_ip_via_netifaces(netifaces)
        except ImportError:
            logger.debug("netifaces not available, using socket fallback")
            return self._get_ip_via_socket()
    
    def _get_ip_via_netifaces(self, netifaces) -> Optional[str]:
        interfaces = netifaces.interfaces()
        
        def priority_key(iface: str) -> tuple:
            for idx, prefix in enumerate(self.INTERFACE_PRIORITY):
                if iface.startswith(prefix):
                    return (idx, iface)
            return (999, iface)
        
        sorted_interfaces = sorted(interfaces, key=priority_key)
        
        for iface in sorted_interfaces:
            try:
                addrs = netifaces.ifaddresses(iface)
                if netifaces.AF_INET in addrs:
                    for addr_info in addrs[netifaces.AF_INET]:
                        ip = addr_info.get('addr')
                        if ip and not ip.startswith('127.'):
                            logger.debug(f"Found IP {ip} on {iface}")
                            return ip
            except (ValueError, KeyError) as e:
                logger.debug(f"Error reading {iface}: {e}")
                continue
        
        return None
    
    def _get_ip_via_socket(self) -> Optional[str]:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.settimeout(1)
                # check route
                s.connect(("8.8.8.8", 80))
                ip = s.getsockname()[0]
                if ip and not ip.startswith('127.'):
                    return ip
        except (socket.error, OSError) as e:
            logger.debug(f"Socket fallback failed: {e}")
        
        return None
    
    def _get_android_ip(self) -> Optional[str]:
        ip = self._get_android_wifi_ip()
        if ip:
            return ip
        
        return self._get_ip_via_socket()
    
    def _get_android_wifi_ip(self) -> Optional[str]:
        try:
            from jnius import autoclass
            
            Context = autoclass('android.content.Context')
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            
            activity = PythonActivity.mActivity
            wifi_manager = activity.getSystemService(Context.WIFI_SERVICE)
            wifi_info = wifi_manager.getConnectionInfo()
            ip_int = wifi_info.getIpAddress()
            
            if ip_int and ip_int != 0:
                ip = self._int_to_ip(ip_int)
                if not ip.startswith('127.'):
                    logger.debug(f"Android WiFi IP: {ip}")
                    return ip
        except Exception as e:
            logger.debug(f"Android WifiManager failed: {e}")
        
        return None
    
    def _int_to_ip(self, ip_int: int) -> str:
        return f"{ip_int & 0xFF}.{(ip_int >> 8) & 0xFF}.{(ip_int >> 16) & 0xFF}.{(ip_int >> 24) & 0xFF}"
    
    def refresh(self):
        self._cached_ip = None
    
    def get_display_value(self) -> str:
        ip = self.get_device_ip()
        return ip if ip else "No Ext Net"
