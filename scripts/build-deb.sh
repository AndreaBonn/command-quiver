#!/usr/bin/env bash
# Costruisce il pacchetto Debian (.deb) di Command Quiver.
#
# Uso:     ./scripts/build-deb.sh
# Richiede: dpkg-deb, python3 con GdkPixbuf (pacchetto python3-gi), gzip.
# Output:  dist/command-quiver_<versione>_all.deb
set -euo pipefail

# --- Percorsi ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PKG_DIR="$PROJECT_DIR/packaging/deb"
BUILD_DIR="$PROJECT_DIR/build/deb"
DIST_DIR="$PROJECT_DIR/dist"
ASSETS_DIR="$PROJECT_DIR/command_quiver/assets"

PKG_NAME="command-quiver"
APP_ID="com.github.commandquiver"
ICON_SIZES="32 48 64 128"
MAINTAINER="Andrea Bonacci <delivery@linkalab.it>"

# --- Versione letta da __init__.py (singola fonte di verità) ---
# Il path è passato come argomento per restare robusto su workspace con spazi.
VERSION="$(python3 - "$PROJECT_DIR/command_quiver/__init__.py" <<'PY'
import re
import sys

text = open(sys.argv[1], encoding="utf-8").read()
print(re.search(r'__version__\s*=\s*"([^"]+)"', text).group(1))
PY
)"
echo "[INFO] Versione: $VERSION"

# --- Pulizia build precedente ---
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR" "$DIST_DIR"

# --- Struttura filesystem target ---
ROOT="$BUILD_DIR/root"
install -d "$ROOT/DEBIAN"
install -d "$ROOT/usr/lib/command-quiver"
install -d "$ROOT/usr/bin"
install -d "$ROOT/usr/share/applications"
install -d "$ROOT/usr/lib/systemd/user"
install -d "$ROOT/usr/share/doc/$PKG_NAME"

# --- Payload Python (senza bytecode compilato) ---
cp -r "$PROJECT_DIR/command_quiver" "$ROOT/usr/lib/command-quiver/"
find "$ROOT/usr/lib/command-quiver" -type d -name __pycache__ -exec rm -rf {} +
find "$ROOT/usr/lib/command-quiver" -type f -name '*.py[co]' -delete

# --- Wrapper eseguibile ---
install -m 0755 "$PKG_DIR/command-quiver" "$ROOT/usr/bin/command-quiver"

# --- systemd user unit ---
install -m 0644 "$PKG_DIR/command-quiver.service" \
    "$ROOT/usr/lib/systemd/user/command-quiver.service"

# --- Desktop entry ---
install -m 0644 "$ASSETS_DIR/$APP_ID.desktop" \
    "$ROOT/usr/share/applications/$APP_ID.desktop"

# --- Icone multi-size generate da icon.png via GdkPixbuf ---
for SIZE in $ICON_SIZES; do
    ICON_DIR="$ROOT/usr/share/icons/hicolor/${SIZE}x${SIZE}/apps"
    install -d "$ICON_DIR"
    python3 - "$ASSETS_DIR/icon.png" "$ICON_DIR/$APP_ID.png" "$SIZE" <<'PY'
import sys

import gi

gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GdkPixbuf

src, dst, size = sys.argv[1], sys.argv[2], int(sys.argv[3])
pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(src, size, size, True)
pixbuf.savev(dst, "png", [], [])
PY
done

# --- copyright ---
install -m 0644 "$PKG_DIR/copyright" "$ROOT/usr/share/doc/$PKG_NAME/copyright"

# --- changelog Debian (richiesto da lintian, compresso) ---
cat > "$BUILD_DIR/changelog.Debian" <<EOF
$PKG_NAME ($VERSION) unstable; urgency=low

  * Release $VERSION.

 -- $MAINTAINER  $(date -R)
EOF
gzip -9 -n -c "$BUILD_DIR/changelog.Debian" \
    > "$ROOT/usr/share/doc/$PKG_NAME/changelog.Debian.gz"

# --- Normalizza i permessi del filesystem target (standard Debian) ---
find "$ROOT/usr" -type d -exec chmod 0755 {} +
find "$ROOT/usr" -type f -exec chmod 0644 {} +
chmod 0755 "$ROOT/usr/bin/command-quiver"

# --- control con versione iniettata ---
sed "s/@VERSION@/$VERSION/" "$PKG_DIR/control.in" > "$ROOT/DEBIAN/control"

# --- Maintainer scripts ---
for script in postinst prerm postrm; do
    install -m 0755 "$PKG_DIR/$script" "$ROOT/DEBIAN/$script"
done

# --- Build del pacchetto (proprietà root:root deterministica) ---
DEB_FILE="$DIST_DIR/${PKG_NAME}_${VERSION}_all.deb"
dpkg-deb --root-owner-group --build "$ROOT" "$DEB_FILE"

echo "[OK] Pacchetto creato: $DEB_FILE"
dpkg-deb --info "$DEB_FILE"
