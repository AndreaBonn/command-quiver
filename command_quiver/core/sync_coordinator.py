"""Coordinamento del sync: una sola sincronizzazione alla volta, debounce e sync finale.

Nessun import di GTK/GLib: timer, main loop e thread arrivano dall'esterno
(``SyncRuntime``), così la logica si prova con scheduler finti e senza display.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from command_quiver.core.sync_engine import SyncResult

logger = logging.getLogger(__name__)

# Secondi di attesa dopo l'ultima modifica prima di pushare
DEBOUNCE_SECONDS = 30


class SyncEngineLike(Protocol):
    """Ciò che il coordinatore chiede al motore di sync."""

    def sync(self) -> SyncResult: ...


class ThreadHandle(Protocol):
    """Thread già avviato, di cui si può attendere la fine."""

    def join(self, timeout: float | None = None) -> None: ...

    def is_alive(self) -> bool: ...


@dataclass(frozen=True)
class SyncRuntime:
    """Equivalenti iniettabili di GLib.timeout_add_seconds, source_remove, idle_add e Thread."""

    schedule: Callable[[int, Callable[[], bool]], int]
    cancel: Callable[[int], None]
    call_on_main: Callable[..., Any]
    spawn: Callable[[Callable[[], object]], ThreadHandle]


class SyncCoordinator:
    """Decide quando far partire il sync e garantisce che non ne girino due insieme."""

    def __init__(
        self,
        make_engine: Callable[[], SyncEngineLike],
        runtime: SyncRuntime,
        on_started: Callable[[], None] | None = None,
        on_finished: Callable[[SyncResult], None] | None = None,
    ) -> None:
        self._make_engine = make_engine
        self._runtime = runtime
        self._on_started = on_started
        self._on_finished = on_finished
        self._engine: SyncEngineLike | None = None
        self._timer_id = 0
        self._running = False

    @property
    def is_enabled(self) -> bool:
        """Vero se esiste un motore di sync attivo."""
        return self._engine is not None

    @property
    def is_running(self) -> bool:
        """Vero se una sincronizzazione è in corso."""
        return self._running

    @property
    def has_pending_request(self) -> bool:
        """Vero se un sync è in attesa del debounce."""
        return self._timer_id != 0

    def set_enabled(self, enabled: bool) -> None:
        """Attiva (nuovo motore e primo sync subito) o disattiva il sync."""
        if enabled:
            self._engine = self._make_engine()
            self.run_now()
            logger.info("Sync attivato, primo sync avviato")
        else:
            self._cancel_timer()
            self._engine = None
            logger.info("Sync disattivato")

    def request_soon(self) -> None:
        """Programma un sync fra ``DEBOUNCE_SECONDS``; ogni richiesta azzera l'attesa."""
        if self._engine is None:
            return
        self._cancel_timer()
        self._timer_id = self._runtime.schedule(DEBOUNCE_SECONDS, self._on_timer)

    def run_now(self) -> None:
        """Avvia un sync in background, a meno che ne sia già in corso uno."""
        if self._engine is None or self._running:
            # Due push in parallelo usano lo stesso SHA e il secondo prende 409
            return
        self._running = True
        if self._on_started is not None:
            self._on_started()
        engine = self._engine

        def work() -> None:
            try:
                result = engine.sync()
            except Exception:
                logger.exception("Eccezione non gestita nel thread sync")
                result = SyncResult(success=False, message="Errore interno sync")
            self._runtime.call_on_main(self._finish, result)

        self._runtime.spawn(work)

    def final_sync(self, timeout: float) -> bool:
        """Sync di chiusura: attende al più ``timeout`` secondi.

        Parameters
        ----------
        timeout : float
            Secondi massimi di attesa, per non bloccare la chiusura con la rete lenta.

        Returns
        -------
        bool
            False se il sync è stato abbandonato per timeout; True se è finito
            o non c'era nulla da fare (sync spento o già in corso).
        """
        self._cancel_timer()
        # Con una sync in volo un secondo push userebbe lo stesso SHA (409)
        if self._engine is None or self._running:
            return True
        thread = self._runtime.spawn(self._engine.sync)
        thread.join(timeout=timeout)
        if thread.is_alive():
            logger.warning("Sync finale timeout, chiusura senza attendere")
            return False
        return True

    def _on_timer(self) -> bool:
        self._timer_id = 0
        self.run_now()
        return False  # Non ripetere

    def _cancel_timer(self) -> None:
        if self._timer_id:
            self._runtime.cancel(self._timer_id)
            self._timer_id = 0

    def _finish(self, result: SyncResult) -> bool:
        """Eseguita sul main loop: libera il flag e avvisa la UI."""
        self._running = False
        if result.success:
            logger.info("Sync completato: %s", result.message)
        else:
            logger.warning("Sync fallito: %s", result.message)
        if self._on_finished is not None:
            self._on_finished(result)
        return False  # Rimuovi da idle
