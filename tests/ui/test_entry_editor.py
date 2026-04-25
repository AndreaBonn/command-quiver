"""Test per EntryEditorDialog: validazione, raccolta dati, shortcut."""

from unittest.mock import MagicMock, patch

from command_quiver.db.queries import Entry, EntryCreate, EntryUpdate, Section
from tests.conftest import requires_display


def _make_sections() -> list[Section]:
    """Helper per creare sezioni di test."""
    return [
        Section(id=1, name="Shell Commands", position=0),
        Section(id=2, name="AI Prompts", position=1),
        Section(id=3, name="Generale", position=2),
    ]


def _make_entry() -> Entry:
    """Helper per creare un entry di test."""
    return Entry(
        id=42,
        name="Docker Build",
        content="docker build -t myapp .",
        section_id=1,
        type="shell",
        tags="docker,build",
        personal_pos=0,
        created_at="2026-01-01",
        updated_at="2026-01-01",
        section_name="Shell Commands",
    )


@requires_display
class TestEntryEditorValidation:
    """Test validazione campi del form."""

    def _create_dialog(self, entry=None, on_save=None):
        import gi

        from command_quiver.ui.entry_editor import EntryEditorDialog

        gi.require_version("Gtk", "4.0")
        from gi.repository import Gtk

        parent = Gtk.Window()
        return EntryEditorDialog(
            parent=parent,
            sections=_make_sections(),
            entry=entry,
            on_save=on_save or MagicMock(),
        )

    def test_validate_rejects_empty_name(self, gtk_init) -> None:
        dialog = self._create_dialog()
        dialog._name_entry.set_text("")
        buf = dialog._content_view.get_buffer()
        buf.set_text("some content")

        assert dialog._validate() is False
        assert dialog._name_error.get_visible() is True

    def test_validate_rejects_empty_content(self, gtk_init) -> None:
        dialog = self._create_dialog()
        dialog._name_entry.set_text("Valid Name")
        # Contenuto vuoto (default)

        assert dialog._validate() is False
        assert dialog._content_error.get_visible() is True

    def test_validate_rejects_whitespace_only_name(self, gtk_init) -> None:
        dialog = self._create_dialog()
        dialog._name_entry.set_text("   ")
        buf = dialog._content_view.get_buffer()
        buf.set_text("content")

        assert dialog._validate() is False

    def test_validate_rejects_whitespace_only_content(self, gtk_init) -> None:
        dialog = self._create_dialog()
        dialog._name_entry.set_text("Name")
        buf = dialog._content_view.get_buffer()
        buf.set_text("   \n  ")

        assert dialog._validate() is False

    def test_validate_accepts_valid_fields(self, gtk_init) -> None:
        dialog = self._create_dialog()
        dialog._name_entry.set_text("Valid Name")
        buf = dialog._content_view.get_buffer()
        buf.set_text("Valid content")

        assert dialog._validate() is True
        assert dialog._name_error.get_visible() is False
        assert dialog._content_error.get_visible() is False

    def test_validate_clears_errors_on_valid_input(self, gtk_init) -> None:
        dialog = self._create_dialog()

        # Prima validazione fallita
        dialog._name_entry.set_text("")
        buf = dialog._content_view.get_buffer()
        buf.set_text("")
        dialog._validate()
        assert dialog._name_error.get_visible() is True

        # Seconda validazione con input valido
        dialog._name_entry.set_text("Name")
        buf.set_text("Content")
        dialog._validate()
        assert dialog._name_error.get_visible() is False
        assert dialog._content_error.get_visible() is False


@requires_display
class TestEntryEditorDataCollection:
    """Test raccolta dati dal form."""

    def _create_dialog(self, entry=None):
        import gi

        from command_quiver.ui.entry_editor import EntryEditorDialog

        gi.require_version("Gtk", "4.0")
        from gi.repository import Gtk

        parent = Gtk.Window()
        return EntryEditorDialog(
            parent=parent,
            sections=_make_sections(),
            entry=entry,
            on_save=MagicMock(),
        )

    def test_collect_data_returns_entry_create_for_new(self, gtk_init) -> None:
        dialog = self._create_dialog()
        dialog._name_entry.set_text("New Entry")
        buf = dialog._content_view.get_buffer()
        buf.set_text("echo test")
        dialog._tag_entry.set_text("test,new")

        data = dialog._collect_data()
        assert isinstance(data, EntryCreate)
        assert data.name == "New Entry"
        assert data.content == "echo test"
        assert data.tags == "test,new"
        assert data.type == "prompt"  # Default

    def test_collect_data_returns_entry_update_for_edit(self, gtk_init) -> None:
        entry = _make_entry()
        dialog = self._create_dialog(entry=entry)

        data = dialog._collect_data()
        assert isinstance(data, EntryUpdate)
        assert data.id == 42

    def test_collect_data_shell_type(self, gtk_init) -> None:
        dialog = self._create_dialog()
        dialog._name_entry.set_text("Name")
        buf = dialog._content_view.get_buffer()
        buf.set_text("content")
        dialog._radio_shell.set_active(True)

        data = dialog._collect_data()
        assert data.type == "shell"

    def test_collect_data_prompt_type(self, gtk_init) -> None:
        dialog = self._create_dialog()
        dialog._name_entry.set_text("Name")
        buf = dialog._content_view.get_buffer()
        buf.set_text("content")
        dialog._radio_prompt.set_active(True)

        data = dialog._collect_data()
        assert data.type == "prompt"

    def test_collect_data_selects_correct_section(self, gtk_init) -> None:
        dialog = self._create_dialog()
        dialog._name_entry.set_text("Name")
        buf = dialog._content_view.get_buffer()
        buf.set_text("content")
        dialog._section_dropdown.set_selected(1)  # AI Prompts (id=2)

        data = dialog._collect_data()
        assert data.section_id == 2

    def test_collect_data_strips_whitespace(self, gtk_init) -> None:
        dialog = self._create_dialog()
        dialog._name_entry.set_text("  Spaced Name  ")
        buf = dialog._content_view.get_buffer()
        buf.set_text("  spaced content  ")

        data = dialog._collect_data()
        assert data.name == "Spaced Name"
        assert data.content == "spaced content"


@requires_display
class TestEntryEditorPopulation:
    """Test pre-popolazione campi in modalità modifica."""

    def test_populates_name_from_entry(self, gtk_init) -> None:
        import gi

        from command_quiver.ui.entry_editor import EntryEditorDialog

        gi.require_version("Gtk", "4.0")
        from gi.repository import Gtk

        parent = Gtk.Window()
        entry = _make_entry()
        dialog = EntryEditorDialog(
            parent=parent,
            sections=_make_sections(),
            entry=entry,
            on_save=MagicMock(),
        )

        assert dialog._name_entry.get_text() == "Docker Build"

    def test_populates_content_from_entry(self, gtk_init) -> None:
        import gi

        from command_quiver.ui.entry_editor import EntryEditorDialog

        gi.require_version("Gtk", "4.0")
        from gi.repository import Gtk

        parent = Gtk.Window()
        entry = _make_entry()
        dialog = EntryEditorDialog(
            parent=parent,
            sections=_make_sections(),
            entry=entry,
            on_save=MagicMock(),
        )

        buf = dialog._content_view.get_buffer()
        start, end = buf.get_bounds()
        content = buf.get_text(start, end, include_hidden_chars=False)
        assert content == "docker build -t myapp ."

    def test_populates_shell_type(self, gtk_init) -> None:
        import gi

        from command_quiver.ui.entry_editor import EntryEditorDialog

        gi.require_version("Gtk", "4.0")
        from gi.repository import Gtk

        parent = Gtk.Window()
        entry = _make_entry()
        dialog = EntryEditorDialog(
            parent=parent,
            sections=_make_sections(),
            entry=entry,
            on_save=MagicMock(),
        )
        assert dialog._radio_shell.get_active() is True

    def test_populates_tags(self, gtk_init) -> None:
        import gi

        from command_quiver.ui.entry_editor import EntryEditorDialog

        gi.require_version("Gtk", "4.0")
        from gi.repository import Gtk

        parent = Gtk.Window()
        entry = _make_entry()
        dialog = EntryEditorDialog(
            parent=parent,
            sections=_make_sections(),
            entry=entry,
            on_save=MagicMock(),
        )
        assert dialog._tag_entry.get_text() == "docker,build"

    def test_title_differs_for_create_and_edit(self, gtk_init) -> None:
        import gi

        from command_quiver.ui.entry_editor import EntryEditorDialog

        gi.require_version("Gtk", "4.0")
        from gi.repository import Gtk

        parent = Gtk.Window()
        create_dialog = EntryEditorDialog(
            parent=parent,
            sections=_make_sections(),
            on_save=MagicMock(),
        )
        edit_dialog = EntryEditorDialog(
            parent=parent,
            sections=_make_sections(),
            entry=_make_entry(),
            on_save=MagicMock(),
        )
        assert create_dialog.get_title() == "Nuova voce"
        assert edit_dialog.get_title() == "Modifica voce"


@requires_display
class TestEntryEditorSave:
    """Test salvataggio voce."""

    def test_do_save_calls_callback_on_valid_input(self, gtk_init) -> None:
        import gi

        from command_quiver.ui.entry_editor import EntryEditorDialog

        gi.require_version("Gtk", "4.0")
        from gi.repository import Gtk

        parent = Gtk.Window()
        mock_save = MagicMock()
        dialog = EntryEditorDialog(
            parent=parent,
            sections=_make_sections(),
            on_save=mock_save,
        )
        dialog._name_entry.set_text("Test")
        buf = dialog._content_view.get_buffer()
        buf.set_text("Content")

        dialog._do_save()
        mock_save.assert_called_once()
        data = mock_save.call_args[0][0]
        assert isinstance(data, EntryCreate)
        assert data.name == "Test"

    def test_do_save_does_not_call_on_invalid(self, gtk_init) -> None:
        import gi

        from command_quiver.ui.entry_editor import EntryEditorDialog

        gi.require_version("Gtk", "4.0")
        from gi.repository import Gtk

        parent = Gtk.Window()
        mock_save = MagicMock()
        dialog = EntryEditorDialog(
            parent=parent,
            sections=_make_sections(),
            on_save=mock_save,
        )
        # Campi vuoti
        dialog._do_save()
        mock_save.assert_not_called()

    def test_do_save_and_copy_copies_content(self, gtk_init) -> None:
        import gi

        from command_quiver.ui.entry_editor import EntryEditorDialog

        gi.require_version("Gtk", "4.0")
        from gi.repository import Gtk

        parent = Gtk.Window()
        mock_save = MagicMock()
        dialog = EntryEditorDialog(
            parent=parent,
            sections=_make_sections(),
            on_save=mock_save,
        )
        dialog._name_entry.set_text("Test")
        buf = dialog._content_view.get_buffer()
        buf.set_text("copied content")

        with patch("command_quiver.ui.entry_editor.copy_to_clipboard") as mock_copy:
            dialog._do_save_and_copy()
            mock_copy.assert_called_once_with("copied content")
            mock_save.assert_called_once()


@requires_display
class TestEntryEditorKeyboard:
    """Test scorciatoie da tastiera."""

    def test_escape_returns_true(self, gtk_init) -> None:
        import gi

        from command_quiver.ui.entry_editor import EntryEditorDialog

        gi.require_version("Gtk", "4.0")
        from gi.repository import Gdk, Gtk

        parent = Gtk.Window()
        dialog = EntryEditorDialog(
            parent=parent,
            sections=_make_sections(),
            on_save=MagicMock(),
        )
        result = dialog._on_key_pressed(None, Gdk.KEY_Escape, 0, Gdk.ModifierType(0))
        assert result is True

    def test_ctrl_s_returns_true(self, gtk_init) -> None:
        import gi

        from command_quiver.ui.entry_editor import EntryEditorDialog

        gi.require_version("Gtk", "4.0")
        from gi.repository import Gdk, Gtk

        parent = Gtk.Window()
        dialog = EntryEditorDialog(
            parent=parent,
            sections=_make_sections(),
            on_save=MagicMock(),
        )
        result = dialog._on_key_pressed(None, Gdk.KEY_s, 0, Gdk.ModifierType.CONTROL_MASK)
        assert result is True

    def test_ctrl_w_returns_true(self, gtk_init) -> None:
        import gi

        from command_quiver.ui.entry_editor import EntryEditorDialog

        gi.require_version("Gtk", "4.0")
        from gi.repository import Gdk, Gtk

        parent = Gtk.Window()
        dialog = EntryEditorDialog(
            parent=parent,
            sections=_make_sections(),
            on_save=MagicMock(),
        )
        result = dialog._on_key_pressed(None, Gdk.KEY_w, 0, Gdk.ModifierType.CONTROL_MASK)
        assert result is True

    def test_unhandled_key_returns_false(self, gtk_init) -> None:
        import gi

        from command_quiver.ui.entry_editor import EntryEditorDialog

        gi.require_version("Gtk", "4.0")
        from gi.repository import Gdk, Gtk

        parent = Gtk.Window()
        dialog = EntryEditorDialog(
            parent=parent,
            sections=_make_sections(),
            on_save=MagicMock(),
        )
        result = dialog._on_key_pressed(None, Gdk.KEY_a, 0, Gdk.ModifierType(0))
        assert result is False

    def test_ctrl_enter_returns_true(self, gtk_init) -> None:
        import gi

        from command_quiver.ui.entry_editor import EntryEditorDialog

        gi.require_version("Gtk", "4.0")
        from gi.repository import Gdk, Gtk

        parent = Gtk.Window()
        dialog = EntryEditorDialog(
            parent=parent,
            sections=_make_sections(),
            on_save=MagicMock(),
        )
        result = dialog._on_key_pressed(None, Gdk.KEY_Return, 0, Gdk.ModifierType.CONTROL_MASK)
        assert result is True


@requires_display
class TestEntryEditorDelete:
    """Test eliminazione voce."""

    def test_do_save_and_copy_invalid_does_not_copy(self, gtk_init) -> None:
        import gi

        from command_quiver.ui.entry_editor import EntryEditorDialog

        gi.require_version("Gtk", "4.0")
        from gi.repository import Gtk

        parent = Gtk.Window()
        mock_save = MagicMock()
        dialog = EntryEditorDialog(
            parent=parent,
            sections=_make_sections(),
            on_save=mock_save,
        )
        # Campi vuoti
        with patch("command_quiver.ui.entry_editor.copy_to_clipboard") as mock_copy:
            dialog._do_save_and_copy()
            mock_copy.assert_not_called()
            mock_save.assert_not_called()

    def test_delete_button_present_in_edit_mode(self, gtk_init) -> None:
        import gi

        from command_quiver.ui.entry_editor import EntryEditorDialog

        gi.require_version("Gtk", "4.0")
        from gi.repository import Gtk

        parent = Gtk.Window()
        entry = _make_entry()
        mock_delete = MagicMock()
        dialog = EntryEditorDialog(
            parent=parent,
            sections=_make_sections(),
            entry=entry,
            on_save=MagicMock(),
            on_delete=mock_delete,
        )
        assert dialog._is_edit is True

    def test_no_delete_button_in_create_mode(self, gtk_init) -> None:
        import gi

        from command_quiver.ui.entry_editor import EntryEditorDialog

        gi.require_version("Gtk", "4.0")
        from gi.repository import Gtk

        parent = Gtk.Window()
        dialog = EntryEditorDialog(
            parent=parent,
            sections=_make_sections(),
            on_save=MagicMock(),
        )
        assert dialog._is_edit is False

    def test_do_save_without_callback_noop(self, gtk_init) -> None:
        import gi

        from command_quiver.ui.entry_editor import EntryEditorDialog

        gi.require_version("Gtk", "4.0")
        from gi.repository import Gtk

        parent = Gtk.Window()
        dialog = EntryEditorDialog(
            parent=parent,
            sections=_make_sections(),
            on_save=None,
        )
        dialog._name_entry.set_text("Test")
        buf = dialog._content_view.get_buffer()
        buf.set_text("Content")

        # Non deve sollevare eccezioni anche senza callback
        dialog._do_save()
