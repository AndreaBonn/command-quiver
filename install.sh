#!/usr/bin/env bash
# Script di installazione per Command Quiver
# Verifica Ubuntu, installa dipendenze, copia file, configura autostart

set -euo pipefail

APP_NAME="command-quiver"
INSTALL_DIR="$HOME/.local/share/$APP_NAME"
CONFIG_DIR="$HOME/.config/$APP_NAME"
AUTOSTART_DIR="$HOME/.config/autostart"
DESKTOP_FILE="$AUTOSTART_DIR/$APP_NAME.desktop"
SYMLINK="/usr/local/bin/$APP_NAME"

# Colori per output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERRORE]${NC} $1"; exit 1; }

# 1. Verifica sistema operativo
if [ ! -f /etc/os-release ]; then
    error "Impossibile determinare il sistema operativo"
fi
source /etc/os-release
if [[ "$ID" != "ubuntu" && "$ID_LIKE" != *"ubuntu"* ]]; then
    error "Questo script è progettato per Ubuntu. Sistema rilevato: $PRETTY_NAME"
fi
info "Sistema rilevato: $PRETTY_NAME"

# 1b. Verifica versione Python >= 3.10
PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "0.0")
PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)
if [ "$PYTHON_MAJOR" -lt 3 ] || { [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 10 ]; }; then
    error "Python >= 3.10 richiesto. Versione trovata: $PYTHON_VERSION"
fi
info "Python $PYTHON_VERSION rilevato"

# 1c. Verifica estensione GNOME AppIndicator (necessaria per il tray icon)
if command -v gnome-extensions &>/dev/null; then
    if gnome-extensions list --enabled 2>/dev/null | grep -qi "appindicator"; then
        info "Estensione AppIndicator attiva"
    else
        warn "L'estensione 'AppIndicator and KStatusNotifierItem Support' non è attiva."
        warn "Senza di essa l'icona nella barra superiore non sarà visibile."
        warn ""
        warn "Per installarla/attivarla:"
        warn "  sudo apt install gnome-shell-extension-appindicator"
        warn "  gnome-extensions enable appindicatorsupport@rgcjonas.gmail.com"
        warn "  (potrebbe servire un logout/login)"
        warn ""
        read -r -p "Continuare comunque l'installazione? [S/n] " response
        if [[ "$response" =~ ^[nN]$ ]]; then
            error "Installazione annullata. Attiva l'estensione e riprova."
        fi
    fi
else
    warn "gnome-extensions non trovato — impossibile verificare AppIndicator"
fi

# 2. Installa dipendenze di sistema
info "Installazione dipendenze di sistema..."
DEPS=(
    python3
    python3-gi
    python3-gi-cairo
    gir1.2-gtk-4.0
    gir1.2-ayatanaappindicator3-0.1
    gnome-terminal
)

MISSING=()
for dep in "${DEPS[@]}"; do
    if ! dpkg -s "$dep" &>/dev/null; then
        MISSING+=("$dep")
    fi
done

if [ ${#MISSING[@]} -gt 0 ]; then
    info "Pacchetti mancanti: ${MISSING[*]}"
    sudo apt update
    sudo apt install -y "${MISSING[@]}"
else
    info "Tutte le dipendenze sono già installate"
fi

# 3. Crea directory
mkdir -p "$INSTALL_DIR"
mkdir -p "$CONFIG_DIR"
mkdir -p "$AUTOSTART_DIR"
info "Directory create"

# 4. Copia il package Python mantenendo la struttura
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Rimuovi installazione precedente del package (se esiste)
if [ -d "$INSTALL_DIR/command_quiver" ]; then
    info "Aggiornamento installazione esistente..."
    rm -rf "$INSTALL_DIR/command_quiver"
fi
# Copia il package come sottodirectory → preserva gli import
cp -r "$SCRIPT_DIR/command_quiver" "$INSTALL_DIR/command_quiver"
info "Package copiato in $INSTALL_DIR/command_quiver"

# 5. Crea entry point wrapper
# PYTHONPATH punta a INSTALL_DIR così Python trova il package command_quiver
cat > "$INSTALL_DIR/run.sh" << WRAPPER
#!/usr/bin/env bash
export PYTHONPATH="$INSTALL_DIR:\${PYTHONPATH:-}"
exec python3 -m command_quiver.main "\$@"
WRAPPER
chmod +x "$INSTALL_DIR/run.sh"

# 6. Installa icone in hicolor per integrazione GNOME (dock, alt-tab)
APP_ID="com.github.commandquiver"
ICON_SRC="$INSTALL_DIR/command_quiver/assets/icon.png"
ICON_SIZES=(32 48 64 128)
for SIZE in "${ICON_SIZES[@]}"; do
    ICON_DIR="$HOME/.local/share/icons/hicolor/${SIZE}x${SIZE}/apps"
    mkdir -p "$ICON_DIR"
    PYTHONPATH="$INSTALL_DIR" python3 -c "
import gi
gi.require_version('GdkPixbuf', '2.0')
from gi.repository import GdkPixbuf
pb = GdkPixbuf.Pixbuf.new_from_file_at_scale('$ICON_SRC', $SIZE, $SIZE, True)
pb.savev('$ICON_DIR/$APP_ID.png', 'png', [], [])
" 2>/dev/null || warn "Installazione icona ${SIZE}x${SIZE} fallita (non critico)"
done
# Aggiorna cache icone
gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor/" 2>/dev/null || true
info "Icone installate in ~/.local/share/icons/hicolor/"

# 7. Installa file .desktop da assets per GNOME (applications + autostart)
DESKTOP_SRC="$INSTALL_DIR/command_quiver/assets/$APP_ID.desktop"

# .desktop in applications (dock, alt-tab, GNOME search)
APPS_DESKTOP="$HOME/.local/share/applications/$APP_ID.desktop"
cp "$DESKTOP_SRC" "$APPS_DESKTOP"
info "Desktop file installato: $APPS_DESKTOP"

# .desktop in autostart (avvio automatico al login) — aggiunge flag autostart
cp "$DESKTOP_SRC" "$DESKTOP_FILE"
cat >> "$DESKTOP_FILE" << AUTOSTART_FLAGS
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
AUTOSTART_FLAGS

info "File autostart creato: $DESKTOP_FILE"

# 8. Crea symlink per avvio da terminale
if [ -L "$SYMLINK" ] || [ -f "$SYMLINK" ]; then
    sudo rm -f "$SYMLINK"
fi
sudo ln -s "$INSTALL_DIR/run.sh" "$SYMLINK"
info "Symlink creato: $SYMLINK"

# 9. Inizializza database
PYTHONPATH="$INSTALL_DIR" python3 -c "
from command_quiver.db.database import Database
db = Database()
db.initialize()
db.close()
print('Database inizializzato')
"
info "Database SQLite inizializzato"

# 10. Riepilogo
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   Command Quiver installato con successo  ║${NC}"
echo -e "${GREEN}╠══════════════════════════════════════════╣${NC}"
echo -e "${GREEN}║${NC} App:      $INSTALL_DIR"
echo -e "${GREEN}║${NC} Config:   $CONFIG_DIR"
echo -e "${GREEN}║${NC} Database: ~/.local/share/command-quiver/vault.db"
echo -e "${GREEN}║${NC} Autostart: attivo al login"
echo -e "${GREEN}║${NC}"
echo -e "${GREEN}║${NC} Avvio:    ${YELLOW}command-quiver${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════╝${NC}"
echo ""

# 11. Avvia applicazione
info "Avvio Command Quiver..."
PYTHONPATH="$INSTALL_DIR" nohup python3 -m command_quiver.main &>/dev/null &
info "Applicazione avviata in background (PID: $!)"
