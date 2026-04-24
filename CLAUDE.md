# Command Quiver

App desktop Ubuntu per system tray GNOME. Libreria personale di prompt AI e comandi shell, ricercabili e organizzati in sezioni.

## Stack

- Python 3.10+ (solo stdlib + PyGObject)
- GTK4 per UI, StatusNotifierItem D-Bus per tray icon
- SQLite3 per persistenza
- No dipendenze pip esterne

## Struttura

```
command_quiver/
├── main.py          # Entry point, logging, single instance
├── app.py           # GtkApplication + StatusNotifierItem tray
├── db/
│   ├── database.py  # Connessione SQLite, schema, seed
│   └── queries.py   # Repository CRUD (sections, entries)
├── core/
│   ├── clipboard.py # Copia negli appunti via GDK4
│   ├── executor.py  # Esecuzione comandi in gnome-terminal
│   └── settings.py  # Config JSON persistente
├── ui/
│   ├── sidebar.py        # Pannello laterale principale
│   ├── entry_list.py     # Lista voci con ordinamento
│   ├── entry_editor.py   # Dialog creazione/modifica
│   └── section_manager.py # Dialog gestione sezioni
└── assets/
    └── icon.png     # Icona tray 32x32
```

## Convenzioni

- Codice commentato in italiano
- Type annotations su tutti i parametri e return
- Logging con RotatingFileHandler (~/.local/share/command-quiver/logs/)
- DB path: ~/.local/share/command-quiver/vault.db
- Config path: ~/.config/command-quiver/settings.json
- Lock file: /tmp/command-quiver.lock

## Architettura tray icon

StatusNotifierItem via D-Bus puro (Gio.DBusConnection), nessuna dipendenza GTK3.
Compatibile con GNOME Shell + estensione AppIndicator (preinstallata su Ubuntu).

## Comandi

```bash
uv run python command_quiver/main.py   # Avvia app
uv run pytest                           # Test
uv run ruff check .                     # Lint
```
