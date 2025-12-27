# monerod UI

A cross-platform graphical user interface for running and managing a Monero daemon (monerod) on Android and Linux desktop systems.

## Features

- **Cross-Platform**: Native builds for Android and Linux
- **Automatic Architecture Detection**: Detects ARM32, ARM64, and x86_64 architectures
- **Storage Management**: 
  - Flexible storage location selection
  - SD card support on Android
  - Automatic free space validation
  - Minimum 10 GiB requirement (configurable)
- **Process Management**: 
  - Start/stop monerod daemon
  - Android linker compatibility
  - Background service support
- **Real-time Statistics**:
  - Block height and sync progress
  - Network connections (incoming/outgoing)
  - Blockchain database size
  - Network bandwidth monitoring
  - Difficulty and transaction pool stats
- **Version Tracking**: Binary version detection and update notifications
- **Material Design UI**: Clean, modern interface using KivyMD
- **Configurable**: Extensive settings for network, RPC, P2P, mining, and more

## Screenshots

*Coming soon*

## Requirements

### Android
- Android 5.0 (API 21) or higher
- ARM32, ARM64, or x86_64 architecture
- ~100+ GiB free storage for pruned node (default)
- ~300+ GiB free storage for full blockchain
- "Allow display over other apps" permission (for "Start on Boot")
- "All Files Access" permission (for persistent storage)

### Linux
- Ubuntu 18.04+ / Debian 10+ / similar distribution
- Python 3.11+
- ~300 GiB free storage (for full blockchain)

## Installation

### Android

1. Download the latest APK from [Releases](https://github.com/yourusername/monerodui/releases)
2. Enable "Install from Unknown Sources" in Android settings
3. Install the APK
4. Grant notifications & storage permission when prompted
5. Select storage location (internal or external)
6. Start monerod

### Linux

1. Download the latest AppImage from [Releases](https://github.com/yourusername/monerodui/releases)
2. Make it executable:
   ```bash
   chmod +x monerodui-*.AppImage
   ```
3. Run the AppImage:
   ```bash
   ./monerodui-*.AppImage
   ```

## Building from Source

### Prerequisites

Clone the repository:
```bash
git clone https://github.com/PromptPunksFauxCough/monerodui.git
cd monerodui
```

### Build Script

The project includes a build script that handles both platforms:

```bash
# Build for Android
bash ./build.sh android

# Build for Linux Desktop
bash ./build.sh desktop

# Build both
./build.sh all

# Skip dependency installation (if already installed)
./build.sh android --skip-deps
```

### Manual Build - Android

1. Install dependencies:
   ```bash
   sudo apt install -y git zip unzip openjdk-17-jdk python3-pip \
       autoconf libtool pkg-config zlib1g-dev libncurses5-dev \
       libncursesw5-dev libtinfo5 cmake libffi-dev libssl-dev
   
   pip3 install --user --upgrade Cython==0.29.33 virtualenv buildozer
   ```

2. Build APK:
   ```bash
   buildozer android debug
   ```

3. Output: `bin/*.apk`

### Manual Build - Desktop

1. Install dependencies:
   ```bash
   sudo apt install -y git build-essential pkg-config python3-dev \
       python3-venv libgirepository1.0-dev libcairo2-dev \
       gir1.2-gtk-3.0 libcanberra-gtk3-module
   
   pip install briefcase
   ```

2. Build AppImage:
   ```bash
   briefcase create linux appimage --no-docker
   briefcase build linux appimage --no-docker
   briefcase package linux appimage --no-docker
   ```

3. Output: `dist/*.AppImage`

## Development

### Project Structure

```
monerodui/
├── src/monerodui/
│   ├── main.py                 # Application entry point
│   ├── components/             # Reusable UI components
│   │   ├── status_card.py
│   │   └── node_stats_card.py
│   ├── screens/                # Screen definitions
│   │   └── main_screen.py
│   ├── ui/                     # KV layout files
│   │   ├── components/
│   │   │   ├── status_card.kv
│   │   │   └── node_stats_card.kv
│   │   └── screens/
│   │       └── main.kv
│   ├── libs/                   # Core functionality
│   │   ├── arch_detector.py   # CPU architecture detection
│   │   ├── storage_manager.py # Storage location management
│   │   ├── process_manager.py # monerod process lifecycle
│   │   ├── node_stats.py      # RPC statistics polling
│   │   └── version_checker.py # Binary version detection
│   ├── settings/               # App settings schema
│   └── assets/                 # Icons and images
├── android/                    # Android-specific files
│   ├── binary/                 # Precompiled monerod binaries
│   └── p4a-recipes/            # Python-for-Android recipes
├── desktop/                    # Desktop-specific files
│   └── binary/                 # Precompiled monerod binary
├── buildozer.spec              # Android build configuration
├── pyproject.toml              # Desktop build configuration
├── build.sh                    # Build automation script
└── README.md
```

### Running in Development

#### Android
```bash
buildozer android debug deploy run logcat
```

#### Desktop
```bash
python src/monerodui/main.py
```

Or using Briefcase:
```bash
briefcase dev
```

### Adding monerod Binaries

The app requires precompiled monerod binaries for each target architecture:

**Android:**
- `android/binary/libmonerod_arm32.so`
- `android/binary/libmonerod_arm64.so`

**Desktop:**
- `desktop/binary/monerod` (x86_64)

Build these from the [Monero source](https://github.com/monero-project/monero) or download official releases.

## Configuration

Settings are accessible via the gear icon in the top-right corner:

- **Network**: Network type (mainnet/testnet/stagenet), offline mode
- **P2P**: Ports, connection limits, peer management
- **RPC**: RPC server configuration, authentication
- **Blockchain**: Pruning, sync mode, database settings
- **Storage**: Minimum free space requirement
- **Background**: Keep running when app is closed (Android)

## Logging

### Android
Logs are written to: `/storage/emulated/0/Download/full_app_log.txt`

### Desktop
Logs are output to stdout/stderr

## Troubleshooting

### Android: "All Files Access" Permission Required
This permission MAY be necessary to store blockchain data in a location that persists across app reinstalls. Without it, users would lose access to all blockchain data when updating or reinstalling the app. If it is possible via android GUI for an app to take ownership over existing files any other way, let me know!

### Insufficient Storage
The Monero blockchain requires 300+ GiB of space (unpruned). The app defaults to a 10 GiB (for testing) minimum requirement, which accommodates a pruned blockchain with growth room.

### Binary Not Found (Desktop)
When running in development mode, place the `monerod` binary in `src/monerodui/` directory.


## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test on both Android and Desktop
5. Submit a pull request

## Acknowledgments

- [Monero Project](https://github.com/monero-project/monero) - The cryptocurrency software
- [KivyMD](https://github.com/kivymd/KivyMD) - Material Design components for Kivy
- [Buildozer](https://github.com/kivy/buildozer) - Android packaging
- [Briefcase](https://github.com/beeware/briefcase) - Desktop packaging
- [Monerod-in-Termux](https://github.com/CryptoGrampy/android-termux-monero-node) - Inspiration 	

## Support

For issues, questions, or feature requests, please [open an issue](https://github.com/yourusername/monerodui/issues).

## Disclaimer

This software is provided as-is. Always verify downloaded binaries and use at your own risk. Ensure you understand the implications of running a full Monero node.

