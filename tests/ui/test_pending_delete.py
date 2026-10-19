"""Test dell'eliminazione rimandata (E7): annullabile per qualche secondo, poi definitiva."""

from unittest.mock import MagicMock, patch

from command_quiver.ui.pending_delete import PendingDeletion


def test_start_does_not_delete_yet() -> None:
    commit = MagicMock()
    with patch("command_quiver.ui.pending_delete.GLib"):
        pending = PendingDeletion(on_commit=commit)
        pending.start(7)
    commit.assert_not_called()
    assert pending.entry_id == 7


def test_timeout_commits() -> None:
    commit = MagicMock()
    with patch("command_quiver.ui.pending_delete.GLib") as glib:
        pending = PendingDeletion(on_commit=commit)
        pending.start(7)
        timeout_callback = glib.timeout_add.call_args.args[1]
        timeout_callback()
    commit.assert_called_once_with(7)
    assert pending.entry_id is None


def test_undo_cancels_and_never_commits() -> None:
    commit = MagicMock()
    with patch("command_quiver.ui.pending_delete.GLib") as glib:
        pending = PendingDeletion(on_commit=commit)
        pending.start(7)
        assert pending.undo() == 7
        glib.source_remove.assert_called_once()
        pending.flush()
    commit.assert_not_called()


def test_new_delete_commits_previous_first() -> None:
    commit = MagicMock()
    with patch("command_quiver.ui.pending_delete.GLib"):
        pending = PendingDeletion(on_commit=commit)
        pending.start(7)
        pending.start(8)
    commit.assert_called_once_with(7)
    assert pending.entry_id == 8


def test_flush_commits_pending_now() -> None:
    commit = MagicMock()
    with patch("command_quiver.ui.pending_delete.GLib"):
        pending = PendingDeletion(on_commit=commit)
        pending.start(7)
        pending.flush()
        pending.flush()
    commit.assert_called_once_with(7)
