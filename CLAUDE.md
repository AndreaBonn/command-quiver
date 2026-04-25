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
├── main.py          # Entry point, logging, --version flag
├── app.py           # GtkApplication lifecycle, tray health check, D-Bus
├── tray_helper.py   # Processo separato GTK3 + AyatanaAppIndicator3
├── db/
│   ├── database.py  # SQLite, schema, migration system (PRAGMA user_version), auto-backup
│   └── queries.py   # Repository CRUD, export/import JSON, paginazione
├── core/
│   ├── clipboard.py # Copia negli appunti via GDK4
│   ├── executor.py  # Esecuzione comandi in gnome-terminal (shlex.quote)
│   ├── i18n.py      # Internazionalizzazione it/en
│   └── settings.py  # Config JSON persistente
├── ui/
│   ├── sidebar.py        # Pannello laterale (debounce search, sort personale)
│   ├── entry_list.py     # Lista voci con ordinamento e move up/down
│   ├── entry_editor.py   # Dialog creazione/modifica
│   ├── section_panel.py  # Pannello sezioni con CRUD
│   ├── section_manager.py # Dialog gestione sezioni (validazione duplicati)
│   └── styles.py         # CSS theme-aware (@success_color, @accent_color)
└── assets/
    └── icon.png     # Icona tray 32x32
```

## Convenzioni

- Codice commentato in italiano
- Type annotations su tutti i parametri e return
- Logging con RotatingFileHandler (~/.local/share/command-quiver/logs/)
- DB path: ~/.local/share/command-quiver/vault.db
- Config path: ~/.config/command-quiver/settings.json
- Single instance: GtkApplication + D-Bus (FLAGS_NONE)
- Backup auto DB: ogni 5 avvii, max 3 copie

## Architettura tray icon

Processo separato (tray_helper.py) con GTK3 + AyatanaAppIndicator3.
GTK3 e GTK4 non coesistono nello stesso processo.
Comunicazione via D-Bus. Health check ogni 10s con auto-restart.
Compatibile con GNOME Shell + estensione AppIndicator (preinstallata su Ubuntu).

## Comandi

```bash
uv run python command_quiver/main.py   # Avvia app
uv run pytest                           # Test
uv run ruff check .                     # Lint
```
