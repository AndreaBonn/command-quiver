"""Test diagnosi della connessione GitHub: un esito per ogni causa correggibile."""

import pytest

from command_quiver.core.github_client import ConnectionStatus, GitHubApiError, GitHubClient


def _client_raising(monkeypatch: pytest.MonkeyPatch, error: Exception | None, result=None):
    client = GitHubClient(token="tok", owner="mrossi", repo="vault")

    def fake_request(method: str, path: str, body: dict | None = None):
        if error is not None:
            raise error
        return result

    monkeypatch.setattr(client, "_request", fake_request)
    return client


def test_check_connection_missing_fields() -> None:
    client = GitHubClient(token="", owner="mrossi", repo="vault")
    assert client.check_connection() is ConnectionStatus.MISSING_FIELDS


def test_check_connection_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client_raising(monkeypatch, error=None, result={"id": 1})
    assert client.check_connection() is ConnectionStatus.OK


def test_check_connection_repo_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client_raising(monkeypatch, error=None, result=None)
    assert client.check_connection() is ConnectionStatus.NOT_FOUND


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        (401, ConnectionStatus.BAD_TOKEN),
        (403, ConnectionStatus.FORBIDDEN),
        (0, ConnectionStatus.NETWORK),
        (500, ConnectionStatus.UNKNOWN),
    ],
)
def test_check_connection_maps_errors(
    monkeypatch: pytest.MonkeyPatch, code: int, expected: ConnectionStatus
) -> None:
    client = _client_raising(monkeypatch, error=GitHubApiError("x", status_code=code))
    assert client.check_connection() is expected


def test_validate_still_boolean(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _client_raising(monkeypatch, error=None, result={"id": 1}).validate() is True
    client = _client_raising(monkeypatch, error=GitHubApiError("x", status_code=401))
    assert client.validate() is False


@pytest.mark.parametrize(
    "error", [TimeoutError("read"), ConnectionResetError(), ValueError("bad json")]
)
def test_check_connection_unexpected_errors_do_not_escape(
    monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    client = _client_raising(monkeypatch, error=error)
    assert client.check_connection() is ConnectionStatus.NETWORK
