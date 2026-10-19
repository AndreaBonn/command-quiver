"""Test per i dialog di gestione sezioni."""

from unittest.mock import MagicMock

from command_quiver.db.models import Section
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
        mock_create = MagicMock(return_value=None)
        dialog = self._create_dialog(on_create=mock_create)
        dialog._name_entry.set_text("Docker")

        dialog._do_create()
        mock_create.assert_called_once_with("Docker")

    def test_strips_whitespace_from_name(self, gtk_init) -> None:
        mock_create = MagicMock(return_value=None)
        dialog = self._create_dialog(on_create=mock_create)
        dialog._name_entry.set_text("  Docker  ")

        dialog._do_create()
        mock_create.assert_called_once_with("Docker")

    def test_shows_error_on_duplicate_name(self, gtk_init) -> None:
        mock_create = MagicMock(return_value="Sezione già esistente")
        dialog = self._create_dialog(on_create=mock_create)
        dialog._name_entry.set_text("Docker")

        dialog._do_create()
        assert dialog._error_label.get_visible() is True
        assert "già esistente" in dialog._error_label.get_label()


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
        mock_rename = MagicMock(return_value=None)
        section = Section(id=5, name="Old", position=0)
        dialog = self._create_dialog(section=section, on_rename=mock_rename)
        dialog._name_entry.set_text("New Name")

        dialog._do_rename()
        mock_rename.assert_called_once_with(5, "New Name")

    def test_shows_error_on_duplicate_rename(self, gtk_init) -> None:
        mock_rename = MagicMock(return_value="Nome già esistente")
        section = Section(id=5, name="Old", position=0)
        dialog = self._create_dialog(section=section, on_rename=mock_rename)
        dialog._name_entry.set_text("Existing")

        dialog._do_rename()
        assert dialog._error_label.get_visible() is True

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


class _FakeAlert:
    """Sostituisce Gtk.AlertDialog: risponde subito con la scelta indicata."""

    choice: int | None = 1  # None = chiuso senza scegliere (GLib.Error)
    last: "_FakeAlert | None" = None

    def __init__(self, message: str, detail: str) -> None:
        self.message = message
        self.buttons: list[str] = []
        type(self).last = self

    def set_buttons(self, buttons: list[str]) -> None:
        self.buttons = buttons

    def set_cancel_button(self, _index: int) -> None:
        pass

    def set_default_button(self, _index: int) -> None:
        pass

    def choose(self, _parent, _cancellable, callback) -> None:
        callback(self, None)

    def choose_finish(self, _result) -> int:
        if self.choice is None:
            from gi.repository import GLib

            raise GLib.Error("annullato")
        return self.choice


@requires_display
class TestDeleteSectionDialog:
    def _ask(self, choice: int | None) -> MagicMock:
        from unittest.mock import patch

        from command_quiver.core.i18n import init as i18n_init
        from command_quiver.ui import section_manager

        i18n_init("it")
        _FakeAlert.choice = choice
        on_confirm = MagicMock()
        with patch.object(section_manager.Gtk, "AlertDialog", _FakeAlert):
            section_manager.show_delete_section_dialog(
                parent=MagicMock(),
                section=Section(id=5, name="Docker"),
                on_confirm=on_confirm,
            )
        return on_confirm

    def test_confirm_deletes_the_section_by_id(self, gtk_init) -> None:
        on_confirm = self._ask(choice=1)

        on_confirm.assert_called_once_with(5)
        assert _FakeAlert.last.buttons == ["Annulla", "Elimina"]
        assert "Docker" in _FakeAlert.last.message

    def test_cancel_button_deletes_nothing(self, gtk_init) -> None:
        self._ask(choice=0).assert_not_called()

    def test_dismissed_dialog_deletes_nothing(self, gtk_init) -> None:
        self._ask(choice=None).assert_not_called()
