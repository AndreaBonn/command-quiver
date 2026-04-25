"""Sistema di internazionalizzazione (i18n) per Command Quiver.

Supporta italiano e inglese tramite dizionari statici.
La lingua viene letta dalle impostazioni utente (settings.json).

Uso:
    from command_quiver.core.i18n import t

    label = Gtk.Label(label=t("sidebar.search_placeholder"))
"""

import logging
from typing import Literal

logger = logging.getLogger(__name__)

Language = Literal["it", "en"]

SUPPORTED_LANGUAGES: tuple[Language, ...] = ("it", "en")
DEFAULT_LANGUAGE: Language = "it"

LANGUAGE_LABELS: dict[Language, str] = {
    "it": "Italiano",
    "en": "English",
}

_current_language: Language = DEFAULT_LANGUAGE

# Dizionario traduzioni organizzato per namespace semantico
_TRANSLATIONS: dict[Language, dict[str, str]] = {
    "it": {
        # --- Sidebar ---
        "sidebar.search_placeholder": "Cerca per nome...",
        "sidebar.sort_label": "Ordina:",
        "sidebar.sort_recent_desc": "Recenti \u2193",
        "sidebar.sort_oldest_asc": "Vecchi \u2191",
        "sidebar.sort_alpha_asc": "A \u2192 Z",
        "sidebar.sort_alpha_desc": "Z \u2192 A",
        "sidebar.sort_personal": "Personale",
        "sidebar.new_entry": "+ Nuova voce",
        "sidebar.sections_header": "SEZIONI",
        "sidebar.new_section": "+ Sezione",
        "sidebar.all_entries": "Tutti ({count})",
        "sidebar.section_row": "{name} ({count})",
        "sidebar.rename": "Rinomina",
        "sidebar.delete": "Elimina",
        # --- Entry list ---
        "entry_list.copy_tooltip": "Copia",
        "entry_list.execute_tooltip": "Esegui in terminale",
        "entry_list.terminal_not_found": "Terminale non trovato",
        "entry_list.empty_title": "Nessuna voce trovata",
        "entry_list.empty_hint": 'Premi "+ Nuova voce" per iniziare',
        # --- Entry editor ---
        "editor.title_edit": "Modifica voce",
        "editor.title_new": "Nuova voce",
        "editor.name_label": "Nome",
        "editor.name_placeholder": "Nome della voce...",
        "editor.type_label": "Tipo:",
        "editor.type_prompt": "Prompt AI",
        "editor.type_shell": "Comando Shell",
        "editor.section_label": "Sezione",
        "editor.content_label": "Contenuto",
        "editor.tags_label": "Tag (separati da virgola)",
        "editor.tags_placeholder": "es: git, deploy, backup",
        "editor.btn_delete": "Elimina",
        "editor.btn_cancel": "Annulla",
        "editor.btn_save_copy": "Salva e Copia",
        "editor.btn_save": "Salva",
        "editor.error_name_required": "Il nome \u00e8 obbligatorio",
        "editor.error_content_required": "Il contenuto \u00e8 obbligatorio",
        "editor.confirm_delete_title": "Eliminare questa voce?",
        "editor.confirm_delete_detail": 'La voce "{name}" verr\u00e0 eliminata definitivamente.',
        # --- Section manager ---
        "section.title_new": "Nuova sezione",
        "section.name_label": "Nome sezione",
        "section.name_placeholder": "Nome della sezione...",
        "section.error_name_required": "Il nome \u00e8 obbligatorio",
        "section.error_name_duplicate": 'La sezione "{name}" esiste gi\u00e0',
        "section.title_rename": "Rinomina sezione",
        "section.new_name_label": "Nuovo nome",
        "section.btn_rename": "Rinomina",
        "section.btn_create": "Crea",
        "section.confirm_delete_title": 'Eliminare la sezione "{name}"?',
        "section.confirm_delete_detail": (
            "Le voci contenute verranno spostate nella sezione 'Generale'."
        ),
        # --- Tray menu ---
        "tray.toggle": "Mostra/Nascondi",
        "tray.new_entry": "Nuova voce",
        "tray.language": "Lingua",
        "tray.quit": "Esci",
        # --- Executor ---
        "executor.terminal_not_found": (
            "gnome-terminal non trovato. Installalo con: sudo apt install gnome-terminal"
        ),
        "executor.press_enter": "\n--- Premere INVIO per chiudere ---",
        # --- Common ---
        "common.cancel": "Annulla",
        "common.delete": "Elimina",
    },
    "en": {
        # --- Sidebar ---
        "sidebar.search_placeholder": "Search by name...",
        "sidebar.sort_label": "Sort:",
        "sidebar.sort_recent_desc": "Recent \u2193",
        "sidebar.sort_oldest_asc": "Oldest \u2191",
        "sidebar.sort_alpha_asc": "A \u2192 Z",
        "sidebar.sort_alpha_desc": "Z \u2192 A",
        "sidebar.sort_personal": "Custom",
        "sidebar.new_entry": "+ New entry",
        "sidebar.sections_header": "SECTIONS",
        "sidebar.new_section": "+ Section",
        "sidebar.all_entries": "All ({count})",
        "sidebar.section_row": "{name} ({count})",
        "sidebar.rename": "Rename",
        "sidebar.delete": "Delete",
        # --- Entry list ---
        "entry_list.copy_tooltip": "Copy",
        "entry_list.execute_tooltip": "Run in terminal",
        "entry_list.terminal_not_found": "Terminal not found",
        "entry_list.empty_title": "No entries found",
        "entry_list.empty_hint": 'Press "+ New entry" to get started',
        # --- Entry editor ---
        "editor.title_edit": "Edit entry",
        "editor.title_new": "New entry",
        "editor.name_label": "Name",
        "editor.name_placeholder": "Entry name...",
        "editor.type_label": "Type:",
        "editor.type_prompt": "AI Prompt",
        "editor.type_shell": "Shell Command",
        "editor.section_label": "Section",
        "editor.content_label": "Content",
        "editor.tags_label": "Tags (comma separated)",
        "editor.tags_placeholder": "e.g.: git, deploy, backup",
        "editor.btn_delete": "Delete",
        "editor.btn_cancel": "Cancel",
        "editor.btn_save_copy": "Save & Copy",
        "editor.btn_save": "Save",
        "editor.error_name_required": "Name is required",
        "editor.error_content_required": "Content is required",
        "editor.confirm_delete_title": "Delete this entry?",
        "editor.confirm_delete_detail": 'Entry "{name}" will be permanently deleted.',
        # --- Section manager ---
        "section.title_new": "New section",
        "section.name_label": "Section name",
        "section.name_placeholder": "Section name...",
        "section.error_name_required": "Name is required",
        "section.error_name_duplicate": 'Section "{name}" already exists',
        "section.title_rename": "Rename section",
        "section.new_name_label": "New name",
        "section.btn_rename": "Rename",
        "section.btn_create": "Create",
        "section.confirm_delete_title": 'Delete section "{name}"?',
        "section.confirm_delete_detail": "Entries will be moved to the 'General' section.",
        # --- Tray menu ---
        "tray.toggle": "Show/Hide",
        "tray.new_entry": "New entry",
        "tray.language": "Language",
        "tray.quit": "Quit",
        # --- Executor ---
        "executor.terminal_not_found": (
            "gnome-terminal not found. Install it with: sudo apt install gnome-terminal"
        ),
        "executor.press_enter": "\n--- Press ENTER to close ---",
        # --- Common ---
        "common.cancel": "Cancel",
        "common.delete": "Delete",
    },
}


def init(language: Language) -> None:
    """Inizializza la lingua corrente. Chiamata una volta all'avvio."""
    global _current_language
    if language in SUPPORTED_LANGUAGES:
        _current_language = language
    else:
        logger.warning("Lingua non supportata: %s, fallback a %s", language, DEFAULT_LANGUAGE)
        _current_language = DEFAULT_LANGUAGE
    logger.info("Lingua impostata: %s", _current_language)


def get_language() -> Language:
    """Restituisce la lingua corrente."""
    return _current_language


def t(key: str, **kwargs: str | int) -> str:
    """Traduce una chiave nella lingua corrente.

    Supporta interpolazione con keyword arguments:
        t("sidebar.all_entries", count=42)  → "Tutti (42)"

    Parameters
    ----------
    key : str
        Chiave di traduzione (es. "sidebar.new_entry").
    **kwargs : str | int
        Valori per interpolazione nella stringa.

    Returns
    -------
    str
        Stringa tradotta, o la chiave stessa se non trovata.
    """
    translations = _TRANSLATIONS.get(_current_language, _TRANSLATIONS[DEFAULT_LANGUAGE])
    text = translations.get(key)

    if text is None:
        # Fallback alla lingua di default
        text = _TRANSLATIONS[DEFAULT_LANGUAGE].get(key)
        if text is None:
            logger.warning("Chiave di traduzione mancante: %s", key)
            return key

    if kwargs:
        try:
            return text.format(**kwargs)
        except KeyError:
            logger.warning("Interpolazione fallita per chiave: %s, kwargs: %s", key, kwargs)
            return text

    return text
