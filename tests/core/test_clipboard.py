"""Test per il modulo clipboard: copia negli appunti via GDK4."""

from unittest.mock import MagicMock, patch

from command_quiver.core.clipboard import copy_to_clipboard


class TestCopyToClipboard:
    """Test copia contenuto negli appunti."""

    def test_returns_false_when_no_display(self) -> None:
        with patch(
            "command_quiver.core.clipboard.Gdk.Display.get_default",
            return_value=None,
        ):
            result = copy_to_clipboard("test content")
            assert result is False

    def test_returns_true_and_sets_content_on_success(self) -> None:
        mock_clipboard = MagicMock()
        mock_display = MagicMock()
        mock_display.get_clipboard.return_value = mock_clipboard

        with patch(
            "command_quiver.core.clipboard.Gdk.Display.get_default",
            return_value=mock_display,
        ):
            result = copy_to_clipboard("echo hello")
            assert result is True
            mock_clipboard.set.assert_called_once_with("echo hello")

    def test_copies_multiline_content(self) -> None:
        mock_clipboard = MagicMock()
        mock_display = MagicMock()
        mock_display.get_clipboard.return_value = mock_clipboard

        multiline = "line1\nline2\nline3"
        with patch(
            "command_quiver.core.clipboard.Gdk.Display.get_default",
            return_value=mock_display,
        ):
            result = copy_to_clipboard(multiline)
            assert result is True
            mock_clipboard.set.assert_called_once_with(multiline)

    def test_copies_empty_string(self) -> None:
        mock_clipboard = MagicMock()
        mock_display = MagicMock()
        mock_display.get_clipboard.return_value = mock_clipboard

        with patch(
            "command_quiver.core.clipboard.Gdk.Display.get_default",
            return_value=mock_display,
        ):
            result = copy_to_clipboard("")
            assert result is True
            mock_clipboard.set.assert_called_once_with("")
