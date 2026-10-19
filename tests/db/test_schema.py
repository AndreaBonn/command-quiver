"""Contratti delle funzioni di schema su connessioni SQLite reali."""

import sqlite3
from collections.abc import Iterator
from pathlib import Path
from uuid import UUID

import pytest

from command_quiver.db.schema import (
    build_schema,
    detect_schema_version,
    migrate,
    migrate_v2,
    populate_uuids,
    seed_if_empty,
)


@pytest.fixture
def connection(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    with sqlite3.connect(tmp_path / "schema.db") as connection:
        connection.row_factory = sqlite3.Row
        yield connection
    connection.close()


def test_build_schema_unknown_language_seeds_english(connection: sqlite3.Connection) -> None:
    build_schema(connection, language="unknown")

    names = connection.execute("SELECT name FROM sections ORDER BY position").fetchall()
    assert [row[0] for row in names] == ["Shell Commands", "AI Prompts", "Git", "Generale"]


def test_build_schema_seed_uuids_are_committed(connection: sqlite3.Connection) -> None:
    build_schema(connection, language="it")

    path = connection.execute("PRAGMA database_list").fetchone()[2]
    with sqlite3.connect(path) as reader:
        uuids = reader.execute("SELECT uuid FROM sections").fetchall()
    assert len(uuids) == 4
    assert all(str(UUID(row[0])) == row[0] for row in uuids)


def test_detect_schema_version_legacy_v1_persists_version(connection: sqlite3.Connection) -> None:
    connection.execute("CREATE TABLE sections (id INTEGER PRIMARY KEY, is_default INTEGER)")

    version = detect_schema_version(connection)

    path = connection.execute("PRAGMA database_list").fetchone()[2]
    with sqlite3.connect(path) as reader:
        assert reader.execute("PRAGMA user_version").fetchone()[0] == version == 1


def test_migrate_missing_entries_propagates_sqlite_error(connection: sqlite3.Connection) -> None:
    connection.execute("PRAGMA user_version = 2")

    with pytest.raises(sqlite3.OperationalError, match="no such table: entries"):
        migrate(connection)
    assert connection.execute("PRAGMA user_version").fetchone()[0] == 2


def test_migrate_v2_missing_entries_propagates_sqlite_error(connection: sqlite3.Connection) -> None:
    connection.execute("CREATE TABLE sections (id INTEGER PRIMARY KEY)")

    with pytest.raises(sqlite3.OperationalError, match="no such table: entries"):
        migrate_v2(connection)
    assert [row[1] for row in connection.execute("PRAGMA table_info(sections)")] == ["id"]


def test_migrate_v2_partial_schema_adds_remaining_columns(connection: sqlite3.Connection) -> None:
    connection.executescript(
        "CREATE TABLE entries (id INTEGER PRIMARY KEY, uuid TEXT);"
        "CREATE TABLE sections (id INTEGER PRIMARY KEY);"
    )

    migrate_v2(connection)

    assert [row[1] for row in connection.execute("PRAGMA table_info(sections)")] == [
        "id",
        "uuid",
        "updated_at",
    ]


def test_migrate_v2_schema_enforces_unique_uuid(connection: sqlite3.Connection) -> None:
    connection.executescript(
        "CREATE TABLE entries (id INTEGER PRIMARY KEY);"
        "CREATE TABLE sections (id INTEGER PRIMARY KEY);"
    )
    migrate_v2(connection)
    connection.execute("INSERT INTO sections (uuid) VALUES ('unique')")

    with pytest.raises(sqlite3.IntegrityError, match="UNIQUE"):
        connection.execute("INSERT INTO sections (uuid) VALUES ('unique')")

    assert connection.execute("SELECT uuid FROM sections").fetchone()[0] == "unique"


def test_migrate_v2_entries_duplicate_uuid_raises_integrity_error(
    connection: sqlite3.Connection,
) -> None:
    connection.executescript(
        "CREATE TABLE entries (id INTEGER PRIMARY KEY);"
        "CREATE TABLE sections (id INTEGER PRIMARY KEY);"
    )
    migrate_v2(connection)
    connection.execute("INSERT INTO entries (uuid) VALUES ('unique-entry')")

    with pytest.raises(sqlite3.IntegrityError, match="UNIQUE"):
        connection.execute("INSERT INTO entries (uuid) VALUES ('unique-entry')")

    assert [row[0] for row in connection.execute("SELECT uuid FROM entries")] == ["unique-entry"]


def test_populate_uuids_schema_without_uuid_preserves_rows(connection: sqlite3.Connection) -> None:
    connection.executescript("CREATE TABLE entries (id INTEGER); INSERT INTO entries VALUES (7);")

    populate_uuids(connection)

    assert [tuple(row) for row in connection.execute("SELECT * FROM entries")] == [(7,)]


def test_populate_uuids_existing_uuid_is_preserved(connection: sqlite3.Connection) -> None:
    build_schema(connection, language="en")
    connection.execute("INSERT INTO entries (name, content, uuid) VALUES ('kept', 'x', 'stable')")
    connection.execute("INSERT INTO entries (name, content) VALUES ('new', 'y')")

    populate_uuids(connection)

    rows = connection.execute("SELECT name, uuid FROM entries ORDER BY id").fetchall()
    assert tuple(rows[0]) == ("kept", "stable")
    assert str(UUID(rows[1][1])) == rows[1][1]


def test_seed_if_empty_populated_sections_keep_original_names(
    connection: sqlite3.Connection,
) -> None:
    build_schema(connection, language="it")

    seed_if_empty(connection, language="en")

    assert [
        row[0] for row in connection.execute("SELECT name FROM sections ORDER BY position")
    ] == ["Comandi shell", "Prompt AI", "Git", "Generale"]
