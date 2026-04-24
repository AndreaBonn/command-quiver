"""Test per i dialog di gestione sezioni."""

from unittest.mock import MagicMock

from command_quiver.db.queries import Section
from tests.conftest import requires_display


@requires_display
class TestSectionCreateDialog:
    """Test dialog creazione sezione."""

    def _create_dialog(self, on_create=None):
        import gi

        from command_quiver.ui.section_manager import SectionCreateDialog

        gi.require_version("Gtk", "4.0")
        from gi.repository import Gtk

        parent = Gtk.Window()
        return SectionCreateDialog(
            parent=parent,
            on_create=on_create or MagicMock(),
        )

    def test_rejects_empty_name(self, gtk_init) -> None:
        mock_create = MagicMock()
        dialog = self._create_dialog(on_create=mock_create)
        dialog._name_entry.set_text("")

        dialog._do_create()
        mock_create.assert_not_called()
        assert dialog._error_label.get_visible() is True

    def test_rejects_whitespace_name(self, gtk_init) -> None:
        mock_create = MagicMock()
        dialog = self._create_dialog(on_create=mock_create)
        dialog._name_entry.set_text("   ")

        dialog._do_create()
        mock_create.assert_not_called()

    def test_calls_on_create_with_valid_name(self, gtk_init) -> None:
        mock_create = MagicMock()
        dialog = self._create_dialog(on_create=mock_create)
        dialog._name_entry.set_text("Docker")

        dialog._do_create()
        mock_create.assert_called_once_with("Docker")

    def test_strips_whitespace_from_name(self, gtk_init) -> None:
        mock_create = MagicMock()
        dialog = self._create_dialog(on_create=mock_create)
        dialog._name_entry.set_text("  Docker  ")

        dialog._do_create()
        mock_create.assert_called_once_with("Docker")


@requires_display
class TestSectionRenameDialog:
    """Test dialog rinomina sezione."""

    def _create_dialog(self, section=None, on_rename=None):
        import gi

        from command_quiver.ui.section_manager import SectionRenameDialog

        gi.require_version("Gtk", "4.0")
        from gi.repository import Gtk

        parent = Gtk.Window()
        section = section or Section(id=1, name="Shell Commands", position=0)
        return SectionRenameDialog(
            parent=parent,
            section=section,
            on_rename=on_rename or MagicMock(),
        )

    def test_prepopulates_current_name(self, gtk_init) -> None:
        section = Section(id=1, name="Old Name", position=0)
        dialog = self._create_dialog(section=section)
        assert dialog._name_entry.get_text() == "Old Name"

    def test_calls_on_rename_with_new_name(self, gtk_init) -> None:
        mock_rename = MagicMock()
        section = Section(id=5, name="Old", position=0)
        dialog = self._create_dialog(section=section, on_rename=mock_rename)
        dialog._name_entry.set_text("New Name")

        dialog._do_rename()
        mock_rename.assert_called_once_with(5, "New Name")

    def test_does_not_rename_if_same_name(self, gtk_init) -> None:
        mock_rename = MagicMock()
        section = Section(id=1, name="Same", position=0)
        dialog = self._create_dialog(section=section, on_rename=mock_rename)
        # Nome invariato
        dialog._do_rename()
        mock_rename.assert_not_called()

    def test_does_not_rename_empty_name(self, gtk_init) -> None:
        mock_rename = MagicMock()
        dialog = self._create_dialog(on_rename=mock_rename)
        dialog._name_entry.set_text("")

        dialog._do_rename()
        mock_rename.assert_not_called()
