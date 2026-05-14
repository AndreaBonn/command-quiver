**English** | [Italiano](ARCHITECTURE.it.md)

# Technical Architecture

Developer reference with detailed diagrams of Command Quiver internals.

## System Architecture

GTK4 main process, GTK3 tray process (separate for compatibility), and GitHub sync via Contents API.

```mermaid
graph LR
  subgraph main_proc["Main Process - GTK4"]
    direction TB
    app["CommandQuiverApp"]
    sidebar["SidebarPanel"]
    sync_eng["SyncEngine"]
    db[("SQLite vault.db")]
    settings["Settings JSON"]
  end

  subgraph tray_proc["Separate Process - GTK3"]
    tray["tray_helper.py<br/>AyatanaAppIndicator3"]
  end

  github["GitHub Private Repo"]

  tray -->|"D-Bus: Toggle, NewEntry,<br/>ChangeLanguage, Quit"| app
  app -->|"Health check 10s<br/>+ auto-restart"| tray
  app --> sidebar
  sidebar -->|"CRUD"| db
  sidebar -->|"Data changed"| app
  app -->|"Debounce 30s"| sync_eng
  sync_eng -->|"Read/Write"| db
  sync_eng -->|"Contents API<br/>urllib"| github
  app -->|"Load/Save"| settings
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

### Tray Process Health Check

The main process polls the tray helper every 10s. If the process has exited, it auto-restarts via `subprocess.Popen`.

```mermaid
stateDiagram-v2
  [*] --> Running

  Running --> Running : Health check OK every 10s
  Running --> Crashed : Process exited
  Crashed --> Restarting : Auto-restart detected
  Restarting --> Running : subprocess.Popen

  note right of Crashed
    tray_process.poll
    returns exit code
  end note
```

## UI Component Hierarchy

GTK4 widget tree. The tray helper runs as a separate GTK3 process, connected via D-Bus.

```mermaid
graph TD
  app["CommandQuiverApp<br/>Gtk.Application"]
  sidebar["SidebarPanel<br/>Gtk.Window"]
  search["SearchEntry"]
  paned["Gtk.Paned"]
  section_panel["SectionPanelWidget"]
  section_list["Section ListBox"]
  new_section["New Section btn<br/>&#8594; SectionCreateDialog"]
  right_panel["Right Panel"]
  entry_list["EntryListWidget"]
  entry_row["EntryRow x N<br/>name | badge | copy | edit | exec"]
  sort_dd["Sort DropDown<br/>5 options"]
  bottom_bar["Bottom Bar"]
  new_entry["New Entry btn<br/>&#8594; EntryEditorDialog"]
  sync_btn["Sync btn<br/>&#8594; SyncSetupDialog"]
  sync_label["Sync status label"]
  tray["tray_helper<br/>separate process, D-Bus"]

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
