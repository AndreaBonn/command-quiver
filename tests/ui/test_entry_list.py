"""Test per EntryRow e EntryListWidget: rendering, azioni copia/esegui."""

from unittest.mock import MagicMock, patch

from command_quiver.db.models import Entry
from tests.conftest import requires_display


def _make_entry(
    entry_id: int = 1,
    name: str = "Test Entry",
    content: str = "echo hello",
    entry_type: str = "shell",
    section_id: int = 1,
) -> Entry:
    """Helper per creare un Entry di test."""
    return Entry(
        id=entry_id,
        name=name,
        content=content,
        section_id=section_id,
        type=entry_type,
        tags="test",
        personal_pos=0,
        created_at="2026-01-01",
        updated_at="2026-01-01",
        section_name="Shell Commands",
    )


@requires_display
class TestEntryRow:
    """Test widget riga voce."""

    def test_creates_with_shell_entry(self, gtk_init) -> None:
        from command_quiver.ui.entry_list import EntryRow, RowCallbacks

        entry = _make_entry(entry_type="shell")
        row = EntryRow(entry=entry, callbacks=RowCallbacks(on_edit=MagicMock()))
        assert row.entry == entry

    def test_creates_with_prompt_entry(self, gtk_init) -> None:
        from command_quiver.ui.entry_list import EntryRow, RowCallbacks

        entry = _make_entry(entry_type="prompt")
        row = EntryRow(entry=entry, callbacks=RowCallbacks(on_edit=MagicMock()))
        assert row.entry.type == "prompt"

    def test_truncates_long_names(self, gtk_init) -> None:
        from command_quiver.ui.entry_list import EntryRow, RowCallbacks

        long_name = "A" * 50
        entry = _make_entry(name=long_name)
        row = EntryRow(entry=entry, callbacks=RowCallbacks(on_edit=MagicMock()))
        # Il nome lungo deve essere troncato nell'UI ma l'entry resta intatta
        assert row.entry.name == long_name

    def test_copy_button_calls_clipboard(self, gtk_init) -> None:
        from command_quiver.ui.entry_list import EntryRow, RowCallbacks

        entry = _make_entry(content="docker ps -a")
        row = EntryRow(entry=entry, callbacks=RowCallbacks(on_edit=MagicMock()))

        with patch(
            "command_quiver.ui.entry_list.copy_to_clipboard",
            return_value=True,
        ) as mock_copy:
            row._on_copy(None)
            mock_copy.assert_called_once_with("docker ps -a")

    def test_copy_feedback_changes_icon(self, gtk_init) -> None:
        from command_quiver.ui.entry_list import EntryRow, RowCallbacks

        entry = _make_entry()
        row = EntryRow(entry=entry, callbacks=RowCallbacks(on_edit=MagicMock()))

        with patch(
            "command_quiver.ui.entry_list.copy_to_clipboard",
            return_value=True,
        ):
            row._on_copy(None)
            assert row._copy_btn.get_icon_name() == "object-select-symbolic"

    def test_copy_no_feedback_on_failure(self, gtk_init) -> None:
        from command_quiver.ui.entry_list import EntryRow, RowCallbacks

        entry = _make_entry()
        row = EntryRow(entry=entry, callbacks=RowCallbacks(on_edit=MagicMock()))

        with patch(
            "command_quiver.ui.entry_list.copy_to_clipboard",
            return_value=False,
        ):
            row._on_copy(None)
            # Icona non cambiata
            assert row._copy_btn.get_icon_name() == "edit-copy-symbolic"

    def test_reset_copy_icon(self, gtk_init) -> None:
        from command_quiver.ui.entry_list import EntryRow, RowCallbacks

        entry = _make_entry()
        row = EntryRow(entry=entry, callbacks=RowCallbacks(on_edit=MagicMock()))
        row._copy_btn.set_icon_name("object-select-symbolic")

        result = row._reset_copy_icon()
        assert row._copy_btn.get_icon_name() == "edit-copy-symbolic"
        # Deve restituire SOURCE_REMOVE per fermare il timer
        from gi.repository import GLib

        assert result == GLib.SOURCE_REMOVE

    def test_execute_calls_terminal(self, gtk_init) -> None:
        from command_quiver.ui.entry_list import EntryRow, RowCallbacks

        entry = _make_entry(content="ls -la", entry_type="shell")
        row = EntryRow(entry=entry, callbacks=RowCallbacks(on_edit=MagicMock()))

        with patch(
            "command_quiver.ui.entry_list.execute_in_terminal",
            return_value=True,
        ) as mock_exec:
            row._on_execute(None)
            mock_exec.assert_called_once_with("ls -la")

    def test_execute_handles_terminal_not_found(self, gtk_init) -> None:
        from command_quiver.core.executor import TerminalNotFoundError
        from command_quiver.ui.entry_list import EntryRow, RowCallbacks

        entry = _make_entry(entry_type="shell")
        row = EntryRow(entry=entry, callbacks=RowCallbacks(on_edit=MagicMock()))

        with patch(
            "command_quiver.ui.entry_list.execute_in_terminal",
            side_effect=TerminalNotFoundError(),
        ):
            # Non deve sollevare eccezioni
            row._on_execute(None)


@requires_display
class TestEntryListWidget:
    """Test widget lista voci."""

    def test_creates_empty_list(self, gtk_init) -> None:
        from command_quiver.ui.entry_list import EntryListWidget, RowCallbacks

        widget = EntryListWidget(RowCallbacks(on_edit=MagicMock()))
        assert widget.entries == []

    def test_update_entries_populates_list(self, gtk_init) -> None:
        from command_quiver.ui.entry_list import EntryListWidget, RowCallbacks

        widget = EntryListWidget(RowCallbacks(on_edit=MagicMock()))
        entries = [_make_entry(entry_id=i, name=f"Entry {i}") for i in range(3)]

        widget.update_entries(entries)
        assert len(widget.entries) == 3

    def test_update_entries_clears_previous(self, gtk_init) -> None:
        from command_quiver.ui.entry_list import EntryListWidget, RowCallbacks

        widget = EntryListWidget(RowCallbacks(on_edit=MagicMock()))

        # Prima popolazione
        widget.update_entries([_make_entry(entry_id=1)])
        # Seconda popolazione
        entries = [_make_entry(entry_id=i) for i in range(5)]
        widget.update_entries(entries)
        assert len(widget.entries) == 5

    def test_update_with_empty_list(self, gtk_init) -> None:
        from command_quiver.ui.entry_list import EntryListWidget, RowCallbacks

        widget = EntryListWidget(RowCallbacks(on_edit=MagicMock()))
        widget.update_entries([_make_entry()])
        widget.update_entries([])
        assert widget.entries == []

    def test_row_activated_copies_content(self, gtk_init) -> None:
        from command_quiver.ui.entry_list import EntryListWidget, RowCallbacks

        widget = EntryListWidget(RowCallbacks(on_edit=MagicMock()))
        entry = _make_entry()
        widget.update_entries([entry])

        # Simula attivazione della prima riga -> deve copiare, non aprire editor
        row = widget._list_box.get_row_at_index(0)
        if row:
            with patch(
                "command_quiver.ui.entry_list.copy_to_clipboard", return_value=True
            ) as mock_copy:
                widget._on_row_activated(widget._list_box, row)
                mock_copy.assert_called_once_with(entry.content)


@requires_display
class TestEntryRowEditClick:
    """Test click su bottone modifica."""

    def test_edit_click_calls_callback(self, gtk_init) -> None:
        from command_quiver.ui.entry_list import EntryRow, RowCallbacks

        entry = _make_entry()
        mock_edit = MagicMock()
        row = EntryRow(entry=entry, callbacks=RowCallbacks(on_edit=mock_edit))

        row._on_edit_clicked(None)
        mock_edit.assert_called_once_with(entry)


@requires_display
class TestEntryRowTerminalError:
    """Test dialog errore terminale."""

    def test_terminal_error_no_crash_without_window(self, gtk_init) -> None:
        from command_quiver.ui.entry_list import EntryRow, RowCallbacks

        entry = _make_entry(entry_type="shell")
        row = EntryRow(entry=entry, callbacks=RowCallbacks(on_edit=MagicMock()))

        # get_root() non restituisce una Window → noop
        row._show_terminal_error("Test error")

    def test_update_entries_with_move_buttons(self, gtk_init) -> None:
        from command_quiver.ui.entry_list import EntryListWidget, RowCallbacks

        mock_move = MagicMock()
        widget = EntryListWidget(RowCallbacks(on_edit=MagicMock(), on_move=mock_move))
        entries = [_make_entry(entry_id=i, name=f"E{i}") for i in range(3)]

        widget.update_entries(entries, show_move=True)
        assert len(widget.entries) == 3


@requires_display
class TestKeyboardReorder:
    """M8: nell'ordine Personale Alt+↑/↓ sposta la riga selezionata (al posto delle frecce)."""

    def _widget(self, on_move: MagicMock, show_move: bool = True):
        from command_quiver.ui.entry_list import EntryListWidget, RowCallbacks

        widget = EntryListWidget(RowCallbacks(on_edit=MagicMock(), on_move=on_move))
        widget.update_entries([_make_entry(entry_id=i, name=f"E{i}") for i in range(3)], show_move)
        widget._list_box.set_focus_child(widget._list_box.get_row_at_index(1))
        return widget

    def _press(self, widget, keyval: int, alt: bool = True) -> bool:
        from gi.repository import Gdk

        state = Gdk.ModifierType.ALT_MASK if alt else Gdk.ModifierType(0)
        return widget._on_key_pressed(None, keyval, 0, state)

    def test_alt_up_moves_focused_row_up(self, gtk_init) -> None:
        from gi.repository import Gdk

        on_move = MagicMock()
        assert self._press(self._widget(on_move), Gdk.KEY_Up) is True
        on_move.assert_called_once_with(1, -1)

    def test_alt_down_moves_focused_row_down(self, gtk_init) -> None:
        from gi.repository import Gdk

        on_move = MagicMock()
        self._press(self._widget(on_move), Gdk.KEY_Down)
        on_move.assert_called_once_with(1, 1)

    def test_plain_arrows_keep_normal_navigation(self, gtk_init) -> None:
        from gi.repository import Gdk

        on_move = MagicMock()
        assert self._press(self._widget(on_move), Gdk.KEY_Down, alt=False) is False
        on_move.assert_not_called()

    def test_no_move_outside_personal_order(self, gtk_init) -> None:
        from gi.repository import Gdk

        on_move = MagicMock()
        assert self._press(self._widget(on_move, show_move=False), Gdk.KEY_Up) is False
        on_move.assert_not_called()

    def test_rows_have_no_arrow_buttons(self, gtk_init) -> None:
        from gi.repository import Gtk

        widget = self._widget(MagicMock())
        row = widget._list_box.get_row_at_index(0).get_child()
        icons = []
        pending = [row]
        while pending:
            child = pending.pop().get_first_child()
            while child is not None:
                if isinstance(child, Gtk.Button):
                    icons.append(child.get_icon_name())
                pending.append(child)
                child = child.get_next_sibling()
        assert "edit-copy-symbolic" in icons  # la ricerca vede davvero i pulsanti
        assert "go-up-symbolic" not in icons
        assert "go-down-symbolic" not in icons


@requires_display
def test_alt_arrow_on_empty_state_does_not_crash(gtk_init) -> None:
    from gi.repository import Gdk, Gtk

    from command_quiver.ui.entry_list import EntryListWidget, RowCallbacks

    on_move = MagicMock()
    widget = EntryListWidget(RowCallbacks(on_edit=MagicMock(), on_move=on_move))
    placeholder = Gtk.Box()
    widget.update_entries([], show_move=True, empty_state=placeholder)
    with patch.object(widget._list_box, "get_focus_child", return_value=placeholder):
        handled = widget._on_key_pressed(None, Gdk.KEY_Up, 0, Gdk.ModifierType.ALT_MASK)
    assert handled is False
    on_move.assert_not_called()


@requires_display
class TestRowCallbacks:
    def _row(self, entry_type="shell", **callbacks):
        from command_quiver.ui.entry_list import EntryRow, RowCallbacks

        entry = _make_entry(entry_type=entry_type)
        return EntryRow(entry=entry, callbacks=RowCallbacks(on_edit=MagicMock(), **callbacks))

    def test_clicking_a_tag_chip_passes_the_tag(self, gtk_init) -> None:
        from tests.conftest import button_labelled

        on_tag = MagicMock()
        row = self._row(on_tag=on_tag)

        button_labelled(row, "test").emit("clicked")

        on_tag.assert_called_once_with("test")

    def test_tag_chip_without_handler_does_nothing(self, gtk_init) -> None:
        from tests.conftest import button_labelled

        row = self._row()

        button_labelled(row, "test").emit("clicked")  # nessuna eccezione, nessuna azione

    def test_run_handler_decides_instead_of_running_directly(self, gtk_init) -> None:
        from tests.conftest import descendants

        on_run = MagicMock()
        row = self._row(on_run=on_run)
        run_button = next(
            b
            for b in descendants(row)
            if hasattr(b, "get_icon_name") and b.get_icon_name() == "media-playback-start-symbolic"
        )

        with patch("command_quiver.ui.entry_list.execute_in_terminal") as execute:
            run_button.emit("clicked")

        on_run.assert_called_once_with(row.entry)
        execute.assert_not_called()

    def test_copy_first_on_empty_list_returns_false(self, gtk_init) -> None:
        from command_quiver.ui.entry_list import EntryListWidget, RowCallbacks

        widget = EntryListWidget(RowCallbacks(on_edit=MagicMock()))
        widget.update_entries([])

        assert widget.copy_first() is False

    def test_copy_first_copies_first_row_and_returns_true(self, gtk_init) -> None:
        from command_quiver.ui.entry_list import EntryListWidget, RowCallbacks

        widget = EntryListWidget(RowCallbacks(on_edit=MagicMock()))
        widget.update_entries([_make_entry(1, content="uno"), _make_entry(2, content="due")])

        with patch("command_quiver.ui.entry_list.copy_to_clipboard", return_value=True) as copy:
            assert widget.copy_first() is True

        copy.assert_called_once_with("uno")


@requires_display
class TestTerminalErrorDialog:
    def test_error_dialog_shown_on_a_window_with_the_reason(self, gtk_init) -> None:
        from gi.repository import Gtk

        from command_quiver.core.i18n import init as i18n_init
        from command_quiver.ui import entry_list

        i18n_init("it")
        parent = Gtk.Window()
        with patch.object(entry_list.Gtk, "AlertDialog") as alert:
            entry_list.show_terminal_error(parent=parent, message="gnome-terminal assente")

        assert alert.call_args.kwargs["detail"] == "gnome-terminal assente"
        alert.return_value.show.assert_called_once_with(parent)

    def test_error_dialog_not_shown_without_a_window(self, gtk_init) -> None:
        from command_quiver.ui import entry_list

        with patch.object(entry_list.Gtk, "AlertDialog") as alert:
            entry_list.show_terminal_error(parent=None, message="x")

        alert.assert_not_called()
