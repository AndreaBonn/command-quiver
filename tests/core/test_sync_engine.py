"""Test del motore di sync: esecuzione cross-thread e messaggi azionabili."""

import threading
from pathlib import Path

import pytest

from command_quiver.core.github_client import GitHubApiError
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
