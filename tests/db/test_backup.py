"""Backup periodici verificati sul filesystem e con SQLite reali."""

import sqlite3
from pathlib import Path

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
