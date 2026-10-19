"""Finestra principale: collegamenti tra ricerca, azioni di finestra, sync e callback dell'app."""

from unittest.mock import MagicMock

import pytest

from command_quiver.core.i18n import init as i18n_init
from command_quiver.core.settings import Settings
from command_quiver.db.entry_repository import EntryRepository
from command_quiver.db.models import EntryCreate
from tests.conftest import button_labelled, key_press, requires_display, run_loop_for, wait_until
from tests.ui.conftest import add_shell_entry, delete_from_editor, shown_names, toplevels


@pytest.fixture(autouse=True)
def _italian() -> None:
    i18n_init("it")


@requires_display
class TestSearch:
    def test_typing_filters_the_list_after_the_debounce(self, make_sidebar, db_for_ui) -> None:
        add_shell_entry(db_for_ui, "Alpha")
        add_shell_entry(db_for_ui, "Beta")
        sidebar = make_sidebar()
        assert sorted(shown_names(sidebar)) == ["Alpha", "Beta"]

        sidebar._search_entry.set_text("alp")

        assert wait_until(lambda: shown_names(sidebar) == ["Alpha"])

    def test_escape_clears_a_non_empty_search_and_is_consumed(self, make_sidebar) -> None:
        from gi.repository import Gdk

        sidebar = make_sidebar()
        sidebar._search_entry.set_text("alp")

        assert key_press(sidebar, Gdk.KEY_Escape) is True
        assert sidebar._search_entry.get_text() == ""

    def test_escape_with_empty_search_is_left_to_gtk(self, make_sidebar) -> None:
        from gi.repository import Gdk

        sidebar = make_sidebar()

        assert key_press(sidebar, Gdk.KEY_Escape) is False

    def test_cancel_pending_timers_drops_a_search_still_debouncing(
        self, make_sidebar, db_for_ui
    ) -> None:
        from command_quiver.ui.search_bar import _SEARCH_DEBOUNCE_MS

        add_shell_entry(db_for_ui, "Alpha")
        add_shell_entry(db_for_ui, "Beta")
        sidebar = make_sidebar()
        sidebar._search_entry.set_text("alp")
        run_loop_for(sidebar._search_entry.get_search_delay() + 60)

        sidebar.cancel_pending_timers()

        run_loop_for(_SEARCH_DEBOUNCE_MS + 200)
        assert sorted(shown_names(sidebar)) == ["Alpha", "Beta"]

    def test_cancel_pending_timers_makes_a_pending_delete_final(
        self, make_sidebar, db_for_ui
    ) -> None:
        entry_id = add_shell_entry(db_for_ui, "Alpha")
        sidebar = make_sidebar()
        delete_from_editor(sidebar, "Alpha")
        assert EntryRepository(db_for_ui.connection).get_by_id(entry_id) is not None

        sidebar.cancel_pending_timers()

        assert EntryRepository(db_for_ui.connection).get_by_id(entry_id) is None


@requires_display
class TestAppCallbacks:
    def test_saving_an_entry_notifies_the_app_once(self, make_sidebar) -> None:
        on_changed = MagicMock()
        sidebar = make_sidebar(on_data_changed=on_changed)

        sidebar._library.save(EntryCreate(name="Nuova", content="ls", section_id=1, type="shell"))

        on_changed.assert_called_once_with()

    def test_language_action_asks_the_app_only_for_a_different_language(self, make_sidebar) -> None:
        from gi.repository import GLib

        requested: list[str] = []
        sidebar = make_sidebar(on_language_changed=requested.append)

        sidebar.activate_action("win.language", GLib.Variant("s", "it"))  # già in uso
        sidebar.activate_action("win.language", GLib.Variant("s", "en"))

        assert wait_until(lambda: requested != [])
        assert requested == ["en"]

    def test_enabling_sync_from_the_dialog_resets_status_and_tells_the_app(
        self, make_sidebar
    ) -> None:
        from command_quiver.ui.sync_dialog import SyncSetupDialog

        toggled = MagicMock()
        sidebar = make_sidebar(on_sync_toggled=toggled)
        assert sidebar._status_bar.text == "Salvato solo su questo computer"
        before = toplevels()

        sidebar.activate_action("win.sync", None)
        dialogs = [w for w in toplevels() - before if isinstance(w, SyncSetupDialog)]
        assert len(dialogs) == 1
        dialogs[0]._repo_entry.set_text("mrossi/vault")
        dialogs[0]._token_entry.set_text("ghp_x")
        button_labelled(dialogs[0], "Attiva sincronizzazione").emit("clicked")

        toggled.assert_called_once_with()
        assert sidebar._status_bar.text == "Non ancora sincronizzato"

    def test_sync_now_button_calls_the_app(self, make_sidebar) -> None:
        from command_quiver.core.settings import SyncSettings
        from command_quiver.ui.sync_dialog import SyncSetupDialog

        requested = MagicMock()
        sidebar = make_sidebar(
            settings=Settings(sync=SyncSettings(enabled=True)), on_sync_now=requested
        )
        before = toplevels()
        sidebar.activate_action("win.sync", None)
        dialog = next(w for w in toplevels() - before if isinstance(w, SyncSetupDialog))
        button = button_labelled(dialog, "Sincronizza ora")
        assert button.get_visible()

        button.emit("clicked")

        requested.assert_called_once_with()


@requires_display
class TestEntrySignals:
    def test_search_activate_copies_first_filtered_entry(
        self, make_sidebar, db_for_ui, monkeypatch
    ) -> None:
        copied: list[str] = []
        monkeypatch.setattr(
            "command_quiver.ui.entry_list.copy_to_clipboard",
            lambda text: copied.append(text) or True,
        )
        add_shell_entry(db_for_ui, "Hidden")
        add_shell_entry(db_for_ui, "Beta")
        add_shell_entry(db_for_ui, "Bravo")
        sidebar = make_sidebar(settings=Settings(sort_order="alpha_asc"))
        sidebar._search_entry.set_text("b")
        assert wait_until(lambda: shown_names(sidebar) == ["Beta", "Bravo"])

        sidebar._search_entry.emit("activate")

        assert copied == ["echo Beta"]

    def test_alt_down_moves_focused_entry_one_place(self, make_sidebar, db_for_ui) -> None:
        from gi.repository import Gdk

        for name in ("First", "Second", "Third"):
            add_shell_entry(db_for_ui, name)
        sidebar = make_sidebar(settings=Settings(sort_order="personal"))
        sidebar.present()
        listing = sidebar._entry_list._list_box
        row = listing.get_row_at_index(1)
        row.grab_focus()
        assert wait_until(lambda: listing.get_focus_child() == row)

        key_press(listing, Gdk.KEY_Down, Gdk.ModifierType.ALT_MASK)

        assert shown_names(sidebar) == ["First", "Third", "Second"]

    def test_copy_row_increments_only_its_usage(self, make_sidebar, db_for_ui, monkeypatch) -> None:
        monkeypatch.setattr("command_quiver.ui.entry_list.copy_to_clipboard", lambda text: True)
        first = add_shell_entry(db_for_ui, "Alpha")
        second = add_shell_entry(db_for_ui, "Beta")
        sidebar = make_sidebar(settings=Settings(sort_order="alpha_asc"))
        listing = sidebar._entry_list._list_box

        listing.emit("row-activated", listing.get_row_at_index(1))

        repo = EntryRepository(db_for_ui.connection)
        assert (repo.get_by_id(first).use_count, repo.get_by_id(second).use_count) == (0, 1)
