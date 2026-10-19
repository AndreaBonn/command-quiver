import logging

from command_quiver.db.entry_repository import EntryRepository
from command_quiver.db.models import EntryCreate
from command_quiver.db.section_repository import SectionRepository

logger = logging.getLogger(__name__)
MAX_IMPORT_ENTRIES = 10_000
MAX_FIELD_LENGTH = 100_000


def normalize_import_item(item: dict) -> dict | None:
    """Normalizza i campi di una voce importata senza modificare l'originale.

    Returns
    -------
    dict | None
        Campi normalizzati, oppure None se nome o contenuto sono vuoti.
    """
    name = str(item.get("name", "")).strip()[:MAX_FIELD_LENGTH]
    content = str(item.get("content", "")).strip()[:MAX_FIELD_LENGTH]
    if not name or not content:
        return None
    entry_type = item.get("type", "prompt")
    return dict(
        name=name,
        content=content,
        type=entry_type if entry_type in ("prompt", "shell") else "prompt",
        tags=str(item.get("tags", ""))[:MAX_FIELD_LENGTH],
        section_name=item.get("section_name", "Generale"),
    )


# SECURITY: le voci importate con type='shell' verranno eseguite letteralmente
# dall'utente. Il file JSON è trattato come input fidato.
def import_entries(
    data: list[dict], *, entry_repo: EntryRepository, section_repo: SectionRepository
) -> int:
    """Importa il prefisso ammesso della libreria, creando le sezioni mancanti.

    Returns
    -------
    int
        Numero di voci importate; quelle senza nome o contenuto vengono saltate.
    """
    if len(data) > MAX_IMPORT_ENTRIES:
        logger.warning(
            "Import troncato: %d voci ricevute, limite %d", len(data), MAX_IMPORT_ENTRIES
        )
        data = data[:MAX_IMPORT_ENTRIES]
    imported = 0
    # Casefold come UNICODE_LOWER: "git" è la "Git" esistente, create() la rifiuterebbe
    section_map = {s.name.casefold(): s.id for s in section_repo.get_all()}
    for item in data:
        normalized = normalize_import_item(item=item)
        if normalized is None:
            continue
        section_name = normalized.pop("section_name")
        key = section_name.casefold()
        if key not in section_map:
            section_map[key] = section_repo.create(name=section_name).id
        entry_repo.create(data=EntryCreate(**normalized, section_id=section_map[key]))
        imported += 1
    logger.info("Importate %d voci su %d", imported, len(data))
    return imported
