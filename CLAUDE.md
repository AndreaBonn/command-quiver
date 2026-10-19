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
│   ├── database.py           # Connessione SQLite: apertura, init, ricreazione, chiusura
│   ├── schema.py             # DDL, seed, migrazioni (PRAGMA user_version), uuid
│   ├── backup.py             # Backup automatico ogni 5 avvii, max 3 copie
│   ├── models.py             # Dataclass Section, Entry, EntryCreate/Update, SyncedEntry
│   ├── section_repository.py # Sezioni per id (UI)
│   ├── entry_repository.py   # Voci per id (UI): lista, ricerca, ordinamento, paginazione
│   ├── tombstone_repository.py # Tombstone del sync, scritte nella transazione della delete
│   ├── sync_repository.py    # Operazioni per uuid usate dal sync
│   └── entry_import.py       # Import JSON della libreria (normalizzazione pura)
├── core/
│   ├── clipboard.py      # Copia negli appunti via GDK4
│   ├── executor.py       # Esecuzione comandi in gnome-terminal (shlex.quote)
│   ├── github_client.py  # Client GitHub Contents API (solo stdlib urllib)
│   ├── i18n.py           # Internazionalizzazione it/en (dizionari in core/locales/)
│   ├── library_io.py     # Formato JSON di import/export della libreria
│   ├── ordering.py       # Riordino per trascinamento (funzione pura)
│   ├── presentation.py   # Funzioni pure: tempo relativo, nome da contenuto, tag, anteprima
│   ├── repo_ref.py       # Parsing "utente/repo" o URL GitHub (campo unico)
│   ├── samples.py        # Voci di esempio del primo avvio (it/en)
│   ├── settings.py       # Config JSON persistente + SyncSettings + token management
│   ├── sync_engine.py    # Sync: client, export dal DB, esecuzione del piano, push/pull
│   ├── sync_merge.py     # Regole pure del sync: merge LWW, tombstone, piano del pull
│   ├── timestamps.py     # Timestamp confrontabili fra formati storici e fusi
│   └── sync_status.py    # Testo dello stato sync (mai "OK" prima di un esito reale)
├── ui/
│   ├── sidebar.py        # Finestra principale: compone i widget sotto
│   ├── header.py         # HeaderBar: "+ Nuova" e menu ☰ (lingua, sync, import/export...)
│   ├── window_actions.py # Azioni win.* e scorciatoie (Ctrl+F/N/Q/?), finestra Informazioni
│   ├── search_bar.py     # Ricerca (debounce) + ordinamento
│   ├── library_controller.py # Operazioni sulle voci: salva, elimina con Annulla, riordina, file
│   ├── pending_delete.py # Eliminazione rimandata: 5 s per Annulla, poi definitiva
│   ├── entry_list.py     # Lista voci: anteprima, tag, copia/esegui, Alt+↑/↓ (+ row_dnd.py: trascinamento)
│   ├── empty_states.py   # Primo avvio, sezione vuota, ricerca senza risultati
│   ├── run_confirm.py    # Conferma prima di eseguire ("non chiedere più" per voce)
│   ├── entry_editor.py   # Dialog creazione/modifica (+ editor_widgets.py, tag_input.py,
│   │                     #   editor_request.py: input del dialog e payload puro)
│   ├── section_panel.py  # Pannello sezioni con CRUD (+ section_row.py)
│   ├── section_manager.py # Dialog gestione sezioni (validazione duplicati)
│   ├── sync_dialog.py    # Dialog configurazione sync GitHub
│   ├── status_bar.py     # Stato sync in fondo alla finestra
│   ├── toast.py          # Avvisi temporanei
│   ├── library_actions.py # Import/export da file, esempi
│   └── styles.py         # CSS (colori dei badge espliciti: @accent_color manca nel tema GTK4)
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
- Chiusura finestra (X o Ctrl+Q) = termina l'app, con sync finale e salvataggio stato.
  Esc svuota la ricerca e non chiude l'app (proposta UX M15, 2026-10-19)
- Sezioni iniziali create solo su DB vuoto, nella lingua delle impostazioni; "Generale"
  non si traduce (il codice la usa come fallback per nome)
- Proposte UX e stato di applicazione: docs/ux-proposte/index.html (codici M/V/E/Y/S/L/I)

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
