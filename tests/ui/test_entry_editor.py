"""Test per EntryEditorDialog: validazione, raccolta dati, shortcut."""

from unittest.mock import MagicMock, patch

from command_quiver.db.models import Entry, EntryCreate, EntryUpdate, Section
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

    def test_validate_accepts_empty_name(self, gtk_init) -> None:
        # E3: il nome è facoltativo, si ricava dalla prima riga del contenuto
        dialog = self._create_dialog()
        dialog._name_entry.set_text("")
        dialog._content_view.get_buffer().set_text("some content")

        assert dialog._validate() is True

    def test_empty_name_taken_from_first_content_line(self, gtk_init) -> None:
        dialog = self._create_dialog()
        dialog._name_entry.set_text("   ")
        dialog._content_view.get_buffer().set_text("\ngit log --oneline -10\nsecond")

        assert dialog._collect_data().name == "git log --oneline -10"

    def test_typed_name_wins_over_content(self, gtk_init) -> None:
        dialog = self._create_dialog()
        dialog._name_entry.set_text("Log")
        dialog._content_view.get_buffer().set_text("git log")

        assert dialog._collect_data().name == "Log"

    def test_validate_rejects_empty_content(self, gtk_init) -> None:
        dialog = self._create_dialog()
        dialog._name_entry.set_text("Valid Name")
        # Contenuto vuoto (default)

        assert dialog._validate() is False
        assert dialog._content_error.get_visible() is True

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
        assert dialog._content_error.get_visible() is False

    def test_validate_clears_errors_on_valid_input(self, gtk_init) -> None:
        dialog = self._create_dialog()

        # Prima validazione fallita
        buf = dialog._content_view.get_buffer()
        buf.set_text("")
        dialog._validate()
        assert dialog._content_error.get_visible() is True

        # Seconda validazione con input valido
        buf.set_text("Content")
        dialog._validate()
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
        # Testo scritto ma non confermato con Invio: non va perso al salvataggio
        dialog._tag_entry.set_text("test,new")

        data = dialog._collect_data()
        assert isinstance(data, EntryCreate)
        assert data.name == "New Entry"
        assert data.content == "echo test"
        assert data.tags == "test, new"
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
        # E5: i tag esistenti diventano etichette, il campo di testo resta libero
        assert dialog._tag_input.tags == ["docker", "build"]
        assert dialog._tag_entry.get_text() == ""

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


@requires_display
class TestEntryEditorUx:
    """Sezione preimpostata, segnaposto del contenuto, tag a etichette."""

    def _dialog(self, **kwargs):
        import gi

        gi.require_version("Gtk", "4.0")
        from gi.repository import Gtk

        from command_quiver.ui.entry_editor import EntryEditorDialog

        return EntryEditorDialog(parent=Gtk.Window(), sections=_make_sections(), **kwargs)

    def test_new_entry_preselects_open_section(self, gtk_init) -> None:
        dialog = self._dialog(initial_section_id=2)
        dialog._content_view.get_buffer().set_text("x")
        assert dialog._collect_data().section_id == 2

    def test_new_entry_from_all_keeps_first_section(self, gtk_init) -> None:
        dialog = self._dialog(initial_section_id=None)
        dialog._content_view.get_buffer().set_text("x")
        assert dialog._collect_data().section_id == 1

    def test_edit_keeps_entry_section_over_open_section(self, gtk_init) -> None:
        dialog = self._dialog(entry=_make_entry(), initial_section_id=2)
        assert dialog._collect_data().section_id == _make_entry().section_id

    def test_content_placeholder_follows_type_and_hides_when_typing(self, gtk_init) -> None:
        dialog = self._dialog()
        assert dialog._content_placeholder.get_visible() is True
        assert dialog._content_placeholder.get_label().startswith("Es. Riassumi")

        dialog._radio_shell.set_active(True)
        assert "git log" in dialog._content_placeholder.get_label()

        dialog._content_view.get_buffer().set_text("ls")
        assert dialog._content_placeholder.get_visible() is False

    def test_enter_turns_typed_tag_into_label(self, gtk_init) -> None:
        dialog = self._dialog()
        dialog._tag_entry.set_text("deploy")
        dialog._tag_input.commit_pending()
        assert dialog._tag_input.tags == ["deploy"]
        assert dialog._tag_entry.get_text() == ""

    def test_known_tag_suggestion_adds_without_duplicates(self, gtk_init) -> None:
        dialog = self._dialog(known_tags=["git", "deploy"])
        dialog._tag_input.add_tag("git")
        dialog._tag_input.add_tag("Git")
        dialog._content_view.get_buffer().set_text("x")
        assert dialog._collect_data().tags == "git"

    def test_removed_tag_not_saved(self, gtk_init) -> None:
        dialog = self._dialog(entry=_make_entry())
        dialog._tag_input.remove_tag("docker")
        assert dialog._collect_data().tags == "build"


@requires_display
class TestEntryEditorSectionFollowsType:
    """Voce nuova da "Tutti": la sezione segue il tipo finché l'utente non la sceglie."""

    def _dialog(self):
        from gi.repository import Gtk

        from command_quiver.ui.entry_editor import EntryEditorDialog

        sections = [
            Section(id=1, name="Comandi shell", icon="utilities-terminal", position=0),
            Section(id=2, name="Prompt AI", icon="format-text-bold", position=1),
            Section(id=3, name="Generale", icon="folder", position=2, is_default=1),
        ]
        dialog = EntryEditorDialog(parent=Gtk.Window(), sections=sections)
        dialog._content_view.get_buffer().set_text("x")
        return dialog

    def test_default_prompt_type_selects_prompt_section(self, gtk_init) -> None:
        assert self._dialog()._collect_data().section_id == 2

    def test_switching_to_shell_moves_to_shell_section(self, gtk_init) -> None:
        dialog = self._dialog()
        dialog._radio_shell.set_active(True)
        assert dialog._collect_data().section_id == 1

    def test_manual_choice_is_not_overridden(self, gtk_init) -> None:
        dialog = self._dialog()
        dialog._section_dropdown.set_selected(2)  # Generale, scelta a mano
        dialog._radio_shell.set_active(True)
        assert dialog._collect_data().section_id == 3


@requires_display
class TestEntryEditorDeleteWithoutConfirmation:
    """E7: Elimina non chiede più conferma; l'annullamento arriva dall'avviso nella lista."""

    def test_delete_calls_callback_immediately_and_closes(self, gtk_init) -> None:
        from gi.repository import Gtk

        from command_quiver.ui.entry_editor import EntryEditorDialog

        on_delete = MagicMock()
        dialog = EntryEditorDialog(
            parent=Gtk.Window(), sections=_make_sections(), entry=_make_entry(), on_delete=on_delete
        )
        with patch.object(dialog, "close") as mock_close:
            dialog._on_delete_clicked(None)
        on_delete.assert_called_once_with(_make_entry().id)
        mock_close.assert_called_once()


@requires_display
class TestEditorKeysAndTypes:
    def _dialog(self, entry=None, on_save=None):
        from gi.repository import Gtk

        from command_quiver.ui.entry_editor import EntryEditorDialog

        return EntryEditorDialog(
            parent=Gtk.Window(), sections=_make_sections(), entry=entry, on_save=on_save
        )

    def test_ctrl_with_unmapped_key_is_not_consumed(self, gtk_init) -> None:
        from gi.repository import Gdk

        from tests.conftest import key_press

        dialog = self._dialog()
        control = Gdk.ModifierType.CONTROL_MASK

        assert key_press(dialog, Gdk.KEY_x, control) is False
        # Appaiato: con il tasto mappato lo stesso modificatore viene consumato
        dialog._content_view.get_buffer().set_text("ls")
        assert key_press(dialog, Gdk.KEY_s, control) is True

    def test_editing_a_prompt_keeps_prompt_type_and_fields(self, gtk_init) -> None:
        entry = _make_entry()
        entry.type = "prompt"
        entry.content = "Riassumi il testo"
        dialog = self._dialog(entry=entry)

        data = dialog._collect_data()

        assert isinstance(data, EntryUpdate)
        assert (data.type, data.content, data.id) == ("prompt", "Riassumi il testo", 42)

    def test_ctrl_enter_copies_even_without_save_callback(self, gtk_init) -> None:
        from gi.repository import Gdk

        from tests.conftest import key_press

        dialog = self._dialog(on_save=None)
        dialog._content_view.get_buffer().set_text("docker ps")

        with patch("command_quiver.ui.entry_editor.copy_to_clipboard") as copy:
            assert key_press(dialog, Gdk.KEY_Return, Gdk.ModifierType.CONTROL_MASK) is True

        copy.assert_called_once_with("docker ps")

    def test_unmatched_section_id_leaves_selection_unchanged(self, gtk_init) -> None:
        from command_quiver.ui.editor_widgets import SectionPicker

        picker = SectionPicker(_make_sections())
        picker.select_section(2)

        picker.select_section(999)

        assert picker.selected_section_id == 2
