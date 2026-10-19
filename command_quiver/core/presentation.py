"""Funzioni pure di presentazione: tempo relativo, nome automatico, tag, anteprima."""

from datetime import datetime

from command_quiver.core.i18n import t

NAME_MAX_LENGTH = 100
PREVIEW_MAX_LENGTH = 90
_ELLIPSIS = "…"
_LINE_BREAK_MARK = " ↵ "
_SECONDS_PER_MINUTE = 60
_SECONDS_PER_HOUR = 3600
_SECONDS_PER_DAY = 86400
_RELATIVE_DAYS_LIMIT = 7


def _truncate(text: str, max_length: int) -> str:
    if len(text) <= max_length:
        return text
    return text[: max_length - 1] + _ELLIPSIS


def format_relative_time(iso: str, now: datetime) -> str:
    """Rende un timestamp ISO come "5 minuti fa"; oltre una settimana mostra la data.

    Restituisce stringa vuota se il timestamp manca o non è valido.
    """
    try:
        moment = datetime.fromisoformat(iso)
    except ValueError:
        return ""
    seconds = int((now - moment).total_seconds())
    if seconds < _SECONDS_PER_MINUTE:
        return t("time.now")
    if seconds < _SECONDS_PER_HOUR:
        return _plural(seconds // _SECONDS_PER_MINUTE, "time.minute", "time.minutes")
    if seconds < _SECONDS_PER_DAY:
        return _plural(seconds // _SECONDS_PER_HOUR, "time.hour", "time.hours")
    days = seconds // _SECONDS_PER_DAY
    if days < _RELATIVE_DAYS_LIMIT:
        return _plural(days, "time.day", "time.days")
    return moment.strftime(t("time.date_format"))


def _plural(count: int, singular_key: str, plural_key: str) -> str:
    return t(singular_key) if count == 1 else t(plural_key, n=count)


def name_from_content(content: str) -> str:
    """Prima riga non vuota del contenuto, usata come nome quando l'utente non lo scrive."""
    for line in content.splitlines():
        stripped = line.strip()
        if stripped:
            return _truncate(stripped, NAME_MAX_LENGTH)
    return ""


def content_preview(content: str, max_length: int = PREVIEW_MAX_LENGTH) -> str:
    """Anteprima su una riga: righe unite dal simbolo di a capo, poi troncata."""
    lines = [line.strip() for line in content.strip().splitlines() if line.strip()]
    return _truncate(_LINE_BREAK_MARK.join(lines), max_length)


def split_tags(text: str) -> list[str]:
    """Tag da stringa separata da virgole: senza spazi, vuoti e duplicati (case-insensitive)."""
    seen: set[str] = set()
    tags: list[str] = []
    for raw in text.split(","):
        tag = raw.strip()
        if tag and tag.casefold() not in seen:
            seen.add(tag.casefold())
            tags.append(tag)
    return tags


def join_tags(tags: list[str]) -> str:
    """Formato di persistenza dei tag (stesso usato finora nel campo testo)."""
    return ", ".join(tags)


def collect_tags(tag_strings: list[str]) -> list[str]:
    """Tutti i tag distinti di più voci, in ordine alfabetico senza distinzione di maiuscole."""
    return sorted(split_tags(",".join(tag_strings)), key=str.casefold)
