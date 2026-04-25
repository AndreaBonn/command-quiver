"""Test per SectionPanelWidget: lista sezioni, selezione, CRUD."""

from unittest.mock import MagicMock

from command_quiver.db.database import Database
from command_quiver.db.queries import (
    EntryRepository,
    SectionRepository,
)
from tests.conftest import requires_display


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
