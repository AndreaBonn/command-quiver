"""Fixture condivise per tutti i test, inclusa inizializzazione GTK4."""

import os
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from command_quiver.core.sync_coordinator import SyncRuntime

# Verifica disponibilità display per test GTK4
_HAS_DISPLAY = bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))

requires_display = pytest.mark.skipif(
    not _HAS_DISPLAY,
    reason="Nessun display disponibile per i test GTK4",
)


@pytest.fixture(scope="session")
def gtk_init():
    """Inizializza GTK4 una sola volta per tutta la sessione di test."""
    if not _HAS_DISPLAY:
        pytest.skip("Nessun display disponibile")

    import gi

    gi.require_version("Gdk", "4.0")
    gi.require_version("Gtk", "4.0")

    # Init esplicito: senza, get_default() è None se nessun altro modulo
    # ha già inizializzato GTK (i test lanciati da soli venivano saltati)
    from gi.repository import Gdk, Gtk

    Gtk.init()

    display = Gdk.Display.get_default()
    if display is None:
        pytest.skip("Impossibile ottenere il display GTK4")
    return display


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_teardown(item: pytest.Item):
    """Chiude le finestre principali rimaste aperte, prima che le fixture chiudano il DB.

    Misurato: un debounce di ricerca o una cancellazione in attesa di una finestra
    lasciata da un test scattavano in un test successivo, a DB già chiuso.
    """
    if "gi.repository.Gtk" in sys.modules and _HAS_DISPLAY:
        from gi.repository import Gtk

        from command_quiver.ui.sidebar import SidebarPanel

        for window in Gtk.Window.list_toplevels():
            if isinstance(window, SidebarPanel):
                window.cancel_pending_timers()
                window.destroy()
    yield


@pytest.fixture(autouse=True)
def _fail_on_gtk_handler_errors(monkeypatch: pytest.MonkeyPatch):
    """Un'eccezione in un handler GTK fa fallire il test invece di essere solo stampata.

    PyGObject non la propaga a ``emit()`` né al main loop: la passa a ``sys.excepthook``,
    e senza questa fixture un clic che va in crash risultava un test verde.
    """
    errors: list[BaseException] = []
    monkeypatch.setattr(sys, "excepthook", lambda _type, err, _tb: errors.append(err))
    yield errors
    if errors:
        pytest.fail(f"eccezione in un handler GTK: {errors[0]!r}", pytrace=False)


@pytest.fixture
def db_for_ui(tmp_path: Path):
    """Database inizializzato per test UI."""
    from command_quiver.db.database import Database

    db = Database(db_path=tmp_path / "test_ui.db")
    db.initialize()
    yield db
    db.close()


@pytest.fixture
def default_settings(tmp_path: Path):
    """Settings di default con path temporaneo."""
    from command_quiver.core.settings import Settings

    return Settings()


def wait_until(predicate, timeout_s: float = 5.0) -> bool:
    """Itera il main loop GLib finché ``predicate()`` è vera; False se scade il timeout.

    Aspetta la condizione e non una durata: un timer di 10 ms sveglia il loop
    anche quando nessun altro evento è in coda.
    """
    import time

    from gi.repository import GLib

    context = GLib.MainContext.default()
    tick = GLib.timeout_add(10, lambda: GLib.SOURCE_CONTINUE)
    deadline = time.monotonic() + timeout_s
    try:
        while not predicate():
            if time.monotonic() > deadline:
                return False
            context.iteration(True)
        return True
    finally:
        GLib.source_remove(tick)


def descendants(widget):
    """Tutti i widget discendenti (visita in profondità)."""
    child = widget.get_first_child()
    while child is not None:
        yield child
        yield from descendants(child)
        child = child.get_next_sibling()


def button_labelled(root, label: str):
    """Il pulsante con quell'etichetta: è il modo in cui l'utente lo individua."""
    from gi.repository import Gtk

    matches = [w for w in descendants(root) if isinstance(w, Gtk.Button) and w.get_label() == label]
    assert len(matches) == 1, f"pulsanti con etichetta {label!r}: {len(matches)}"
    return matches[0]


def key_press(window, keyval: int, state=None) -> bool:
    """Preme un tasto su tutti i controller di tastiera della finestra, come farebbe GTK."""
    from gi.repository import Gdk, Gtk

    controllers = window.observe_controllers()
    keys = [
        c
        for c in (controllers.get_item(i) for i in range(controllers.get_n_items()))
        if isinstance(c, Gtk.EventControllerKey)
    ]
    modifiers = state if state is not None else Gdk.ModifierType(0)
    handled = [bool(c.emit("key-pressed", keyval, 0, modifiers)) for c in keys]
    return any(handled)


@pytest.fixture
def isolated_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Settings e token di sync su tmp_path: nessun test tocca ~/.config reale."""
    from command_quiver.core import settings as settings_module

    monkeypatch.setattr(settings_module, "DEFAULT_CONFIG_PATH", tmp_path / "settings.json")
    monkeypatch.setattr(settings_module, "SYNC_TOKEN_PATH", tmp_path / ".sync_token")
    return tmp_path


def fake_file_dialog(chosen: Path | None):
    """Sostituto di Gtk.FileDialog: "sceglie" ``chosen`` (None = annullato) e richiama subito."""

    class _Dialog:
        def __init__(self, **_kwargs) -> None:
            pass

        def _finish(self, _result):
            from unittest.mock import MagicMock

            if chosen is None:
                from gi.repository import GLib

                raise GLib.Error("annullato")
            file = MagicMock()
            file.get_path.return_value = str(chosen)
            return file

        save_finish = _finish
        open_finish = _finish

        def save(self, _window, _cancellable, callback) -> None:
            callback(self, None)

        open = save

    return _Dialog


def run_loop_for(milliseconds: int) -> None:
    """Fa girare il main loop per un tempo reale, solo per comportamenti a tempo (debounce).

    Aspetta un timer GLib, non un ``sleep``: gli altri timer scadono nel loro ordine.
    """
    from gi.repository import GLib

    fired: list[bool] = []
    GLib.timeout_add(milliseconds, lambda: fired.append(True) or GLib.SOURCE_REMOVE)
    assert wait_until(lambda: fired != [])


@pytest.fixture(autouse=True)
def _never_touch_real_config(tmp_path_factory, monkeypatch: pytest.MonkeyPatch) -> None:
    """Rete di sicurezza: un test che salva settings o token senza isolarli non scrive in ~/.config.

    Misurato: ``test_sidebar.py`` e ``test_run_confirm.py`` riscrivevano il vero settings.json.
    """
    from command_quiver.core import settings as settings_module

    safe = tmp_path_factory.mktemp("config")
    monkeypatch.setattr(settings_module, "DEFAULT_CONFIG_PATH", safe / "settings.json")
    monkeypatch.setattr(settings_module, "SYNC_TOKEN_PATH", safe / ".sync_token")


@pytest.fixture(autouse=True)
def _italian_by_default() -> None:
    """Ogni test parte in italiano: la lingua è stato globale di i18n.

    Misurato: un test che passava a "en" lasciava in inglese i successivi, e i test che
    leggono "Comando"/"Prompt" passavano solo grazie all'ordine alfabetico dei file.
    """
    from command_quiver.core import i18n

    i18n.init("it")


class FakeThread:
    """Thread finto: ``alive`` decide se il join ha raggiunto la fine o è scaduto."""

    def __init__(self, alive: bool) -> None:
        self._alive = alive
        self.joined_with: float | None = None

    def join(self, timeout: float | None = None) -> None:
        self.joined_with = timeout

    def is_alive(self) -> bool:
        return self._alive


class FakeRuntime:
    """Scheduler, main loop e thread controllati dal test."""

    def __init__(self) -> None:
        self.timers: dict[int, Callable[[], bool]] = {}
        self.scheduled: list[tuple[int, int]] = []  # (id, secondi)
        self.cancelled: list[int] = []
        self.spawned: list[Callable[[], object]] = []
        self.threads: list[FakeThread] = []
        self.threads_stay_alive = False
        self.on_spawn: Callable[[], None] | None = None
        self._main_queue: list[tuple[Callable[..., object], tuple]] = []
        self._next_id = 1
        self._ran = 0

    def schedule(self, seconds: int, callback: Callable[[], bool]) -> int:
        timer_id = self._next_id
        self._next_id += 1
        self.timers[timer_id] = callback
        self.scheduled.append((timer_id, seconds))
        return timer_id

    def cancel(self, timer_id: int) -> None:
        self.cancelled.append(timer_id)
        self.timers.pop(timer_id, None)

    def call_on_main(self, fn: Callable[..., object], *args: object) -> None:
        self._main_queue.append((fn, args))

    def spawn(self, target: Callable[[], object]) -> FakeThread:
        if self.on_spawn is not None:
            self.on_spawn()
        self.spawned.append(target)
        thread = FakeThread(alive=self.threads_stay_alive)
        self.threads.append(thread)
        return thread

    def fire_timer(self) -> object:
        """Scatta l'unico timer attivo, come farebbe GLib, e ne restituisce il valore di ritorno."""
        (timer_id,) = self.timers
        return self.timers.pop(timer_id)()

    def complete_syncs(self) -> list[object]:
        """Esegue i thread avviati e le callback sul main loop; restituisce i loro ritorni."""
        while self._ran < len(self.spawned):
            self.spawned[self._ran]()
            self._ran += 1
        queue, self._main_queue = self._main_queue, []
        return [fn(*args) for fn, args in queue]

    def as_runtime(self) -> SyncRuntime:
        return SyncRuntime(
            schedule=self.schedule,
            cancel=self.cancel,
            call_on_main=self.call_on_main,
            spawn=self.spawn,
        )
