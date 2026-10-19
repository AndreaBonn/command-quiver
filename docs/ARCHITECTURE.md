**English** | [Italiano](ARCHITECTURE.it.md)

# Technical Architecture

Developer reference with detailed diagrams of Command Quiver internals.

## System Architecture

GTK4 main process and GitHub sync via Contents API.

```mermaid
%%{init: {'theme': 'default'}}%%
graph LR
  subgraph main_proc["Main Process - GTK4"]
    direction TB
    app["CommandQuiverApp"]
    sidebar["SidebarPanel"]
    sync_eng["SyncEngine"]
    db[("SQLite vault.db")]
    settings["Settings JSON"]
  end

  github["GitHub Private Repo"]

  app --> sidebar
  sidebar -->|"CRUD"| db
  sidebar -->|"Data changed"| app
  sidebar -->|"Language switch"| app
  app -->|"Debounce 30s"| sync_eng
  sync_eng -->|"Read/Write"| db
  sync_eng -->|"Contents API<br/>urllib"| github
  app -->|"Load/Save"| settings

  classDef core fill:#2563eb,stroke:#1d4ed8,color:#fff
  classDef data fill:#d97706,stroke:#b45309,color:#fff
  classDef ext fill:#6b7280,stroke:#4b5563,color:#fff
  classDef engine fill:#059669,stroke:#047857,color:#fff

  class app,sidebar core
  class db,settings data
  class github ext
  class sync_eng engine
```

## Sync Flow

Cross-device sync sequence: CRUD triggers a 30s debounce, then export-pull-merge-push in a background thread.

```mermaid
sequenceDiagram
  autonumber
  participant ui as SidebarPanel
  participant app as App
  participant engine as SyncEngine
  participant db as SQLite
  participant gh as GitHub API

  ui->>app: CRUD operation
  app->>app: Debounce timer 30s

  Note over app: Timer fires

  app->>engine: Start background thread
  activate engine
  engine->>db: Export local state
  db-->>engine: Sections + Entries + Tombstones

  engine->>gh: GET remote file
  gh-->>engine: Remote state + SHA

  engine->>db: Apply remote changes
  Note over engine,db: Create/update entries from remote

  engine->>db: Re-export local state
  db-->>engine: Updated local state

  engine->>engine: Merge last-write-wins by UUID

  engine->>gh: PUT merged state with SHA
  gh-->>engine: New SHA

  engine->>db: Cleanup tombstones older than 90d

  deactivate engine
  engine-->>app: GLib.idle_add callback

  app->>ui: Refresh if entries pulled
```

## Database Schema

Three tables: sections and entries (with UUID for cross-device identity), plus tombstones for deletion propagation.

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
    text type "prompt or shell"
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
    text entity_type "entry or section"
    datetime deleted_at
  }

  SECTIONS ||--o{ ENTRIES : "contains"
```

## State Machines

### Sync Debounce

CRUD events start a 30s debounce timer. Each new CRUD resets it. When the timer fires, sync runs in a background thread and returns via `GLib.idle_add`.

```mermaid
stateDiagram-v2
  [*] --> Idle

  Idle --> Debouncing : CRUD event
  Debouncing --> Debouncing : New CRUD resets timer
  Debouncing --> Syncing : 30s timeout
  Syncing --> Idle : Success
  Syncing --> Idle : Error logged

  note right of Debouncing
    GLib.timeout 30s
    resets on each CRUD
  end note

  note right of Syncing
    Background thread
    callback via GLib.idle_add
  end note
```

### Application Lifecycle

The main window is the application: closing it (close button or `Ctrl+Q`) runs a final sync, saves state, and quits via `do_shutdown`.

```mermaid
stateDiagram-v2
  [*] --> Starting

  Starting --> Active : do_startup + do_activate
  Active --> Active : Language switch rebuilds sidebar
  Active --> ShuttingDown : Window closed (X or Ctrl+Q)
  ShuttingDown --> [*] : Final sync + save + db.close

  note right of ShuttingDown
    do_shutdown
    final sync timeout 5s
  end note
```

## UI Component Hierarchy

GTK4 widget tree of the main window. Dialogs are separate `Gtk.Window`s opened from the widgets that point to them.

```mermaid
%%{init: {'theme': 'default'}}%%
graph TD
  app["CommandQuiverApp<br/>Gtk.Application"]
  sidebar["SidebarPanel<br/>Gtk.Window"]
  header["HeaderBar"]
  new_entry["New btn<br/>&#8594; EntryEditorDialog"]
  menu["Main menu &#9776;<br/>language, sync, import/export,<br/>shortcuts, about, quit"]
  search_bar["SearchBar"]
  search["SearchEntry<br/>names, content, tags"]
  sort_dd["Sort DropDown<br/>6 options"]
  paned["Gtk.Paned"]
  section_panel["SectionPanelWidget"]
  section_row["SectionRow x N<br/>icon | name | count | menu"]
  new_section["+ Section btn<br/>&#8594; SectionNameDialog"]
  toast["ToastOverlay<br/>copied, deleted + Undo"]
  entry_list["EntryListWidget"]
  entry_row["EntryRow x N<br/>name | preview | tags | badge<br/>edit | copy | run"]
  empty["Empty state<br/>welcome, empty section, no results"]
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
