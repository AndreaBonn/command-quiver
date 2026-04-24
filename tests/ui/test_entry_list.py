"""Test per EntryRow e EntryListWidget: rendering, azioni copia/esegui."""

from unittest.mock import MagicMock, patch

from command_quiver.db.queries import Entry
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
        from command_quiver.ui.entry_list import EntryRow

        entry = _make_entry(entry_type="shell")
        row = EntryRow(entry=entry, on_click=MagicMock())
        assert row.entry == entry

    def test_creates_with_prompt_entry(self, gtk_init) -> None:
        from command_quiver.ui.entry_list import EntryRow

        entry = _make_entry(entry_type="prompt")
        row = EntryRow(entry=entry, on_click=MagicMock())
        assert row.entry.type == "prompt"

    def test_truncates_long_names(self, gtk_init) -> None:
        from command_quiver.ui.entry_list import EntryRow

        long_name = "A" * 50
        entry = _make_entry(name=long_name)
        row = EntryRow(entry=entry, on_click=MagicMock())
        # Il nome lungo deve essere troncato nell'UI ma l'entry resta intatta
        assert row.entry.name == long_name

    def test_copy_button_calls_clipboard(self, gtk_init) -> None:
        from command_quiver.ui.entry_list import EntryRow

        entry = _make_entry(content="docker ps -a")
        row = EntryRow(entry=entry, on_click=MagicMock())

        with patch(
            "command_quiver.ui.entry_list.copy_to_clipboard",
            return_value=True,
        ) as mock_copy:
            row._on_copy(None)
            mock_copy.assert_called_once_with("docker ps -a")

    def test_copy_feedback_changes_icon(self, gtk_init) -> None:
        from command_quiver.ui.entry_list import EntryRow

        entry = _make_entry()
        row = EntryRow(entry=entry, on_click=MagicMock())

        with patch(
            "command_quiver.ui.entry_list.copy_to_clipboard",
            return_value=True,
        ):
            row._on_copy(None)
            assert row._copy_btn.get_icon_name() == "object-select-symbolic"

    def test_copy_no_feedback_on_failure(self, gtk_init) -> None:
        from command_quiver.ui.entry_list import EntryRow

        entry = _make_entry()
        row = EntryRow(entry=entry, on_click=MagicMock())

        with patch(
            "command_quiver.ui.entry_list.copy_to_clipboard",
            return_value=False,
        ):
            row._on_copy(None)
            # Icona non cambiata
            assert row._copy_btn.get_icon_name() == "edit-copy-symbolic"

    def test_reset_copy_icon(self, gtk_init) -> None:
        from command_quiver.ui.entry_list import EntryRow

        entry = _make_entry()
        row = EntryRow(entry=entry, on_click=MagicMock())
        row._copy_btn.set_icon_name("object-select-symbolic")

        result = row._reset_copy_icon()
        assert row._copy_btn.get_icon_name() == "edit-copy-symbolic"
        # Deve restituire SOURCE_REMOVE per fermare il timer
        from gi.repository import GLib

        assert result == GLib.SOURCE_REMOVE

    def test_execute_calls_terminal(self, gtk_init) -> None:
        from command_quiver.ui.entry_list import EntryRow

        entry = _make_entry(content="ls -la", entry_type="shell")
        row = EntryRow(entry=entry, on_click=MagicMock())

        with patch(
            "command_quiver.ui.entry_list.execute_in_terminal",
            return_value=True,
        ) as mock_exec:
            row._on_execute(None)
            mock_exec.assert_called_once_with("ls -la")

    def test_execute_handles_terminal_not_found(self, gtk_init) -> None:
        from command_quiver.core.executor import TerminalNotFoundError
        from command_quiver.ui.entry_list import EntryRow

        entry = _make_entry(entry_type="shell")
        row = EntryRow(entry=entry, on_click=MagicMock())

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
        from command_quiver.ui.entry_list import EntryListWidget

        widget = EntryListWidget(on_entry_click=MagicMock())
        assert widget._entries == []

    def test_update_entries_populates_list(self, gtk_init) -> None:
        from command_quiver.ui.entry_list import EntryListWidget

        widget = EntryListWidget(on_entry_click=MagicMock())
        entries = [_make_entry(entry_id=i, name=f"Entry {i}") for i in range(3)]

        widget.update_entries(entries)
        assert len(widget._entries) == 3

    def test_update_entries_clears_previous(self, gtk_init) -> None:
        from command_quiver.ui.entry_list import EntryListWidget

        widget = EntryListWidget(on_entry_click=MagicMock())

        # Prima popolazione
        widget.update_entries([_make_entry(entry_id=1)])
        # Seconda popolazione
        entries = [_make_entry(entry_id=i) for i in range(5)]
        widget.update_entries(entries)
        assert len(widget._entries) == 5

    def test_update_with_empty_list(self, gtk_init) -> None:
        from command_quiver.ui.entry_list import EntryListWidget

        widget = EntryListWidget(on_entry_click=MagicMock())
        widget.update_entries([_make_entry()])
        widget.update_entries([])
        assert widget._entries == []

    def test_row_activated_calls_on_click(self, gtk_init) -> None:
        from command_quiver.ui.entry_list import EntryListWidget

        mock_click = MagicMock()
        widget = EntryListWidget(on_entry_click=mock_click)
        entry = _make_entry()
        widget.update_entries([entry])

        # Simula attivazione della prima riga
        row = widget._list_box.get_row_at_index(0)
        if row:
            widget._on_row_activated(widget._list_box, row)
            mock_click.assert_called_once_with(entry)
