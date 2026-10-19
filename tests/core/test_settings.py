"""Test per il modulo impostazioni."""

import json
import os
import stat
from pathlib import Path

import pytest

from command_quiver.core import settings as settings_module
from command_quiver.core.settings import (
    Settings,
    SyncSettings,
    delete_sync_token,
    load_settings,
    load_sync_token,
    save_settings,
    save_sync_token,
)


@pytest.fixture
def config_path(tmp_path: Path) -> Path:
    return tmp_path / "settings.json"


class TestSettings:
    """Test dataclass Settings."""

    def test_default_values(self) -> None:
        s = Settings()
        assert s.sort_order == "chronological_desc"
        assert s.last_section_id is None
        assert s.window_width == 640  # sta nella larghezza minima di sezioni + lista
        assert s.window_height == 600
        assert s.theme == "auto"

    def test_invalid_sort_order_falls_back_to_default(self) -> None:
        s = Settings(sort_order="invalid")
        assert s.sort_order == "chronological_desc"

    def test_valid_sort_orders_accepted(self) -> None:
        valid = ("alpha_asc", "alpha_desc", "chronological_asc", "chronological_desc", "personal")
        for order in valid:
            s = Settings(sort_order=order)
            assert s.sort_order == order

    def test_minimum_window_size_enforced(self) -> None:
        s = Settings(window_width=100, window_height=50)
        assert s.window_width == 640
        assert s.window_height == 600

    def test_invalid_language_falls_back_to_italian(self) -> None:
        s = Settings(language="fr")
        assert s.language == "it"

    def test_valid_languages_accepted(self) -> None:
        for lang in ("it", "en"):
            s = Settings(language=lang)
            assert s.language == lang

    def test_boundary_window_width_exactly_minimum(self) -> None:
        s = Settings(window_width=600)
        assert s.window_width == 600

    def test_old_narrow_saved_width_reopens_at_default(self) -> None:
        # Le versioni precedenti salvavano 520: con il pannello sezioni largo 224 px
        # la lista resterebbe troppo stretta e i nomi si troncherebbero
        assert Settings(window_width=520).window_width == 640
        assert Settings(window_width=599).window_width == 640

    def test_boundary_window_height_exactly_300(self) -> None:
        s = Settings(window_height=300)
        assert s.window_height == 300


class TestLoadSettings:
    """Test caricamento impostazioni da file."""

    def test_missing_file_returns_defaults(self, config_path: Path) -> None:
        s = load_settings(config_path=config_path)
        assert s.sort_order == "chronological_desc"

    def test_valid_file_loads_correctly(self, config_path: Path) -> None:
        config_path.write_text(
            json.dumps(
                {
                    "sort_order": "alpha_asc",
                    "last_section_id": 3,
                    "window_width": 600,
                }
            )
        )
        s = load_settings(config_path=config_path)
        assert s.sort_order == "alpha_asc"
        assert s.last_section_id == 3
        assert s.window_width == 600
        assert s.window_height == 600  # Default per campi non presenti

    def test_corrupted_file_returns_defaults(self, config_path: Path) -> None:
        config_path.write_text("not valid json {{{")
        s = load_settings(config_path=config_path)
        assert s.sort_order == "chronological_desc"

    def test_extra_fields_ignored(self, config_path: Path) -> None:
        config_path.write_text(
            json.dumps(
                {
                    "sort_order": "alpha_desc",
                    "unknown_field": "value",
                    "another": 123,
                }
            )
        )
        s = load_settings(config_path=config_path)
        assert s.sort_order == "alpha_desc"
        assert not hasattr(s, "unknown_field")


class TestSaveSettings:
    """Test salvataggio impostazioni su file."""

    def test_save_creates_file(self, config_path: Path) -> None:
        save_settings(Settings(), config_path=config_path)
        assert config_path.exists()

    def test_save_roundtrip(self, config_path: Path) -> None:
        original = Settings(sort_order="personal", last_section_id=5, window_width=700)
        save_settings(original, config_path=config_path)

        loaded = load_settings(config_path=config_path)
        assert loaded.sort_order == original.sort_order
        assert loaded.last_section_id == original.last_section_id
        assert loaded.window_width == original.window_width

    def test_save_sync_settings_roundtrip_preserves_typed_values(self, config_path: Path) -> None:
        original = Settings(sync=SyncSettings(enabled=True, repo_owner="a", repo_name="b"))
        save_settings(settings=original, config_path=config_path)

        loaded = load_settings(config_path=config_path)

        assert loaded.sync == SyncSettings(enabled=True, repo_owner="a", repo_name="b")

    def test_load_sync_settings_unknown_fields_preserves_enabled(self, config_path: Path) -> None:
        config_path.write_text(
            json.dumps({"sync": {"enabled": True, "campo_futuro": 1}}), encoding="utf-8"
        )

        loaded = load_settings(config_path=config_path)

        assert loaded.sync == SyncSettings(enabled=True)

    def test_save_creates_parent_dirs(self, tmp_path: Path) -> None:
        path = tmp_path / "subdir" / "deep" / "settings.json"
        save_settings(Settings(), config_path=path)
        assert path.exists()

    def test_save_writes_valid_json(self, config_path: Path) -> None:
        save_settings(Settings(), config_path=config_path)
        data = json.loads(config_path.read_text())
        assert isinstance(data, dict)
        assert "sort_order" in data


class TestUxSettings:
    """Ordinamento 'Più usati' persistente e voci eseguibili senza conferma."""

    def test_usage_sort_order_survives_validation(self) -> None:
        assert Settings(sort_order="usage").sort_order == "usage"

    def test_usage_sort_order_survives_reload(self, config_path: Path) -> None:
        save_settings(Settings(sort_order="usage"), config_path=config_path)
        assert load_settings(config_path=config_path).sort_order == "usage"

    def test_skip_run_confirm_defaults_empty(self) -> None:
        assert Settings().skip_run_confirm == []

    def test_skip_run_confirm_persisted(self, config_path: Path) -> None:
        save_settings(Settings(skip_run_confirm=["uuid-1"]), config_path=config_path)
        assert load_settings(config_path=config_path).skip_run_confirm == ["uuid-1"]

    def test_skip_run_confirm_invalid_type_reset(self) -> None:
        bad_value: object = "uuid-1"
        assert Settings(skip_run_confirm=bad_value).skip_run_confirm == []


@pytest.fixture
def token_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Reindirizza il file token su tmp_path: mai toccare ~/.config reale."""
    path = tmp_path / "cfg" / ".sync_token"
    monkeypatch.setattr(settings_module, "SYNC_TOKEN_PATH", path)
    return path


class TestSyncToken:
    """Il token GitHub vive in un file dedicato leggibile solo dal proprietario."""

    def test_save_sync_token_then_load_returns_same_token(self, token_path: Path) -> None:
        save_sync_token("ghp_abc123")

        assert load_sync_token() == "ghp_abc123"

    def test_save_sync_token_restricts_permissions_to_owner(self, token_path: Path) -> None:
        # umask permissivo: il 600 deve venire dal chmod, non dal caso
        old_umask = os.umask(0o000)
        try:
            save_sync_token("ghp_abc123")
        finally:
            os.umask(old_umask)

        assert stat.S_IMODE(os.stat(token_path).st_mode) == 0o600

    def test_save_sync_token_creates_missing_parent_directory(self, token_path: Path) -> None:
        assert not token_path.parent.exists()

        save_sync_token("ghp_abc123")

        assert token_path.is_file()

    def test_save_sync_token_overwrites_previous_token(self, token_path: Path) -> None:
        save_sync_token("vecchio")
        save_sync_token("nuovo")

        assert load_sync_token() == "nuovo"

    def test_load_sync_token_missing_file_returns_empty_string(self, token_path: Path) -> None:
        assert load_sync_token() == ""

    def test_load_sync_token_strips_surrounding_whitespace(self, token_path: Path) -> None:
        token_path.parent.mkdir(parents=True)
        token_path.write_text("  ghp_abc123 \n\n", encoding="utf-8")

        assert load_sync_token() == "ghp_abc123"

    def test_load_sync_token_unreadable_path_returns_empty_string(self, token_path: Path) -> None:
        # Una directory al posto del file fa fallire la lettura con OSError
        token_path.mkdir(parents=True)

        assert load_sync_token() == ""

    def test_delete_sync_token_removes_file_and_token_is_gone(self, token_path: Path) -> None:
        save_sync_token("ghp_abc123")
        assert token_path.exists()

        delete_sync_token()

        assert not token_path.exists()
        assert load_sync_token() == ""

    def test_delete_sync_token_without_file_is_noop(self, token_path: Path) -> None:
        delete_sync_token()

        assert not token_path.exists()
