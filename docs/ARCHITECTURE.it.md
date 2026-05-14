[English](ARCHITECTURE.md) | **Italiano**

# Architettura tecnica

Reference tecnico con diagrammi dettagliati degli internals di Command Quiver.

## Architettura di sistema

Processo principale GTK4, processo tray GTK3 (separato per compatibilita), e sync GitHub via Contents API.

```mermaid
graph LR
  subgraph main_proc["Processo principale - GTK4"]
    direction TB
    app["CommandQuiverApp"]
    sidebar["SidebarPanel"]
    sync_eng["SyncEngine"]
    db[("SQLite vault.db")]
    settings["Impostazioni JSON"]
  end

  subgraph tray_proc["Processo separato - GTK3"]
    tray["tray_helper.py<br/>AyatanaAppIndicator3"]
  end

  github["Repo privato GitHub"]

  tray -->|"D-Bus: Toggle, NewEntry,<br/>ChangeLanguage, Quit"| app
  app -->|"Health check 10s<br/>+ auto-restart"| tray
  app --> sidebar
  sidebar -->|"CRUD"| db
  sidebar -->|"Dati modificati"| app
  app -->|"Debounce 30s"| sync_eng
  sync_eng -->|"Lettura/Scrittura"| db
  sync_eng -->|"Contents API<br/>urllib"| github
  app -->|"Carica/Salva"| settings
```

## Flusso di sincronizzazione

Sequenza sync cross-device: le operazioni CRUD attivano un debounce di 30s, poi export-pull-merge-push in un thread background.

```mermaid
sequenceDiagram
  autonumber
  participant ui as SidebarPanel
  participant app as App
  participant engine as SyncEngine
  participant db as SQLite
  participant gh as API GitHub

  ui->>app: Operazione CRUD
  app->>app: Timer debounce 30s

  Note over app: Timer scaduto

  app->>engine: Avvia thread background
  activate engine
  engine->>db: Esporta stato locale
  db-->>engine: Sezioni + Voci + Tombstone

  engine->>gh: GET file remoto
  gh-->>engine: Stato remoto + SHA

  engine->>db: Applica modifiche remote
  Note over engine,db: Crea/aggiorna voci dal remoto

  engine->>db: Ri-esporta stato locale
  db-->>engine: Stato locale aggiornato

  engine->>engine: Merge last-write-wins per UUID

  engine->>gh: PUT stato unificato con SHA
  gh-->>engine: Nuovo SHA

  engine->>db: Pulizia tombstone oltre 90gg

  deactivate engine
  engine-->>app: Callback GLib.idle_add

  app->>ui: Aggiorna se voci scaricate
```

## Schema database

Tre tabelle: sections e entries (con UUID per identita cross-device), piu tombstones per la propagazione delle cancellazioni.

```mermaid
erDiagram
  SECTIONS {
    int id PK
    text name UK
    text icon
    int position
    int is_default
    datetime created_at
    text uuid UK
    datetime updated_at
  }

  ENTRIES {
    int id PK
    text name
    text content
    int section_id FK
    text type "prompt o shell"
    text tags
    int personal_pos
    datetime created_at
    datetime updated_at
    text uuid UK
  }

  SYNC_TOMBSTONES {
    text uuid PK
    text entity_type "entry o section"
    datetime deleted_at
  }

  SECTIONS ||--o{ ENTRIES : "contiene"
```

## Macchine a stati

### Debounce sincronizzazione

Gli eventi CRUD avviano un timer debounce di 30s. Ogni nuovo CRUD lo resetta. Quando il timer scade, la sync gira in un thread background e ritorna via `GLib.idle_add`.

```mermaid
stateDiagram-v2
  [*] --> Inattivo

  Inattivo --> Attesa : Evento CRUD
  Attesa --> Attesa : Nuovo CRUD resetta timer
  Attesa --> Sincronizzazione : Timeout 30s
  Sincronizzazione --> Inattivo : Successo
  Sincronizzazione --> Inattivo : Errore loggato

  note right of Attesa
    GLib.timeout 30s
    reset ad ogni CRUD
  end note

  note right of Sincronizzazione
    Thread background
    callback via GLib.idle_add
  end note
```

### Health check processo tray

Il processo principale verifica il tray helper ogni 10s. Se il processo e terminato, lo riavvia automaticamente via `subprocess.Popen`.

```mermaid
stateDiagram-v2
  [*] --> In_esecuzione

  In_esecuzione --> In_esecuzione : Health check OK ogni 10s
  In_esecuzione --> Crashato : Processo terminato
  Crashato --> Riavvio : Auto-restart rilevato
  Riavvio --> In_esecuzione : subprocess.Popen

  note right of Crashato
    tray_process.poll
    restituisce exit code
  end note
```

## Gerarchia componenti UI

Albero widget GTK4. Il tray helper gira come processo GTK3 separato, connesso via D-Bus.

```mermaid
graph TD
  app["CommandQuiverApp<br/>Gtk.Application"]
  sidebar["SidebarPanel<br/>Gtk.Window"]
  search["Campo ricerca"]
  paned["Gtk.Paned"]
  section_panel["SectionPanelWidget"]
  section_list["Lista sezioni"]
  new_section["Btn nuova sezione<br/>&#8594; SectionCreateDialog"]
  right_panel["Pannello destro"]
  entry_list["EntryListWidget"]
  entry_row["EntryRow x N<br/>nome | badge | copia | modifica | esegui"]
  sort_dd["Ordinamento DropDown<br/>5 opzioni"]
  bottom_bar["Barra inferiore"]
  new_entry["Btn nuova voce<br/>&#8594; EntryEditorDialog"]
  sync_btn["Btn sync<br/>&#8594; SyncSetupDialog"]
  sync_label["Stato sincronizzazione"]
  tray["tray_helper<br/>processo separato, D-Bus"]

  app --> sidebar
  app -.->|"D-Bus"| tray
  sidebar --> search
  sidebar --> paned
  sidebar --> bottom_bar
  paned --> section_panel
  paned --> right_panel
  section_panel --> section_list
  section_panel --> new_section
  right_panel --> entry_list
  right_panel --> sort_dd
  entry_list --> entry_row
  bottom_bar --> new_entry
  bottom_bar --> sync_btn
  bottom_bar --> sync_label
```
