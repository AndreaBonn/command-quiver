"""Sistema di internazionalizzazione (i18n) per Command Quiver.

Supporta italiano e inglese tramite dizionari statici.
La lingua viene letta dalle impostazioni utente (settings.json).

Uso:
    from command_quiver.core.i18n import t

    label = Gtk.Label(label=t("sidebar.search_placeholder"))
"""

import logging
from typing import Literal

from command_quiver.core.locales import en as en_locale
from command_quiver.core.locales import it as it_locale

logger = logging.getLogger(__name__)

Language = Literal["it", "en"]

SUPPORTED_LANGUAGES: tuple[Language, ...] = ("it", "en")
DEFAULT_LANGUAGE: Language = "it"

LANGUAGE_LABELS: dict[Language, str] = {
    "it": "Italiano",
    "en": "English",
}

_current_language: Language = DEFAULT_LANGUAGE

# Dizionari per lingua in core/locales/, organizzati per namespace semantico
_TRANSLATIONS: dict[Language, dict[str, str]] = {"it": it_locale.STRINGS, "en": en_locale.STRINGS}


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
