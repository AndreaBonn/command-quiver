# PromptVault — Specifiche Tecniche e Funzionali

> Documento destinato a Claude Code per lo sviluppo autonomo dell'intero sistema.  
> Versione: 1.0 — Aprile 2026

---

## 1. Panoramica del Progetto

**PromptVault** è un'applicazione desktop per Ubuntu che risiede nella system tray (barra superiore del desktop GNOME). Il suo scopo è fornire accesso rapido a una libreria personale di prompt AI e comandi shell frequentemente utilizzati, organizzati in sezioni, ricercabili per nome e fruibili in un click.

### 1.1 Obiettivo principale

L'utente deve poter:
1. Cliccare sull'icona nella barra superiore
2. Trovare in pochi secondi il prompt o comando cercato
3. Copiarlo negli appunti oppure eseguirlo in un nuovo terminale

---

## 2. Stack Tecnologico

| Componente | Tecnologia | Versione minima |
|---|---|---|
| Linguaggio | Python | 3.10 |
| UI Framework | GTK 4 | 4.0 |
| Tray icon | `libayatana-appindicator3` | 0.5 |
| Database | SQLite 3 (via `sqlite3` stdlib) | 3.35 |
| Packaging | Script bash di installazione | — |
| Esecuzione comandi | `subprocess` + `gnome-terminal` | — |
| Clipboard | `GDK Clipboard` (via GTK4) | — |

### 2.1 Dipendenze di sistema da installare

```
python3
python3-gi
python3-gi-cairo
gir1.2-gtk-4.0
gir1.2-ayatanaappindicator3-0.1
libayatana-appindicator3-1
gnome-terminal
```

### 2.2 Struttura dei file del progetto

```
promptvault/
├── main.py                  # Entry point
├── app.py                   # AppIndicator + gestione ciclo di vita
├── ui/
│   ├── sidebar.py           # Pannello laterale principale
│   ├── entry_list.py        # Lista delle voci con ordinamento/ricerca
│   ├── entry_editor.py      # Dialog di creazione/modifica voce
│   └── section_manager.py   # Dialog gestione sezioni
├── db/
│   ├── database.py          # Connessione e inizializzazione SQLite
│   └── queries.py           # Tutte le query CRUD
├── core/
│   ├── executor.py          # Logica esecuzione comandi in terminale
│   └── clipboard.py         # Copia negli appunti
├── assets/
│   └── icon.png             # Icona tray (32x32 px, formato PNG)
├── install.sh               # Script di installazione
├── uninstall.sh             # Script di rimozione
└── README.md
```

---

## 3. Schema del Database

Il database SQLite viene salvato in `~/.local/share/promptvault/vault.db`.

### 3.1 Tabella `sections`

```sql
CREATE TABLE IF NOT EXISTS sections (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    icon        TEXT DEFAULT 'folder',        -- nome icona GTK
    position    INTEGER NOT NULL DEFAULT 0,   -- ordine personalizzato
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### 3.2 Tabella `entries`

```sql
CREATE TABLE IF NOT EXISTS entries (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL,              -- nome/titolo dell'entry (ricercabile)
    content       TEXT NOT NULL,              -- corpo del prompt o comando
    section_id    INTEGER REFERENCES sections(id) ON DELETE SET NULL,
    type          TEXT DEFAULT 'prompt'       -- 'prompt' | 'shell'
                  CHECK(type IN ('prompt', 'shell')),
    tags          TEXT DEFAULT '',            -- tag separati da virgola
    personal_pos  INTEGER DEFAULT 0,          -- posizione per ordine personale
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at    DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### 3.3 Dati iniziali

All'installazione, creare le seguenti sezioni di default:

```sql
INSERT INTO sections (name, icon, position) VALUES
    ('Shell Commands', 'utilities-terminal', 0),
    ('AI Prompts',     'format-text-bold',   1),
    ('Git',            'vcs-commit',          2),
    ('Generale',       'folder',              3);
```

---

## 4. Funzionalità — Descrizione Dettagliata

### 4.1 Tray Icon

- L'app si avvia in background senza aprire finestre
- Mostra un'icona nella system tray GNOME tramite `AppIndicator3`
- Click sinistro sull'icona → apre/chiude il pannello laterale
- Click destro → menu contestuale con: `Mostra/Nascondi`, `Nuova voce`, `Separatore`, `Esci`
- L'icona è un file PNG 32×32 px incluso in `assets/icon.png`

### 4.2 Pannello Laterale (Sidebar)

Il pannello laterale è una finestra GTK senza bordi decorativi che si posiziona automaticamente vicino all'icona nella barra superiore.

**Layout del pannello:**

```
┌────────────────────────────────────┐
│ 🔍 [Cerca per nome...          ]   │
├──────────────┬─────────────────────┤
│ SEZIONI      │ LISTA VOCI          │
│              │                     │
│ ▶ Tutti (42) │ [nome]  [tipo] [⎘] [▶]│
│   Shell (15) │ [nome]  [tipo] [⎘] [▶]│
│   AI (20)    │ ...                 │
│   Git (5)    │                     │
│   Generale(2)│                     │
│              │                     │
│ [+ Sezione]  │ Ordina: ▼           │
├──────────────┴─────────────────────┤
│ [+ Nuova voce]          [Gestisci] │
└────────────────────────────────────┘
```

**Dimensioni pannello:** larghezza 520px, altezza 600px.

**Comportamento:** il pannello si chiude automaticamente quando l'utente clicca fuori da esso (focus-out).

### 4.3 Ricerca

- Campo di ricerca in cima al pannello
- Ricerca **in tempo reale** (on-change) sul campo `name` delle entry
- La ricerca filtra le voci della sezione attualmente selezionata (oppure tutte se selezionato "Tutti")
- Case-insensitive, ricerca per sottostringa (`LIKE '%query%'`)
- Se la ricerca è attiva, disabilitare il cambio di ordinamento (mostrare risultati di ricerca flat)

### 4.4 Sezioni

- La colonna sinistra mostra la lista delle sezioni con il conteggio delle voci
- "Tutti" è sempre la prima voce e mostra tutte le entry aggregate
- Click su una sezione → filtra la lista destra
- Sezione attiva evidenziata visivamente
- Bottone `[+ Sezione]` in fondo alla lista → apre dialog di creazione sezione
- Tasto destro su una sezione → menu: `Rinomina`, `Elimina`
- Eliminare una sezione non elimina le voci: vengono spostate in "Generale"

### 4.5 Lista delle Voci

Ogni riga della lista mostra:
- **Nome** della voce (testo principale, troncato se > 40 caratteri)
- **Badge tipo**: etichetta colorata `SHELL` (verde) o `PROMPT` (blu)
- **Bottone Copia** `⎘` → copia il contenuto negli appunti
- **Bottone Esegui** `▶` → apre gnome-terminal ed esegue (visibile solo se `type == 'shell'`)
- **Click sulla riga** → apre il pannello di dettaglio/modifica

**Ordinamento** (menu a tendina in basso a destra della lista):
- Alfabetico A→Z
- Alfabetico Z→A
- Cronologico (più recenti prima)
- Cronologico (più vecchi prima)
- Personale (drag-and-drop, posizione salvata in `personal_pos`)

L'ordinamento selezionato viene salvato in `~/.config/promptvault/settings.json` e ripristinato all'avvio.

### 4.6 Dettaglio / Editor Voce

Apre una finestra modale (dialog GTK) con i seguenti campi:

| Campo | Tipo | Obbligatorio | Note |
|---|---|---|---|
| Nome | Text input | ✅ | Max 100 caratteri |
| Tipo | Radio button | ✅ | `Prompt AI` / `Comando Shell` |
| Sezione | Dropdown | ✅ | Lista sezioni esistenti |
| Contenuto | Text area | ✅ | Multiriga, font monospace, syntax highlight base |
| Tag | Text input | ❌ | Tag separati da virgola |

**Bottoni della dialog:**
- `Salva` → salva e chiude
- `Salva e Copia` → salva, copia il contenuto negli appunti, chiude
- `Annulla` → chiude senza salvare
- `Elimina` (rosso, solo in modalità modifica) → richiede conferma, poi elimina

**Shortcut da tastiera nell'editor:**
- `Ctrl+S` → Salva
- `Ctrl+W` / `Escape` → Annulla/Chiudi
- `Ctrl+Enter` → Salva e Copia

### 4.7 Esecuzione Comandi nel Terminale

Quando l'utente preme `▶` su una voce di tipo `shell`:

1. Il comando viene eseguito tramite:
```python
subprocess.Popen([
    'gnome-terminal',
    '--',
    'bash', '-c',
    f'{command}; echo "\n--- Premere INVIO per chiudere ---"; read'
])
```

2. La riga `echo + read` garantisce che la finestra rimanga aperta dopo l'esecuzione per leggere l'output.

3. Dopo aver lanciato il terminale, il pannello laterale rimane aperto.

**Nota:** non è richiesta la selezione di terminali già aperti — viene sempre aperta una nuova finestra di gnome-terminal.

### 4.8 Copia negli Appunti

```python
# Usando GDK Clipboard tramite GTK4
clipboard = Gdk.Display.get_default().get_clipboard()
clipboard.set(content)
```

Dopo la copia, mostrare una notifica visiva non invasiva: il bottone `⎘` cambia temporaneamente icona/colore per 1.5 secondi (feedback visivo inline, senza popup).

---

## 5. Gestione Impostazioni

File: `~/.config/promptvault/settings.json`

```json
{
  "sort_order": "chronological_desc",
  "last_section_id": null,
  "window_width": 520,
  "window_height": 600,
  "theme": "auto"
}
```

- `sort_order`: uno tra `alpha_asc`, `alpha_desc`, `chronological_asc`, `chronological_desc`, `personal`
- `last_section_id`: ID sezione selezionata all'ultima chiusura (null = "Tutti")
- `theme`: `auto` segue il tema di sistema GNOME (light/dark)

---

## 6. Script di Installazione (`install.sh`)

Lo script deve:

1. Verificare che il sistema sia Ubuntu (esci con errore se non lo è)
2. Installare le dipendenze di sistema via `apt`
3. Creare la directory `~/.local/share/promptvault/`
4. Creare la directory `~/.config/promptvault/`
5. Copiare i file dell'applicazione in `~/.local/share/promptvault/`
6. Creare il file `.desktop` per l'autostart:

```ini
# ~/.config/autostart/promptvault.desktop
[Desktop Entry]
Type=Application
Name=PromptVault
Exec=python3 /home/USER/.local/share/promptvault/main.py
Icon=/home/USER/.local/share/promptvault/assets/icon.png
Comment=Accesso rapido a prompt e comandi shell
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
```

7. Creare un symlink `/usr/local/bin/promptvault` → `main.py` per avvio da terminale
8. Inizializzare il database SQLite con lo schema e i dati di default
9. Avviare l'applicazione al termine dell'installazione
10. Stampare un riepilogo con istruzioni post-installazione

---

## 7. Script di Disinstallazione (`uninstall.sh`)

1. Terminare il processo `promptvault` se in esecuzione
2. Rimuovere il file `.desktop` dall'autostart
3. Rimuovere il symlink da `/usr/local/bin/`
4. Chiedere conferma prima di eliminare `~/.local/share/promptvault/` (contiene il database)
5. Chiedere conferma prima di eliminare `~/.config/promptvault/` (contiene le impostazioni)

---

## 8. Comportamento Edge Case

| Scenario | Comportamento atteso |
|---|---|
| `gnome-terminal` non installato | Mostrare dialog di errore con istruzione di installazione |
| Database corrotto o mancante | Ricrearlo automaticamente da zero |
| Sezione eliminata con voci | Voci spostate in "Generale" automaticamente |
| Nome voce duplicato nella stessa sezione | Consentito, non è un errore |
| Contenuto voce vuoto | Impedire il salvataggio, mostrare validazione inline |
| Nome voce vuoto | Impedire il salvataggio, mostrare validazione inline |
| App già in esecuzione al secondo avvio | Mostrare/nascondere il pannello esistente (single instance) |
| GNOME non disponibile (Wayland/X11 misto) | Loggare warning, tentare comunque l'avvio |

---

## 9. Requisiti Non Funzionali

- **Avvio:** il pannello deve aprirsi entro 200ms dal click sull'icona
- **Ricerca:** il filtraggio deve essere percepibilmente istantaneo (< 50ms per librerie fino a 500 voci)
- **Memoria:** footprint RAM in idle < 60 MB
- **Single instance:** se l'utente lancia `main.py` una seconda volta, non aprire una seconda istanza ma mostrare il pannello di quella già in esecuzione (usare lock file in `/tmp/promptvault.lock`)
- **Compatibilità:** Ubuntu 22.04 LTS e superiori

---

## 10. Icona dell'Applicazione

In assenza di un file `assets/icon.png`, generare programmaticamente un'icona SVG semplice (lettera "P" stilizzata su sfondo scuro) e convertirla in PNG 32×32 e 64×64 usando `cairosvg` o PIL. L'icona deve essere leggibile sia su tray chiara che scura.

---

## 11. Ordine di Sviluppo Consigliato

Seguire questo ordine per uno sviluppo incrementale e testabile:

1. **Database** — schema, CRUD, query (`db/`)
2. **Core** — clipboard, executor (`core/`)
3. **App base** — tray icon, ciclo di vita (`app.py`, `main.py`)
4. **UI Sidebar** — struttura pannello, sezioni, lista voci
5. **UI Editor** — dialog creazione/modifica
6. **Ricerca e ordinamento**
7. **Impostazioni persistenti**
8. **Script install/uninstall**
9. **Test edge case e polish UI**

---

## 12. Note per Claude Code

- Usare esclusivamente **GTK4** (non GTK3) per tutti i widget UI
- Non usare `Tkinter` o altre UI alternative
- Il codice deve essere compatibile con **Python 3.10+** senza dipendenze pip esterne (solo stdlib + PyGObject)
- Tutti i path devono usare `pathlib.Path` per portabilità
- Il database deve essere accessibile solo dal thread principale (GTK è single-threaded)
- Usare `GLib.idle_add` se necessario per aggiornamenti UI da callback
- Aggiungere logging su file in `~/.local/share/promptvault/logs/app.log` con rotazione (max 1 MB, 3 backup)
- Il codice deve essere commentato in italiano
- Ogni modulo deve avere una docstring con descrizione, autore e data

---

*Fine documento — PromptVault v1.0 Specs*
