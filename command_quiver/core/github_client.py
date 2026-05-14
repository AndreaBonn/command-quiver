"""Client per GitHub Contents API via stdlib urllib.

Gestisce lettura/scrittura di un singolo file JSON in un repo privato.
Zero dipendenze esterne: usa solo urllib.request e json.
"""

import contextlib
import json
import logging
from base64 import b64decode, b64encode
from dataclasses import dataclass
from http.client import HTTPResponse
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.github.com"
_TIMEOUT_SECONDS = 30


@dataclass
class FileContent:
    """Contenuto di un file GitHub con il suo SHA (necessario per aggiornamenti)."""

    content: str
    sha: str


class GitHubApiError(Exception):
    """Errore nelle chiamate GitHub API."""

    def __init__(self, message: str, status_code: int = 0) -> None:
        self.status_code = status_code
        super().__init__(message)


class GitHubClient:
    """Client minimale per GitHub Contents API.

    Operazioni supportate:
    - get_file: scarica contenuto + SHA
    - put_file: crea o aggiorna file
    - validate: verifica credenziali e accesso al repo
    """

    def __init__(self, token: str, owner: str, repo: str) -> None:
        self._token = token
        self._owner = owner
        self._repo = repo

    def _request(
        self,
        method: str,
        path: str,
        body: dict | None = None,
    ) -> dict | None:
        """Esegue una richiesta HTTP verso GitHub API.

        Returns
        -------
        dict | None
            Risposta JSON parsata, o None per 404.

        Raises
        ------
        GitHubApiError
            Per errori HTTP diversi da 404.
        """
        url = f"{_BASE_URL}{path}"
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "CommandQuiver-Sync/1.0",
        }

        data = json.dumps(body).encode("utf-8") if body else None
        if data:
            headers["Content-Type"] = "application/json"

        req = Request(url, data=data, headers=headers, method=method)

        try:
            response: HTTPResponse = urlopen(req, timeout=_TIMEOUT_SECONDS)
            return json.loads(response.read().decode("utf-8"))
        except HTTPError as err:
            if err.code == 404:
                return None
            error_body = ""
            with contextlib.suppress(OSError):
                error_body = err.read().decode("utf-8")
            logger.error(
                "GitHub API errore %d: %s %s - %s",
                err.code,
                method,
                path,
                error_body,
            )
            raise GitHubApiError(
                f"GitHub API {err.code}: {error_body}",
                status_code=err.code,
            ) from err
        except URLError as err:
            logger.error("Errore di rete GitHub: %s", err.reason)
            raise GitHubApiError(f"Errore di rete: {err.reason}") from err

    def validate(self) -> bool:
        """Verifica che token e repo siano validi e accessibili.

        Returns
        -------
        bool
            True se il token è valido e il repo è accessibile.
        """
        if not all([self._token, self._owner, self._repo]):
            return False

        try:
            result = self._request("GET", f"/repos/{self._owner}/{self._repo}")
            return result is not None
        except GitHubApiError:
            return False

    def get_file(self, path: str) -> FileContent | None:
        """Scarica un file dal repo.

        Returns
        -------
        FileContent | None
            Contenuto decodificato e SHA, o None se il file non esiste.
        """
        result = self._request(
            "GET",
            f"/repos/{self._owner}/{self._repo}/contents/{path}",
        )
        if result is None:
            return None

        content_b64 = result.get("content", "")
        sha = result.get("sha", "")

        # GitHub restituisce content in base64 con newline
        content = b64decode(content_b64).decode("utf-8")
        return FileContent(content=content, sha=sha)

    def put_file(self, path: str, content: str, sha: str = "") -> str:
        """Crea o aggiorna un file nel repo.

        Parameters
        ----------
        path : str
            Percorso del file nel repo.
        content : str
            Contenuto del file (testo).
        sha : str
            SHA del file corrente (obbligatorio per aggiornamenti, vuoto per creazione).

        Returns
        -------
        str
            Nuovo SHA del file dopo l'operazione.

        Raises
        ------
        GitHubApiError
            Se la richiesta fallisce.
        """
        body: dict = {
            "message": "sync: update vault",
            "content": b64encode(content.encode("utf-8")).decode("ascii"),
        }
        if sha:
            body["sha"] = sha

        result = self._request(
            "PUT",
            f"/repos/{self._owner}/{self._repo}/contents/{path}",
            body=body,
        )
        if result is None:
            raise GitHubApiError("Risposta vuota da PUT file")

        return result.get("content", {}).get("sha", "")
