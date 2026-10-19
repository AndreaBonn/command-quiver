"""Finestra Informazioni e azioni della finestra principale."""

import pytest

from command_quiver.core.settings import Settings
from command_quiver.db.entry_repository import EntryRepository
from command_quiver.db.models import EntryCreate
from tests.conftest import requires_display, wait_until
from tests.ui.conftest import add_shell_entry, delete_from_editor, shown_names, toplevels


def _menu_actions(model) -> dict[str, str]:
    actions = {}
    for index in range(model.get_n_items()):
        action = model.get_item_attribute_value(index, "action", None)
        if action is not None:
            label = model.get_item_attribute_value(index, "label", None)
            actions[label.get_string()] = action.get_string()
        for link in ("section", "submenu"):
            child = model.get_item_link(index, link)
            if child is not None:
                actions.update(_menu_actions(child))
    return actions


@requires_display
def test_header_controls_target_expected_window_actions(make_sidebar) -> None:
    from gi.repository import Gtk

    from command_quiver.core.i18n import init as i18n_init
    from tests.conftest import descendants

    i18n_init("it")
    window = make_sidebar()
    widgets = list(descendants(window.get_titlebar()))
    menu = next(w for w in widgets if isinstance(w, Gtk.MenuButton))
    new = next(
        w
        for w in widgets
        if isinstance(w, Gtk.Button) and w.get_tooltip_text() == "Nuova voce (Ctrl+N)"
    )

    assert (new.get_action_name(), _menu_actions(menu.get_menu_model())) == (
        "win.new-entry",
        {
            "Italiano": "win.language",
            "English": "win.language",
            "Sincronizzazione…": "win.sync",
            "Importa voci…": "win.import",
            "Esporta voci…": "win.export",
            "Scorciatoie da tastiera": "win.shortcuts",
            "Informazioni": "win.about",
            "Esci": "win.quit",
        },
    )


@requires_display
def test_about_dialog_shows_the_app_version(gtk_init) -> None:
    from gi.repository import Gtk

    from command_quiver import __version__
    from command_quiver.core.i18n import init as i18n_init
    from command_quiver.ui.window_actions import show_about

    i18n_init("it")
    parent = Gtk.Window()
    before = set(Gtk.Window.list_toplevels())

    show_about(parent)

    about = [w for w in Gtk.Window.list_toplevels() if w not in before]
    try:
        assert len(about) == 1
        assert isinstance(about[0], Gtk.AboutDialog)
        assert about[0].get_version() == __version__
        assert about[0].get_program_name() == "Command Quiver"
    finally:
        for window in about:
            window.destroy()
        parent.destroy()


@requires_display
def test_window_shortcut_controller_maps_documented_keys(gtk_init, db_for_ui) -> None:
    from gi.repository import Gtk

    from command_quiver.ui.sidebar import SidebarPanel

    window = SidebarPanel(db=db_for_ui, settings=Settings())
    try:
        controllers = window.observe_controllers()
        mappings = {}
        for index in range(controllers.get_n_items()):
            controller = controllers.get_item(index)
            if isinstance(controller, Gtk.ShortcutController):
                for item in range(controller.get_n_items()):
                    shortcut = controller.get_item(item)
                    action = shortcut.get_action().to_string()
                    if action.startswith("action(win."):
                        mappings[shortcut.get_trigger().to_string()] = action

        assert mappings == {
            "<Control>f": "action(win.focus-search)",
            "<Control>n": "action(win.new-entry)",
            "<Control>q": "action(win.quit)",
            "<Control>question": "action(win.shortcuts)",
        }
    finally:
        window.destroy()


@requires_display
class TestWindowActions:
    @pytest.mark.parametrize("action", ["new-entry", "shortcuts", "about"])
    def test_action_opens_expected_dialog(self, make_sidebar, action) -> None:
        from gi.repository import Gtk

        from command_quiver.ui.entry_editor import EntryEditorDialog
        from command_quiver.ui.shortcuts_dialog import ShortcutsDialog

        expected = {
            "new-entry": EntryEditorDialog,
            "shortcuts": ShortcutsDialog,
            "about": Gtk.AboutDialog,
        }
        sidebar = make_sidebar()
        before = toplevels()

        sidebar.activate_action(f"win.{action}", None)

        assert wait_until(
            lambda: any(isinstance(w, expected[action]) for w in toplevels() - before)
        )

    def test_focus_search_action_moves_keyboard_focus(self, make_sidebar) -> None:
        from tests.conftest import descendants

        sidebar = make_sidebar()
        sidebar.present()
        sidebar._sort_dropdown.grab_focus()
        assert wait_until(
            lambda: (
                sidebar.get_focus()
                in [sidebar._sort_dropdown, *descendants(sidebar._sort_dropdown)]
            )
        )

        sidebar.activate_action("win.focus-search", None)

        assert wait_until(lambda: sidebar.get_focus() in descendants(sidebar._search_entry))

    def test_quit_action_closes_window_and_saves_state(self, make_sidebar) -> None:
        from command_quiver.core.settings import load_settings

        sidebar = make_sidebar()
        sidebar.present()
        assert wait_until(sidebar.get_visible)
        sidebar.set_default_size(900, 740)

        sidebar.activate_action("win.quit", None)

        assert wait_until(lambda: not sidebar.get_visible())
        assert (load_settings().window_width, load_settings().window_height) == (900, 740)

    def test_export_action_writes_library(
        self, make_sidebar, db_for_ui, tmp_path, monkeypatch
    ) -> None:
        from command_quiver.core.library_io import parse_import
        from command_quiver.ui import library_actions
        from tests.conftest import fake_file_dialog

        add_shell_entry(db_for_ui, "Alpha")
        target = tmp_path / "export.json"
        monkeypatch.setattr(library_actions.Gtk, "FileDialog", fake_file_dialog(target))
        sidebar = make_sidebar()

        sidebar.activate_action("win.export", None)

        assert [(e["name"], e["content"]) for e in parse_import(target.read_text())] == [
            ("Alpha", "echo Alpha")
        ]

    def test_import_action_loads_library_and_updates_list(
        self, make_sidebar, tmp_path, monkeypatch
    ) -> None:
        from command_quiver.core.library_io import serialize_export
        from command_quiver.ui import library_actions
        from tests.conftest import fake_file_dialog

        source = tmp_path / "import.json"
        source.write_text(serialize_export([{"name": "Imported", "content": "echo imported"}]))
        monkeypatch.setattr(library_actions.Gtk, "FileDialog", fake_file_dialog(source))
        sidebar = make_sidebar()

        sidebar.activate_action("win.import", None)

        assert shown_names(sidebar) == ["Imported"]


@requires_display
class TestWindowState:
    def test_close_saves_selected_section_and_dimensions(
        self, make_sidebar, isolated_config
    ) -> None:
        from command_quiver.core.settings import load_settings

        sidebar = make_sidebar()
        sidebar._section_panel.select_section(2)
        sidebar.set_default_size(880, 720)

        sidebar.emit("close-request")

        saved = load_settings()
        assert (saved.last_section_id, saved.window_width, saved.window_height) == (2, 880, 720)

    def test_close_finalizes_pending_delete(self, make_sidebar, db_for_ui) -> None:
        entry_id = add_shell_entry(db_for_ui, "Alpha")
        sidebar = make_sidebar()
        delete_from_editor(sidebar, "Alpha")
        repo = EntryRepository(db_for_ui.connection)
        assert repo.get_by_id(entry_id).name == "Alpha"

        sidebar.emit("close-request")

        assert repo.get_by_id(entry_id) is None

    def test_startup_restores_saved_section_and_its_entries(self, make_sidebar, db_for_ui) -> None:
        add_shell_entry(db_for_ui, "Shell")
        EntryRepository(db_for_ui.connection).create(
            EntryCreate(name="Prompt", content="Riassumi", section_id=2)
        )

        sidebar = make_sidebar(settings=Settings(last_section_id=2))

        selected = sidebar._section_panel._section_list.get_selected_row().get_child()
        assert (selected.section_id, shown_names(sidebar)) == (2, ["Prompt"])

    @pytest.mark.parametrize(
        ("index", "order", "names"),
        [(2, "alpha_asc", ["Alpha", "Beta"]), (3, "alpha_desc", ["Beta", "Alpha"])],
    )
    def test_sort_dropdown_persists_choice_and_reorders(
        self, make_sidebar, db_for_ui, index, order, names
    ) -> None:
        from command_quiver.core.settings import load_settings

        add_shell_entry(db_for_ui, "Alpha")
        add_shell_entry(db_for_ui, "Beta")
        sidebar = make_sidebar()

        sidebar._sort_dropdown.set_selected(index)

        assert (load_settings().sort_order, shown_names(sidebar)) == (order, names)
