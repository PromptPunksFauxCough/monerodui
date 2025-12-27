"""Background service for monerod UI."""
import sys
import os
import time
import logging
import configparser
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='[SERVICE] %(message)s')
logger = logging.getLogger(__name__)

#if 'ANDROID_ROOT' in os.environ:
#    log_dir = '/storage/emulated/0/Download/'
#    try:
#        sys.stdout = open(os.path.join(log_dir, "monerod_service_log.txt"), "a", buffering=1)
#        sys.stderr = sys.stdout
#    except:
#        pass

logger.info("=== SERVICE STARTING ===")

from jnius import autoclass

PythonService = autoclass('org.kivy.android.PythonService')
service = PythonService.mService
Context = autoclass('android.content.Context')
NotificationBuilder = autoclass('android.app.Notification$Builder')
NotificationManager = autoclass('android.app.NotificationManager')
NotificationChannel = autoclass('android.app.NotificationChannel')
PendingIntent = autoclass('android.app.PendingIntent')
Intent = autoclass('android.content.Intent')
BigTextStyle = autoclass('android.app.Notification$BigTextStyle')

# Globals for notification updates
notification_manager = None
notification_builder = None
NOTIFICATION_ID = 1002
CHANNEL_ID = "monerodui_service"


def load_config():
    """Load settings from app config file."""
    config = configparser.ConfigParser()
    
    config_path = "/data/user/0/org.monerodui.monerodui/files/app/.monerodui.ini"
    
    alt_paths = [
        "/data/user/0/org.monerodui.monerodui/files/app/monerodui.ini",
        "/data/data/org.monerodui.monerodui/files/app/.monerodui.ini",
        "/data/data/org.monerodui.monerodui/files/app/monerodui.ini",
    ]
    
    if os.path.exists(config_path):
        config.read(config_path)
        logger.info(f"Loaded config from {config_path}")
    else:
        for path in alt_paths:
            if os.path.exists(path):
                config.read(path)
                logger.info(f"Loaded config from {path}")
                break
        else:
            logger.warning("Config file not found, using defaults")
    
    return config


def get_rpc_settings(config):
    """Get RPC settings from config."""
    rpc_host = config.get("rpc", "bind_ip", fallback="127.0.0.1")
    rpc_port = config.getint("rpc", "bind_port", fallback=18081)
    return rpc_host, rpc_port


def get_extra_args(config):
    """Build extra args from config."""
    args = ['--non-interactive']
    
    # Network
    net_type = config.get("network", "network_type", fallback="mainnet")
    if net_type == "testnet":
        args.append("--testnet")
    elif net_type == "stagenet":
        args.append("--stagenet")
    
    if config.get("network", "sync_pruned_blocks", fallback="1") == "1":
        args.append("--sync-pruned-blocks")
    
    # RPC
    rpc_host = config.get("rpc", "bind_ip", fallback="127.0.0.1")
    rpc_port = config.get("rpc", "bind_port", fallback="18081")
    args.extend(["--rpc-bind-ip", rpc_host])
    args.extend(["--rpc-bind-port", rpc_port])
    
    # ZMQ
    if config.get("zmq", "disabled", fallback="0") != "1":
        zmq_ip = config.get("zmq", "bind_ip", fallback="127.0.0.1")
        zmq_port = config.get("zmq", "bind_port", fallback="18082")
        args.extend(["--zmq-rpc-bind-ip", zmq_ip])
        args.extend(["--zmq-rpc-bind-port", zmq_port])
    else:
        args.append("--no-zmq")
    
    # Blockchain
    if config.get("blockchain", "prune", fallback="1") == "1":
        args.append("--prune-blockchain")
    
    db_sync = config.get("blockchain", "db_sync_mode", fallback="fast:async:250000000bytes")
    if db_sync:
        args.extend(["--db-sync-mode", db_sync])
    
    if config.get("blockchain", "fast_block_sync", fallback="1") == "1":
        args.append("--fast-block-sync=1")
    else:
        args.append("--fast-block-sync=0")
    
    # DNS
    check_updates = config.get("dns", "check_updates", fallback="notify")
    if check_updates:
        args.extend(["--check-updates", check_updates])
    
    # NAT
    igd = config.get("nat", "igd", fallback="delayed")
    if igd:
        args.extend(["--igd", igd])
    
    # Logging
    log_level = config.get("logging", "level", fallback="0")
    args.extend(["--log-level", log_level])
    
    return args


def create_notification():
    global notification_manager, notification_builder
    
    try:
        app_context = service.getApplicationContext()
        notification_manager = service.getSystemService(Context.NOTIFICATION_SERVICE)
        
        # Create channel
        channel = NotificationChannel(CHANNEL_ID, "monerod Service", NotificationManager.IMPORTANCE_LOW)
        channel.setDescription("Shows node sync status")
        notification_manager.createNotificationChannel(channel)
        
        # Create pending intent for tap action
        package_name = app_context.getPackageName()
        intent = service.getPackageManager().getLaunchIntentForPackage(package_name)
        intent.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP)
        
        pending_intent = PendingIntent.getActivity(
            service, 0, intent, 67108864  # FLAG_IMMUTABLE
        )
        
        # Create initial notification
        notification_builder = NotificationBuilder(service, CHANNEL_ID)
        notification_builder.setContentTitle("monerod UI")
        notification_builder.setContentText("Starting...")
        notification_builder.setSmallIcon(app_context.getApplicationInfo().icon)
        notification_builder.setContentIntent(pending_intent)
        notification_builder.setOngoing(True)
        notification_builder.setProgress(100, 0, True)  #  indeterminate initially
        
        service.startForeground(NOTIFICATION_ID, notification_builder.build())
        logger.info("Foreground notification active")
        
    except Exception as e:
        logger.error(f"Notification failed: {e}")


def update_notification(stats, rpc_host, rpc_port):
    global notification_manager, notification_builder
    
    if not notification_builder or not notification_manager:
        return
    
    try:
        if stats.status == "offline":
            notification_builder.setContentTitle("monerod UI")
            notification_builder.setContentText("Node offline")
            notification_builder.setProgress(0, 0, False)
            notification_builder.setStyle(None)
        else:
            progress = int(stats.sync_progress)
            blocks_remaining = stats.blocks_remaining
            
            if blocks_remaining > 0:
                blocks_text = f"{blocks_remaining:,} Blocks Remaining"
            else:
                blocks_text = "Synchronized"
            
            rpc_text = f"RPC: {rpc_host}:{rpc_port}"
            
            if stats.synchronized:
                title = "monerod UI - Synchronized"
            else:
                title = f"monerod UI - {progress}%"
            
            big_text = f"{blocks_text}\n\n{rpc_text}"
            
            style = BigTextStyle()
            style.bigText(big_text)
            style.setBigContentTitle(title)
            
            notification_builder.setContentTitle(title)
            notification_builder.setContentText(blocks_text)
            notification_builder.setStyle(style)
            
            if stats.synchronized:
                notification_builder.setProgress(0, 0, False)
            else:
                notification_builder.setProgress(100, progress, False)
        
        notification_manager.notify(NOTIFICATION_ID, notification_builder.build())
        
    except Exception as e:
        logger.error(f"Failed to update notification: {e}")


create_notification()

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

try:
    from libs.process_manager import ProcessManager
except ImportError:
    try:
        from monerodui.libs.process_manager import ProcessManager
    except ImportError:
        logger.error("Could not import ProcessManager")
        ProcessManager = None

try:
    from libs.node_stats import NodeStatsPoller
except ImportError:
    try:
        from monerodui.libs.node_stats import NodeStatsPoller
    except ImportError:
        logger.error("Could not import NodeStatsPoller")
        NodeStatsPoller = None


def main():
    logger.info("Service main() entered")
    
    if not ProcessManager:
        logger.error("ProcessManager unavailable, service exiting")
        return

    config = load_config()
    
    rpc_host, rpc_port = get_rpc_settings(config)
    logger.info(f"RPC settings: {rpc_host}:{rpc_port}")
    
    extra_args = get_extra_args(config)
    logger.info(f"Extra args: {extra_args}")

    files_dir = "/data/user/0/org.monerodui.monerodui/files"
    binary_path = Path(files_dir) / "bin" / "monerod"
    working_dir = Path("/storage/emulated/0/Download/.monerod")

    pm = ProcessManager()
    pm.configure(binary_path=binary_path, working_dir=working_dir, extra_args=extra_args)
    
    poller = None
    if NodeStatsPoller:
        poller = NodeStatsPoller(host=rpc_host, port=rpc_port)

    time.sleep(3)
    
    last_notification_update = 0
    NOTIFICATION_INTERVAL = 10

    while True:
        if not pm.is_running:
            logger.info("monerod not running. Attempting start...")
            success = pm.start()
            if success:
                logger.info("monerod started successfully")
            else:
                logger.error(f"Failed to start: {pm.last_error}")
                time.sleep(10)
        
        now = time.time()
        if poller and (now - last_notification_update) >= NOTIFICATION_INTERVAL:
            try:
                stats = poller.poll()
                update_notification(stats, rpc_host, rpc_port)
                last_notification_update = now
            except Exception as e:
                logger.error(f"Failed to poll stats: {e}")
        
        time.sleep(5)


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        logger.critical(f"Service crashed: {e}", exc_info=True)


