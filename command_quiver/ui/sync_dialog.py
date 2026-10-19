"""Dialog per configurazione sincronizzazione GitHub."""

import logging
import threading
from collections.abc import Callable
from datetime import datetime

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, GLib, Gtk

from command_quiver.core.github_client import ConnectionStatus, GitHubClient
from command_quiver.core.i18n import t
from command_quiver.core.presentation import format_relative_time
from command_quiver.core.repo_ref import format_repo_ref, parse_repo_ref
from command_quiver.core.settings import (
    Settings,
    delete_sync_token,
    load_sync_token,
    save_settings,
    save_sync_token,
)

logger = logging.getLogger(__name__)

TOKEN_HELP_URL = "https://github.com/settings/personal-access-tokens/new"
_BAD_REPO = "bad_repo"


def connection_message(status: ConnectionStatus | str) -> str:
    """Messaggio che dice cosa correggere per ciascun esito del test di connessione."""
    key = status if isinstance(status, str) else status.value
    return t(f"sync.conn_{key}")


class SyncSetupDialog(Gtk.Window):
    """Configura la sincronizzazione: un campo repository, token, test e attivazione."""

    def __init__(
        self,
        parent: Gtk.Window,
        settings: Settings,
        on_sync_toggled: Callable[[], None] | None = None,
        on_sync_now: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(
            title=t("sync.title"),
            transient_for=parent,
            modal=True,
            default_width=460,
        )
        self._settings = settings
        self._on_sync_toggled = on_sync_toggled
        self._on_sync_now = on_sync_now

        self._build_ui()
        self._load_current_values()

    def _build_ui(self) -> None:
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        for side in ("top", "bottom", "start", "end"):
            getattr(main_box, f"set_margin_{side}")(16)
        self.set_child(main_box)

        intro = Gtk.Label(label=t("sync.intro"), xalign=0, wrap=True)
        intro.add_css_class("sync-intro")
        main_box.append(intro)

        main_box.append(self._heading(t("sync.repo")))
        self._repo_entry = Gtk.Entry(placeholder_text=t("sync.repo_placeholder"))
        main_box.append(self._repo_entry)
        main_box.append(self._hint(t("sync.repo_hint")))

        main_box.append(self._heading(t("sync.token")))
        self._token_entry = Gtk.PasswordEntry(
            placeholder_text=t("sync.token_placeholder"), show_peek_icon=True
        )
        main_box.append(self._token_entry)
        link = Gtk.LinkButton(
            uri=TOKEN_HELP_URL, label=t("sync.token_link"), halign=Gtk.Align.START
        )
        main_box.append(link)
        main_box.append(self._hint(t("sync.token_hint")))

        self._status_label = Gtk.Label(label="", xalign=0, wrap=True)
        main_box.append(self._status_label)
        self._last_sync_label = Gtk.Label(label="", xalign=0)
        self._last_sync_label.add_css_class("dim-label")
        main_box.append(self._last_sync_label)
        main_box.append(self._build_buttons())

        key_controller = Gtk.EventControllerKey()
        key_controller.connect("key-pressed", self._on_key_pressed)
        self.add_controller(key_controller)

    @staticmethod
    def _heading(text: str) -> Gtk.Label:
        label = Gtk.Label(label=text, xalign=0)
        label.add_css_class("heading")
        return label

    @staticmethod
    def _hint(text: str) -> Gtk.Label:
        label = Gtk.Label(label=text, xalign=0, wrap=True)
        label.add_css_class("dim-label")
        label.add_css_class("caption")
        return label

    def _build_buttons(self) -> Gtk.Box:
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8, margin_top=8)
        self._test_btn = Gtk.Button(label=t("sync.btn_test"))
        self._test_btn.connect("clicked", self._on_test_clicked)
        btn_box.append(self._test_btn)

        self._sync_now_btn = Gtk.Button(label=t("sync.btn_sync_now"))
        self._sync_now_btn.connect("clicked", self._on_sync_now_clicked)
        btn_box.append(self._sync_now_btn)

        btn_box.append(Gtk.Box(hexpand=True))
        self._toggle_btn = Gtk.Button()
        self._toggle_btn.connect("clicked", self._on_toggle_clicked)
        btn_box.append(self._toggle_btn)
        return btn_box

    def _load_current_values(self) -> None:
        sync = self._settings.sync
        self._repo_entry.set_text(format_repo_ref(owner=sync.repo_owner, name=sync.repo_name))
        token = load_sync_token()
        if token:
            self._token_entry.set_text(token)
        self._update_state()

    def _update_state(self) -> None:
        """Pulsanti e riga "ultima sincronizzazione" coerenti con lo stato attuale."""
        enabled = self._settings.sync.enabled
        self._toggle_btn.set_label(t("sync.btn_disable") if enabled else t("sync.btn_enable"))
        self._toggle_btn.remove_css_class(
            "destructive-action" if not enabled else "suggested-action"
        )
        self._toggle_btn.add_css_class("destructive-action" if enabled else "suggested-action")
        self._sync_now_btn.set_visible(enabled and self._on_sync_now is not None)

        when = format_relative_time(iso=self._settings.sync.last_sync, now=datetime.now())
        if enabled:
            self._last_sync_label.set_label(
                t("sync.last_sync", time=when) if when else t("sync.never")
            )
        self._last_sync_label.set_visible(enabled)

    def _read_fields(self) -> tuple[tuple[str, str] | None, str]:
        """(owner, repo) oppure None se il repository non è leggibile, e token."""
        return parse_repo_ref(self._repo_entry.get_text()), self._token_entry.get_text().strip()

    def _show_status(self, message: str, ok: bool) -> None:
        self._status_label.set_label(message)
        self._status_label.remove_css_class("success-label" if not ok else "error-label")
        self._status_label.add_css_class("success-label" if ok else "error-label")

    def _field_problem(self) -> str | None:
        """Errore sui campi prima di chiamare GitHub, o None se sono compilati bene."""
        repo, token = self._read_fields()
        if not self._repo_entry.get_text().strip() or not token:
            return connection_message(ConnectionStatus.MISSING_FIELDS)
        if repo is None:
            return connection_message(_BAD_REPO)
        return None

    def _on_test_clicked(self, _button: Gtk.Button) -> None:
        """Testa la connessione in un thread separato e dice cosa correggere."""
        problem = self._field_problem()
        if problem:
            self._show_status(problem, ok=False)
            return
        (owner, repo), token = self._read_fields()
        self._status_label.set_label(t("sync.testing"))
        self._test_btn.set_sensitive(False)

        def _test_in_thread() -> None:
            status = GitHubClient(token=token, owner=owner, repo=repo).check_connection()
            GLib.idle_add(self._on_test_result, status)

        threading.Thread(target=_test_in_thread, daemon=True).start()

    def _on_test_result(self, status: ConnectionStatus) -> bool:
        """Callback risultato test connessione (eseguita sul main thread)."""
        self._test_btn.set_sensitive(True)
        self._show_status(connection_message(status), ok=status is ConnectionStatus.OK)
        return False

    def _on_toggle_clicked(self, _button: Gtk.Button) -> None:
        """Attiva o disattiva la sincronizzazione."""
        if not self._settings.sync.enabled:
            problem = self._field_problem()
            if problem:
                self._show_status(problem, ok=False)
                return
            (owner, repo), token = self._read_fields()
            self._settings.sync.enabled = True
            self._settings.sync.repo_owner = owner
            self._settings.sync.repo_name = repo
            save_sync_token(token)
            message = t("sync.saved")
        else:
            self._settings.sync.enabled = False
            delete_sync_token()
            message = t("sync.disabled_info")

        save_settings(self._settings)
        self._update_state()
        self._show_status(message, ok=True)
        if self._on_sync_toggled:
            self._on_sync_toggled()

    def _on_sync_now_clicked(self, _button: Gtk.Button) -> None:
        if self._on_sync_now:
            self._on_sync_now()
        self.close()

    def _on_key_pressed(self, _controller, keyval: int, _keycode: int, _state) -> bool:
        """Chiude con Escape."""
        if keyval == Gdk.KEY_Escape:
            self.close()
            return True
        return False
