"""Test per il modulo impostazioni."""

import json
from pathlib import Path

import pytest

from command_quiver.core.settings import Settings, load_settings, save_settings


@pytest.fixture
def config_path(tmp_path: Path) -> Path:
    return tmp_path / "settings.json"


class TestSettings:
    """Test dataclass Settings."""

    def test_default_values(self) -> None:
        s = Settings()
        assert s.sort_order == "chronological_desc"
        assert s.last_section_id is None
        assert s.window_width == 520
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
        assert s.window_width == 520
        assert s.window_height == 600


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

    def test_save_creates_parent_dirs(self, tmp_path: Path) -> None:
        path = tmp_path / "subdir" / "deep" / "settings.json"
        save_settings(Settings(), config_path=path)
        assert path.exists()

    def test_save_writes_valid_json(self, config_path: Path) -> None:
        save_settings(Settings(), config_path=config_path)
        data = json.loads(config_path.read_text())
        assert isinstance(data, dict)
        assert "sort_order" in data
