"""Importa/esporta dal menu: flusso completo con selettore di file simulato e DB reale."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from command_quiver.core.i18n import init as i18n_init
from command_quiver.db.database import Database
from command_quiver.db.entry_repository import EntryRepository
from command_quiver.db.models import EntryCreate, Section
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
    @pytest.mark.parametrize("language", ["it", "en"])
    def test_added_samples_keep_catalog_types_and_tags(
        self, gtk_init, db_for_ui, language: str
    ) -> None:
        from command_quiver.core.samples import sample_entries
        from command_quiver.ui.library_actions import add_sample_entries

        i18n_init(language)
        entries = EntryRepository(db_for_ui.connection)
        sections = SectionRepository(db_for_ui.connection)
        catalog = sample_entries(language)

        add_sample_entries(entry_repo=entries, section_repo=sections)

        actual = {
            entry.name: (entry.type, entry.tags) for entry in entries.get_all(None, "", "alpha_asc")
        }
        assert actual == {sample["name"]: (sample["type"], sample["tags"]) for sample in catalog}

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

    def test_cancelled_import_reports_nothing(self, gtk_init, tmp_path) -> None:
        from command_quiver.ui import library_actions

        done: list[tuple[str, bool]] = []
        target = _db(tmp_path, "e.db")
        with patch.object(library_actions.Gtk, "FileDialog", _FakeDialog):
            _FakeDialog.path = None
            library_actions.import_library(
                MagicMock(),
                EntryRepository(target.connection),
                SectionRepository(target.connection),
                lambda msg, changed: done.append((msg, changed)),
            )
        assert done == []

    def test_export_writes_file_and_counts_entries(self, gtk_init, tmp_path) -> None:
        from command_quiver.ui import library_actions

        messages: list[str] = []
        target_file = tmp_path / "out.json"
        repo = EntryRepository(_db(tmp_path, "g.db").connection)
        repo.create(EntryCreate(name="Uno", content="ls", section_id=3, type="shell"))
        with patch.object(library_actions.Gtk, "FileDialog", _FakeDialog):
            _FakeDialog.path = target_file
            library_actions.export_library(MagicMock(), repo, messages.append)
        assert messages == ["Esportate 1 voci"]
        assert '"Uno"' in target_file.read_text(encoding="utf-8")

    def test_export_to_unwritable_path_reports_failure(self, gtk_init, tmp_path) -> None:
        from command_quiver.ui import library_actions

        messages: list[str] = []
        # La cartella non esiste: la scrittura fallisce con OSError
        unwritable = tmp_path / "non-esiste" / "export.json"
        repo = EntryRepository(_db(tmp_path, "f.db").connection)
        with patch.object(library_actions.Gtk, "FileDialog", _FakeDialog):
            _FakeDialog.path = unwritable
            library_actions.export_library(MagicMock(), repo, messages.append)
        assert messages == ["Impossibile scrivere il file"]
        assert not unwritable.exists()

    def test_import_of_non_utf8_file_is_rejected(self, gtk_init, tmp_path) -> None:
        from command_quiver.ui import library_actions

        broken = tmp_path / "binario.json"
        broken.write_bytes(b"\xff\xfe\x00non utf8")
        target = _db(tmp_path, "h.db")
        done: list[tuple[str, bool]] = []
        with patch.object(library_actions.Gtk, "FileDialog", _FakeDialog):
            _FakeDialog.path = broken
            library_actions.import_library(
                MagicMock(),
                EntryRepository(target.connection),
                SectionRepository(target.connection),
                lambda msg, changed: done.append((msg, changed)),
            )
        assert done == [("Il file non è un export valido di Command Quiver", False)]


_GIT_SAMPLE = {"type": "shell", "content": "git status"}


@pytest.mark.parametrize(
    ("sections", "expected"),
    [
        ([Section(id=8, name="Shell", icon="utilities-terminal")], 8),
        ([Section(id=9, name="Default", is_default=1)], 9),
        ([], None),
    ],
    ids=["git-falls-back-to-shell", "falls-back-to-default", "no-section"],
)
def test_section_for_sample_missing_git_section_uses_fallback(
    sections: list[Section], expected: int | None
) -> None:
    from command_quiver.ui.library_actions import section_for_sample

    assert section_for_sample(sample=_GIT_SAMPLE, sections=sections) == expected


def test_section_for_sample_git_command_prefers_git_section() -> None:
    from command_quiver.ui.library_actions import section_for_sample

    sections = [
        Section(id=8, name="Shell", icon="utilities-terminal"),
        Section(id=10, name="Git", icon="vcs-commit"),
    ]

    assert section_for_sample(sample=_GIT_SAMPLE, sections=sections) == 10


def test_section_for_sample_non_git_shell_ignores_git_section() -> None:
    from command_quiver.ui.library_actions import section_for_sample

    sections = [
        Section(id=8, name="Shell", icon="utilities-terminal"),
        Section(id=10, name="Git", icon="vcs-commit"),
    ]

    sample = {"type": "shell", "content": "df -h"}
    assert section_for_sample(sample=sample, sections=sections) == 8
