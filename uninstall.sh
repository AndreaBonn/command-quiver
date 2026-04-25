#!/usr/bin/env bash
# Script di disinstallazione per Command Quiver

set -euo pipefail

APP_NAME="command-quiver"
INSTALL_DIR="$HOME/.local/share/$APP_NAME"
CONFIG_DIR="$HOME/.config/$APP_NAME"
DESKTOP_FILE="$HOME/.config/autostart/$APP_NAME.desktop"
SYMLINK="/usr/local/bin/$APP_NAME"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }

echo -e "${YELLOW}╔══════════════════════════════════════════╗${NC}"
echo -e "${YELLOW}║   Disinstallazione Command Quiver         ║${NC}"
echo -e "${YELLOW}╚══════════════════════════════════════════╝${NC}"
echo ""

# 1. Termina il processo se in esecuzione
if pgrep -f "command_quiver.main" > /dev/null 2>&1; then
    info "Terminazione processo in esecuzione..."
    pkill -f "command_quiver.main" || true
    sleep 1
fi

# 2. Rimuovi file .desktop (autostart + applications)
APP_ID="com.github.commandquiver"
if [ -f "$DESKTOP_FILE" ]; then
    rm -f "$DESKTOP_FILE"
    info "File autostart rimosso"
fi
APPS_DESKTOP="$HOME/.local/share/applications/$APP_ID.desktop"
if [ -f "$APPS_DESKTOP" ]; then
    rm -f "$APPS_DESKTOP"
    info "Desktop file rimosso: $APPS_DESKTOP"
fi

# 2b. Rimuovi icone da hicolor
for SIZE in 32 48 64 128; do
    ICON="$HOME/.local/share/icons/hicolor/${SIZE}x${SIZE}/apps/$APP_ID.png"
    [ -f "$ICON" ] && rm -f "$ICON"
done
gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor/" 2>/dev/null || true
info "Icone rimosse"

# 3. Rimuovi symlink
if [ -L "$SYMLINK" ]; then
    sudo rm -f "$SYMLINK"
    info "Symlink rimosso: $SYMLINK"
fi

# 4. Chiedi conferma per dati dell'applicazione (contiene il database)
if [ -d "$INSTALL_DIR" ]; then
    echo ""
    echo -e "${YELLOW}La directory $INSTALL_DIR contiene il database con tutti i tuoi dati.${NC}"
    read -r -p "Eliminare i dati dell'applicazione? [s/N] " response
    if [[ "$response" =~ ^[sS]$ ]]; then
        rm -rf "$INSTALL_DIR"
        info "Directory dati rimossa: $INSTALL_DIR"
    else
        warn "Directory dati conservata: $INSTALL_DIR"
    fi
fi

# 5. Chiedi conferma per impostazioni
if [ -d "$CONFIG_DIR" ]; then
    read -r -p "Eliminare le impostazioni? [s/N] " response
    if [[ "$response" =~ ^[sS]$ ]]; then
        rm -rf "$CONFIG_DIR"
        info "Directory impostazioni rimossa: $CONFIG_DIR"
    else
        warn "Directory impostazioni conservata: $CONFIG_DIR"
    fi
fi

echo ""
info "Disinstallazione completata."
