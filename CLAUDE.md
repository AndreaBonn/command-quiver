# Command Quiver by Bonn

App desktop Ubuntu/GNOME. Libreria personale di prompt AI e comandi shell, ricercabili e organizzati in sezioni.

## Stack

- Python 3.10+ (solo stdlib + PyGObject)
- GTK4 per UI
- SQLite3 per persistenza
- No dipendenze pip esterne

## Struttura

```
command_quiver/
├── main.py          # Entry point, logging, --version flag
├── app.py           # GtkApplication lifecycle, sync, cambio lingua
├── db/
│   ├── database.py  # SQLite, schema, migration system (PRAGMA user_version), auto-backup
│   └── queries.py   # Repository CRUD, export/import JSON, paginazione
├── core/
│   ├── clipboard.py      # Copia negli appunti via GDK4
│   ├── executor.py       # Esecuzione comandi in gnome-terminal (shlex.quote)
│   ├── github_client.py  # Client GitHub Contents API (solo stdlib urllib)
│   ├── i18n.py           # Internazionalizzazione it/en
│   ├── settings.py       # Config JSON persistente + SyncSettings + token management
│   └── sync_engine.py    # Sync engine: export, merge (last-write-wins), push/pull
├── ui/
│   ├── sidebar.py        # Pannello laterale (debounce search, sort personale, selettore lingua)
│   ├── entry_list.py     # Lista voci con ordinamento e move up/down
│   ├── entry_editor.py   # Dialog creazione/modifica
│   ├── section_panel.py  # Pannello sezioni con CRUD
│   ├── section_manager.py # Dialog gestione sezioni (validazione duplicati)
│   ├── sync_dialog.py    # Dialog configurazione sync GitHub
│   └── styles.py         # CSS theme-aware (@success_color, @accent_color)
└── assets/
    └── icon.png     # Icona applicazione
```

## Convenzioni

- Codice commentato in italiano
- Type annotations su tutti i parametri e return
- Logging con RotatingFileHandler (~/.local/share/command-quiver/logs/)
- DB path: ~/.local/share/command-quiver/vault.db
- Config path: ~/.config/command-quiver/settings.json
- Sync token path: ~/.config/command-quiver/.sync_token (600 perms)
- Single instance: GtkApplication + D-Bus (FLAGS_NONE)
- Backup auto DB: ogni 5 avvii, max 3 copie
- Chiusura finestra (X o Escape) = termina l'app, con sync finale e salvataggio stato

## Sync cross-device (GitHub)

Sincronizzazione via GitHub private repo (Contents API, solo stdlib urllib).
- UUID su ogni entry/section per identita cross-device
- Merge strategy: last-write-wins basato su updated_at
- Tombstones per propagare cancellazioni (cleanup 90gg)
- Sync: all'avvio (pull+merge), debounced 30s dopo CRUD, alla chiusura
- Token GitHub in file separato con permessi 600

## Comandi

```bash
uv run python command_quiver/main.py   # Avvia app
uv run pytest                           # Test
uv run ruff check .                     # Lint
```
