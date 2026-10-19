"""Test per SectionPanelWidget: lista sezioni, selezione, CRUD."""

from unittest.mock import MagicMock, patch

import pytest

from command_quiver.core.i18n import init as i18n_init
from command_quiver.db.database import Database
from command_quiver.db.entry_repository import EntryRepository
from command_quiver.db.section_repository import SectionRepository
from command_quiver.ui.section_row import SectionRow
from tests.conftest import button_labelled, descendants, requires_display


@requires_display
class TestSectionPanelWidget:
    """Test pannello sezioni con database reale."""

    @pytest.fixture(autouse=True)
    def _italian(self) -> None:
        i18n_init("it")

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
        assert result == 'La sezione "Shell Commands" esiste già'

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
        assert result == 'La sezione "AI Prompts" esiste già'

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

        selected = panel._section_list.get_selected_row()
        assert selected.get_child().section_id == 1

    def test_refresh_shows_distinct_section_counts_and_total(
        self, gtk_init, db_for_ui: Database
    ) -> None:
        from command_quiver.db.models import EntryCreate

        repo = EntryRepository(db_for_ui.connection)
        for name, section_id in (("One", 1), ("Two", 1), ("Three", 2)):
            repo.create(EntryCreate(name=name, content=name, section_id=section_id))
        panel = self._create_panel(db_for_ui)

        panel.refresh()

        counts = {
            row.section_id: row.count_label.get_label()
            for row in descendants(panel._section_list)
            if isinstance(row, SectionRow)
        }
        assert (counts[1], counts[2], counts[None]) == ("2", "1", "3")


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
        from gi.repository import Gtk

        from command_quiver.ui.section_manager import SectionNameDialog

        dialog = self._open_dialog(panel, SectionNameDialog)
        assert dialog.get_visible() is True
        dialog._name_entry.set_text("Docker")

        button_labelled(dialog, "Crea").emit("clicked")

        assert "Docker" in self._names(db_for_ui)
        assert "Docker" in [
            w.get_label() for w in descendants(panel._section_list) if isinstance(w, Gtk.Label)
        ]
        assert dialog.get_visible() is False

    def test_duplicate_name_keeps_dialog_open_with_error(self, panel, db_for_ui: Database) -> None:
        from command_quiver.ui.section_manager import SectionNameDialog

        before = self._names(db_for_ui)
        dialog = self._open_dialog(panel, SectionNameDialog)
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

    def test_right_click_on_section_opens_its_menu(self, panel, db_for_ui: Database) -> None:
        from unittest.mock import patch

        from gi.repository import Gtk

        name = self._names(db_for_ui)[0]
        row = next(
            r
            for r in descendants(panel._section_list)
            if isinstance(r, SectionRow) and r.section is not None and r.section.name == name
        )
        controllers = row.observe_controllers()
        gestures = [
            c
            for c in (controllers.get_item(i) for i in range(controllers.get_n_items()))
            if isinstance(c, Gtk.GestureClick) and c.get_button() == 3
        ]
        assert len(gestures) == 1

        with patch.object(row.menu_button, "popup") as popup:
            gestures[0].emit("pressed", 1, 0.0, 0.0)

        popup.assert_called_once_with()

    def test_rename_from_menu_saves_new_name(self, panel, db_for_ui: Database) -> None:
        from gi.repository import Gtk

        from command_quiver.ui.section_manager import SectionNameDialog

        old = self._names(db_for_ui)[0]
        before = set(_toplevels_of(SectionNameDialog))
        button_labelled(self._menu_of(panel, old), "Rinomina").emit("clicked")
        dialog = _opened_since(before, SectionNameDialog)[0]
        assert dialog._name_entry.get_text() == old
        dialog._name_entry.set_text("Rinominata")

        button_labelled(dialog, "Rinomina").emit("clicked")

        assert "Rinominata" in self._names(db_for_ui)
        assert old not in self._names(db_for_ui)
        labels = [
            w.get_label() for w in descendants(panel._section_list) if isinstance(w, Gtk.Label)
        ]
        assert "Rinominata" in labels
        assert old not in labels

    def test_rename_to_existing_name_is_refused(self, panel, db_for_ui: Database) -> None:
        from command_quiver.ui.section_manager import SectionNameDialog

        first, second = self._names(db_for_ui)[:2]
        before = set(_toplevels_of(SectionNameDialog))
        button_labelled(self._menu_of(panel, first), "Rinomina").emit("clicked")
        dialog = _opened_since(before, SectionNameDialog)[0]
        dialog._name_entry.set_text(second)

        button_labelled(dialog, "Rinomina").emit("clicked")

        assert self._names(db_for_ui).count(second) == 1
        assert first in self._names(db_for_ui)
        assert dialog._error_label.get_visible() is True

    @pytest.mark.parametrize(("choice", "deleted"), [(1, True), (0, False)])
    def test_delete_from_menu_only_when_confirmed(
        self, panel, db_for_ui: Database, choice: int, deleted: bool
    ) -> None:
        from gi.repository import Gtk

        from command_quiver.ui import section_manager

        _AutoAnswer.choice = choice
        removable = [
            s for s in SectionRepository(db_for_ui.connection).get_all() if not s.is_default
        ]
        target = removable[0].name
        before_names = self._names(db_for_ui)
        with patch.object(section_manager.Gtk, "AlertDialog", _AutoAnswer):
            button_labelled(self._menu_of(panel, target), "Elimina").emit("clicked")

        assert (target not in self._names(db_for_ui)) is deleted
        expected = ["Tutti", *[name for name in before_names if not (deleted and name == target)]]
        labels = [
            next(
                w.get_label()
                for w in descendants(row)
                if isinstance(w, Gtk.Label)
                and w.get_parent() == row
                and not w.has_css_class("section-count")
            )
            for row in descendants(panel._section_list)
            if isinstance(row, SectionRow)
        ]
        assert labels == expected


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


class TestVisibleCounts:
    """Conteggi al netto della voce in cancellazione (funzione pura)."""

    def _sections(self):
        from command_quiver.db.models import Section

        return [Section(id=1, name="A", entry_count=3), Section(id=2, name="B", entry_count=0)]

    def _entry(self, section_id: int):
        from command_quiver.db.models import Entry

        return Entry(id=9, name="x", content="y", section_id=section_id)

    def test_visible_counts_without_hidden_keeps_counts(self) -> None:
        from command_quiver.ui.section_panel import visible_counts

        assert visible_counts(total=3, sections=self._sections(), hidden=None) == (3, {1: 3, 2: 0})

    def test_visible_counts_hidden_entry_lowers_total_and_its_section(self) -> None:
        from command_quiver.ui.section_panel import visible_counts

        result = visible_counts(total=3, sections=self._sections(), hidden=self._entry(1))

        assert result == (2, {1: 2, 2: 0})

    def test_visible_counts_never_goes_below_zero(self) -> None:
        from command_quiver.ui.section_panel import visible_counts

        _, per_section = visible_counts(total=1, sections=self._sections(), hidden=self._entry(2))

        assert per_section[2] == 0


class TestRowIndexFor:
    def test_row_index_for_known_section_returns_its_position(self) -> None:
        from command_quiver.ui.section_panel import row_index_for

        assert row_index_for([None, 4, 7], current_id=7) == 2

    def test_row_index_for_none_selects_all_row(self) -> None:
        from command_quiver.ui.section_panel import row_index_for

        assert row_index_for([None, 4, 7], current_id=None) == 0

    def test_row_index_for_unknown_section_falls_back_to_first(self) -> None:
        from command_quiver.ui.section_panel import row_index_for

        assert row_index_for([None, 4, 7], current_id=99) == 0
