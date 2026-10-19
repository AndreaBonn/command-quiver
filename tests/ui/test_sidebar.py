"""Test per il pannello laterale Sidebar: integrazione con DB reale."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from command_quiver.core.settings import Settings
from command_quiver.db.database import Database
from command_quiver.db.entry_repository import EntryRepository
from command_quiver.db.models import EntryCreate, EntryUpdate
from tests.conftest import requires_display


@requires_display
class TestSidebarPanel:
    """Test pannello laterale con database reale."""

    def _create_sidebar(self, db: Database, settings: Settings | None = None):
        from command_quiver.ui.sidebar import SidebarPanel

        return SidebarPanel(
            db=db,
            settings=settings or Settings(),
        )

    def test_creates_with_default_sections(
        self,
        gtk_init,
        db_for_ui: Database,
    ) -> None:
        sidebar = self._create_sidebar(db_for_ui)
        # Lista sezioni: "Tutti" + 4 default
        row_count = 0
        while sidebar._section_panel._section_list.get_row_at_index(row_count):
            row_count += 1
        assert row_count == 5  # Tutti + 4 sezioni

    def test_search_filters_entries(
        self,
        gtk_init,
        db_for_ui: Database,
    ) -> None:
        # Inserisci voci
        repo = EntryRepository(db_for_ui.connection)
        repo.create(
            EntryCreate(
                name="Docker Build",
                content="docker build .",
                section_id=1,
                type="shell",
            )
        )
        repo.create(
            EntryCreate(
                name="Git Status",
                content="git status",
                section_id=1,
                type="shell",
            )
        )

        sidebar = self._create_sidebar(db_for_ui)

        # Ricerca "docker"
        sidebar._search_text = "docker"
        sidebar._refresh_entries()

        assert len(sidebar._entry_list.entries) == 1
        assert sidebar._entry_list.entries[0].name == "Docker Build"

    def test_section_selection_filters_entries(
        self,
        gtk_init,
        db_for_ui: Database,
    ) -> None:
        repo = EntryRepository(db_for_ui.connection)
        repo.create(
            EntryCreate(
                name="Shell Cmd",
                content="ls",
                section_id=1,
                type="shell",
            )
        )
        repo.create(
            EntryCreate(
                name="AI Prompt",
                content="summarize",
                section_id=2,
                type="prompt",
            )
        )

        sidebar = self._create_sidebar(db_for_ui)

        # Seleziona sezione Shell Commands (id=1)
        sidebar._section_panel.current_section_id = 1
        sidebar._refresh_entries()
        assert len(sidebar._entry_list.entries) == 1
        assert sidebar._entry_list.entries[0].name == "Shell Cmd"

        # Seleziona "Tutti" (None)
        sidebar._section_panel.current_section_id = None
        sidebar._refresh_entries()
        assert len(sidebar._entry_list.entries) == 2

    def test_on_entry_saved_creates_new(
        self,
        gtk_init,
        db_for_ui: Database,
    ) -> None:
        sidebar = self._create_sidebar(db_for_ui)
        repo = EntryRepository(db_for_ui.connection)

        assert repo.count_all() == 0

        sidebar._library.save(
            EntryCreate(
                name="New",
                content="echo new",
                section_id=1,
                type="shell",
            )
        )
        assert repo.count_all() == 1

    def test_on_entry_saved_updates_existing(
        self,
        gtk_init,
        db_for_ui: Database,
    ) -> None:
        repo = EntryRepository(db_for_ui.connection)
        entry = repo.create(
            EntryCreate(
                name="Old",
                content="old",
                section_id=1,
                type="shell",
            )
        )

        sidebar = self._create_sidebar(db_for_ui)
        sidebar._library.save(
            EntryUpdate(
                id=entry.id,
                name="Updated",
                content="new content",
                section_id=1,
                type="shell",
            )
        )

        updated = repo.get_by_id(entry.id)
        assert updated.name == "Updated"
        assert updated.content == "new content"

    def test_on_entry_deleted_removes_entry(
        self,
        gtk_init,
        db_for_ui: Database,
    ) -> None:
        repo = EntryRepository(db_for_ui.connection)
        entry = repo.create(
            EntryCreate(
                name="To Delete",
                content="x",
                section_id=1,
                type="shell",
            )
        )

        sidebar = self._create_sidebar(db_for_ui)
        sidebar._library.delete(entry.id)
        # E7: la cancellazione diventa definitiva alla scadenza dell'annullamento
        sidebar._pending_delete.flush()
        assert repo.get_by_id(entry.id) is None

    def test_on_section_created(
        self,
        gtk_init,
        db_for_ui: Database,
    ) -> None:
        from command_quiver.db.section_repository import SectionRepository

        sidebar = self._create_sidebar(db_for_ui)
        sidebar._section_panel._on_section_created("Docker")

        sections = SectionRepository(db_for_ui.connection).get_all()
        names = [s.name for s in sections]
        assert "Docker" in names

    def test_on_section_deleted_resets_current(
        self,
        gtk_init,
        db_for_ui: Database,
    ) -> None:
        sidebar = self._create_sidebar(db_for_ui)
        sidebar._section_panel.current_section_id = 1

        sidebar._section_panel._on_section_deleted(1)
        assert sidebar._section_panel.current_section_id is None

    def test_on_section_renamed(
        self,
        gtk_init,
        db_for_ui: Database,
    ) -> None:
        from command_quiver.db.section_repository import SectionRepository

        sidebar = self._create_sidebar(db_for_ui)
        sidebar._section_panel._on_section_renamed(section_id=1, new_name="Comandi")

        section = SectionRepository(db_for_ui.connection).get_by_id(1)
        assert section.name == "Comandi"

    def test_escape_clears_search_instead_of_closing(
        self,
        gtk_init,
        db_for_ui: Database,
    ) -> None:
        # M15: Esc svuota la ricerca; non chiude più la finestra (e quindi l'app)
        import gi

        gi.require_version("Gtk", "4.0")
        from gi.repository import Gdk

        sidebar = self._create_sidebar(db_for_ui)
        sidebar._search_entry.set_text("docker")
        with patch.object(sidebar, "close") as mock_close:
            result = sidebar._on_key_pressed(None, Gdk.KEY_Escape, 0, Gdk.ModifierType(0))
        assert result is True
        assert sidebar._search_entry.get_text() == ""
        mock_close.assert_not_called()

    def test_escape_with_empty_search_does_not_close(
        self,
        gtk_init,
        db_for_ui: Database,
    ) -> None:
        import gi

        gi.require_version("Gtk", "4.0")
        from gi.repository import Gdk

        sidebar = self._create_sidebar(db_for_ui)
        with patch.object(sidebar, "close") as mock_close:
            result = sidebar._on_key_pressed(None, Gdk.KEY_Escape, 0, Gdk.ModifierType(0))
        assert result is False
        mock_close.assert_not_called()

    def test_close_request_saves_settings(
        self,
        gtk_init,
        db_for_ui: Database,
        tmp_path: Path,
    ) -> None:
        settings = Settings()
        sidebar = self._create_sidebar(db_for_ui, settings=settings)
        sidebar._section_panel.current_section_id = 3

        with patch("command_quiver.ui.sidebar.save_settings") as mock_save:
            result = sidebar._on_close_request(sidebar)
            assert result is False  # Consente la distruzione: l'app termina
            mock_save.assert_called_once()
            saved = mock_save.call_args[0][0]
            assert saved.last_section_id == 3
            # Si salva la dimensione predefinita (quella che GTK riapplica), non get_width:
            # get_width esclude i margini e la finestra si stringeva a ogni avvio
            assert (saved.window_width, saved.window_height) == sidebar.get_default_size()

    def test_language_menu_action_invokes_callback_with_code(
        self,
        gtk_init,
        db_for_ui: Database,
    ) -> None:
        # S1: la lingua è nel menu principale (azione win.language)
        from gi.repository import GLib

        from command_quiver.core.i18n import init as i18n_init
        from command_quiver.ui.sidebar import SidebarCallbacks, SidebarPanel

        i18n_init("it")
        callback = MagicMock()
        sidebar = SidebarPanel(
            db=db_for_ui,
            settings=Settings(),
            callbacks=SidebarCallbacks(on_language_changed=callback),
        )

        # idle_add eseguito subito per verificare l'invocazione del callback
        with patch("gi.repository.GLib.idle_add", side_effect=lambda fn, *a: fn(*a)):
            sidebar.activate_action("win.language", GLib.Variant("s", "en"))

        callback.assert_called_once_with("en")

    def test_sort_change_persists(
        self,
        gtk_init,
        db_for_ui: Database,
    ) -> None:
        sidebar = self._create_sidebar(db_for_ui)

        with patch("command_quiver.ui.sidebar.save_settings") as mock_save:
            sidebar._sort_dropdown.set_selected(2)  # A → Z
            # Il signal notify::selected dovrebbe aver salvato
            # Verifichiamo manualmente
            sidebar._on_sort_changed(sidebar._sort_dropdown, None)
            mock_save.assert_called()

    def test_open_new_entry_dialog(
        self,
        gtk_init,
        db_for_ui: Database,
    ) -> None:
        sidebar = self._create_sidebar(db_for_ui)

        with patch("command_quiver.ui.library_controller.EntryEditorDialog") as mock_dialog:
            sidebar.open_new_entry_dialog()
            mock_dialog.assert_called_once()

    def test_non_escape_key_returns_false(
        self,
        gtk_init,
        db_for_ui: Database,
    ) -> None:
        import gi

        gi.require_version("Gtk", "4.0")
        from gi.repository import Gdk

        sidebar = self._create_sidebar(db_for_ui)
        result = sidebar._on_key_pressed(None, Gdk.KEY_a, 0, Gdk.ModifierType(0))
        assert result is False

    def test_entry_move_swaps_positions(
        self,
        gtk_init,
        db_for_ui: Database,
    ) -> None:
        repo = EntryRepository(db_for_ui.connection)
        e1 = repo.create(EntryCreate(name="First", content="1", section_id=1, type="shell"))
        e2 = repo.create(EntryCreate(name="Second", content="2", section_id=1, type="shell"))

        sidebar = self._create_sidebar(db_for_ui)
        sidebar._section_panel.current_section_id = 1

        # Imposta ordinamento personale
        sidebar._sort_dropdown.set_selected(4)  # personal
        sidebar._settings.sort_order = "personal"
        sidebar._refresh_entries()

        # Sposta la prima voce in giù
        sidebar._library.move(entry_id=e1.id, direction=1)

        assert [entry.id for entry in sidebar._entry_list.entries] == [e2.id, e1.id]

    def test_entry_move_noop_at_boundary(
        self,
        gtk_init,
        db_for_ui: Database,
    ) -> None:
        repo = EntryRepository(db_for_ui.connection)
        e1 = repo.create(EntryCreate(name="First", content="x", section_id=1, type="shell"))
        e2 = repo.create(EntryCreate(name="Second", content="y", section_id=1, type="shell"))

        sidebar = self._create_sidebar(db_for_ui)
        sidebar._section_panel.current_section_id = 1
        sidebar._sort_dropdown.set_selected(4)
        sidebar._settings.sort_order = "personal"
        sidebar._refresh_entries()

        # Sposta verso l'alto -> fuori range -> noop
        sidebar._library.move(entry_id=e1.id, direction=-1)
        assert [entry.id for entry in sidebar._entry_list.entries] == [e1.id, e2.id]

    def test_entry_move_nonexistent_entry_noop(
        self,
        gtk_init,
        db_for_ui: Database,
    ) -> None:
        repo = EntryRepository(db_for_ui.connection)
        first = repo.create(EntryCreate(name="First", content="x", section_id=1))
        second = repo.create(EntryCreate(name="Second", content="y", section_id=1))
        sidebar = self._create_sidebar(db_for_ui, Settings(sort_order="personal"))

        sidebar._library.move(entry_id=9999, direction=1)

        assert [entry.id for entry in sidebar._entry_list.entries] == [first.id, second.id]

    def test_on_entry_click_opens_editor(
        self,
        gtk_init,
        db_for_ui: Database,
    ) -> None:
        repo = EntryRepository(db_for_ui.connection)
        entry = repo.create(EntryCreate(name="Click Me", content="x", section_id=1, type="shell"))

        sidebar = self._create_sidebar(db_for_ui)

        with patch("command_quiver.ui.library_controller.EntryEditorDialog") as mock_dialog:
            sidebar._on_entry_click(entry)
            mock_dialog.assert_called_once()
            # Verifica che entry viene passato al dialog
            call_kwargs = mock_dialog.call_args[1]
            assert call_kwargs["request"].entry == entry
