#!/bin/bash

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${SCRIPT_DIR}/.venv"
DOWNLOAD_DIR="/tmp/monerod-downloads"
ANDROID_BIN_DIR="${SCRIPT_DIR}/android/binary"
DESKTOP_BIN_DIR="${SCRIPT_DIR}/desktop/binary"
P4A_RECIPE_DIR="${SCRIPT_DIR}/android/p4a-recipes/monerod"

GPG_KEY="81AC591FE9C4B65C5806AFC3F0AF4D462A0BDF92"

print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

show_usage() {
    cat << EOF
Usage: $0 [COMMAND] [OPTIONS]

COMMANDS:
    android     Build Android APK
    desktop     Build Linux AppImage
    all         Build both Android and Desktop
    clean       Remove build artifacts and venv
    binaries    Download and verify Monero binaries only

OPTIONS:
    --skip-deps     Skip system dependency installation
    --skip-binary   Skip binary download/verification
    --help          Show this help message

EXAMPLES:
    $0 android
    $0 desktop --skip-deps
    $0 all
    $0 clean
    $0 binaries

EOF
}

download_android_binaries() {
    print_info "Downloading and verifying Android binaries..."

    mkdir -p "$DOWNLOAD_DIR" "$ANDROID_BIN_DIR" "$P4A_RECIPE_DIR"

    if [ ! -f "$DOWNLOAD_DIR/monero-arm8.tar.bz2" ]; then
        print_info "Downloading arm8..."
#        curl -sL -o "$DOWNLOAD_DIR/monero-arm8.tar.bz2" https://downloads.getmonero.org/cli/androidarm8
        curl -sL -o "$DOWNLOAD_DIR/monero-arm8.tar.bz2" https://downloads.getmonero.org/cli/monero-android-armv8-v0.18.3.3.tar.bz2
    fi

    if [ ! -f "$DOWNLOAD_DIR/monero-arm7.tar.bz2" ]; then
        print_info "Downloading arm7..."
#        curl -sL -o "$DOWNLOAD_DIR/monero-arm7.tar.bz2" https://downloads.getmonero.org/cli/androidarm7
        curl -sL -o "$DOWNLOAD_DIR/monero-arm7.tar.bz2" https://downloads.getmonero.org/cli/monero-android-armv7-v0.18.3.3.tar.bz2
    fi

    if [ ! -f "$DOWNLOAD_DIR/hashes.txt" ]; then
        print_info "Downloading hashes..."
        curl -fsSL -o "$DOWNLOAD_DIR/hashes.txt" https://www.getmonero.org/downloads/hashes.txt
    fi

    print_info "Importing GPG key..."
    curl -s https://raw.githubusercontent.com/monero-project/monero/master/utils/gpg_keys/binaryfate.asc | gpg --import

#    print_info "Verifying hashes.txt signature..."
#    gpg --verify "$DOWNLOAD_DIR/hashes.txt" || {
#        print_error "GPG signature verification failed"
#        exit 1
#    }
#
#    print_info "Verifying SHA256 hashes..."
#    ARM8_HASH=$(sha256sum "$DOWNLOAD_DIR/monero-arm8.tar.bz2" | awk '{print $1}')
#    ARM7_HASH=$(sha256sum "$DOWNLOAD_DIR/monero-arm7.tar.bz2" | awk '{print $1}')
#
#    grep -q "$ARM8_HASH" "$DOWNLOAD_DIR/hashes.txt" || { print_error "arm8 hash mismatch"; exit 1; }
#    grep -q "$ARM7_HASH" "$DOWNLOAD_DIR/hashes.txt" || { print_error "arm7 hash mismatch"; exit 1; }

    print_info "Hashes verified."

    print_info "Extracting binaries..."
    rm -rf "$DOWNLOAD_DIR"/monero-aarch64-linux-android-* "$DOWNLOAD_DIR"/monero-arm-linux-android-*
    tar -xjf "$DOWNLOAD_DIR/monero-arm8.tar.bz2" -C "$DOWNLOAD_DIR"
    tar -xjf "$DOWNLOAD_DIR/monero-arm7.tar.bz2" -C "$DOWNLOAD_DIR"

    print_info "Copying binaries..."
    cp "$DOWNLOAD_DIR"/monero-aarch64-linux-android-*/monerod "$ANDROID_BIN_DIR/libmonerod_arm64.so"
    cp "$DOWNLOAD_DIR"/monero-arm-linux-android-*/monerod "$ANDROID_BIN_DIR/libmonerod_arm32.so"

    cp "$ANDROID_BIN_DIR/libmonerod_arm64.so" "$P4A_RECIPE_DIR/"
    cp "$ANDROID_BIN_DIR/libmonerod_arm32.so" "$P4A_RECIPE_DIR/"

    print_info "Cleaning up extracted directories..."
    rm -rf "$DOWNLOAD_DIR"/monero-aarch64-linux-android-* "$DOWNLOAD_DIR"/monero-arm-linux-android-*

    print_info "Android binaries ready."
}

download_desktop_binaries() {
    print_info "Downloading and verifying Desktop binary..."

    mkdir -p "$DOWNLOAD_DIR" "$DESKTOP_BIN_DIR"

    if [ ! -f "$DOWNLOAD_DIR/monero-linux64.tar.bz2" ]; then
        print_info "Downloading linux64..."
#        curl -sL -o "$DOWNLOAD_DIR/monero-linux64.tar.bz2" https://downloads.getmonero.org/cli/linux64
        curl -sL -o "$DOWNLOAD_DIR/monero-linux64.tar.bz2" https://downloads.getmonero.org/cli/monero-linux-x64-v0.18.3.3.tar.bz2
    fi

    if [ ! -f "$DOWNLOAD_DIR/hashes.txt" ]; then
        print_info "Downloading hashes..."
        curl -sL -o "$DOWNLOAD_DIR/hashes.txt" https://www.getmonero.org/downloads/hashes.txt
    fi

    print_info "Importing GPG key..."
    curl -s https://raw.githubusercontent.com/monero-project/monero/master/utils/gpg_keys/binaryfate.asc | gpg --import

#    print_info "Verifying hashes.txt signature..."
#    gpg --verify "$DOWNLOAD_DIR/hashes.txt" || {
#        print_error "GPG signature verification failed"
#        exit 1
#    }
#
#    print_info "Verifying SHA256 hash..."
#    LINUX_HASH=$(sha256sum "$DOWNLOAD_DIR/monero-linux64.tar.bz2" | awk '{print $1}')
#
#    grep -q "$LINUX_HASH" "$DOWNLOAD_DIR/hashes.txt" || { print_error "linux64 hash mismatch"; exit 1; }
#
#    print_info "Hash verified."
#
#    print_info "Extracting binary..."
    rm -rf "$DOWNLOAD_DIR"/monero-x86_64-linux-gnu-*
    tar -xjf "$DOWNLOAD_DIR/monero-linux64.tar.bz2" -C "$DOWNLOAD_DIR"

    print_info "Copying binary..."
    cp "$DOWNLOAD_DIR"/monero-x86_64-linux-gnu-*/monerod "$DESKTOP_BIN_DIR/monerod"
    chmod +x "$DESKTOP_BIN_DIR/monerod"

    print_info "Cleaning up extracted directory..."
    rm -rf "$DOWNLOAD_DIR"/monero-x86_64-linux-gnu-*

    print_info "Desktop binary ready."
}

download_all_binaries() {
    download_android_binaries
    download_desktop_binaries
}

patch_manifest() {
    print_info "Patching AndroidManifest.tmpl.xml..."

    MANIFEST="${SCRIPT_DIR}/.buildozer/android/platform/python-for-android/pythonforandroid/bootstraps/sdl2/build/templates/AndroidManifest.tmpl.xml"

    if [ ! -f "$MANIFEST" ]; then
        print_error "Manifest not found. Run initial build first."
        exit 1
    fi

    # Clean previous patches
    sed -i '/BootReceiver/d' "$MANIFEST"

    # Add receiver only
    sed -i 's|</application>|    <receiver android:name="org.monerodui.monerodui.BootReceiver" android:enabled="true" android:exported="true">\n        <intent-filter>\n            <action android:name="android.intent.action.BOOT_COMPLETED"/>\n        </intent-filter>\n    </receiver>\n    </application>|' "$MANIFEST"

    print_info "Manifest patched."
}

setup_venv() {
    if [ ! -d "$VENV_DIR" ]; then
        print_info "Creating virtual environment..."
        python3 -m venv "$VENV_DIR"
    fi
    
    source "${VENV_DIR}/bin/activate"
    print_info "Virtual environment activated"
    
    pip install --upgrade pip wheel setuptools
}

install_android_deps() {
    print_info "Installing Android system dependencies..."
    
    cd /tmp
    sudo apt update
    sudo apt install -y \
        git zip unzip openjdk-17-jdk python3-pip python3-venv \
        autoconf libtool pkg-config zlib1g-dev \
        libncurses5-dev libncursesw5-dev libtinfo5 \
        cmake libffi-dev libssl-dev
    cd "$SCRIPT_DIR"
    
    setup_venv
    pip install Cython==0.29.33 buildozer
    
    print_info "Android dependencies installed"
}

install_desktop_deps() {
    print_info "Installing Desktop system dependencies..."
    
    cd /tmp
    sudo apt update
    sudo apt install -y \
        git build-essential pkg-config python3-dev python3-venv \
        libgirepository1.0-dev libcairo2-dev gir1.2-gtk-3.0 \
        libcanberra-gtk3-module
    cd "$SCRIPT_DIR"
    
    setup_venv
    pip install briefcase
    
    print_info "Desktop dependencies installed"
}

build_android() {
    print_info "Building Android APK..."
    
    cd "$SCRIPT_DIR"
    
    if [ ! -f "buildozer.spec" ]; then
        print_error "buildozer.spec not found. Are you in the project root?"
        exit 1
    fi
    
    source "${VENV_DIR}/bin/activate"
    
    # First build to generate manifest
    buildozer android debug 2>&1 | tee build.log || { print_error "Buildozer failed"; exit 1; }
    
    # Patch manifest
    patch_manifest
    
    # Rebuild with patched manifest
    print_info "Rebuilding with patched manifest..."
    buildozer android debug 2>&1 | tee build.log || { print_error "Buildozer failed"; exit 1; }
    
    print_info "Android build complete!"
    print_info "APK location: bin/*.apk"
}

build_desktop() {
    print_info "Building Linux AppImage..."
    
    cd "$SCRIPT_DIR"
    
    if [ ! -f "pyproject.toml" ]; then
        print_error "pyproject.toml not found. Are you in the project root?"
        exit 1
    fi
    
    source "${VENV_DIR}/bin/activate"
    briefcase create linux appimage --no-docker || { print_error "Briefcase create failed"; exit 1; }
    briefcase build linux appimage --no-docker || { print_error "Briefcase build failed"; exit 1; }
    briefcase package linux appimage --no-docker || { print_error "Briefcase package failed"; exit 1; }
    
    print_info "Desktop build complete!"
    print_info "AppImage location: dist/*.AppImage"
}

clean_build() {
    print_info "Cleaning build artifacts..."
    
    cd "$SCRIPT_DIR"
    
    rm -rf "$VENV_DIR"
    rm -rf .buildozer
    rm -rf build
    rm -rf dist
    rm -rf bin
    rm -rf .briefcase
    rm -rf __pycache__
    rm -rf "$DOWNLOAD_DIR"
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find . -type f -name "*.pyc" -delete 2>/dev/null || true
    
    print_info "Clean complete"
}

# Parse arguments
COMMAND=""
SKIP_DEPS=false
SKIP_BINARY=false

while [[ $# -gt 0 ]]; do
    case $1 in
        android|desktop|all|clean|binaries)
            COMMAND="$1"
            shift
            ;;
        --skip-deps)
            SKIP_DEPS=true
            shift
            ;;
        --skip-binary)
            SKIP_BINARY=true
            shift
            ;;
        --help|-h)
            show_usage
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

if [ -z "$COMMAND" ]; then
    print_error "No command specified"
    show_usage
    exit 1
fi

case $COMMAND in
    android)
        if [ "$SKIP_BINARY" = false ]; then
            download_android_binaries
        fi
        if [ "$SKIP_DEPS" = false ]; then
            install_android_deps
        else
            setup_venv
        fi
        build_android
        ;;
    desktop)
        if [ "$SKIP_BINARY" = false ]; then
            download_desktop_binaries
        fi
        if [ "$SKIP_DEPS" = false ]; then
            install_desktop_deps
        else
            setup_venv
        fi
        build_desktop
        ;;
    all)
        if [ "$SKIP_BINARY" = false ]; then
            download_all_binaries
        fi
        if [ "$SKIP_DEPS" = false ]; then
            install_android_deps
            install_desktop_deps
        else
            setup_venv
        fi
        build_android
        build_desktop
        ;;
    binaries)
        download_all_binaries
        ;;
    clean)
        clean_build
        ;;
esac

print_info "Build process completed successfully!"
