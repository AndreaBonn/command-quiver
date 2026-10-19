"""Test dei comportamenti UX della finestra principale (proposte del mockup ux-proposte)."""

from datetime import datetime
from unittest.mock import patch

import pytest

from command_quiver.core.i18n import init as i18n_init
from command_quiver.core.settings import Settings
from command_quiver.core.sync_engine import SyncResult
from command_quiver.db.database import Database
from command_quiver.db.entry_repository import EntryRepository
from command_quiver.db.models import EntryCreate
from tests.conftest import requires_display


@pytest.fixture(autouse=True)
def _italian() -> None:
    i18n_init("it")


def _sidebar(db: Database, settings: Settings | None = None):
    from command_quiver.ui.sidebar import SidebarPanel

    with patch("command_quiver.ui.sidebar.save_settings"):
        return SidebarPanel(db=db, settings=settings or Settings())


def _labels(widget) -> list[str]:
    """Tutti i testi delle Gtk.Label discendenti (per verificare cosa vede l'utente)."""
    from gi.repository import Gtk

    found = []
    child = widget.get_first_child()
    while child is not None:
        if isinstance(child, Gtk.Label):
            found.append(child.get_label())
        found.extend(_labels(child))
        child = child.get_next_sibling()
    return found


def _placeholder(sidebar):
    return sidebar._entry_list.empty_state


def _add(db: Database, name: str, content: str, entry_type: str = "shell", section_id: int = 1):
    return EntryRepository(db.connection).create(
        EntryCreate(name=name, content=content, section_id=section_id, type=entry_type)
    )


@requires_display
class TestEmptyStates:
    def test_first_run_shows_welcome_not_search_failure(self, gtk_init, db_for_ui) -> None:
        texts = _labels(_placeholder(_sidebar(db_for_ui)))
        assert "Tieni a portata di mano i tuoi prompt e comandi" in texts
        assert "Nessuna voce trovata" not in texts

    def test_add_samples_creates_six_entries(self, gtk_init, db_for_ui) -> None:
        sidebar = _sidebar(db_for_ui)
        sidebar._library.add_samples()
        assert EntryRepository(db_for_ui.connection).count_all() == 6
        assert len(sidebar._entry_list.entries) == 6
        assert sidebar._toast.message == "Aggiunte 6 voci di esempio"

    def test_empty_section_names_the_section(self, gtk_init, db_for_ui) -> None:
        _add(db_for_ui, "x", "x", section_id=1)
        sidebar = _sidebar(db_for_ui)
        sidebar._section_panel.select_section(3)  # Git, vuota
        texts = _labels(_placeholder(sidebar))
        assert "Ancora niente in Git" in texts

    def test_search_without_results_echoes_query_and_offers_all_sections(
        self, gtk_init, db_for_ui
    ) -> None:
        _add(db_for_ui, "Docker build", "docker build .", section_id=1)
        sidebar = _sidebar(db_for_ui)
        sidebar._section_panel.select_section(2)
        sidebar._search_text = "docker"
        sidebar._refresh_entries()
        texts = _labels(_placeholder(sidebar))
        assert any("«docker»" in text for text in texts)

        sidebar._section_panel.select_section(None)  # "Cerca in tutte le sezioni"
        assert [e.name for e in sidebar._entry_list.entries] == ["Docker build"]


@requires_display
class TestCopyAndRun:
    def test_copy_shows_toast_with_entry_name(self, gtk_init, db_for_ui) -> None:
        _add(db_for_ui, "Log", "git log")
        sidebar = _sidebar(db_for_ui)
        with patch("command_quiver.ui.entry_list.copy_to_clipboard", return_value=True):
            assert sidebar._entry_list.copy_first() is True
        assert sidebar._toast.message == "Copiato: Log"

    def test_run_asks_confirmation_before_executing(self, gtk_init, db_for_ui) -> None:
        entry = _add(db_for_ui, "Upgrade", "sudo apt upgrade")
        sidebar = _sidebar(db_for_ui)
        with (
            patch("command_quiver.ui.entry_list.execute_in_terminal") as mock_exec,
            patch("command_quiver.ui.run_confirm.RunConfirmDialog") as mock_dialog,
        ):
            sidebar._on_run_requested(entry)
        mock_exec.assert_not_called()
        mock_dialog.assert_called_once()

    def test_confirm_with_remember_skips_next_confirmation(self, gtk_init, db_for_ui) -> None:
        entry = _add(db_for_ui, "Disk", "df -h")
        settings = Settings()
        sidebar = _sidebar(db_for_ui, settings)
        with (
            patch("command_quiver.ui.entry_list.execute_in_terminal") as mock_exec,
            patch("command_quiver.ui.run_confirm.save_settings"),
            patch("command_quiver.ui.run_confirm.RunConfirmDialog") as mock_dialog,
        ):
            sidebar._on_run_requested(entry)
            # L'utente spunta "non chiedere più" e conferma
            mock_dialog.call_args.kwargs["on_confirm"](entry, True)
            sidebar._on_run_requested(entry)
        assert settings.skip_run_confirm == [entry.uuid]
        assert mock_exec.call_count == 2
        mock_dialog.assert_called_once()

    def test_confirm_without_remember_asks_again(self, gtk_init, db_for_ui) -> None:
        entry = _add(db_for_ui, "Disk", "df -h")
        settings = Settings()
        sidebar = _sidebar(db_for_ui, settings)
        with (
            patch("command_quiver.ui.entry_list.execute_in_terminal") as mock_exec,
            patch("command_quiver.ui.run_confirm.RunConfirmDialog") as mock_dialog,
        ):
            sidebar._on_run_requested(entry)
            mock_dialog.call_args.kwargs["on_confirm"](entry, False)
            sidebar._on_run_requested(entry)
        assert settings.skip_run_confirm == []
        assert mock_exec.call_count == 1
        assert mock_dialog.call_count == 2

    def test_tag_click_filters_by_tag(self, gtk_init, db_for_ui) -> None:
        sidebar = _sidebar(db_for_ui)
        sidebar._entry_list._callbacks.on_tag("git")
        assert sidebar._search_entry.get_text() == "git"


@requires_display
class TestSyncStatus:
    def test_disabled_sync_says_local_only(self, gtk_init, db_for_ui) -> None:
        assert _sidebar(db_for_ui)._status_bar.text == "Salvato solo su questo computer"

    def test_enabled_but_never_synced_is_not_ok(self, gtk_init, db_for_ui) -> None:
        settings = Settings()
        settings.sync.enabled = True
        assert _sidebar(db_for_ui, settings)._status_bar.text == "Non ancora sincronizzato"

    def test_real_result_shows_counts(self, gtk_init, db_for_ui) -> None:
        settings = Settings()
        settings.sync.enabled = True
        sidebar = _sidebar(db_for_ui, settings)
        sidebar.set_sync_pending()
        assert sidebar._status_bar.text == "Sincronizzazione in corso…"

        settings.sync.last_sync = datetime.now().isoformat()
        sidebar.update_sync_status(SyncResult(success=True, entries_pulled=1, entries_pushed=2))
        assert sidebar._status_bar.text == "Sincronizzato adesso: 1 ricevute, 2 inviate"

    def test_failure_keeps_message_as_tooltip(self, gtk_init, db_for_ui) -> None:
        settings = Settings()
        settings.sync.enabled = True
        sidebar = _sidebar(db_for_ui, settings)
        sidebar.update_sync_status(SyncResult(success=False, message="Token scaduto"))
        assert sidebar._status_bar.text == "Sincronizzazione non riuscita"
        assert sidebar._status_bar.get_tooltip_text() == "Token scaduto"


@requires_display
class TestSectionsMenu:
    def test_default_section_menu_has_no_delete(self, gtk_init, db_for_ui) -> None:
        from command_quiver.db.section_repository import SectionRepository
        from command_quiver.ui.section_row import build_section_menu

        default = next(s for s in SectionRepository(db_for_ui.connection).get_all() if s.is_default)
        other = next(
            s for s in SectionRepository(db_for_ui.connection).get_all() if not s.is_default
        )

        default_texts = _labels(build_section_menu(default, on_rename=print, on_delete=print))
        other_menu = build_section_menu(other, on_rename=print, on_delete=print)

        assert "Elimina: non disponibile, è la sezione predefinita" in default_texts
        assert "Elimina" not in [
            b.get_label()
            for b in _buttons(build_section_menu(default, on_rename=print, on_delete=print))
        ]
        assert "Elimina" in [b.get_label() for b in _buttons(other_menu)]


def _buttons(widget) -> list:
    from gi.repository import Gtk

    found = []
    child = widget.get_first_child()
    while child is not None:
        if isinstance(child, Gtk.Button):
            found.append(child)
        found.extend(_buttons(child))
        child = child.get_next_sibling()
    return found


def test_section_icon_falls_back_when_theme_lacks_it() -> None:
    from command_quiver.ui.section_row import FALLBACK_ICON, resolve_section_icon

    assert resolve_section_icon("vcs-commit", has_icon=lambda _name: False) == FALLBACK_ICON
    assert (
        resolve_section_icon("utilities-terminal", has_icon=lambda _name: True)
        == "utilities-terminal-symbolic"
    )


@requires_display
class TestDeleteWithUndo:
    """E7: la voce sparisce subito, "Annulla" la riporta, la cancellazione vera arriva dopo."""

    def _count(self, sidebar, row_index: int) -> str:
        row = sidebar._section_panel._section_list.get_row_at_index(row_index)
        return row.get_child().count_label.get_label()

    def test_delete_hides_entry_and_updates_counts(self, gtk_init, db_for_ui) -> None:
        entry = _add(db_for_ui, "Log", "git log", section_id=1)
        _add(db_for_ui, "Df", "df -h", section_id=1)
        sidebar = _sidebar(db_for_ui)
        sidebar._library.delete(entry.id)

        assert [e.name for e in sidebar._entry_list.entries] == ["Df"]
        assert self._count(sidebar, 0) == "1"  # Tutti
        assert self._count(sidebar, 1) == "1"  # sezione della voce
        assert EntryRepository(db_for_ui.connection).get_by_id(entry.id) is not None
        assert sidebar._toast.message == "Eliminata: Log"

    def test_undo_restores_entry_without_deleting(self, gtk_init, db_for_ui) -> None:
        entry = _add(db_for_ui, "Log", "git log")
        sidebar = _sidebar(db_for_ui)
        sidebar._library.delete(entry.id)
        sidebar._library.undo_delete()
        sidebar._pending_delete.flush()

        assert [e.name for e in sidebar._entry_list.entries] == ["Log"]
        assert EntryRepository(db_for_ui.connection).get_by_id(entry.id) is not None

    def test_close_commits_pending_delete(self, gtk_init, db_for_ui) -> None:
        entry = _add(db_for_ui, "Log", "git log")
        sidebar = _sidebar(db_for_ui)
        sidebar._library.delete(entry.id)
        with patch("command_quiver.ui.sidebar.save_settings"):
            sidebar._on_close_request(sidebar)
        assert EntryRepository(db_for_ui.connection).get_by_id(entry.id) is None

    def test_second_delete_commits_first(self, gtk_init, db_for_ui) -> None:
        first = _add(db_for_ui, "A", "a")
        second = _add(db_for_ui, "B", "b")
        sidebar = _sidebar(db_for_ui)
        sidebar._library.delete(first.id)
        sidebar._library.delete(second.id)
        repo = EntryRepository(db_for_ui.connection)
        assert repo.get_by_id(first.id) is None
        assert repo.get_by_id(second.id) is not None
        assert sidebar._entry_list.entries == []


@requires_display
class TestDragReorder:
    """M8: nell'ordine Personale una voce trascinata prende il posto della destinazione."""

    def test_drop_reorders_and_persists(self, gtk_init, db_for_ui) -> None:
        a = _add(db_for_ui, "A", "a")
        _add(db_for_ui, "B", "b")
        c = _add(db_for_ui, "C", "c")
        settings = Settings(sort_order="personal")
        sidebar = _sidebar(db_for_ui, settings)
        assert [e.name for e in sidebar._entry_list.entries] == ["A", "B", "C"]

        sidebar._entry_list._callbacks.on_reorder(c.id, a.id)

        assert [e.name for e in sidebar._entry_list.entries] == ["C", "A", "B"]
        reloaded = _sidebar(db_for_ui, settings)
        assert [e.name for e in reloaded._entry_list.entries] == ["C", "A", "B"]

    def test_drag_handle_only_in_personal_order(self, gtk_init, db_for_ui) -> None:
        _add(db_for_ui, "A", "a")
        personal = _sidebar(db_for_ui, Settings(sort_order="personal"))
        recent = _sidebar(db_for_ui, Settings())
        row_personal = personal._entry_list._list_box.get_row_at_index(0).get_child()
        row_recent = recent._entry_list._list_box.get_row_at_index(0).get_child()
        assert row_personal.drag_handle is not None
        assert row_recent.drag_handle is None


@requires_display
class TestSecondReviewFixes:
    def test_plain_toast_does_not_hide_pending_undo(self, gtk_init, db_for_ui) -> None:
        first = _add(db_for_ui, "A", "a")
        _add(db_for_ui, "B", "b")
        sidebar = _sidebar(db_for_ui)
        sidebar._library.delete(first.id)
        with patch("command_quiver.ui.entry_list.copy_to_clipboard", return_value=True):
            sidebar._entry_list.copy_first()
        assert sidebar._toast.message == "Eliminata: A"
        assert sidebar._toast._action.get_visible() is True

    def test_section_change_keeps_hidden_entry_out_of_counts(self, gtk_init, db_for_ui) -> None:
        entry = _add(db_for_ui, "A", "a", section_id=1)
        sidebar = _sidebar(db_for_ui)
        sidebar._library.delete(entry.id)
        sidebar._section_panel._on_section_created("Nuova")
        row = sidebar._section_panel._section_list.get_row_at_index(0)
        assert row.get_child().count_label.get_label() == "0"

    def test_keyboard_move_in_all_sections_with_duplicate_positions(
        self, gtk_init, db_for_ui
    ) -> None:
        # In "Tutti" le posizioni personali si ripetono tra sezioni (0 in ciascuna)
        a = _add(db_for_ui, "A", "a", section_id=1)
        _add(db_for_ui, "B", "b", section_id=2)
        sidebar = _sidebar(db_for_ui, Settings(sort_order="personal"))
        assert [e.name for e in sidebar._entry_list.entries] == ["A", "B"]
        sidebar._library.move(a.id, 1)
        assert [e.name for e in sidebar._entry_list.entries] == ["B", "A"]
