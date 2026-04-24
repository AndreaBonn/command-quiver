"""Test per CommandQuiverApp."""

from pathlib import Path

from tests.conftest import requires_display


@requires_display
class TestCommandQuiverAppIconGeneration:
    """Test generazione icona."""

    def test_generate_icon_creates_png(self, gtk_init, tmp_path: Path) -> None:
        from command_quiver.app import CommandQuiverApp

        icon_path = tmp_path / "assets" / "icon.png"
        CommandQuiverApp._generate_icon(icon_path)

        assert icon_path.exists()
        # Verifica che sia un PNG valido (magic bytes)
        data = icon_path.read_bytes()
        assert data[:4] == b"\x89PNG"

    def test_generate_icon_creates_parent_dirs(
        self,
        gtk_init,
        tmp_path: Path,
    ) -> None:
        from command_quiver.app import CommandQuiverApp

        icon_path = tmp_path / "deep" / "nested" / "icon.png"
        CommandQuiverApp._generate_icon(icon_path)
        assert icon_path.exists()

    def test_generate_icon_respects_size(self, gtk_init, tmp_path: Path) -> None:
        from command_quiver.app import CommandQuiverApp

        for size in [32, 48, 64, 128]:
            icon_path = tmp_path / f"icon_{size}.png"
            CommandQuiverApp._generate_icon(path=icon_path, size=size)
            assert icon_path.exists()
