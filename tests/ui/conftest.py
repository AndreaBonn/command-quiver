"""Fixture e helper della finestra principale condivisi fra i test UI."""

import pytest

from command_quiver.core.settings import Settings
from command_quiver.db.database import Database
from command_quiver.db.entry_repository import EntryRepository
from command_quiver.db.models import EntryCreate
from tests.conftest import button_labelled


def toplevels() -> set:
    from gi.repository import Gtk

    return set(Gtk.Window.list_toplevels())


@pytest.fixture
def make_sidebar(gtk_init, db_for_ui: Database, isolated_config):
    """Costruisce la finestra con settings su tmp; chiude ciò che il test ha aperto."""
    from command_quiver.ui.sidebar import SidebarCallbacks, SidebarPanel

    before = toplevels()

    def _make(settings: Settings | None = None, **callbacks) -> SidebarPanel:
        return SidebarPanel(
            db=db_for_ui,
            settings=settings or Settings(),
            callbacks=SidebarCallbacks(**callbacks),
        )

    yield _make
    for window in toplevels() - before:
        if isinstance(window, SidebarPanel):
            # Come fa l'app prima di distruggerla: un debounce di ricerca pendente
            # scatterebbe in un test successivo, a DB già chiuso
            window.cancel_pending_timers()
        window.destroy()


def add_shell_entry(db: Database, name: str) -> int:
    return (
        EntryRepository(db.connection)
        .create(EntryCreate(name=name, content=f"echo {name}", section_id=1, type="shell"))
        .id
    )


def delete_from_editor(sidebar, name: str) -> None:
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


def shown_names(sidebar) -> list[str]:
    return [e.name for e in sidebar._entry_list.entries]
