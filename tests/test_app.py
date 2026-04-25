"""Test per CommandQuiverApp — logica applicazione, lifecycle e tray management."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from command_quiver import APP_ID


class TestCommandQuiverAppInit:
    """Test inizializzazione applicazione."""

    def test_app_has_correct_application_id(self) -> None:
        with patch("command_quiver.app.Gtk"), patch("command_quiver.app.Gdk"):
            from command_quiver.app import CommandQuiverApp

            app = CommandQuiverApp()
            assert app.get_application_id() == APP_ID

    def test_app_initial_state(self) -> None:
        with patch("command_quiver.app.Gtk"), patch("command_quiver.app.Gdk"):
            from command_quiver.app import CommandQuiverApp

            app = CommandQuiverApp()
            assert app._db is None
            assert app._settings is None
            assert app._sidebar is None
            assert app._tray_process is None
            assert app._tray_health_source == 0


class TestTrayHelperManagement:
    """Test gestione processo tray helper."""

    def test_stop_tray_helper_terminates_running_process(self) -> None:
        with patch("command_quiver.app.Gtk"), patch("command_quiver.app.Gdk"):
            from command_quiver.app import CommandQuiverApp

            app = CommandQuiverApp()
            mock_process = MagicMock(spec=subprocess.Popen)
            mock_process.poll.return_value = None  # Processo attivo
            app._tray_process = mock_process

            app._stop_tray_helper()

            mock_process.terminate.assert_called_once()
            mock_process.wait.assert_called_once_with(timeout=3)

    def test_stop_tray_helper_kills_after_timeout(self) -> None:
        with patch("command_quiver.app.Gtk"), patch("command_quiver.app.Gdk"):
            from command_quiver.app import CommandQuiverApp

            app = CommandQuiverApp()
            mock_process = MagicMock(spec=subprocess.Popen)
            mock_process.poll.return_value = None
            mock_process.wait.side_effect = subprocess.TimeoutExpired(cmd="tray", timeout=3)
            app._tray_process = mock_process

            app._stop_tray_helper()

            mock_process.kill.assert_called_once()

    def test_stop_tray_helper_noop_when_already_dead(self) -> None:
        with patch("command_quiver.app.Gtk"), patch("command_quiver.app.Gdk"):
            from command_quiver.app import CommandQuiverApp

            app = CommandQuiverApp()
            mock_process = MagicMock(spec=subprocess.Popen)
            mock_process.poll.return_value = 0  # Già terminato
            app._tray_process = mock_process

            app._stop_tray_helper()

            mock_process.terminate.assert_not_called()

    def test_stop_tray_helper_noop_when_no_process(self) -> None:
        with patch("command_quiver.app.Gtk"), patch("command_quiver.app.Gdk"):
            from command_quiver.app import CommandQuiverApp

            app = CommandQuiverApp()
            app._tray_process = None

            # Non deve sollevare eccezione
            app._stop_tray_helper()

    def test_stop_tray_helper_closes_stderr_file(self) -> None:
        with patch("command_quiver.app.Gtk"), patch("command_quiver.app.Gdk"):
            from command_quiver.app import CommandQuiverApp

            app = CommandQuiverApp()
            mock_process = MagicMock(spec=subprocess.Popen)
            mock_process.poll.return_value = None
            app._tray_process = mock_process
            mock_stderr = MagicMock()
            app._tray_stderr_file = mock_stderr

            app._stop_tray_helper()

            mock_stderr.close.assert_called_once()
            assert app._tray_stderr_file is None

    def test_launch_tray_process_returns_true_on_success(self) -> None:
        with (
            patch("command_quiver.app.Gtk"),
            patch("command_quiver.app.Gdk"),
            patch("command_quiver.app.subprocess.Popen") as mock_popen,
        ):
            from command_quiver.app import CommandQuiverApp

            mock_popen.return_value = MagicMock(pid=1234)
            app = CommandQuiverApp()
            app._tray_helper_path = Path("/fake/tray_helper.py")

            result = app._launch_tray_process()

            assert result is True
            assert app._tray_process is not None

    def test_launch_tray_process_returns_false_on_oserror(self) -> None:
        with (
            patch("command_quiver.app.Gtk"),
            patch("command_quiver.app.Gdk"),
            patch("command_quiver.app.subprocess.Popen", side_effect=OSError("fail")),
        ):
            from command_quiver.app import CommandQuiverApp

            app = CommandQuiverApp()
            app._tray_helper_path = Path("/fake/tray_helper.py")

            result = app._launch_tray_process()

            assert result is False

    def test_check_tray_health_restarts_crashed_process(self) -> None:
        with patch("command_quiver.app.Gtk"), patch("command_quiver.app.Gdk"):
            from command_quiver.app import CommandQuiverApp

            app = CommandQuiverApp()
            mock_process = MagicMock(spec=subprocess.Popen)
            mock_process.poll.return_value = 1  # Crashato
            mock_process.returncode = 1
            app._tray_process = mock_process
            app._tray_helper_path = Path("/fake/tray_helper.py")

            with patch.object(app, "_launch_tray_process") as mock_launch:
                result = app._check_tray_health()

            assert result is True  # Continua polling
            mock_launch.assert_called_once()

    def test_check_tray_health_noop_when_running(self) -> None:
        with patch("command_quiver.app.Gtk"), patch("command_quiver.app.Gdk"):
            from command_quiver.app import CommandQuiverApp

            app = CommandQuiverApp()
            mock_process = MagicMock(spec=subprocess.Popen)
            mock_process.poll.return_value = None  # Attivo
            app._tray_process = mock_process

            with patch.object(app, "_launch_tray_process") as mock_launch:
                result = app._check_tray_health()

            assert result is True
            mock_launch.assert_not_called()

    def test_check_tray_health_stops_polling_when_no_process(self) -> None:
        with patch("command_quiver.app.Gtk"), patch("command_quiver.app.Gdk"):
            from command_quiver.app import CommandQuiverApp

            app = CommandQuiverApp()
            app._tray_process = None

            result = app._check_tray_health()

            assert result is False  # Rimuovi timeout


class TestQuitApp:
    """Test chiusura ordinata."""

    def test_quit_saves_settings_and_closes_db(self) -> None:
        with (
            patch("command_quiver.app.Gtk"),
            patch("command_quiver.app.Gdk"),
            patch("command_quiver.app.save_settings") as mock_save,
        ):
            from command_quiver.app import CommandQuiverApp

            app = CommandQuiverApp()
            mock_db = MagicMock()
            mock_settings = MagicMock()
            app._db = mock_db
            app._settings = mock_settings
            app._tray_process = None

            # Mock metodi GTK che richiedono un'app registrata
            with (
                patch.object(app, "release"),
                patch.object(app, "quit"),
            ):
                app._quit_app()

            mock_save.assert_called_once_with(mock_settings)
            mock_db.close.assert_called_once()

    def test_quit_skips_save_when_no_settings(self) -> None:
        with (
            patch("command_quiver.app.Gtk"),
            patch("command_quiver.app.Gdk"),
            patch("command_quiver.app.save_settings") as mock_save,
        ):
            from command_quiver.app import CommandQuiverApp

            app = CommandQuiverApp()
            app._settings = None
            app._db = None
            app._tray_process = None

            with (
                patch.object(app, "release"),
                patch.object(app, "quit"),
            ):
                app._quit_app()

            mock_save.assert_not_called()

    def test_quit_removes_health_source(self) -> None:
        with (
            patch("command_quiver.app.Gtk"),
            patch("command_quiver.app.Gdk"),
            patch("command_quiver.app.save_settings"),
            patch("command_quiver.app.GLib") as mock_glib,
        ):
            from command_quiver.app import CommandQuiverApp

            app = CommandQuiverApp()
            app._tray_health_source = 42
            app._settings = MagicMock()
            app._db = MagicMock()
            app._tray_process = None

            with (
                patch.object(app, "release"),
                patch.object(app, "quit"),
            ):
                app._quit_app()

            mock_glib.source_remove.assert_called_once_with(42)
            assert app._tray_health_source == 0


class TestToggleSidebar:
    """Test toggle sidebar."""

    def test_toggle_creates_sidebar_when_none(self) -> None:
        with patch("command_quiver.app.Gtk"), patch("command_quiver.app.Gdk"):
            from command_quiver.app import CommandQuiverApp

            app = CommandQuiverApp()
            app._sidebar = None

            with patch.object(app, "do_activate") as mock_activate:
                app._toggle_sidebar()
                mock_activate.assert_called_once()

    def test_toggle_hides_visible_sidebar(self) -> None:
        with patch("command_quiver.app.Gtk"), patch("command_quiver.app.Gdk"):
            from command_quiver.app import CommandQuiverApp

            app = CommandQuiverApp()
            mock_sidebar = MagicMock()
            mock_sidebar.get_visible.return_value = True
            app._sidebar = mock_sidebar

            app._toggle_sidebar()

            mock_sidebar.set_visible.assert_called_once_with(False)

    def test_toggle_shows_hidden_sidebar(self) -> None:
        with patch("command_quiver.app.Gtk"), patch("command_quiver.app.Gdk"):
            from command_quiver.app import CommandQuiverApp

            app = CommandQuiverApp()
            mock_sidebar = MagicMock()
            mock_sidebar.get_visible.return_value = False
            app._sidebar = mock_sidebar

            app._toggle_sidebar()

            mock_sidebar.present.assert_called_once()


class TestOpenNewEntry:
    """Test apertura dialog nuova voce."""

    def test_open_new_entry_creates_sidebar_when_none(self) -> None:
        with (
            patch("command_quiver.app.Gtk"),
            patch("command_quiver.app.Gdk"),
            patch("command_quiver.app.GLib") as mock_glib,
        ):
            from command_quiver.app import CommandQuiverApp

            app = CommandQuiverApp()
            app._sidebar = None

            with patch.object(app, "do_activate") as mock_activate:
                # do_activate imposta _sidebar
                mock_sidebar = MagicMock()
                mock_activate.side_effect = lambda: setattr(app, "_sidebar", mock_sidebar)
                app._open_new_entry()
                mock_activate.assert_called_once()
                mock_glib.idle_add.assert_called_once()

    def test_open_new_entry_shows_hidden_sidebar(self) -> None:
        with (
            patch("command_quiver.app.Gtk"),
            patch("command_quiver.app.Gdk"),
            patch("command_quiver.app.GLib"),
        ):
            from command_quiver.app import CommandQuiverApp

            app = CommandQuiverApp()
            mock_sidebar = MagicMock()
            mock_sidebar.get_visible.return_value = False
            app._sidebar = mock_sidebar

            app._open_new_entry()

            mock_sidebar.present.assert_called_once()


class TestChangeLanguage:
    """Test cambio lingua."""

    def test_change_language_noop_when_same(self) -> None:
        with (
            patch("command_quiver.app.Gtk"),
            patch("command_quiver.app.Gdk"),
            patch("command_quiver.app.save_settings") as mock_save,
        ):
            from command_quiver.app import CommandQuiverApp

            app = CommandQuiverApp()
            app._settings = MagicMock()

            # Imposta lingua corrente a "it" e chiede di cambiare a "it"
            import command_quiver.core.i18n as i18n_mod

            original = i18n_mod._current_language
            i18n_mod._current_language = "it"
            try:
                app._change_language("it")
            finally:
                i18n_mod._current_language = original

            mock_save.assert_not_called()

    def test_change_language_updates_settings(self) -> None:
        with (
            patch("command_quiver.app.Gtk"),
            patch("command_quiver.app.Gdk"),
            patch("command_quiver.app.save_settings") as mock_save,
        ):
            from command_quiver.app import CommandQuiverApp

            app = CommandQuiverApp()
            mock_settings = MagicMock()
            app._settings = mock_settings
            app._sidebar = None

            with (
                patch("command_quiver.core.i18n.get_language", return_value="it"),
                patch("command_quiver.core.i18n.init"),
            ):
                app._change_language("en")

            assert mock_settings.language == "en"
            mock_save.assert_called_once_with(mock_settings)

    def test_change_language_rebuilds_sidebar(self) -> None:
        with (
            patch("command_quiver.app.Gtk"),
            patch("command_quiver.app.Gdk"),
            patch("command_quiver.app.save_settings"),
            patch("command_quiver.app.SidebarPanel") as mock_sidebar_cls,
        ):
            from command_quiver.app import CommandQuiverApp

            app = CommandQuiverApp()
            mock_settings = MagicMock()
            app._settings = mock_settings
            app._db = MagicMock()

            old_sidebar = MagicMock()
            old_sidebar.get_visible.return_value = True
            app._sidebar = old_sidebar

            with (
                patch("command_quiver.core.i18n.get_language", return_value="it"),
                patch("command_quiver.core.i18n.init"),
                patch.object(app, "remove_window"),
                patch.object(app, "add_window"),
            ):
                app._change_language("en")

            old_sidebar.destroy.assert_called_once()
            mock_sidebar_cls.assert_called_once()


class TestDbusMethodCall:
    """Test handler metodi D-Bus."""

    def test_dbus_toggle(self) -> None:
        with patch("command_quiver.app.Gtk"), patch("command_quiver.app.Gdk"):
            from command_quiver.app import CommandQuiverApp

            app = CommandQuiverApp()
            mock_invocation = MagicMock()

            with patch.object(app, "_toggle_sidebar") as mock_toggle:
                app._on_dbus_method_call(None, "", "", "", "Toggle", None, mock_invocation)
                mock_toggle.assert_called_once()
            mock_invocation.return_value.assert_called_once_with(None)

    def test_dbus_new_entry(self) -> None:
        with patch("command_quiver.app.Gtk"), patch("command_quiver.app.Gdk"):
            from command_quiver.app import CommandQuiverApp

            app = CommandQuiverApp()
            mock_invocation = MagicMock()

            with patch.object(app, "_open_new_entry") as mock_new:
                app._on_dbus_method_call(None, "", "", "", "NewEntry", None, mock_invocation)
                mock_new.assert_called_once()

    def test_dbus_change_language(self) -> None:
        with patch("command_quiver.app.Gtk"), patch("command_quiver.app.Gdk"):
            from command_quiver.app import CommandQuiverApp

            app = CommandQuiverApp()
            mock_invocation = MagicMock()
            mock_params = MagicMock()
            mock_params.unpack.return_value = ("en",)

            with patch.object(app, "_change_language") as mock_lang:
                app._on_dbus_method_call(
                    None, "", "", "", "ChangeLanguage", mock_params, mock_invocation
                )
                mock_lang.assert_called_once_with("en")

    def test_dbus_change_language_fallback_without_params(self) -> None:
        with patch("command_quiver.app.Gtk"), patch("command_quiver.app.Gdk"):
            from command_quiver.app import CommandQuiverApp

            app = CommandQuiverApp()
            mock_invocation = MagicMock()

            with patch.object(app, "_change_language") as mock_lang:
                # params è None -> fallback a "it"
                app._on_dbus_method_call(None, "", "", "", "ChangeLanguage", None, mock_invocation)
                mock_lang.assert_called_once_with("it")

    def test_dbus_unknown_method_no_error(self) -> None:
        with patch("command_quiver.app.Gtk"), patch("command_quiver.app.Gdk"):
            from command_quiver.app import CommandQuiverApp

            app = CommandQuiverApp()
            mock_invocation = MagicMock()

            # Metodo sconosciuto -> non deve crashare
            app._on_dbus_method_call(None, "", "", "", "Unknown", None, mock_invocation)
            mock_invocation.return_value.assert_called_once_with(None)

    def test_dbus_quit(self) -> None:
        with patch("command_quiver.app.Gtk"), patch("command_quiver.app.Gdk"):
            from command_quiver.app import CommandQuiverApp

            app = CommandQuiverApp()
            mock_invocation = MagicMock()

            with patch.object(app, "_quit_app") as mock_quit:
                app._on_dbus_method_call(None, "", "", "", "Quit", None, mock_invocation)
                mock_quit.assert_called_once()


class TestShowErrorDialog:
    """Test dialog errore fatale."""

    def test_show_error_dialog_creates_alert(self) -> None:
        with (
            patch("command_quiver.app.Gtk") as mock_gtk,
            patch("command_quiver.app.Gdk"),
        ):
            from command_quiver.app import CommandQuiverApp

            app = CommandQuiverApp()
            app._show_error_dialog("test error message")

            mock_gtk.AlertDialog.assert_called_once()


class TestInitServices:
    """Test inizializzazione servizi."""

    def test_init_services_initializes_db_and_settings(self) -> None:
        with (
            patch("command_quiver.app.Gtk"),
            patch("command_quiver.app.Gdk"),
            patch("command_quiver.app.Database") as mock_db_cls,
            patch("command_quiver.app.load_settings") as mock_load,
        ):
            from command_quiver.app import CommandQuiverApp

            mock_db = MagicMock()
            mock_db_cls.return_value = mock_db
            mock_settings = MagicMock()
            mock_settings.language = "it"
            mock_load.return_value = mock_settings

            app = CommandQuiverApp()

            with (
                patch.object(app, "_register_dbus_interface"),
                patch.object(app, "_start_tray_helper"),
                patch("command_quiver.core.i18n.init"),
            ):
                app._init_services()

            mock_db.initialize.assert_called_once()
            mock_load.assert_called_once()
            assert app._db is mock_db
            assert app._settings is mock_settings


class TestStartTrayHelper:
    """Test avvio tray helper."""

    def test_launch_tray_process_uses_correct_executable(self) -> None:
        with (
            patch("command_quiver.app.Gtk"),
            patch("command_quiver.app.Gdk"),
            patch("command_quiver.app.subprocess.Popen") as mock_popen,
        ):
            from command_quiver.app import CommandQuiverApp

            mock_popen.return_value = MagicMock(pid=9999)
            app = CommandQuiverApp()
            app._tray_helper_path = Path("/fake/tray_helper.py")

            result = app._launch_tray_process()

            assert result is True
            args = mock_popen.call_args[0][0]
            assert args[1] == "/fake/tray_helper.py"
