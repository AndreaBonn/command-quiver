"""Test per StatusNotifierItem e CommandQuiverApp."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from tests.conftest import requires_display


class TestStatusNotifierItem:
    """Test tray icon SNI (logica pura, senza D-Bus reale)."""

    def _create_sni(self, icon_path=None):
        from command_quiver.app import StatusNotifierItem

        return StatusNotifierItem(
            app_id="test.app",
            icon_path=icon_path or Path("/tmp/test/icon.png"),
            on_activate=MagicMock(),
            on_new_entry=MagicMock(),
            on_quit=MagicMock(),
        )

    def test_init_stores_callbacks(self) -> None:
        on_activate = MagicMock()
        on_new_entry = MagicMock()
        on_quit = MagicMock()

        from command_quiver.app import StatusNotifierItem

        sni = StatusNotifierItem(
            app_id="test",
            icon_path=Path("/tmp/icon.png"),
            on_activate=on_activate,
            on_new_entry=on_new_entry,
            on_quit=on_quit,
        )
        assert sni._on_activate is on_activate
        assert sni._on_new_entry is on_new_entry
        assert sni._on_quit is on_quit

    def test_icon_path_parsed(self) -> None:
        sni = self._create_sni(icon_path=Path("/home/user/assets/icon.png"))
        assert sni._icon_dir == "/home/user/assets"
        assert sni._icon_name == "icon"

    def test_sni_get_property_returns_known_props(self) -> None:
        sni = self._create_sni()

        result = sni._on_sni_get_property(None, "", "", "", "Category")
        assert result.get_string() == "ApplicationStatus"

        result = sni._on_sni_get_property(None, "", "", "", "Status")
        assert result.get_string() == "Active"

        result = sni._on_sni_get_property(None, "", "", "", "Id")
        assert result.get_string() == "test.app"

    def test_sni_get_property_returns_none_for_unknown(self) -> None:
        sni = self._create_sni()
        result = sni._on_sni_get_property(None, "", "", "", "UnknownProp")
        assert result is None

    def test_handle_menu_click_toggle(self) -> None:
        from command_quiver.app import _MENU_ID_TOGGLE

        sni = self._create_sni()
        with patch("command_quiver.app.GLib.idle_add") as mock_idle:
            sni._handle_menu_click(_MENU_ID_TOGGLE)
            mock_idle.assert_called_once_with(sni._on_activate)

    def test_handle_menu_click_new_entry(self) -> None:
        from command_quiver.app import _MENU_ID_NEW_ENTRY

        sni = self._create_sni()
        with patch("command_quiver.app.GLib.idle_add") as mock_idle:
            sni._handle_menu_click(_MENU_ID_NEW_ENTRY)
            mock_idle.assert_called_once_with(sni._on_new_entry)

    def test_handle_menu_click_quit(self) -> None:
        from command_quiver.app import _MENU_ID_QUIT

        sni = self._create_sni()
        with patch("command_quiver.app.GLib.idle_add") as mock_idle:
            sni._handle_menu_click(_MENU_ID_QUIT)
            mock_idle.assert_called_once_with(sni._on_quit)

    def test_build_menu_layout_has_4_items(self) -> None:
        sni = self._create_sni()
        layout = sni._build_menu_layout()
        # layout = (id, props, children)
        assert layout[0] == 0  # Root ID
        assert len(layout[2]) == 4  # Toggle, New, Separator, Quit

    def test_menu_get_property_returns_known(self) -> None:
        sni = self._create_sni()
        result = sni._on_menu_get_property(None, "", "", "", "Version")
        assert result.get_uint32() == 3

    def test_menu_get_property_returns_none_for_unknown(self) -> None:
        sni = self._create_sni()
        result = sni._on_menu_get_property(None, "", "", "", "Fake")
        assert result is None

    def test_unregister_without_bus_no_error(self) -> None:
        sni = self._create_sni()
        sni.unregister()  # Nessun errore

    def test_sni_method_call_activate(self) -> None:
        sni = self._create_sni()
        mock_invocation = MagicMock()

        with patch("command_quiver.app.GLib.idle_add") as mock_idle:
            sni._on_sni_method_call(None, "", "", "", "Activate", None, mock_invocation)
            mock_idle.assert_called_once_with(sni._on_activate)
            mock_invocation.return_value.assert_called_once_with(None)

    def test_sni_method_call_secondary_activate(self) -> None:
        sni = self._create_sni()
        mock_invocation = MagicMock()

        with patch("command_quiver.app.GLib.idle_add") as mock_idle:
            sni._on_sni_method_call(None, "", "", "", "SecondaryActivate", None, mock_invocation)
            mock_idle.assert_called_once_with(sni._on_activate)

    def test_sni_method_call_context_menu(self) -> None:
        sni = self._create_sni()
        mock_invocation = MagicMock()

        sni._on_sni_method_call(None, "", "", "", "ContextMenu", None, mock_invocation)
        mock_invocation.return_value.assert_called_once_with(None)


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
