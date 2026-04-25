#!/usr/bin/env bash
# Installa il file .desktop e l'icona per il menu GNOME.
# Uso: ./scripts/install-desktop.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
ASSETS_DIR="$PROJECT_DIR/command_quiver/assets"
VENV_BIN="$PROJECT_DIR/.venv/bin/command-quiver"

DESKTOP_DIR="$HOME/.local/share/applications"
ICON_DIR="$HOME/.local/share/icons/hicolor/scalable/apps"

# Verifica che il venv esista
if [ ! -f "$VENV_BIN" ]; then
    echo "Errore: $VENV_BIN non trovato. Esegui prima: uv sync"
    exit 1
fi

# Installa icona PNG per il menu app (ridimensiona a 128x128)
ICON_PNG_DIR="$HOME/.local/share/icons/hicolor/128x128/apps"
mkdir -p "$ICON_PNG_DIR"
if command -v magick &>/dev/null; then
    magick "$ASSETS_DIR/icon.png" -resize 128x128 "$ICON_PNG_DIR/com.github.commandquiver.png"
elif command -v convert &>/dev/null; then
    convert "$ASSETS_DIR/icon.png" -resize 128x128 "$ICON_PNG_DIR/com.github.commandquiver.png"
else
    cp "$ASSETS_DIR/icon.png" "$ICON_PNG_DIR/com.github.commandquiver.png"
fi
echo "Icona installata: $ICON_PNG_DIR/com.github.commandquiver.png"

# Installa anche la SVG simbolica per il tray
mkdir -p "$ICON_DIR"
cp "$ASSETS_DIR/command-quiver-symbolic.svg" "$ICON_DIR/com.github.commandquiver-symbolic.svg"
echo "Icona simbolica installata: $ICON_DIR/com.github.commandquiver-symbolic.svg"

# Installa .desktop con percorso assoluto all'eseguibile
mkdir -p "$DESKTOP_DIR"
sed "s|^Exec=.*|Exec=$VENV_BIN|" \
    "$ASSETS_DIR/com.github.commandquiver.desktop" \
    > "$DESKTOP_DIR/com.github.commandquiver.desktop"
echo "Desktop file installato: $DESKTOP_DIR/com.github.commandquiver.desktop"

# Aggiorna cache
update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true
gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" 2>/dev/null || true

echo "Installazione completata. L'app dovrebbe apparire nel menu GNOME."
