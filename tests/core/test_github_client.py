"""Test diagnosi della connessione GitHub: un esito per ogni causa correggibile."""

import json
from base64 import b64encode
from io import BytesIO
from urllib.error import HTTPError, URLError
from urllib.request import Request

import pytest

from command_quiver.core.github_client import (
    ConnectionStatus,
    FileContent,
    GitHubApiError,
    GitHubClient,
)


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


def test_validate_valid_connection_returns_true(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _client_raising(monkeypatch, error=None, result={"id": 1}).validate() is True


def test_validate_rejected_token_returns_false(monkeypatch: pytest.MonkeyPatch) -> None:
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


def _fake_urlopen(monkeypatch: pytest.MonkeyPatch, *responses: dict | Exception | None) -> list:
    """Sostituisce urlopen: registra le richieste e risponde con i JSON (o errori) dati."""
    requests: list[Request] = []
    replies = iter(responses)

    def fake_urlopen(request: Request, *, timeout: int) -> BytesIO:
        requests.append(request)
        reply = next(replies)
        if isinstance(reply, Exception):
            raise reply
        return BytesIO(json.dumps(reply).encode("utf-8"))

    monkeypatch.setattr("command_quiver.core.github_client.urlopen", fake_urlopen)
    return requests


def _http_error(code: int, body: BytesIO | None = None) -> HTTPError:
    return HTTPError(url="https://api.github.com", code=code, msg="error", hdrs=None, fp=body)


def test_get_file_json_response_decodes_content_and_sha(monkeypatch: pytest.MonkeyPatch) -> None:
    content = '{"nome": "caffè"}'
    encoded = b64encode(content.encode("utf-8")).decode("ascii")
    _fake_urlopen(monkeypatch, {"content": encoded + "\n", "sha": "remote-sha"})
    client = GitHubClient(token="secret", owner="bonn", repo="vault")

    result = client.get_file(path="folder/vault.json")

    assert result == FileContent(content=content, sha="remote-sha")


def test_get_file_requests_the_file_contents_url_with_get(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests = _fake_urlopen(monkeypatch, {"content": "e30=", "sha": "s"})
    client = GitHubClient(token="secret", owner="bonn", repo="vault")

    client.get_file(path="folder/vault.json")

    assert requests[0].full_url == (
        "https://api.github.com/repos/bonn/vault/contents/folder/vault.json"
    )
    assert requests[0].get_method() == "GET"


def test_get_file_authenticates_with_bearer_token(monkeypatch: pytest.MonkeyPatch) -> None:
    requests = _fake_urlopen(monkeypatch, {"content": "e30=", "sha": "s"})
    client = GitHubClient(token="secret", owner="bonn", repo="vault")

    client.get_file(path="vault.json")

    assert requests[0].get_header("Authorization") == "Bearer secret"


def test_get_file_missing_file_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_urlopen(monkeypatch, _http_error(404))
    client = GitHubClient(token="tok", owner="bonn", repo="vault")

    assert client.get_file(path="missing.json") is None


def test_get_file_existing_file_returns_content(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_urlopen(monkeypatch, {"content": "e30=", "sha": "found"})
    client = GitHubClient(token="tok", owner="bonn", repo="vault")

    assert client.get_file(path="existing.json") == FileContent(content="{}", sha="found")


class _UnreadableBody(BytesIO):
    def read(self, *args: object) -> bytes:
        raise OSError("disconnected")


@pytest.mark.parametrize(
    ("body", "expected_body"),
    [
        (BytesIO(b'{"message":"Bad credentials"}'), '{"message":"Bad credentials"}'),
        (_UnreadableBody(), ""),
    ],
    ids=["body", "unreadable"],
)
def test_get_file_unauthorized_response_raises_status_and_available_body(
    monkeypatch: pytest.MonkeyPatch, body: BytesIO, expected_body: str
) -> None:
    error = _http_error(401, body)
    _fake_urlopen(monkeypatch, error)
    client = GitHubClient(token="tok", owner="bonn", repo="vault")

    with pytest.raises(GitHubApiError) as caught:
        client.get_file(path="vault.json")

    assert str(caught.value) == f"GitHub API 401: {expected_body}"
    assert caught.value.status_code == 401
    assert caught.value.__cause__ is error


def test_get_file_network_error_raises_error_without_http_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    error = URLError(reason="offline")
    _fake_urlopen(monkeypatch, error)
    client = GitHubClient(token="tok", owner="bonn", repo="vault")

    with pytest.raises(GitHubApiError, match="Errore di rete: offline") as caught:
        client.get_file(path="vault.json")

    assert caught.value.status_code == 0
    assert caught.value.__cause__ is error


def test_put_file_create_returns_new_sha(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_urlopen(monkeypatch, {"content": {"sha": "created"}})
    client = GitHubClient(token="secret", owner="bonn", repo="vault")

    assert client.put_file(path="vault.json", content="caffè") == "created"


def test_put_file_update_returns_new_sha(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_urlopen(monkeypatch, {"content": {"sha": "updated"}})
    client = GitHubClient(token="secret", owner="bonn", repo="vault")

    assert client.put_file(path="vault.json", content="caffè", sha="created") == "updated"


def test_put_file_create_sends_utf8_content_base64_encoded_without_sha(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests = _fake_urlopen(monkeypatch, {"content": {"sha": "created"}})
    client = GitHubClient(token="secret", owner="bonn", repo="vault")

    client.put_file(path="vault.json", content="caffè")

    body = json.loads(requests[0].data)
    assert body["content"] == b64encode("caffè".encode()).decode("ascii")
    assert "sha" not in body


def test_put_file_update_sends_previous_sha(monkeypatch: pytest.MonkeyPatch) -> None:
    requests = _fake_urlopen(monkeypatch, {"content": {"sha": "updated"}})
    client = GitHubClient(token="secret", owner="bonn", repo="vault")

    client.put_file(path="vault.json", content="caffè", sha="created")

    assert json.loads(requests[0].data)["sha"] == "created"


def test_put_file_sends_a_commit_message(monkeypatch: pytest.MonkeyPatch) -> None:
    requests = _fake_urlopen(monkeypatch, {"content": {"sha": "created"}})
    client = GitHubClient(token="secret", owner="bonn", repo="vault")

    client.put_file(path="vault.json", content="{}")

    assert json.loads(requests[0].data)["message"]


def test_put_file_requests_the_file_contents_url_with_put_and_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests = _fake_urlopen(monkeypatch, {"content": {"sha": "created"}})
    client = GitHubClient(token="secret", owner="bonn", repo="vault")

    client.put_file(path="vault.json", content="{}")

    request = requests[0]
    assert request.full_url == "https://api.github.com/repos/bonn/vault/contents/vault.json"
    assert request.get_method() == "PUT"
    assert request.get_header("Content-type") == "application/json"


def test_put_file_authenticates_with_bearer_token(monkeypatch: pytest.MonkeyPatch) -> None:
    requests = _fake_urlopen(monkeypatch, {"content": {"sha": "created"}})
    client = GitHubClient(token="secret", owner="bonn", repo="vault")

    client.put_file(path="vault.json", content="{}")

    assert requests[0].get_header("Authorization") == "Bearer secret"


def test_put_file_empty_response_raises_api_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_urlopen(monkeypatch, None)
    client = GitHubClient(token="tok", owner="bonn", repo="vault")

    with pytest.raises(GitHubApiError, match="Risposta vuota da PUT file"):
        client.put_file(path="vault.json", content="{}")
