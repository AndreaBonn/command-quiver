"""Test per il modulo di internazionalizzazione (i18n)."""

import pytest

from command_quiver.core.i18n import (
    _TRANSLATIONS,
    DEFAULT_LANGUAGE,
    SUPPORTED_LANGUAGES,
    get_language,
    init,
    t,
)


class TestInit:
    """Test inizializzazione lingua."""

    def test_init_italian(self) -> None:
        init("it")
        assert get_language() == "it"

    def test_init_english(self) -> None:
        init("en")
        assert get_language() == "en"

    def test_init_unsupported_falls_back_to_default(self) -> None:
        init("fr")
        assert get_language() == DEFAULT_LANGUAGE

    def teardown_method(self) -> None:
        init(DEFAULT_LANGUAGE)


class TestTranslation:
    """Test funzione di traduzione t()."""

    def test_translate_italian_key(self) -> None:
        init("it")
        assert t("sidebar.new_entry") == "+ Nuova voce"

    def test_translate_english_key(self) -> None:
        init("en")
        assert t("sidebar.new_entry") == "+ New entry"

    def test_interpolation_single_param(self) -> None:
        init("it")
        result = t("sidebar.all_entries", count=42)
        assert result == "Tutti (42)"

    def test_interpolation_multiple_params(self) -> None:
        init("en")
        result = t("sidebar.section_row", name="Git", count=5)
        assert result == "Git (5)"

    def test_missing_key_returns_key(self) -> None:
        init("it")
        assert t("nonexistent.key") == "nonexistent.key"

    def test_missing_interpolation_param_returns_template(self) -> None:
        init("it")
        result = t("sidebar.all_entries")
        assert "{count}" in result

    def test_wrong_interpolation_kwargs_returns_template(self) -> None:
        """t() con kwargs errati (KeyError) restituisce il template non interpolato."""
        init("it")
        result = t("sidebar.all_entries", wrong_param=42)
        assert "{count}" in result
        assert "42" not in result

    def test_fallback_to_default_language_for_missing_key(self) -> None:
        """Se la chiave manca nella lingua corrente, usa il default."""
        from unittest.mock import patch

        init("en")
        # Rimuovi temporaneamente una chiave dalla traduzione inglese
        with patch.dict(_TRANSLATIONS["en"], clear=False) as patched:
            del patched["sidebar.new_entry"]
            result = t("sidebar.new_entry")
            # Deve restituire la traduzione italiana (default)
            assert result == "+ Nuova voce"

    def teardown_method(self) -> None:
        init(DEFAULT_LANGUAGE)


class TestTranslationCompleteness:
    """Verifica che tutte le chiavi siano presenti in entrambe le lingue."""

    def test_all_languages_have_same_keys(self) -> None:
        it_keys = set(_TRANSLATIONS["it"].keys())
        en_keys = set(_TRANSLATIONS["en"].keys())

        missing_in_en = it_keys - en_keys
        missing_in_it = en_keys - it_keys

        assert not missing_in_en, f"Chiavi mancanti in 'en': {missing_in_en}"
        assert not missing_in_it, f"Chiavi mancanti in 'it': {missing_in_it}"

    def test_no_empty_translations(self) -> None:
        for lang in SUPPORTED_LANGUAGES:
            for key, value in _TRANSLATIONS[lang].items():
                assert value.strip(), f"Traduzione vuota: lang={lang}, key={key}"

    @pytest.mark.parametrize("lang", list(SUPPORTED_LANGUAGES))
    def test_interpolation_placeholders_match(self, lang: str) -> None:
        """Verifica che i placeholder {xxx} siano coerenti tra le lingue."""
        import re

        base_lang = "it"
        base = _TRANSLATIONS[base_lang]
        target = _TRANSLATIONS[lang]

        for key in base:
            base_placeholders = set(re.findall(r"\{(\w+)\}", base[key]))
            target_placeholders = set(re.findall(r"\{(\w+)\}", target[key]))
            assert base_placeholders == target_placeholders, (
                f"Placeholder mismatch per '{key}': "
                f"{base_lang}={base_placeholders}, {lang}={target_placeholders}"
            )
