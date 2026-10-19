"""Test per CommandQuiverApp — logica applicazione e lifecycle."""

from unittest.mock import MagicMock, patch

import pytest

from command_quiver import APP_ID
from tests.conftest import FakeRuntime


def _app_with_fake_sync(engine=None):
    """App col coordinatore su runtime finto: nessun thread né timer GLib veri."""
    from command_quiver.app import CommandQuiverApp
    from command_quiver.core.sync_coordinator import SyncCoordinator

    app = CommandQuiverApp()
    runtime = FakeRuntime()
    engine = engine or MagicMock()
    app._sync = SyncCoordinator(
        make_engine=lambda: engine,
        runtime=runtime.as_runtime(),
        on_started=app._on_sync_started,
        on_finished=app._on_sync_finished,
    )
    return app, runtime


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
            assert not app._sync.is_enabled
            assert not app._sync.has_pending_request


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
        ):
            app, runtime = _app_with_fake_sync()
            app._sync.set_enabled(True)
            runtime.complete_syncs()
            app._sync.request_soon()
            timer_id = runtime.scheduled[0][0]
            app._settings = MagicMock()
            app._db = MagicMock()

            app.do_shutdown()

            assert runtime.cancelled == [timer_id]
            assert not app._sync.has_pending_request


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

    @pytest.mark.parametrize("was_visible", [True, False], ids=["visible", "hidden"])
    def test_change_language_presents_new_window_only_if_old_was_visible(
        self, was_visible: bool
    ) -> None:
        with (
            patch("command_quiver.app.Gtk"),
            patch("command_quiver.app.Gdk"),
            patch("command_quiver.app.save_settings"),
            patch("command_quiver.app.SidebarPanel") as mock_sidebar_cls,
        ):
            from command_quiver.app import CommandQuiverApp

            app = CommandQuiverApp()
            app._settings = MagicMock()
            app._db = MagicMock()
            old_sidebar = MagicMock()
            old_sidebar.get_default_size.return_value = (640, 600)
            old_sidebar.get_visible.return_value = was_visible
            app._sidebar = old_sidebar

            with (
                patch("command_quiver.core.i18n.get_language", return_value="it"),
                patch("command_quiver.core.i18n.init"),
                patch.object(app, "remove_window"),
                patch.object(app, "add_window"),
            ):
                app._change_language("en")

            assert mock_sidebar_cls.return_value.present.called is was_visible

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
            old_sidebar.get_default_size.return_value = (640, 600)
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
    """Collegamento fra app e coordinatore (la logica del sync è in test_sync_coordinator)."""

    def test_init_services_starts_first_sync_when_enabled(self) -> None:
        with (
            patch("command_quiver.app.Gtk"),
            patch("command_quiver.app.Gdk"),
            patch("command_quiver.app.Database"),
            patch("command_quiver.app.load_settings") as mock_load,
            patch("command_quiver.core.i18n.init"),
        ):
            mock_load.return_value = MagicMock(language="it", sync=MagicMock(enabled=True))
            app, runtime = _app_with_fake_sync()

            app._init_services()

            assert app._sync.is_enabled
            assert len(runtime.spawned) == 1

    def test_init_services_does_not_start_sync_when_disabled(self) -> None:
        with (
            patch("command_quiver.app.Gtk"),
            patch("command_quiver.app.Gdk"),
            patch("command_quiver.app.Database"),
            patch("command_quiver.app.load_settings") as mock_load,
            patch("command_quiver.core.i18n.init"),
        ):
            mock_load.return_value = MagicMock(language="it", sync=MagicMock(enabled=False))
            app, runtime = _app_with_fake_sync()

            app._init_services()

            assert not app._sync.is_enabled
            assert runtime.spawned == []

    def test_sync_engine_is_built_on_the_app_db_and_settings(self) -> None:
        with (
            patch("command_quiver.app.Gtk"),
            patch("command_quiver.app.Gdk"),
            patch("command_quiver.app.SyncEngine") as mock_engine,
        ):
            from command_quiver.app import CommandQuiverApp

            app = CommandQuiverApp()
            app._db = MagicMock()
            app._settings = MagicMock()

            engine = app._make_sync_engine()

            mock_engine.assert_called_once_with(db=app._db, settings=app._settings)
            assert engine is mock_engine.return_value

    def test_glib_runtime_maps_to_the_real_glib_functions(self) -> None:
        with patch("command_quiver.app.GLib") as glib:
            from command_quiver.app import _glib_runtime

            runtime = _glib_runtime()

        assert runtime.schedule is glib.timeout_add_seconds
        assert runtime.cancel is glib.source_remove
        assert runtime.call_on_main is glib.idle_add

    def test_shutdown_gives_the_final_sync_its_timeout(self) -> None:
        from command_quiver.app import _FINAL_SYNC_TIMEOUT_SECONDS

        with patch("command_quiver.app.Gtk"), patch("command_quiver.app.Gdk"):
            app, runtime = _app_with_fake_sync()
            app._sync.set_enabled(True)
            runtime.complete_syncs()

            app.do_shutdown()

        assert runtime.threads[-1].joined_with == _FINAL_SYNC_TIMEOUT_SECONDS

    def test_sync_runs_in_a_daemon_thread(self) -> None:
        with patch("command_quiver.app.threading") as mock_threading:
            from command_quiver.app import _spawn_daemon_thread

            target = MagicMock()
            handle = _spawn_daemon_thread(target)

        mock_threading.Thread.assert_called_once_with(target=target, daemon=True)
        mock_threading.Thread.return_value.start.assert_called_once()
        assert handle is mock_threading.Thread.return_value

    def test_sync_start_marks_the_sidebar_as_pending(self) -> None:
        app, _runtime = _app_with_fake_sync()
        app._sidebar = MagicMock()

        app._sync.set_enabled(True)

        app._sidebar.set_sync_pending.assert_called_once_with()

    def test_sync_finished_refreshes_sidebar_when_entries_pulled(self) -> None:
        app, _runtime = _app_with_fake_sync()
        sidebar = MagicMock()
        app._sidebar = sidebar
        result = MagicMock(success=True, entries_pulled=2, sections_pulled=0)

        app._on_sync_finished(result)

        sidebar.refresh_all.assert_called_once()
        sidebar.update_sync_status.assert_called_once_with(result)

    def test_sync_finished_refreshes_sidebar_when_sections_pulled(self) -> None:
        app, _runtime = _app_with_fake_sync()
        sidebar = MagicMock()
        app._sidebar = sidebar

        app._on_sync_finished(MagicMock(success=True, entries_pulled=0, sections_pulled=1))

        sidebar.refresh_all.assert_called_once()

    def test_sync_finished_no_refresh_when_nothing_pulled(self) -> None:
        app, _runtime = _app_with_fake_sync()
        sidebar = MagicMock()
        app._sidebar = sidebar
        result = MagicMock(success=True, entries_pulled=0, sections_pulled=0)

        app._on_sync_finished(result)

        sidebar.refresh_all.assert_not_called()
        sidebar.update_sync_status.assert_called_once_with(result)

    def test_sync_finished_failure_updates_status_only(self) -> None:
        app, _runtime = _app_with_fake_sync()
        sidebar = MagicMock()
        app._sidebar = sidebar
        result = MagicMock(success=False, entries_pulled=0, sections_pulled=0)

        app._on_sync_finished(result)

        sidebar.refresh_all.assert_not_called()
        sidebar.update_sync_status.assert_called_once_with(result)

    def test_sync_finished_without_sidebar_is_a_noop(self) -> None:
        app, _runtime = _app_with_fake_sync()

        app._on_sync_finished(MagicMock(success=True, entries_pulled=1, sections_pulled=0))

    def test_sync_toggled_enabled_starts_a_sync(self) -> None:
        app, runtime = _app_with_fake_sync()
        app._settings = MagicMock()
        app._settings.sync.enabled = True

        app._on_sync_toggled()

        assert app._sync.is_enabled
        assert len(runtime.spawned) == 1

    def test_sync_toggled_disabled_turns_the_sync_off(self) -> None:
        app, runtime = _app_with_fake_sync()
        app._sync.set_enabled(True)
        spawned = len(runtime.spawned)
        app._settings = MagicMock()
        app._settings.sync.enabled = False

        app._on_sync_toggled()

        assert not app._sync.is_enabled
        assert len(runtime.spawned) == spawned

    def test_sidebar_data_changed_callback_schedules_a_debounced_sync(self) -> None:
        with (
            patch("command_quiver.app.Gtk"),
            patch("command_quiver.app.Gdk"),
            patch("command_quiver.app.SidebarPanel") as mock_sidebar_cls,
        ):
            app, runtime = _app_with_fake_sync()
            app._sync.set_enabled(True)
            runtime.complete_syncs()

            app._create_sidebar()
            callbacks = mock_sidebar_cls.call_args.kwargs["callbacks"]
            callbacks.on_data_changed()

        assert len(runtime.scheduled) == 1

    def test_sidebar_sync_now_callback_starts_a_sync(self) -> None:
        with (
            patch("command_quiver.app.Gtk"),
            patch("command_quiver.app.Gdk"),
            patch("command_quiver.app.SidebarPanel") as mock_sidebar_cls,
        ):
            app, runtime = _app_with_fake_sync()
            app._sync.set_enabled(True)
            runtime.complete_syncs()
            before = len(runtime.spawned)

            app._create_sidebar()
            mock_sidebar_cls.call_args.kwargs["callbacks"].on_sync_now()

        assert len(runtime.spawned) == before + 1

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


class TestReviewFixes:
    """Cancellazione in attesa e sync finale (seconda review)."""

    def test_language_switch_flushes_pending_delete_before_new_window(self) -> None:
        with (
            patch("command_quiver.app.Gtk"),
            patch("command_quiver.app.Gdk"),
            patch("command_quiver.app.save_settings"),
            patch("command_quiver.app.SidebarPanel") as mock_sidebar_cls,
        ):
            from command_quiver.app import CommandQuiverApp

            app = CommandQuiverApp()
            app._settings = MagicMock()
            app._db = MagicMock()
            calls: list[str] = []
            old_sidebar = MagicMock()
            old_sidebar.get_default_size.return_value = (640, 600)
            old_sidebar.cancel_pending_timers.side_effect = lambda: calls.append("flush")
            mock_sidebar_cls.side_effect = lambda **_kw: calls.append("new") or MagicMock()
            app._sidebar = old_sidebar
            with (
                patch("command_quiver.core.i18n.get_language", return_value="it"),
                patch("command_quiver.core.i18n.init"),
                patch.object(app, "remove_window"),
                patch.object(app, "add_window"),
            ):
                app._change_language("en")
        assert calls == ["flush", "new"]

    def test_shutdown_skips_final_sync_while_one_is_running(self) -> None:
        with patch("command_quiver.app.Gtk"), patch("command_quiver.app.Gdk"):
            app, runtime = _app_with_fake_sync()
            app._sync.set_enabled(True)  # sync in corso: il thread non è ancora tornato
            running_spawns = len(runtime.spawned)

            app.do_shutdown()

        assert len(runtime.spawned) == running_spawns

    def test_shutdown_flushes_pending_delete_before_final_sync(self) -> None:
        with patch("command_quiver.app.Gtk"), patch("command_quiver.app.Gdk"):
            app, runtime = _app_with_fake_sync()
            app._sync.set_enabled(True)
            runtime.complete_syncs()
            calls: list[str] = []
            app._sidebar = MagicMock()
            app._sidebar.cancel_pending_timers.side_effect = lambda: calls.append("flush")
            runtime.on_spawn = lambda: calls.append("sync")

            app.do_shutdown()
        assert calls == ["flush", "sync"]


def test_language_switch_keeps_current_window_size() -> None:
    with (
        patch("command_quiver.app.Gtk"),
        patch("command_quiver.app.Gdk"),
        patch("command_quiver.app.save_settings"),
        patch("command_quiver.app.SidebarPanel") as mock_sidebar_cls,
    ):
        from command_quiver.app import CommandQuiverApp
        from command_quiver.core.settings import Settings

        app = CommandQuiverApp()
        app._settings = Settings(window_width=640, window_height=600)
        app._db = MagicMock()
        old_sidebar = MagicMock()
        old_sidebar.get_default_size.return_value = (640, 600)
        old_sidebar.get_default_size.return_value = (900, 700)
        app._sidebar = old_sidebar
        with (
            patch("command_quiver.core.i18n.get_language", return_value="it"),
            patch("command_quiver.core.i18n.init"),
            patch.object(app, "remove_window"),
            patch.object(app, "add_window"),
        ):
            app._change_language("en")
        settings = mock_sidebar_cls.call_args.kwargs["settings"]
        assert (settings.window_width, settings.window_height) == (900, 700)


class TestStartup:
    """do_startup: un errore nei servizi mostra l'avviso e chiude, senza lasciare l'app a metà."""

    def _app(self):
        from command_quiver.app import CommandQuiverApp

        return CommandQuiverApp()

    def test_startup_failure_shows_error_and_quits(self) -> None:
        with patch("command_quiver.app.Gtk"), patch("command_quiver.app.Gdk"):
            app = self._app()
            with (
                patch.object(app, "_init_services", side_effect=RuntimeError("db corrotto")),
                patch.object(app, "_show_error_dialog") as show_error,
                patch.object(app, "quit") as quit_app,
            ):
                app.do_startup()

        show_error.assert_called_once()
        assert "Impossibile avviare" in show_error.call_args.args[0]
        quit_app.assert_called_once_with()

    def test_startup_success_initializes_services_and_keeps_running(self) -> None:
        with patch("command_quiver.app.Gtk"), patch("command_quiver.app.Gdk"):
            app = self._app()
            with (
                patch.object(app, "_init_services") as init_services,
                patch.object(app, "_show_error_dialog") as show_error,
                patch.object(app, "quit") as quit_app,
            ):
                app.do_startup()

        init_services.assert_called_once_with()
        show_error.assert_not_called()
        quit_app.assert_not_called()


class TestActivate:
    def test_second_activation_presents_the_same_window(self) -> None:
        from command_quiver.app import CommandQuiverApp

        app = CommandQuiverApp()
        sidebar = MagicMock()
        with (
            patch.object(app, "_create_sidebar", return_value=sidebar) as create,
            patch.object(app, "add_window"),
        ):
            app.do_activate()
            app.do_activate()

        create.assert_called_once_with()
        assert sidebar.present.call_count == 2

    def test_activation_error_is_logged_not_raised(self, caplog) -> None:
        from command_quiver.app import CommandQuiverApp

        app = CommandQuiverApp()
        with patch.object(app, "_create_sidebar", side_effect=RuntimeError("boom")):
            app.do_activate()

        assert "Errore in do_activate" in caplog.text
        assert app._sidebar is None


class TestSyncInThread:
    """Sync vero in thread: l'esito torna sul main loop e sblocca la sync successiva."""

    def _app_with_engine(self, engine):
        from command_quiver.app import CommandQuiverApp

        app = CommandQuiverApp()
        app._db = MagicMock()
        app._settings = MagicMock()
        app._sidebar = MagicMock()
        with patch("command_quiver.app.SyncEngine", return_value=engine):
            app._sync.set_enabled(True)  # il primo sync parte subito, in un thread vero
        return app

    def test_exception_in_sync_is_reported_as_internal_error(self) -> None:
        from tests.conftest import wait_until

        engine = MagicMock()
        engine.sync.side_effect = RuntimeError("rete esplosa")
        app = self._app_with_engine(engine)

        app._sidebar.set_sync_pending.assert_called_once_with()
        assert wait_until(lambda: app._sidebar.update_sync_status.called)
        result = app._sidebar.update_sync_status.call_args.args[0]
        assert (result.success, result.message) == (False, "Errore interno sync")

    def test_sync_runs_again_after_a_failed_one(self) -> None:
        from tests.conftest import wait_until

        engine = MagicMock()
        engine.sync.side_effect = [
            RuntimeError("1"),
            MagicMock(success=True, entries_pulled=0, sections_pulled=0),
        ]
        app = self._app_with_engine(engine)

        assert wait_until(lambda: app._sidebar.update_sync_status.call_count == 1)
        app._sync.run_now()

        assert wait_until(lambda: app._sidebar.update_sync_status.call_count == 2)
        assert engine.sync.call_count == 2

    def test_second_request_while_running_is_ignored_with_real_thread(self) -> None:
        import threading

        from tests.conftest import wait_until

        release = threading.Event()
        engine = MagicMock()
        engine.sync.side_effect = lambda: (
            release.wait(timeout=5) and MagicMock(success=True, entries_pulled=0, sections_pulled=0)
        )
        app = self._app_with_engine(engine)

        app._sync.run_now()
        release.set()

        assert wait_until(lambda: app._sidebar.update_sync_status.called)
        assert engine.sync.call_count == 1
        app._sidebar.set_sync_pending.assert_called_once_with()


def test_final_sync_that_takes_too_long_is_abandoned_with_a_warning(caplog) -> None:
    app, runtime = _app_with_fake_sync()
    app._sync.set_enabled(True)
    runtime.complete_syncs()
    runtime.threads_stay_alive = True
    app.do_shutdown()

    assert "Sync finale timeout" in caplog.text


def test_language_change_without_window_still_saves_the_choice() -> None:
    from command_quiver.app import CommandQuiverApp
    from command_quiver.core.settings import Settings

    app = CommandQuiverApp()
    app._settings = Settings(language="it")
    with (
        patch("command_quiver.core.i18n.get_language", return_value="it"),
        patch("command_quiver.core.i18n.init") as i18n_init,
        patch("command_quiver.app.save_settings") as save,
    ):
        app._change_language("en")

    i18n_init.assert_called_once_with("en")
    assert app._settings.language == "en"
    save.assert_called_once_with(app._settings)
