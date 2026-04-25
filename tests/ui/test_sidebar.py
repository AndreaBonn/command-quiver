"""Test per il pannello laterale Sidebar: integrazione con DB reale."""

from pathlib import Path
from unittest.mock import patch

from command_quiver.core.settings import Settings
from command_quiver.db.database import Database
from command_quiver.db.queries import EntryCreate, EntryRepository, EntryUpdate
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

        assert len(sidebar._entry_list._entries) == 1
        assert sidebar._entry_list._entries[0].name == "Docker Build"

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
        assert len(sidebar._entry_list._entries) == 1
        assert sidebar._entry_list._entries[0].name == "Shell Cmd"

        # Seleziona "Tutti" (None)
        sidebar._section_panel.current_section_id = None
        sidebar._refresh_entries()
        assert len(sidebar._entry_list._entries) == 2

    def test_on_entry_saved_creates_new(
        self,
        gtk_init,
        db_for_ui: Database,
    ) -> None:
        sidebar = self._create_sidebar(db_for_ui)
        repo = EntryRepository(db_for_ui.connection)

        assert repo.count_all() == 0

        sidebar._on_entry_saved(
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
        sidebar._on_entry_saved(
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
        sidebar._on_entry_deleted(entry.id)
        assert repo.get_by_id(entry.id) is None

    def test_on_section_created(
        self,
        gtk_init,
        db_for_ui: Database,
    ) -> None:
        from command_quiver.db.queries import SectionRepository

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
        from command_quiver.db.queries import SectionRepository

        sidebar = self._create_sidebar(db_for_ui)
        sidebar._section_panel._on_section_renamed(section_id=1, new_name="Comandi")

        section = SectionRepository(db_for_ui.connection).get_by_id(1)
        assert section.name == "Comandi"

    def test_escape_hides_panel(
        self,
        gtk_init,
        db_for_ui: Database,
    ) -> None:
        import gi

        gi.require_version("Gtk", "4.0")
        from gi.repository import Gdk

        sidebar = self._create_sidebar(db_for_ui)
        result = sidebar._on_key_pressed(None, Gdk.KEY_Escape, 0, Gdk.ModifierType(0))
        assert result is True

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
            assert result is True  # Impedisce la distruzione
            mock_save.assert_called_once()
            saved = mock_save.call_args[0][0]
            assert saved.last_section_id == 3

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

        with patch("command_quiver.ui.sidebar.EntryEditorDialog") as mock_dialog:
            sidebar.open_new_entry_dialog()
            mock_dialog.assert_called_once()
