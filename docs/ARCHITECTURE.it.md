[English](ARCHITECTURE.md) | **Italiano**

# Architettura tecnica

Reference tecnico con diagrammi dettagliati degli internals di Command Quiver.

## Architettura di sistema

Processo principale GTK4 e sync GitHub via Contents API.

```mermaid
%%{init: {'theme': 'default'}}%%
graph LR
  subgraph main_proc["Processo principale - GTK4"]
    direction TB
    app["CommandQuiverApp"]
    sidebar["SidebarPanel"]
    sync_eng["SyncEngine"]
    db[("SQLite vault.db")]
    settings["Impostazioni JSON"]
  end

  github["Repo privato GitHub"]

  app --> sidebar
  sidebar -->|"CRUD"| db
  sidebar -->|"Dati modificati"| app
  sidebar -->|"Cambio lingua"| app
  app -->|"Debounce 30s"| sync_eng
  sync_eng -->|"Lettura/Scrittura"| db
  sync_eng -->|"Contents API<br/>urllib"| github
  app -->|"Carica/Salva"| settings

  classDef core fill:#2563eb,stroke:#1d4ed8,color:#fff
  classDef data fill:#d97706,stroke:#b45309,color:#fff
  classDef ext fill:#6b7280,stroke:#4b5563,color:#fff
  classDef engine fill:#059669,stroke:#047857,color:#fff

  class app,sidebar core
  class db,settings data
  class github ext
  class sync_eng engine
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
    int use_count
    datetime last_used_at
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

### Ciclo di vita dell'applicazione

La finestra principale è l'applicazione: chiudendola (pulsante di chiusura o `Ctrl+Q`) viene eseguita una sincronizzazione finale, salvato lo stato e l'app termina via `do_shutdown`.

```mermaid
stateDiagram-v2
  [*] --> Avvio

  Avvio --> Attiva : do_startup + do_activate
  Attiva --> Attiva : Cambio lingua ricostruisce la sidebar
  Attiva --> Chiusura : Finestra chiusa (X o Ctrl+Q)
  Chiusura --> [*] : Sync finale + salvataggio + db.close

  note right of Chiusura
    do_shutdown
    sync finale timeout 5s
  end note
```

## Gerarchia componenti UI

Albero dei widget GTK4 della finestra principale. I dialog sono `Gtk.Window` separate, aperte dai widget che puntano a loro.

```mermaid
%%{init: {'theme': 'default'}}%%
graph TD
  app["CommandQuiverApp<br/>Gtk.Application"]
  sidebar["SidebarPanel<br/>Gtk.Window"]
  header["HeaderBar"]
  new_entry["Pulsante Nuova<br/>&#8594; EntryEditorDialog"]
  menu["Menu principale &#9776;<br/>lingua, sincronizzazione, import/export,<br/>scorciatoie, informazioni, esci"]
  search_bar["SearchBar"]
  search["SearchEntry<br/>nomi, contenuti, tag"]
  sort_dd["Sort DropDown<br/>6 opzioni"]
  paned["Gtk.Paned"]
  section_panel["SectionPanelWidget"]
  section_row["SectionRow x N<br/>icona | nome | conteggio | menu"]
  new_section["Pulsante + Sezione<br/>&#8594; SectionNameDialog"]
  toast["ToastOverlay<br/>copiato, eliminato + Annulla"]
  entry_list["EntryListWidget"]
  entry_row["EntryRow x N<br/>nome | anteprima | tag | badge<br/>modifica | copia | esegui"]
  empty["Stato vuoto<br/>benvenuto, sezione vuota, nessun risultato"]
  run_confirm["RunConfirmDialog"]
  status_bar["SyncStatusBar<br/>&#8594; SyncSetupDialog"]

  app --> sidebar
  sidebar --> header
  sidebar --> search_bar
  sidebar --> paned
  sidebar --> status_bar
  header --> new_entry
  header --> menu
  search_bar --> search
  search_bar --> sort_dd
  paned --> section_panel
  paned --> toast
  section_panel --> section_row
  section_panel --> new_section
  toast --> entry_list
  entry_list --> entry_row
  entry_list --> empty
  entry_row --> run_confirm

  classDef root fill:#1d4ed8,stroke:#1e40af,color:#fff
  classDef container fill:#2563eb,stroke:#1d4ed8,color:#fff
  classDef leaf fill:#bfdbfe,stroke:#3b82f6,color:#1e3a5f
  classDef action fill:#d97706,stroke:#b45309,color:#fff

  class app root
  class sidebar,header,search_bar,paned,section_panel,toast,entry_list container
  class search,sort_dd,section_row,entry_row,empty leaf
  class new_entry,menu,new_section,run_confirm,status_bar action
```
