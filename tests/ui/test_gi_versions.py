"""Ogni modulo UI fissa le versioni GObject che usa prima di importarle."""

import subprocess
import sys

import pytest

# Moduli che importano Gdk: senza require_version PyGObject avvisa e,
# con più versioni installate, può caricare quella sbagliata
_GDK_MODULES = [
    "entry_editor",
    "entry_list",
    "row_dnd",
    "run_confirm",
    "section_row",
    "shortcuts_dialog",
    "sidebar",
    "styles",
    "sync_dialog",
]


@pytest.mark.parametrize("module", _GDK_MODULES)
def test_import_ui_module_alone_raises_no_gi_warning(module: str) -> None:
    # Processo nuovo: nessun altro modulo ha già fissato la versione di Gdk
    result = subprocess.run(
        [sys.executable, "-W", "error", "-c", f"import command_quiver.ui.{module}"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
