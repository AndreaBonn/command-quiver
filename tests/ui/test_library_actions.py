"""Importa/esporta dal menu: flusso completo con selettore di file simulato e DB reale."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from command_quiver.core.i18n import init as i18n_init
from command_quiver.db.database import Database
from command_quiver.db.entry_repository import EntryRepository
from command_quiver.db.models import EntryCreate
from command_quiver.db.section_repository import SectionRepository
from tests.conftest import requires_display


@pytest.fixture(autouse=True)
def _italian() -> None:
    i18n_init("it")


class _FakeDialog:
    """Sostituisce Gtk.FileDialog: "sceglie" il file indicato e chiama subito il callback."""

    path: Path | None = None

    def __init__(self, **_kwargs) -> None:
        pass

    def _finish(self, _result):
        if self.path is None:
            from gi.repository import GLib

            raise GLib.Error("annullato")
        file = MagicMock()
        file.get_path.return_value = str(self.path)
        return file

    save_finish = _finish
    open_finish = _finish

    def save(self, _window, _cancellable, callback) -> None:
        callback(self, None)

    open = save


def _db(tmp_path: Path, name: str) -> Database:
    db = Database(db_path=tmp_path / name)
    db.initialize(language="it")
    return db


@requires_display
class TestExportImport:
    def test_roundtrip_moves_library_between_databases(self, gtk_init, tmp_path) -> None:
        from command_quiver.ui import library_actions

        source = _db(tmp_path, "a.db")
        repo = EntryRepository(source.connection)
        repo.create(
            EntryCreate(name="Log", content="git log", section_id=3, type="shell", tags="git")
        )
        repo.create(EntryCreate(name="Riassunto", content="Riassumi...", section_id=2))
        export_file = tmp_path / "export.json"
        messages: list[str] = []

        with patch.object(library_actions.Gtk, "FileDialog", _FakeDialog):
            _FakeDialog.path = export_file
            library_actions.export_library(MagicMock(), repo, messages.append)

            target = _db(tmp_path, "b.db")
            target_repo = EntryRepository(target.connection)
            done: list[tuple[str, bool]] = []
            library_actions.import_library(
                MagicMock(),
                target_repo,
                SectionRepository(target.connection),
                lambda msg, changed: done.append((msg, changed)),
            )

        assert messages == ["Esportate 2 voci"]
        assert done == [("Importate 2 voci", True)]
        imported = {e.name: e for e in target_repo.get_all(None, "", "alpha_asc")}
        assert imported["Log"].type == "shell"
        assert imported["Log"].tags == "git"
        assert imported["Log"].section_name == "Git"

    def test_import_of_foreign_file_reports_and_changes_nothing(self, gtk_init, tmp_path) -> None:
        from command_quiver.ui import library_actions

        bad = tmp_path / "foto.json"
        bad.write_text('{"qualcosa": 1}', encoding="utf-8")
        target = _db(tmp_path, "c.db")
        done: list[tuple[str, bool]] = []

        with patch.object(library_actions.Gtk, "FileDialog", _FakeDialog):
            _FakeDialog.path = bad
            library_actions.import_library(
                MagicMock(),
                EntryRepository(target.connection),
                SectionRepository(target.connection),
                lambda msg, changed: done.append((msg, changed)),
            )

        assert done == [("Il file non è un export valido di Command Quiver", False)]
        assert EntryRepository(target.connection).count_all() == 0

    def test_cancelled_dialog_does_nothing(self, gtk_init, tmp_path) -> None:
        from command_quiver.ui import library_actions

        messages: list[str] = []
        with patch.object(library_actions.Gtk, "FileDialog", _FakeDialog):
            _FakeDialog.path = None
            library_actions.export_library(
                MagicMock(), EntryRepository(_db(tmp_path, "d.db").connection), messages.append
            )
        assert messages == []
