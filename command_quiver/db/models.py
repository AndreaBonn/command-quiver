"""Modelli dati ed eccezioni per il database Command Quiver."""

from dataclasses import dataclass


class DuplicateSectionError(Exception):
    """Errore sollevato quando si tenta di creare/rinominare una sezione con nome duplicato."""

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"Sezione '{name}' esiste già")


@dataclass
class Section:
    """Rappresenta una sezione/categoria di voci."""

    id: int
    name: str
    icon: str = "folder"
    position: int = 0
    is_default: int = 0
    created_at: str = ""
    entry_count: int = 0  # Calcolato via query, non persistito


@dataclass
class Entry:
    """Rappresenta una voce (prompt o comando shell)."""

    id: int
    name: str
    content: str
    section_id: int | None = None
    type: str = "prompt"
    tags: str = ""
    personal_pos: int = 0
    created_at: str = ""
    updated_at: str = ""
    section_name: str = ""  # Calcolato via JOIN, non persistito


@dataclass
class EntryCreate:
    """Dati per la creazione di una nuova voce."""

    name: str
    content: str
    section_id: int | None = None
    type: str = "prompt"
    tags: str = ""


@dataclass
class EntryUpdate:
    """Dati per l'aggiornamento di una voce esistente."""

    id: int
    name: str
    content: str
    section_id: int | None = None
    type: str = "prompt"
    tags: str = ""
