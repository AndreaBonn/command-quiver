"""Dialog per configurazione sincronizzazione GitHub."""

import logging
import threading
from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk

from command_quiver.core.github_client import GitHubClient
from command_quiver.core.i18n import t
from command_quiver.core.settings import (
    Settings,
    delete_sync_token,
    load_sync_token,
    save_settings,
    save_sync_token,
)

logger = logging.getLogger(__name__)


class SyncSetupDialog(Gtk.Window):
    """Dialog per configurare la sincronizzazione GitHub.

    Campi: repo owner, repo name, token (mascherato).
    Azioni: test connessione, attiva/disattiva sync.
    """

    def __init__(
        self,
        parent: Gtk.Window,
        settings: Settings,
        on_sync_toggled: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(
            title=t("sync.title"),
            transient_for=parent,
            modal=True,
            default_width=420,
            default_height=380,
        )
        self._settings = settings
        self._on_sync_toggled = on_sync_toggled

        self._build_ui()
        self._load_current_values()

    def _build_ui(self) -> None:
        """Costruisce il layout del dialog."""
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        main_box.set_margin_top(16)
        main_box.set_margin_bottom(16)
        main_box.set_margin_start(16)
        main_box.set_margin_end(16)
        self.set_child(main_box)

        # --- Repo owner ---
        owner_label = Gtk.Label(label=t("sync.repo_owner"), xalign=0)
        owner_label.add_css_class("heading")
        main_box.append(owner_label)

        self._owner_entry = Gtk.Entry(
            placeholder_text=t("sync.repo_owner_placeholder"),
        )
        main_box.append(self._owner_entry)

        # --- Repo name ---
        repo_label = Gtk.Label(label=t("sync.repo_name"), xalign=0)
        repo_label.add_css_class("heading")
        main_box.append(repo_label)

        self._repo_entry = Gtk.Entry(
            placeholder_text=t("sync.repo_name_placeholder"),
        )
        main_box.append(self._repo_entry)

        # --- Token ---
        token_label = Gtk.Label(label=t("sync.token"), xalign=0)
        token_label.add_css_class("heading")
        main_box.append(token_label)

        self._token_entry = Gtk.PasswordEntry(
            placeholder_text=t("sync.token_placeholder"),
            show_peek_icon=True,
        )
        main_box.append(self._token_entry)

        # --- Status label ---
        self._status_label = Gtk.Label(label="", xalign=0)
        self._status_label.set_wrap(True)
        main_box.append(self._status_label)

        # --- Ultimo sync ---
        self._last_sync_label = Gtk.Label(label="", xalign=0)
        self._last_sync_label.add_css_class("dim-label")
        main_box.append(self._last_sync_label)

        # --- Bottoni ---
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_box.set_margin_top(8)

        test_btn = Gtk.Button(label=t("sync.btn_test"))
        test_btn.connect("clicked", self._on_test_clicked)
        btn_box.append(test_btn)

        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        btn_box.append(spacer)

        self._toggle_btn = Gtk.Button()
        self._toggle_btn.connect("clicked", self._on_toggle_clicked)
        btn_box.append(self._toggle_btn)

        main_box.append(btn_box)

        # Chiusura con Escape
        key_controller = Gtk.EventControllerKey()
        key_controller.connect("key-pressed", self._on_key_pressed)
        self.add_controller(key_controller)

    def _load_current_values(self) -> None:
        """Popola i campi con la configurazione corrente."""
        sync = self._settings.sync
        self._owner_entry.set_text(sync.repo_owner)
        self._repo_entry.set_text(sync.repo_name)

        token = load_sync_token()
        if token:
            self._token_entry.set_text(token)

        self._update_toggle_button()

        if sync.last_sync:
            # Mostra solo data e ora, no microsecondi
            display_time = sync.last_sync[:19].replace("T", " ")
            self._last_sync_label.set_label(
                t("sync.last_sync", time=display_time),
            )

    def _update_toggle_button(self) -> None:
        """Aggiorna testo e stile del bottone toggle."""
        if self._settings.sync.enabled:
            self._toggle_btn.set_label(t("sync.btn_disable"))
            self._toggle_btn.remove_css_class("suggested-action")
            self._toggle_btn.add_css_class("destructive-action")
        else:
            self._toggle_btn.set_label(t("sync.btn_enable"))
            self._toggle_btn.remove_css_class("destructive-action")
            self._toggle_btn.add_css_class("suggested-action")

    def _read_fields(self) -> tuple[str, str, str]:
        """Legge i valori dai campi di input."""
        owner = self._owner_entry.get_text().strip()
        repo = self._repo_entry.get_text().strip()
        token = self._token_entry.get_text().strip()
        return owner, repo, token

    def _on_test_clicked(self, _button: Gtk.Button) -> None:
        """Testa la connessione GitHub in un thread separato."""
        owner, repo, token = self._read_fields()
        if not all([owner, repo, token]):
            self._status_label.set_label(t("sync.test_fail"))
            return

        self._status_label.set_label("...")

        def _test_in_thread() -> None:
            client = GitHubClient(token=token, owner=owner, repo=repo)
            success = client.validate()
            GLib.idle_add(self._on_test_result, success)

        thread = threading.Thread(target=_test_in_thread, daemon=True)
        thread.start()

    def _on_test_result(self, success: bool) -> bool:
        """Callback risultato test connessione (eseguita sul main thread)."""
        if success:
            self._status_label.set_label(t("sync.test_success"))
            self._status_label.remove_css_class("error")
            self._status_label.add_css_class("success")
        else:
            self._status_label.set_label(t("sync.test_fail"))
            self._status_label.remove_css_class("success")
            self._status_label.add_css_class("error")
        return False  # Rimuovi da idle

    def _on_toggle_clicked(self, _button: Gtk.Button) -> None:
        """Attiva o disattiva la sincronizzazione."""
        owner, repo, token = self._read_fields()

        if not self._settings.sync.enabled:
            # Attivazione: salva configurazione
            if not all([owner, repo, token]):
                self._status_label.set_label(t("sync.test_fail"))
                return

            self._settings.sync.enabled = True
            self._settings.sync.repo_owner = owner
            self._settings.sync.repo_name = repo
            save_sync_token(token)
        else:
            # Disattivazione
            self._settings.sync.enabled = False
            delete_sync_token()

        save_settings(self._settings)
        self._update_toggle_button()
        self._status_label.set_label(t("sync.saved"))
        self._status_label.remove_css_class("error")
        self._status_label.remove_css_class("success")

        if self._on_sync_toggled:
            self._on_sync_toggled()

    def _on_key_pressed(
        self,
        _controller: Gtk.EventControllerKey,
        keyval: int,
        _keycode: int,
        _state,
    ) -> bool:
        """Chiude con Escape."""
        from gi.repository import Gdk

        if keyval == Gdk.KEY_Escape:
            self.close()
            return True
        return False
