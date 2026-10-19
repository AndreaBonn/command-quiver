"""Formato file di import/export della libreria (backup e trasferimento senza GitHub)."""

import json

EXPORT_FORMAT = "command-quiver-export"
EXPORT_VERSION = 1
_REQUIRED_FIELDS = ("name", "content")
# Stessa sezione di fallback di db.entry_import.normalize_import_item
DEFAULT_SECTION_NAME = "Generale"


class InvalidExportError(ValueError):
    """Il file non è un export di Command Quiver leggibile."""


def serialize_export(entries: list[dict]) -> str:
    """JSON con intestazione di formato: un file qualsiasi non passa per un export."""
    payload = {"format": EXPORT_FORMAT, "version": EXPORT_VERSION, "entries": entries}
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def parse_import(text: str) -> list[dict]:
    """Voci da un file di export; accetta anche una lista nuda di voci.

    Raises
    ------
    InvalidExportError
        JSON non valido, formato sconosciuto, o nessuna voce con nome e contenuto.
    """
    try:
        data = json.loads(text)
    except json.JSONDecodeError as err:
        raise InvalidExportError("JSON non valido") from err

    if isinstance(data, dict):
        if data.get("format") != EXPORT_FORMAT:
            raise InvalidExportError("formato sconosciuto")
        data = data.get("entries")
    if not isinstance(data, list):
        raise InvalidExportError("nessuna lista di voci")

    entries = [_normalize_section(item) for item in data if _has_required_text(item)]
    if not entries:
        raise InvalidExportError("nessuna voce valida")
    return entries


def _has_required_text(item: object) -> bool:
    """Voce utilizzabile: dizionario con nome e contenuto stringhe non vuote."""
    return isinstance(item, dict) and all(
        isinstance(item.get(k), str) and item[k].strip() for k in _REQUIRED_FIELDS
    )


def _normalize_section(item: dict) -> dict:
    """Sezione di destinazione sempre stringa valida: un valore non testuale (lista,
    numero, null) faceva fallire l'import a metà, con parte delle voci già scritte."""
    section = item.get("section_name")
    cleaned = section.strip() if isinstance(section, str) else ""
    return {**item, "section_name": cleaned or DEFAULT_SECTION_NAME}
