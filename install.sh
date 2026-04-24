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

# 2. Installa dipendenze di sistema
info "Installazione dipendenze di sistema..."
DEPS=(
    python3
    python3-gi
    python3-gi-cairo
    gir1.2-gtk-4.0
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

# 4. Copia file dell'applicazione
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cp -r "$SCRIPT_DIR/command_quiver/"* "$INSTALL_DIR/"
info "File copiati in $INSTALL_DIR"

# 5. Crea entry point wrapper
cat > "$INSTALL_DIR/run.sh" << 'WRAPPER'
#!/usr/bin/env bash
exec python3 "$(dirname "$0")/main.py" "$@"
WRAPPER
chmod +x "$INSTALL_DIR/run.sh"

# 6. Crea file .desktop per autostart
cat > "$DESKTOP_FILE" << DESKTOP
[Desktop Entry]
Type=Application
Name=Command Quiver
Exec=python3 $INSTALL_DIR/main.py
Icon=$INSTALL_DIR/assets/icon.png
Comment=Accesso rapido a prompt e comandi shell
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
Categories=Utility;
DESKTOP

info "File autostart creato: $DESKTOP_FILE"

# 7. Crea symlink per avvio da terminale
if [ -L "$SYMLINK" ] || [ -f "$SYMLINK" ]; then
    sudo rm -f "$SYMLINK"
fi
sudo ln -s "$INSTALL_DIR/run.sh" "$SYMLINK"
info "Symlink creato: $SYMLINK"

# 8. Inizializza database (avviando brevemente l'app con flag init)
python3 -c "
import sys
sys.path.insert(0, '$INSTALL_DIR')
from db.database import Database
db = Database()
db.initialize()
db.close()
print('Database inizializzato')
"
info "Database SQLite inizializzato"

# 9. Genera icona se mancante
if [ ! -f "$INSTALL_DIR/assets/icon.png" ]; then
    python3 -c "
import sys
sys.path.insert(0, '$INSTALL_DIR')
from app import CommandQuiverApp
from pathlib import Path
icon_path = Path('$INSTALL_DIR/assets/icon.png')
CommandQuiverApp._generate_icon(icon_path)
print(f'Icona generata: {icon_path}')
" 2>/dev/null || warn "Generazione icona fallita (non critico)"
fi

# 10. Riepilogo
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   Command Quiver installato con successo  ║${NC}"
echo -e "${GREEN}╠══════════════════════════════════════════╣${NC}"
echo -e "${GREEN}║${NC} App:      $INSTALL_DIR"
echo -e "${GREEN}║${NC} Config:   $CONFIG_DIR"
echo -e "${GREEN}║${NC} Database: $INSTALL_DIR/vault.db"
echo -e "${GREEN}║${NC} Autostart: attivo al login"
echo -e "${GREEN}║${NC}"
echo -e "${GREEN}║${NC} Avvio:    ${YELLOW}command-quiver${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════╝${NC}"
echo ""

# 11. Avvia l'applicazione
info "Avvio Command Quiver..."
nohup python3 "$INSTALL_DIR/main.py" &>/dev/null &
info "Applicazione avviata in background (PID: $!)"
