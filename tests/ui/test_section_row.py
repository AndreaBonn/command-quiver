"""Test per il menu contestuale della sezione."""

from unittest.mock import MagicMock

from command_quiver.core.i18n import init as i18n_init
from command_quiver.core.i18n import t
from command_quiver.db.models import Section
from tests.conftest import button_labelled, descendants, requires_display


@requires_display
class TestBuildSectionMenu:
    def _menu(self, section: Section, on_rename=None, on_delete=None):
        from command_quiver.ui.section_row import build_section_menu

        i18n_init("it")
        return build_section_menu(
            section, on_rename=on_rename or MagicMock(), on_delete=on_delete or MagicMock()
        )

    def test_rename_button_popdowns_and_passes_the_section(self, gtk_init) -> None:
        section = Section(id=3, name="Docker")
        on_rename = MagicMock()
        popover = self._menu(section, on_rename=on_rename)
        popover.popdown = MagicMock()

        button_labelled(popover, "Rinomina").emit("clicked")

        on_rename.assert_called_once_with(section)
        popover.popdown.assert_called_once()

    def test_delete_button_passes_the_section_for_normal_sections(self, gtk_init) -> None:
        section = Section(id=3, name="Docker")
        on_delete = MagicMock()
        popover = self._menu(section, on_delete=on_delete)

        button_labelled(popover, "Elimina").emit("clicked")

        on_delete.assert_called_once_with(section)

    def test_default_section_has_note_and_no_delete_button(self, gtk_init) -> None:
        from gi.repository import Gtk

        section = Section(id=1, name="Generale", is_default=True)
        popover = self._menu(section)
        labels = [
            w.get_label()
            for w in descendants(popover.get_child())
            if isinstance(w, (Gtk.Button, Gtk.Label))
        ]

        assert "Elimina" not in labels
        assert t("sidebar.default_not_deletable") in labels


@requires_display
class TestSectionRowIdentity:
    def test_section_row_id_is_the_id_of_its_section(self, gtk_init) -> None:
        from command_quiver.ui.section_row import SectionRow

        row = SectionRow(label="Docker", section=Section(id=7, name="Docker"), count=2)

        assert (row.section_id, row.section.name) == (7, "Docker")

    def test_all_entries_row_has_no_section_id(self, gtk_init) -> None:
        from command_quiver.ui.section_row import SectionRow

        row = SectionRow(label="Tutti", count=5)

        assert (row.section_id, row.section) == (None, None)
