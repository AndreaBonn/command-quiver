"""SyncCoordinator: debounce, una sola sync alla volta, sync finale. Senza GTK."""

import logging

from command_quiver.core.sync_coordinator import DEBOUNCE_SECONDS, SyncCoordinator
from command_quiver.core.sync_engine import SyncResult
from tests.conftest import FakeRuntime


class FakeEngine:
    def __init__(self, outcome: SyncResult | Exception | None = None) -> None:
        self.outcome = outcome or SyncResult(success=True, message="ok")
        self.calls = 0

    def sync(self) -> SyncResult:
        self.calls += 1
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


class Harness:
    """Coordinatore con motore e runtime finti; registra ciò che arriva alla UI."""

    def __init__(self, engine: FakeEngine | None = None, with_callbacks: bool = True) -> None:
        self.runtime = FakeRuntime()
        self.engine = engine or FakeEngine()
        self.started = 0
        self.finished: list[SyncResult] = []
        self.coordinator = SyncCoordinator(
            make_engine=lambda: self.engine,
            runtime=self.runtime.as_runtime(),
            on_started=(lambda: setattr(self, "started", self.started + 1))
            if with_callbacks
            else None,
            on_finished=self.finished.append if with_callbacks else None,
        )

    def enabled(self) -> "Harness":
        """Attiva il sync e lascia terminare il primo sync, lasciando il coordinatore a riposo."""
        self.coordinator.set_enabled(True)
        self.runtime.complete_syncs()
        return self


class TestDebounce:
    def test_request_soon_schedules_a_timer_with_the_debounce_delay(self) -> None:
        h = Harness().enabled()

        h.coordinator.request_soon()

        assert [seconds for _id, seconds in h.runtime.scheduled] == [DEBOUNCE_SECONDS]
        assert h.coordinator.has_pending_request

    def test_request_soon_without_sync_enabled_schedules_nothing(self) -> None:
        h = Harness()

        h.coordinator.request_soon()

        assert h.runtime.scheduled == []
        assert not h.coordinator.has_pending_request

    def test_new_request_resets_the_pending_timer(self) -> None:
        h = Harness().enabled()

        h.coordinator.request_soon()
        first_id = h.runtime.scheduled[0][0]
        h.coordinator.request_soon()

        assert h.runtime.cancelled == [first_id]
        assert len(h.runtime.timers) == 1
        assert len(h.runtime.scheduled) == 2

    def test_first_request_has_nothing_to_cancel(self) -> None:
        h = Harness().enabled()

        h.coordinator.request_soon()

        assert h.runtime.cancelled == []

    def test_timer_fire_starts_a_sync_and_clears_the_pending_flag(self) -> None:
        h = Harness().enabled()
        h.coordinator.request_soon()
        before = len(h.runtime.spawned)

        returned = h.runtime.fire_timer()

        assert len(h.runtime.spawned) == before + 1
        assert not h.coordinator.has_pending_request
        assert returned is False  # True farebbe ripetere il timer a GLib

    def test_timer_fire_while_a_sync_is_running_is_ignored(self) -> None:
        h = Harness().enabled()
        h.coordinator.run_now()
        h.coordinator.request_soon()
        running_spawns = len(h.runtime.spawned)

        h.runtime.fire_timer()

        assert len(h.runtime.spawned) == running_spawns


class TestRunNow:
    def test_run_now_starts_one_sync_and_notifies_the_ui(self) -> None:
        h = Harness()
        h.coordinator.set_enabled(True)

        assert len(h.runtime.spawned) == 1
        assert h.started == 1
        assert h.coordinator.is_running

    def test_request_while_running_is_ignored(self) -> None:
        h = Harness()
        h.coordinator.set_enabled(True)

        h.coordinator.run_now()
        h.coordinator.run_now()

        assert len(h.runtime.spawned) == 1
        assert h.started == 1

    def test_sync_allowed_again_after_completion(self) -> None:
        h = Harness().enabled()

        h.coordinator.run_now()
        h.runtime.complete_syncs()
        h.coordinator.run_now()

        assert len(h.runtime.spawned) == 3  # primo sync + due run_now
        assert h.engine.calls == 2

    def test_run_now_without_sync_enabled_does_nothing(self) -> None:
        h = Harness()

        h.coordinator.run_now()

        assert h.runtime.spawned == []
        assert h.started == 0

    def test_finish_hands_the_result_to_the_ui_and_frees_the_flag(self) -> None:
        result = SyncResult(success=True, message="fatto", entries_pulled=3)
        h = Harness(FakeEngine(result))

        h.coordinator.set_enabled(True)
        assert h.coordinator.is_running
        returned = h.runtime.complete_syncs()

        assert h.finished == [result]
        assert not h.coordinator.is_running
        assert returned == [False]  # True farebbe ripetere l'idle a GLib

    def test_failed_result_reaches_the_ui_and_is_logged_as_warning(self, caplog) -> None:
        failed = SyncResult(success=False, message="401")
        h = Harness(FakeEngine(failed))

        with caplog.at_level(logging.INFO):
            h.coordinator.set_enabled(True)
            h.runtime.complete_syncs()

        assert h.finished == [failed]
        assert any(r.levelno == logging.WARNING and "401" in r.message for r in caplog.records)

    def test_exception_in_the_thread_becomes_an_error_result_and_frees_the_flag(self) -> None:
        h = Harness(FakeEngine(RuntimeError("rete esplosa")))

        h.coordinator.set_enabled(True)
        h.runtime.complete_syncs()

        (result,) = h.finished
        assert (result.success, result.message) == (False, "Errore interno sync")
        assert not h.coordinator.is_running
        h.coordinator.run_now()
        assert len(h.runtime.spawned) == 2

    def test_works_without_ui_callbacks(self) -> None:
        h = Harness(with_callbacks=False)

        h.coordinator.set_enabled(True)
        h.runtime.complete_syncs()

        assert h.engine.calls == 1
        assert not h.coordinator.is_running


class TestSetEnabled:
    def test_enabling_creates_the_engine_and_starts_the_first_sync(self) -> None:
        h = Harness()
        assert not h.coordinator.is_enabled

        h.coordinator.set_enabled(True)

        assert h.coordinator.is_enabled
        assert len(h.runtime.spawned) == 1

    def test_disabling_cancels_the_pending_timer(self) -> None:
        h = Harness().enabled()
        h.coordinator.request_soon()
        timer_id = h.runtime.scheduled[0][0]

        h.coordinator.set_enabled(False)

        assert h.runtime.cancelled == [timer_id]
        assert h.runtime.timers == {}
        assert not h.coordinator.has_pending_request
        assert not h.coordinator.is_enabled

    def test_after_disabling_no_sync_starts(self) -> None:
        h = Harness().enabled()
        h.coordinator.set_enabled(False)
        before = len(h.runtime.spawned)

        h.coordinator.run_now()
        h.coordinator.request_soon()

        assert len(h.runtime.spawned) == before
        assert h.runtime.timers == {}


class TestFinalSync:
    def test_final_sync_within_timeout_returns_true(self) -> None:
        h = Harness().enabled()
        before = len(h.runtime.spawned)

        done = h.coordinator.final_sync(timeout=5)

        assert done is True
        assert len(h.runtime.spawned) == before + 1
        assert h.runtime.threads[-1].joined_with == 5

    def test_final_sync_past_timeout_is_abandoned_with_a_warning(self, caplog) -> None:
        h = Harness().enabled()
        h.runtime.threads_stay_alive = True

        with caplog.at_level(logging.WARNING):
            done = h.coordinator.final_sync(timeout=5)

        assert done is False
        assert "Sync finale timeout" in caplog.text

    def test_final_sync_skipped_while_a_sync_is_running(self) -> None:
        h = Harness().enabled()
        h.coordinator.run_now()
        running_spawns = len(h.runtime.spawned)

        done = h.coordinator.final_sync(timeout=5)

        assert done is True
        assert len(h.runtime.spawned) == running_spawns

    def test_final_sync_without_sync_enabled_does_nothing(self) -> None:
        h = Harness()

        assert h.coordinator.final_sync(timeout=5) is True
        assert h.runtime.spawned == []

    def test_final_sync_cancels_the_pending_debounce(self) -> None:
        h = Harness().enabled()
        h.coordinator.request_soon()
        timer_id = h.runtime.scheduled[0][0]

        h.coordinator.final_sync(timeout=5)

        assert h.runtime.cancelled == [timer_id]
        assert not h.coordinator.has_pending_request


class TestFinalSyncOutcome:
    """Il thread di chiusura riporta l'esito nel log del progetto, non nel vuoto."""

    def test_final_sync_exception_is_logged_not_raised(self, caplog) -> None:
        h = Harness().enabled()
        h.engine.outcome = RuntimeError("disco pieno")

        with caplog.at_level(logging.ERROR, logger="command_quiver.core.sync_coordinator"):
            h.coordinator.final_sync(timeout=5)
            h.runtime.complete_syncs()

        errors = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert len(errors) == 1
        assert errors[0].exc_info is not None

    def test_final_sync_failed_result_is_logged_as_warning(self, caplog) -> None:
        h = Harness().enabled()
        h.engine.outcome = SyncResult(success=False, message="Token non valido")

        with caplog.at_level(logging.WARNING, logger="command_quiver.core.sync_coordinator"):
            h.coordinator.final_sync(timeout=5)
            h.runtime.complete_syncs()

        assert "Token non valido" in caplog.text

    def test_final_sync_success_logs_no_warning(self, caplog) -> None:
        """Positivo appaiato: un sync finale riuscito non produce avvisi."""
        h = Harness().enabled()

        with caplog.at_level(logging.WARNING, logger="command_quiver.core.sync_coordinator"):
            h.coordinator.final_sync(timeout=5)
            h.runtime.complete_syncs()

        assert [r for r in caplog.records if r.levelno >= logging.WARNING] == []
