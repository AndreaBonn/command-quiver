"""Cosa apre l'editor delle voci e cosa ne esce al salvataggio (logica pura, senza GTK)."""

from collections.abc import Sequence
from dataclasses import dataclass

from command_quiver.core.presentation import name_from_content
from command_quiver.db.models import Entry, EntryCreate, EntryUpdate, Section


def entry_payload(draft: EntryCreate, entry_id: int | None) -> EntryCreate | EntryUpdate:
    """Dati da salvare a partire da quanto scritto nel form.

    Parameters
    ----------
    draft : EntryCreate
        Campi del form così come sono; il nome può essere vuoto.
    entry_id : int | None
        Voce in modifica, o None per una voce nuova.

    Returns
    -------
    EntryCreate | EntryUpdate
        Il nome, se vuoto, è la prima riga del contenuto; con ``entry_id``
        è l'aggiornamento di quella voce.
    """
    name = draft.name.strip() or name_from_content(draft.content)
    fields = dict(content=draft.content, section_id=draft.section_id, type=draft.type)
    if entry_id is None:
        return EntryCreate(name=name, tags=draft.tags, **fields)
    return EntryUpdate(id=entry_id, name=name, tags=draft.tags, **fields)


@dataclass(frozen=True)
class EditorRequest:
    """Cosa apre l'editor: la voce da modificare (None per una nuova) e il suo contesto.

    ``initial_section_id`` è la sezione aperta nella finestra, usata solo per una
    voce nuova; ``known_tags`` alimenta i suggerimenti del campo tag.
    """

    sections: Sequence[Section]
    entry: Entry | None = None
    initial_section_id: int | None = None
    known_tags: Sequence[str] = ()
