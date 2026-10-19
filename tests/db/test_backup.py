"""Backup periodici verificati sul filesystem e con SQLite reali."""

import logging
import sqlite3
from pathlib import Path

import pytest

from command_quiver.db.backup import auto_backup


def test_auto_backup_missing_database_skips_counter(tmp_path: Path) -> None:
    with sqlite3.connect(tmp_path / "source.db") as connection:
        auto_backup(connection, db_path=tmp_path / "vault.db")

    assert not (tmp_path / ".backup_counter").exists()


def test_auto_backup_first_start_writes_counter_one(tmp_path: Path) -> None:
    """Positivo appaiato: con il database presente il contatore parte."""
    with sqlite3.connect(tmp_path / "vault.db") as connection:
        auto_backup(connection, db_path=tmp_path / "vault.db")

    assert (tmp_path / ".backup_counter").read_text() == "1"


def test_auto_backup_unwritable_counter_does_not_raise(tmp_path: Path) -> None:
    # Una directory al posto del file rende impossibile scrivere il contatore
    counter = tmp_path / ".backup_counter"
    counter.mkdir()

    with sqlite3.connect(tmp_path / "vault.db") as connection:
        auto_backup(connection, db_path=tmp_path / "vault.db")

    assert counter.is_dir()
    assert list(tmp_path.glob("vault.auto.bak.*")) == []


def test_auto_backup_fifth_start_updates_counter(tmp_path: Path) -> None:
    (tmp_path / ".backup_counter").write_text("4")

    with sqlite3.connect(tmp_path / "vault.db") as connection:
        auto_backup(connection, db_path=tmp_path / "vault.db")

    assert (tmp_path / ".backup_counter").read_text() == "5"


def test_auto_backup_fifth_start_copies_committed_rows(tmp_path: Path) -> None:
    path = tmp_path / "vault.db"
    (tmp_path / ".backup_counter").write_text("4")
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE saved (value TEXT)")
        connection.execute("INSERT INTO saved VALUES ('preserved')")
        connection.commit()

        auto_backup(connection, db_path=path)

    backup = next(tmp_path.glob("vault.auto.bak.*"))
    with sqlite3.connect(backup) as reader:
        assert reader.execute("SELECT value FROM saved").fetchall() == [("preserved",)]


def _prepare_four_backups(tmp_path: Path, oldest_is_dir: bool) -> Path:
    """Quattro backup per una soglia di tre: il più vecchio va eliminato."""
    oldest = tmp_path / "vault.auto.bak.20000101T000000"
    if oldest_is_dir:
        oldest.mkdir()
    else:
        oldest.touch()
    for day in ("02", "03"):
        (tmp_path / f"vault.auto.bak.200001{day}T000000").touch()
    (tmp_path / ".backup_counter").write_text("4")
    return oldest


def test_auto_backup_failed_prune_logs_warning_with_path(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Regressione DC4: la rimozione fallita di un vecchio backup non resta silenziosa."""
    # Una directory al posto del file fa fallire unlink()
    oldest = _prepare_four_backups(tmp_path, oldest_is_dir=True)

    with (
        sqlite3.connect(tmp_path / "vault.db") as connection,
        caplog.at_level(logging.WARNING, logger="command_quiver.db.backup"),
    ):
        auto_backup(connection, db_path=tmp_path / "vault.db")

    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert str(oldest) in warnings[0].getMessage()


def test_auto_backup_successful_prune_removes_oldest_without_warning(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Positivo appaiato: quando unlink riesce nessun avviso e il più vecchio sparisce."""
    oldest = _prepare_four_backups(tmp_path, oldest_is_dir=False)

    with (
        sqlite3.connect(tmp_path / "vault.db") as connection,
        caplog.at_level(logging.WARNING, logger="command_quiver.db.backup"),
    ):
        auto_backup(connection, db_path=tmp_path / "vault.db")

    assert [r for r in caplog.records if r.levelno == logging.WARNING] == []
    assert not oldest.exists()
