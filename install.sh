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

# 1b. Verifica estensione GNOME AppIndicator (necessaria per il tray icon)
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
rm -rf "$INSTALL_DIR/command_quiver"
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

# 6. Crea file .desktop per autostart
cat > "$DESKTOP_FILE" << DESKTOP
[Desktop Entry]
Type=Application
Name=Command Quiver
Exec=bash -c 'PYTHONPATH=$INSTALL_DIR python3 -m command_quiver.main'
Icon=$INSTALL_DIR/command_quiver/assets/icon.png
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

# 8. Inizializza database
PYTHONPATH="$INSTALL_DIR" python3 -c "
from command_quiver.db.database import Database
db = Database()
db.initialize()
db.close()
print('Database inizializzato')
"
info "Database SQLite inizializzato"

# 9. Genera icona se mancante
if [ ! -f "$INSTALL_DIR/command_quiver/assets/icon.png" ]; then
    PYTHONPATH="$INSTALL_DIR" python3 -c "
from command_quiver.app import CommandQuiverApp
from pathlib import Path
icon_path = Path('$INSTALL_DIR/command_quiver/assets/icon.png')
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
PYTHONPATH="$INSTALL_DIR" nohup python3 -m command_quiver.main &>/dev/null &
info "Applicazione avviata in background (PID: $!)"
