"""Test del motore di sync: esecuzione cross-thread e messaggi azionabili."""

import threading
from pathlib import Path

import pytest

from command_quiver.core.github_client import GitHubApiError, GitHubClient
from command_quiver.core.settings import Settings
from command_quiver.core.sync_engine import SyncEngine
from command_quiver.db.database import Database


class _FakeClient:
    """Client GitHub finto: simula un primo sync (nessun file remoto)."""

    def get_file(self, path: str) -> None:
        return None

    def put_file(self, path: str, content: str, sha: str = "") -> str:
        return "fakesha"


@pytest.fixture
def sync_engine(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """SyncEngine su DB temporaneo, con rete e persistenza settings neutralizzate."""
    db = Database(db_path=tmp_path / "vault.db")
    db.initialize()
    engine = SyncEngine(db=db, settings=Settings())
    # Bypassa token/rete: il client finto simula un primo sync riuscito.
    monkeypatch.setattr(engine, "_create_client", lambda: _FakeClient())
    # Evita di sovrascrivere il settings reale dell'utente durante il test.
    monkeypatch.setattr("command_quiver.core.sync_engine.save_settings", lambda s: None)
    yield engine
    db.close()


def test_sync_from_separate_thread_does_not_raise(sync_engine: SyncEngine) -> None:
    """sync() eseguito in un thread diverso da quello di init deve funzionare.

    Regressione: SyncEngine veniva costruito nel thread GTK ma sync() gira in
    un thread daemon; riusare la connessione principale sollevava
    sqlite3.ProgrammingError (connessione condivisa cross-thread).
    """
    errors: list[Exception] = []
    results = []

    def run() -> None:
        try:
            results.append(sync_engine.sync())
        except Exception as exc:
            errors.append(exc)

    thread = threading.Thread(target=run)
    thread.start()
    thread.join()

    assert errors == [], f"sync() ha sollevato in un thread separato: {errors}"
    assert results[0].success is True


def test_sync_in_thread_completes_push(sync_engine: SyncEngine) -> None:
    """Il sync in thread arriva in fondo: lo SHA restituito dal push è salvato."""
    thread = threading.Thread(target=sync_engine.sync)
    thread.start()
    thread.join()

    assert sync_engine._settings.sync.last_sha == "fakesha"


@pytest.mark.parametrize(
    ("status_code", "expected_substring"),
    [
        (401, "token"),
        (403, "permessi"),
        (404, "repository"),
        (409, "conflitto"),
        (422, "percorso file"),
    ],
)
def test_humanize_github_error_maps_status(status_code: int, expected_substring: str) -> None:
    from command_quiver.core.sync_engine import humanize_github_error

    message = humanize_github_error(GitHubApiError("raw body", status_code=status_code))
    assert expected_substring.lower() in message.lower()


def test_humanize_github_error_network_when_no_status() -> None:
    from command_quiver.core.sync_engine import humanize_github_error

    message = humanize_github_error(GitHubApiError("Errore di rete: timeout"))
    assert "rete" in message.lower()


def test_humanize_github_error_unknown_status_keeps_code() -> None:
    from command_quiver.core.sync_engine import humanize_github_error

    message = humanize_github_error(GitHubApiError("teapot", status_code=418))
    assert "418" in message


def test_count_pushed_counts_new_and_changed_entries() -> None:
    from command_quiver.core.sync_merge import count_pushed

    remote = [{"uuid": "a", "updated_at": "1"}, {"uuid": "b", "updated_at": "1"}]
    merged = [
        {"uuid": "a", "updated_at": "1"},  # invariata
        {"uuid": "b", "updated_at": "2"},  # modificata in locale
        {"uuid": "c", "updated_at": "1"},  # nuova
    ]
    assert count_pushed(merged=merged, remote=remote) == 2


def test_count_pushed_nothing_changed() -> None:
    from command_quiver.core.sync_merge import count_pushed

    same = [{"uuid": "a", "updated_at": "1"}]
    assert count_pushed(merged=same, remote=same) == 0


def test_first_sync_reports_all_local_entries_pushed(sync_engine: SyncEngine) -> None:
    from command_quiver.db.entry_repository import EntryRepository
    from command_quiver.db.models import EntryCreate

    repo = EntryRepository(sync_engine._db.connection)
    repo.create(EntryCreate(name="a", content="a", section_id=1))
    repo.create(EntryCreate(name="b", content="b", section_id=1))

    result = sync_engine.sync()

    assert result.success is True
    assert result.entries_pushed == 2


@pytest.mark.parametrize(
    "case",
    [
        ("", True, "a", "b", False),
        ("token", False, "a", "b", False),
        ("token", True, "", "b", False),
        ("token", True, "a", "", False),
        ("token", True, "a", "b", True),
    ],
)
def test_create_client_configuration_returns_expected_client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case: tuple
) -> None:
    token, enabled, owner, repo, expected = case
    settings = Settings()
    settings.sync.enabled = enabled
    settings.sync.repo_owner = owner
    settings.sync.repo_name = repo
    engine = SyncEngine(db=Database(db_path=tmp_path / "unused.db"), settings=settings)
    monkeypatch.setattr("command_quiver.core.sync_engine.load_sync_token", lambda: token)

    client = engine._create_client()

    assert isinstance(client, GitHubClient) is expected
    settings.sync.enabled = True
    settings.sync.repo_owner = "a"
    settings.sync.repo_name = "b"
    monkeypatch.setattr("command_quiver.core.sync_engine.load_sync_token", lambda: "token")
    assert engine._create_client()._owner == "a"


def test_sync_unconfigured_returns_failure(
    sync_engine: SyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sync_engine, "_create_client", lambda: None)

    result = sync_engine.sync()

    assert (result.success, result.message) == (False, "Sync non configurato")
    monkeypatch.setattr(sync_engine, "_create_client", lambda: _FakeClient())
    assert sync_engine.sync().message == "Primo sync"


@pytest.mark.parametrize("content", ["{broken", '{"entries": [{}]}', '{"entries": null}'])
def test_sync_corrupt_remote_returns_data_error(
    sync_engine: SyncEngine, monkeypatch: pytest.MonkeyPatch, content: str
) -> None:
    from command_quiver.core.github_client import FileContent

    class Client(_FakeClient):
        def get_file(self, path: str) -> FileContent:
            return FileContent(content=content, sha="old")

    monkeypatch.setattr(sync_engine, "_create_client", lambda: Client())

    result = sync_engine.sync()

    assert result.success is False
    assert result.message.startswith("Dati remoti corrotti:")
    monkeypatch.setattr(sync_engine, "_create_client", lambda: _FakeClient())
    assert sync_engine.sync().success is True


def test_sync_failed_push_returns_humanized_error(
    sync_engine: SyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Client(_FakeClient):
        def put_file(self, path: str, content: str, sha: str = "") -> str:
            raise GitHubApiError("raw", status_code=401)

    monkeypatch.setattr(sync_engine, "_create_client", lambda: Client())

    result = sync_engine.sync()

    assert result.success is False
    assert "Token GitHub non valido o scaduto" in result.message
    monkeypatch.setattr(sync_engine, "_create_client", lambda: _FakeClient())
    assert sync_engine.sync().success is True
