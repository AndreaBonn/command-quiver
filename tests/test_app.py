"""Test per CommandQuiverApp — logica applicazione e lifecycle."""

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
            assert app._sync_engine is None
            assert app._sync_debounce_id == 0


class TestShutdown:
    """Test chiusura ordinata (do_shutdown)."""

    def test_shutdown_saves_settings_and_closes_db(self) -> None:
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

            app.do_shutdown()

            mock_save.assert_called_once_with(mock_settings)
            mock_db.close.assert_called_once()

    def test_shutdown_skips_save_when_no_settings(self) -> None:
        with (
            patch("command_quiver.app.Gtk"),
            patch("command_quiver.app.Gdk"),
            patch("command_quiver.app.save_settings") as mock_save,
        ):
            from command_quiver.app import CommandQuiverApp

            app = CommandQuiverApp()
            app._settings = None
            app._db = None

            app.do_shutdown()

            mock_save.assert_not_called()

    def test_shutdown_removes_pending_debounce(self) -> None:
        with (
            patch("command_quiver.app.Gtk"),
            patch("command_quiver.app.Gdk"),
            patch("command_quiver.app.save_settings"),
            patch("command_quiver.app.GLib") as mock_glib,
        ):
            from command_quiver.app import CommandQuiverApp

            app = CommandQuiverApp()
            app._sync_debounce_id = 77
            app._settings = MagicMock()
            app._db = MagicMock()

            app.do_shutdown()

            mock_glib.source_remove.assert_called_once_with(77)
            assert app._sync_debounce_id == 0


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
                patch.object(app, "remove_window") as mock_remove,
                patch.object(app, "add_window") as mock_add,
            ):
                app._change_language("en")

            # La nuova finestra è aggiunta prima di rimuovere la vecchia
            mock_add.assert_called_once()
            mock_remove.assert_called_once_with(old_sidebar)
            old_sidebar.destroy.assert_called_once()
            mock_sidebar_cls.assert_called_once()
            assert app._sidebar is mock_sidebar_cls.return_value


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
            mock_settings.sync.enabled = False
            mock_load.return_value = mock_settings

            app = CommandQuiverApp()

            with patch("command_quiver.core.i18n.init"):
                app._init_services()

            mock_db.initialize.assert_called_once()
            mock_load.assert_called_once()
            assert app._db is mock_db
            assert app._settings is mock_settings


class TestSyncLifecycle:
    """Test dei metodi di sync e del ciclo di vita non coperti altrove."""

    def test_init_sync_disabled_does_not_create_engine(self) -> None:
        with patch("command_quiver.app.Gtk"), patch("command_quiver.app.Gdk"):
            from command_quiver.app import CommandQuiverApp

            app = CommandQuiverApp()
            app._settings = MagicMock()
            app._settings.sync.enabled = False

            app._init_sync()

            assert app._sync_engine is None

    def test_init_sync_enabled_creates_engine_and_syncs(self) -> None:
        with (
            patch("command_quiver.app.Gtk"),
            patch("command_quiver.app.Gdk"),
            patch("command_quiver.core.sync_engine.SyncEngine") as mock_engine,
        ):
            from command_quiver.app import CommandQuiverApp

            app = CommandQuiverApp()
            app._settings = MagicMock()
            app._settings.sync.enabled = True
            app._db = MagicMock()

            with patch.object(app, "_run_sync_background") as mock_run:
                app._init_sync()

            mock_engine.assert_called_once()
            assert app._sync_engine is mock_engine.return_value
            mock_run.assert_called_once()

    def test_run_sync_background_no_engine_is_noop(self) -> None:
        with (
            patch("command_quiver.app.Gtk"),
            patch("command_quiver.app.Gdk"),
            patch("command_quiver.app.threading") as mock_threading,
        ):
            from command_quiver.app import CommandQuiverApp

            app = CommandQuiverApp()
            app._sync_engine = None

            app._run_sync_background()

            mock_threading.Thread.assert_not_called()

    def test_run_sync_background_starts_daemon_thread(self) -> None:
        with (
            patch("command_quiver.app.Gtk"),
            patch("command_quiver.app.Gdk"),
            patch("command_quiver.app.threading") as mock_threading,
        ):
            from command_quiver.app import CommandQuiverApp

            app = CommandQuiverApp()
            app._sync_engine = MagicMock()

            app._run_sync_background()

            mock_threading.Thread.assert_called_once()
            mock_threading.Thread.return_value.start.assert_called_once()

    def test_on_sync_complete_refreshes_sidebar_when_entries_pulled(self) -> None:
        with patch("command_quiver.app.Gtk"), patch("command_quiver.app.Gdk"):
            from command_quiver.app import CommandQuiverApp

            app = CommandQuiverApp()
            sidebar = MagicMock()
            app._sidebar = sidebar
            result = MagicMock(success=True, entries_pulled=2, sections_pulled=0)

            ret = app._on_sync_complete(result)

            sidebar.refresh_all.assert_called_once()
            sidebar.update_sync_status.assert_called_once_with(result)
            assert ret is False

    def test_on_sync_complete_no_refresh_when_nothing_pulled(self) -> None:
        with patch("command_quiver.app.Gtk"), patch("command_quiver.app.Gdk"):
            from command_quiver.app import CommandQuiverApp

            app = CommandQuiverApp()
            sidebar = MagicMock()
            app._sidebar = sidebar
            result = MagicMock(success=True, entries_pulled=0, sections_pulled=0)

            app._on_sync_complete(result)

            sidebar.refresh_all.assert_not_called()
            sidebar.update_sync_status.assert_called_once_with(result)

    def test_on_sync_complete_failure_updates_status_only(self) -> None:
        with patch("command_quiver.app.Gtk"), patch("command_quiver.app.Gdk"):
            from command_quiver.app import CommandQuiverApp

            app = CommandQuiverApp()
            sidebar = MagicMock()
            app._sidebar = sidebar
            result = MagicMock(success=False, entries_pulled=0, sections_pulled=0)

            app._on_sync_complete(result)

            sidebar.refresh_all.assert_not_called()
            sidebar.update_sync_status.assert_called_once_with(result)

    def test_on_sync_toggled_enabled_creates_engine(self) -> None:
        with (
            patch("command_quiver.app.Gtk"),
            patch("command_quiver.app.Gdk"),
            patch("command_quiver.core.sync_engine.SyncEngine") as mock_engine,
        ):
            from command_quiver.app import CommandQuiverApp

            app = CommandQuiverApp()
            app._settings = MagicMock()
            app._settings.sync.enabled = True
            app._db = MagicMock()

            with patch.object(app, "_run_sync_background") as mock_run:
                app._on_sync_toggled()

            assert app._sync_engine is mock_engine.return_value
            mock_run.assert_called_once()

    def test_on_sync_toggled_disabled_clears_engine(self) -> None:
        with patch("command_quiver.app.Gtk"), patch("command_quiver.app.Gdk"):
            from command_quiver.app import CommandQuiverApp

            app = CommandQuiverApp()
            app._settings = MagicMock()
            app._settings.sync.enabled = False
            app._sync_engine = MagicMock()

            app._on_sync_toggled()

            assert app._sync_engine is None

    def test_on_data_changed_without_engine_is_noop(self) -> None:
        with (
            patch("command_quiver.app.Gtk"),
            patch("command_quiver.app.Gdk"),
            patch("command_quiver.app.GLib") as mock_glib,
        ):
            from command_quiver.app import CommandQuiverApp

            app = CommandQuiverApp()
            app._sync_engine = None

            app.on_data_changed()

            mock_glib.timeout_add_seconds.assert_not_called()

    def test_on_data_changed_schedules_debounce(self) -> None:
        with (
            patch("command_quiver.app.Gtk"),
            patch("command_quiver.app.Gdk"),
            patch("command_quiver.app.GLib") as mock_glib,
        ):
            from command_quiver.app import CommandQuiverApp

            app = CommandQuiverApp()
            app._sync_engine = MagicMock()
            app._sync_debounce_id = 0
            mock_glib.timeout_add_seconds.return_value = 99

            app.on_data_changed()

            mock_glib.timeout_add_seconds.assert_called_once()
            assert app._sync_debounce_id == 99

    def test_on_data_changed_resets_pending_timer(self) -> None:
        with (
            patch("command_quiver.app.Gtk"),
            patch("command_quiver.app.Gdk"),
            patch("command_quiver.app.GLib") as mock_glib,
        ):
            from command_quiver.app import CommandQuiverApp

            app = CommandQuiverApp()
            app._sync_engine = MagicMock()
            app._sync_debounce_id = 42

            app.on_data_changed()

            mock_glib.source_remove.assert_called_once_with(42)

    def test_sync_debounce_fire_runs_sync_and_clears_id(self) -> None:
        with patch("command_quiver.app.Gtk"), patch("command_quiver.app.Gdk"):
            from command_quiver.app import CommandQuiverApp

            app = CommandQuiverApp()
            app._sync_debounce_id = 5

            with patch.object(app, "_run_sync_background") as mock_run:
                ret = app._on_sync_debounce_fire()

            assert app._sync_debounce_id == 0
            mock_run.assert_called_once()
            assert ret is False

    def test_do_activate_creates_and_presents_sidebar(self) -> None:
        with (
            patch("command_quiver.app.Gtk"),
            patch("command_quiver.app.Gdk"),
            patch("command_quiver.app.SidebarPanel") as mock_sidebar_cls,
        ):
            from command_quiver.app import CommandQuiverApp

            app = CommandQuiverApp()
            app._db = MagicMock()
            app._settings = MagicMock()
            app._sidebar = None

            with patch.object(app, "add_window") as mock_add:
                app.do_activate()

            mock_sidebar_cls.assert_called_once()
            mock_add.assert_called_once()
            mock_sidebar_cls.return_value.present.assert_called_once()
