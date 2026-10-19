"""Parsing del riferimento a un repository GitHub inserito dall'utente in un campo unico."""

import re

# Regole GitHub: owner solo lettere, cifre e trattini (niente punti, così
# "github.com/owner" non viene scambiato per owner/repo); repo anche "_" e "."
_OWNER = r"[A-Za-z0-9-]+"
_NAME = r"[A-Za-z0-9_.-]+"
_PATTERNS = (
    re.compile(rf"^(?:https?://)?(?:www\.)?github\.com/({_OWNER})/({_NAME})(?:/.*)?$"),
    re.compile(rf"^git@github\.com:({_OWNER})/({_NAME})$"),
    re.compile(rf"^({_OWNER})/({_NAME})$"),
)


def parse_repo_ref(text: str) -> tuple[str, str] | None:
    """Estrae owner e nome del repository da "owner/repo" o da un URL GitHub.

    Parameters
    ----------
    text : str
        Testo incollato dall'utente: "owner/repo", URL https o indirizzo SSH.

    Returns
    -------
    tuple[str, str] | None
        Coppia (owner, repo) senza suffisso ".git", oppure None se il testo
        non identifica un repository GitHub.
    """
    cleaned = text.strip().rstrip("/")
    for pattern in _PATTERNS:
        match = pattern.match(cleaned)
        if match:
            owner, repo = match.group(1), match.group(2)
            repo = repo.removesuffix(".git")
            return (owner, repo) if repo else None
    return None


def format_repo_ref(owner: str, name: str) -> str:
    """Ricompone "owner/repo" per mostrarlo nel campo unico (vuoto se non configurato)."""
    if not owner or not name:
        return ""
    return f"{owner}/{name}"
