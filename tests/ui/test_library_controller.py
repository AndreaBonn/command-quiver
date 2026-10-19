"""LibraryController con DB reale: vista e file dialog finti ai bordi."""

from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from command_quiver.core.i18n import init as i18n_init
from command_quiver.core.library_io import serialize_export
from command_quiver.db.database import Database
from command_quiver.db.entry_repository import EntryRepository
from command_quiver.db.models import EntryCreate, EntryUpdate
from command_quiver.db.section_repository import SectionRepository
from tests.conftest import fake_file_dialog, requires_display


@pytest.fixture(autouse=True)
def _italian() -> None:
    i18n_init("it")


class _Harness:
    """Controller + repository reali, finestra e avvisi finti."""

    def __init__(self, db: Database) -> None:
        from command_quiver.ui.library_controller import LibraryController, LibraryView

        self.entries = EntryRepository(db.connection)
        self.view = LibraryView(
            window=MagicMock(),
            toast=MagicMock(),
            refresh_all=MagicMock(),
            refresh_entries=MagicMock(),
            visible_entries=lambda: self.entries.get_all(
                section_id=None, search="", sort_order="personal"
            ),
            notify_changed=MagicMock(),
        )
        self.controller = LibraryController(
            self.entries, SectionRepository(db.connection), self.view
        )

    def add(self, name: str) -> int:
        return self.entries.create(
            EntryCreate(name=name, content=f"echo {name}", section_id=1, type="shell")
        ).id

    def positions(self) -> dict[str, int]:
        return {e.name: e.personal_pos for e in self.entries.get_all(None, "", "personal")}


@pytest.fixture
def harness(db_for_ui: Database, gtk_init) -> _Harness:
    built = _Harness(db_for_ui)
    yield built
    # Il timer di annullamento è un source GLib: non deve sopravvivere al test
    built.controller.pending_delete.flush()


@requires_display
class TestDelete:
    def test_flush_pending_delete_notifies_library_change(self, harness) -> None:
        entry_id = harness.add("Log")
        harness.controller.delete(entry_id)
        before_flush = harness.view.notify_changed.call_count
        pending_entry = harness.entries.get_by_id(entry_id)

        harness.controller.pending_delete.flush()

        assert (
            pending_entry.id,
            before_flush,
            harness.view.notify_changed.call_args_list,
            harness.entries.get_by_id(entry_id),
        ) == (entry_id, 0, [call()], None)

    def test_delete_unknown_entry_shows_nothing_and_hides_nothing(self, harness) -> None:
        harness.controller.delete(9999)

        assert harness.controller.pending_entry is None
        harness.view.toast.show_message.assert_not_called()
        harness.view.refresh_all.assert_not_called()

    def test_delete_existing_entry_offers_undo_with_its_name(self, harness) -> None:
        entry_id = harness.add("Log")

        harness.controller.delete(entry_id)

        message = harness.view.toast.show_message.call_args
        assert message.args == ("Eliminata: Log",)
        assert message.kwargs["action_label"] == "Annulla"
        assert harness.controller.pending_entry.id == entry_id


@requires_display
class TestReorder:
    def test_drop_on_invisible_entry_changes_nothing(self, harness) -> None:
        first = harness.add("A")
        harness.add("B")
        before = harness.positions()

        harness.controller.reorder(moved_id=first, target_id=9999)

        assert harness.positions() == before
        harness.view.refresh_entries.assert_not_called()

    def test_drop_on_another_entry_swaps_positions_and_refreshes(self, harness) -> None:
        first = harness.add("A")
        second = harness.add("B")
        before = harness.positions()

        harness.controller.reorder(moved_id=first, target_id=second)

        after = harness.positions()
        assert after["A"] == before["B"]
        assert after["B"] == before["A"]
        harness.view.refresh_entries.assert_called_once_with()


@requires_display
class TestSave:
    @pytest.mark.parametrize("editing", [False, True], ids=["create", "update"])
    def test_save_refreshes_library_view(self, harness, editing: bool) -> None:
        if editing:
            data = EntryUpdate(id=harness.add("Before"), name="After", content="ls", section_id=1)
        else:
            data = EntryCreate(name="After", content="ls", section_id=1)

        harness.controller.save(data)

        harness.view.refresh_all.assert_called_once_with()


@requires_display
class TestFiles:
    def _import(self, harness, chosen: Path | None) -> None:
        from command_quiver.ui import library_actions

        with patch.object(library_actions.Gtk, "FileDialog", fake_file_dialog(chosen)):
            harness.controller.import_file()

    def test_import_adds_entries_refreshes_and_notifies(self, harness, tmp_path) -> None:
        source = tmp_path / "in.json"
        source.write_text(
            serialize_export(
                [{"name": "Da file", "content": "ls -la", "type": "shell", "section_name": "Git"}]
            ),
            encoding="utf-8",
        )

        self._import(harness, source)

        assert [e.name for e in harness.entries.get_all(None, "", "alpha_asc")] == ["Da file"]
        harness.view.toast.show_message.assert_called_once_with("Importate 1 voci")
        harness.view.refresh_all.assert_called_once_with()
        harness.view.notify_changed.assert_called_once_with()

    def test_import_of_invalid_file_warns_without_refresh_or_sync(self, harness, tmp_path) -> None:
        source = tmp_path / "foto.json"
        source.write_text("non è json", encoding="utf-8")

        self._import(harness, source)

        harness.view.toast.show_message.assert_called_once_with(
            "Il file non è un export valido di Command Quiver"
        )
        harness.view.refresh_all.assert_not_called()
        harness.view.notify_changed.assert_not_called()
        assert harness.entries.count_all() == 0

    def test_export_writes_file_and_shows_count(self, harness, tmp_path) -> None:
        from command_quiver.ui import library_actions

        harness.add("Uno")
        target = tmp_path / "out.json"

        with patch.object(library_actions.Gtk, "FileDialog", fake_file_dialog(target)):
            harness.controller.export_file()

        harness.view.toast.show_message.assert_called_once_with("Esportate 1 voci")
        assert '"Uno"' in target.read_text(encoding="utf-8")
