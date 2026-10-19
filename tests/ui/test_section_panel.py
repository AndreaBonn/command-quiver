"""Test per SectionPanelWidget: lista sezioni, selezione, CRUD."""

from unittest.mock import MagicMock, patch

import pytest
from gi.repository import Gtk

from command_quiver.core.i18n import init as i18n_init
from command_quiver.db.database import Database
from command_quiver.db.entry_repository import EntryRepository
from command_quiver.db.section_repository import SectionRepository
from command_quiver.ui.section_row import SectionRow
from tests.conftest import button_labelled, descendants, requires_display


@requires_display
class TestSectionPanelWidget:
    """Test pannello sezioni con database reale."""

    def _create_panel(self, db: Database, on_changed=None):
        from command_quiver.ui.section_panel import SectionPanelWidget

        section_repo = SectionRepository(db.connection)
        entry_repo = EntryRepository(db.connection)
        return SectionPanelWidget(
            section_repo=section_repo,
            entry_repo=entry_repo,
            on_section_changed=on_changed or MagicMock(),
        )

    def test_refresh_shows_all_sections_plus_tutti(self, gtk_init, db_for_ui: Database) -> None:
        panel = self._create_panel(db_for_ui)
        panel.refresh()

        row_count = 0
        while panel._section_list.get_row_at_index(row_count):
            row_count += 1
        assert row_count == 5  # "Tutti" + 4 default

    def test_current_section_id_property(self, gtk_init, db_for_ui: Database) -> None:
        panel = self._create_panel(db_for_ui)
        assert panel.current_section_id is None

        panel.current_section_id = 42
        assert panel.current_section_id == 42

    def test_on_section_created_success(self, gtk_init, db_for_ui: Database) -> None:
        panel = self._create_panel(db_for_ui)
        result = panel._on_section_created("Docker")
        assert result is None

        sections = SectionRepository(db_for_ui.connection).get_all()
        names = [s.name for s in sections]
        assert "Docker" in names

    def test_on_section_created_duplicate_returns_error(
        self, gtk_init, db_for_ui: Database
    ) -> None:
        panel = self._create_panel(db_for_ui)
        # "Shell Commands" è una sezione default
        result = panel._on_section_created("Shell Commands")
        assert result is not None  # Messaggio errore

    def test_on_section_renamed_success(self, gtk_init, db_for_ui: Database) -> None:
        panel = self._create_panel(db_for_ui)
        result = panel._on_section_renamed(section_id=1, new_name="Comandi")
        assert result is None

        section = SectionRepository(db_for_ui.connection).get_by_id(1)
        assert section.name == "Comandi"

    def test_on_section_renamed_duplicate_returns_error(
        self, gtk_init, db_for_ui: Database
    ) -> None:
        panel = self._create_panel(db_for_ui)
        # Rinomina Shell Commands → AI Prompts (già esiste)
        result = panel._on_section_renamed(section_id=1, new_name="AI Prompts")
        assert result is not None

    def test_on_section_deleted_resets_current(self, gtk_init, db_for_ui: Database) -> None:
        mock_changed = MagicMock()
        panel = self._create_panel(db_for_ui, on_changed=mock_changed)
        panel.current_section_id = 1

        panel._on_section_deleted(1)

        assert panel.current_section_id is None
        mock_changed.assert_called_with(None)

    def test_on_section_deleted_different_section_keeps_current(
        self, gtk_init, db_for_ui: Database
    ) -> None:
        mock_changed = MagicMock()
        panel = self._create_panel(db_for_ui, on_changed=mock_changed)
        panel.current_section_id = 2

        panel._on_section_deleted(1)

        assert panel.current_section_id == 2

    def test_on_section_selected_none_row_noop(self, gtk_init, db_for_ui: Database) -> None:
        mock_changed = MagicMock()
        panel = self._create_panel(db_for_ui, on_changed=mock_changed)

        panel._on_section_selected(panel._section_list, None)
        mock_changed.assert_not_called()

    def test_select_current_selects_matching_section(self, gtk_init, db_for_ui: Database) -> None:
        panel = self._create_panel(db_for_ui)
        panel._current_section_id = 1
        panel.refresh()

        # Verifica che una riga sia selezionata
        selected = panel._section_list.get_selected_row()
        assert selected is not None


def _toplevels_of(kind) -> list:
    from gi.repository import Gtk

    return [w for w in Gtk.Window.list_toplevels() if isinstance(w, kind)]


def _opened_since(before: set, kind) -> list:
    """Finestre di quel tipo aperte dopo ``before`` (altri test lasciano le loro in giro)."""
    return [w for w in _toplevels_of(kind) if w not in before]


@requires_display
class TestSectionPanelDialogs:
    """CRUD dal punto di vista dell'utente: pulsanti e dialog veri, DB reale."""

    @pytest.fixture(autouse=True)
    def _italian(self) -> None:
        i18n_init("it")

    @pytest.fixture
    def panel(self, gtk_init, db_for_ui: Database):
        from gi.repository import Gtk

        from command_quiver.ui.section_panel import SectionPanelWidget

        widget = SectionPanelWidget(
            section_repo=SectionRepository(db_for_ui.connection),
            entry_repo=EntryRepository(db_for_ui.connection),
            on_section_changed=MagicMock(),
        )
        before = set(_toplevels_of(Gtk.Window))
        window = Gtk.Window()
        window.set_child(widget)
        widget.refresh()
        yield widget
        for opened in _opened_since(before, Gtk.Window):
            opened.destroy()

    def _names(self, db: Database) -> list[str]:
        return [s.name for s in SectionRepository(db.connection).get_all()]

    def _open_dialog(self, panel, kind):
        before = set(_toplevels_of(kind))
        button_labelled(panel, "+ Sezione").emit("clicked")
        dialogs = _opened_since(before, kind)
        assert len(dialogs) == 1
        return dialogs[0]

    def test_new_section_is_created_listed_and_dialog_closes(
        self, panel, db_for_ui: Database
    ) -> None:
        from command_quiver.ui.section_manager import SectionCreateDialog

        dialog = self._open_dialog(panel, SectionCreateDialog)
        assert dialog.get_visible() is True
        dialog._name_entry.set_text("Docker")

        button_labelled(dialog, "Crea").emit("clicked")

        assert "Docker" in self._names(db_for_ui)
        assert "Docker" in [
            w.get_label() for w in descendants(panel._section_list) if isinstance(w, Gtk.Label)
        ]
        assert dialog.get_visible() is False

    def test_duplicate_name_keeps_dialog_open_with_error(self, panel, db_for_ui: Database) -> None:
        from command_quiver.ui.section_manager import SectionCreateDialog

        before = self._names(db_for_ui)
        dialog = self._open_dialog(panel, SectionCreateDialog)
        dialog._name_entry.set_text(before[0])

        button_labelled(dialog, "Crea").emit("clicked")

        assert self._names(db_for_ui) == before
        assert dialog.get_visible() is True
        assert dialog._error_label.get_visible() is True
        assert before[0] in dialog._error_label.get_label()

    def _menu_of(self, panel, name: str):
        rows = [
            r
            for r in descendants(panel._section_list)
            if isinstance(r, SectionRow) and r.section is not None and r.section.name == name
        ]
        assert len(rows) == 1
        return rows[0].menu_button.get_popover()

    def test_rename_from_menu_saves_new_name(self, panel, db_for_ui: Database) -> None:
        from command_quiver.ui.section_manager import SectionRenameDialog

        old = self._names(db_for_ui)[0]
        before = set(_toplevels_of(SectionRenameDialog))
        button_labelled(self._menu_of(panel, old), "Rinomina").emit("clicked")
        dialog = _opened_since(before, SectionRenameDialog)[0]
        assert dialog._name_entry.get_text() == old
        dialog._name_entry.set_text("Rinominata")

        button_labelled(dialog, "Rinomina").emit("clicked")

        assert "Rinominata" in self._names(db_for_ui)
        assert old not in self._names(db_for_ui)

    def test_rename_to_existing_name_is_refused(self, panel, db_for_ui: Database) -> None:
        from command_quiver.ui.section_manager import SectionRenameDialog

        first, second = self._names(db_for_ui)[:2]
        before = set(_toplevels_of(SectionRenameDialog))
        button_labelled(self._menu_of(panel, first), "Rinomina").emit("clicked")
        dialog = _opened_since(before, SectionRenameDialog)[0]
        dialog._name_entry.set_text(second)

        button_labelled(dialog, "Rinomina").emit("clicked")

        assert self._names(db_for_ui).count(second) == 1
        assert first in self._names(db_for_ui)
        assert dialog._error_label.get_visible() is True

    @pytest.mark.parametrize(("choice", "deleted"), [(1, True), (0, False)])
    def test_delete_from_menu_only_when_confirmed(
        self, panel, db_for_ui: Database, choice: int, deleted: bool
    ) -> None:
        from command_quiver.ui import section_manager

        _AutoAnswer.choice = choice
        removable = [
            s for s in SectionRepository(db_for_ui.connection).get_all() if not s.is_default
        ]
        target = removable[0].name
        with patch.object(section_manager.Gtk, "AlertDialog", _AutoAnswer):
            button_labelled(self._menu_of(panel, target), "Elimina").emit("clicked")

        assert (target not in self._names(db_for_ui)) is deleted


class _AutoAnswer:
    """Gtk.AlertDialog che risponde subito con ``choice``."""

    choice = 1

    def __init__(self, **_kwargs) -> None:
        pass

    def set_buttons(self, _buttons) -> None:
        pass

    def set_cancel_button(self, _i) -> None:
        pass

    def set_default_button(self, _i) -> None:
        pass

    def choose(self, _parent, _cancellable, callback) -> None:
        callback(self, None)

    def choose_finish(self, _result) -> int:
        return type(self).choice
