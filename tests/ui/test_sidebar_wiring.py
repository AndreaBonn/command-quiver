"""Finestra principale: collegamenti tra ricerca, azioni di finestra, sync e callback dell'app."""

from unittest.mock import MagicMock

import pytest

from command_quiver.core.i18n import init as i18n_init
from command_quiver.core.settings import Settings
from command_quiver.db.database import Database
from command_quiver.db.entry_repository import EntryRepository
from command_quiver.db.models import EntryCreate
from tests.conftest import button_labelled, key_press, requires_display, run_loop_for, wait_until


@pytest.fixture(autouse=True)
def _italian() -> None:
    i18n_init("it")


def _toplevels() -> set:
    from gi.repository import Gtk

    return set(Gtk.Window.list_toplevels())


@pytest.fixture
def make_sidebar(gtk_init, db_for_ui: Database, isolated_config):
    """Costruisce la finestra con settings su tmp; chiude ciò che il test ha aperto."""
    from command_quiver.ui.sidebar import SidebarCallbacks, SidebarPanel

    before = _toplevels()

    def _make(settings: Settings | None = None, **callbacks) -> SidebarPanel:
        return SidebarPanel(
            db=db_for_ui,
            settings=settings or Settings(),
            callbacks=SidebarCallbacks(**callbacks),
        )

    yield _make
    for window in _toplevels() - before:
        window.destroy()


def _add(db: Database, name: str) -> int:
    return (
        EntryRepository(db.connection)
        .create(EntryCreate(name=name, content=f"echo {name}", section_id=1, type="shell"))
        .id
    )


def _delete_from_editor(sidebar, name: str) -> None:
    """Come l'utente: matita sulla riga, poi "Elimina" nell'editor."""
    from gi.repository import Gtk

    from command_quiver.ui.entry_editor import EntryEditorDialog
    from command_quiver.ui.entry_list import EntryRow
    from tests.conftest import descendants

    row = next(
        w
        for w in descendants(sidebar._entry_list)
        if isinstance(w, EntryRow) and w.entry.name == name
    )
    edit = next(
        b
        for b in descendants(row)
        if isinstance(b, Gtk.Button) and b.get_icon_name() == "document-edit-symbolic"
    )
    before = set(Gtk.Window.list_toplevels())
    edit.emit("clicked")
    editor = next(
        w
        for w in Gtk.Window.list_toplevels()
        if isinstance(w, EntryEditorDialog) and w not in before
    )
    button_labelled(editor, "Elimina").emit("clicked")


def _shown(sidebar) -> list[str]:
    return [e.name for e in sidebar._entry_list.entries]


@requires_display
class TestSearch:
    def test_typing_filters_the_list_after_the_debounce(self, make_sidebar, db_for_ui) -> None:
        _add(db_for_ui, "Alpha")
        _add(db_for_ui, "Beta")
        sidebar = make_sidebar()
        assert sorted(_shown(sidebar)) == ["Alpha", "Beta"]

        sidebar._search_entry.set_text("alp")

        assert wait_until(lambda: _shown(sidebar) == ["Alpha"])

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

        _add(db_for_ui, "Alpha")
        _add(db_for_ui, "Beta")
        sidebar = make_sidebar()
        sidebar._search_entry.set_text("alp")
        run_loop_for(sidebar._search_entry.get_search_delay() + 60)

        sidebar.cancel_pending_timers()

        run_loop_for(_SEARCH_DEBOUNCE_MS + 200)
        assert sorted(_shown(sidebar)) == ["Alpha", "Beta"]

    def test_cancel_pending_timers_makes_a_pending_delete_final(
        self, make_sidebar, db_for_ui
    ) -> None:
        entry_id = _add(db_for_ui, "Alpha")
        sidebar = make_sidebar()
        _delete_from_editor(sidebar, "Alpha")
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
        before = _toplevels()

        sidebar.activate_action("win.sync", None)
        dialogs = [w for w in _toplevels() - before if isinstance(w, SyncSetupDialog)]
        assert len(dialogs) == 1
        dialogs[0]._repo_entry.set_text("mrossi/vault")
        dialogs[0]._token_entry.set_text("ghp_x")
        button_labelled(dialogs[0], "Attiva sincronizzazione").emit("clicked")

        toggled.assert_called_once_with()
        assert sidebar._status_bar.text == "Non ancora sincronizzato"
