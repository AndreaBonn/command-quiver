"""Fixture condivise per tutti i test, inclusa inizializzazione GTK4."""

import os
from pathlib import Path

import pytest

# Verifica disponibilità display per test GTK4
_HAS_DISPLAY = bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))

requires_display = pytest.mark.skipif(
    not _HAS_DISPLAY,
    reason="Nessun display disponibile per i test GTK4",
)


@pytest.fixture(scope="session")
def gtk_init():
    """Inizializza GTK4 una sola volta per tutta la sessione di test."""
    if not _HAS_DISPLAY:
        pytest.skip("Nessun display disponibile")

    import gi

    gi.require_version("Gtk", "4.0")

    # GTK4 non richiede gtk_init() esplicito, ma verifichiamo il display
    from gi.repository import Gdk

    display = Gdk.Display.get_default()
    if display is None:
        pytest.skip("Impossibile ottenere il display GTK4")
    return display


@pytest.fixture
def db_for_ui(tmp_path: Path):
    """Database inizializzato per test UI."""
    from command_quiver.db.database import Database

    db = Database(db_path=tmp_path / "test_ui.db")
    db.initialize()
    yield db
    db.close()


@pytest.fixture
def default_settings(tmp_path: Path):
    """Settings di default con path temporaneo."""
    from command_quiver.core.settings import Settings

    return Settings()
