# Spec: scomposizione god-module e copertura comportamentale

## Requisiti
- R1 Nessuna regressione: dopo ogni commit `uv run pytest` verde, numero di test passati >= commit precedente.
- R2 db: nessun file > 300 righe, nessuna classe > 200 righe sotto command_quiver/db/.
- R3 sync: merge LWW, tombstone e piano delle modifiche remote in un modulo puro (nessun import di sqlite3,
  urllib, db.*, settings); sync_engine.py resta shell I/O.
- R4 database.py: DDL/migrazioni e backup fuori dalla classe Database; classe <= 200 righe.
- R5 Ogni funzione creata o spostata <= 30 righe e <= 4 parametri (metrica: righe fisiche def..fine, docstring
  incluse, misurate con scratchpad/measure.py). Firme imposte da GTK escluse.
- R6 Copertura `--cov-branch`: totale >= 95%; 100% su core/sync_merge.py, core/sync_engine.py,
  core/github_client.py, core/settings.py, db/*. Ogni riga residua scoperta elencata con motivo; nessun
  `# pragma: no cover` senza approvazione.
- R7 Qualità test: ogni test nuovo visto rosso (mutazione manuale del codice e ripristino) nello stesso task;
  nessuna asserzione solo `is not None`; ogni asserzione negativa con caso positivo appaiato; boundary finti solo
  su rete (urlopen / client GitHub) e orologio, SQLite reale su tmp_path.
- R8 Contratti invariati: formato JSON di sync (chiavi, FORMAT_VERSION=1), schema DDL e PRAGMA user_version,
  `SyncEngine(db=, settings=).sync() -> SyncResult`, messaggi utente, formato export/import della libreria.
- R9 Commit atomici su main (autorizzato): 1 cambiamento logico, Conventional Commits in inglese,
  `uv run ruff check .` e `uv run ruff format --check .` verdi. Nessun push (non autorizzato).
- R10 Anomalie trovate segnalate nel report e mai corrette in silenzio dentro un refactor:
  ognuna ha il suo commit `fix(...)` con test di regressione (vedi § Decisioni, A6).
- R11 Floor CI rialzato: `--cov-branch --cov-fail-under=<misurato - 1>`.

## Definition of Done
- [ ] R1: `uv run pytest -q` verde a ogni commit (verificato da hook e a mano prima di `git commit`).
- [ ] R2/R4/R5: `python3 -I scratchpad/measure.py command_quiver | grep -E "db/|sync_"` vuoto.
- [ ] R3: `grep -nE "^(import|from) (sqlite3|urllib|command_quiver\.(db|core\.settings))" command_quiver/core/sync_merge.py` vuoto.
- [ ] R6: `uv run pytest --cov=command_quiver --cov-branch --cov-report=term-missing` mostra TOTAL >= 95% e 100% sui
      moduli elencati.
- [ ] R8: test di caratterizzazione T1/T6/T12 verdi senza modifiche dopo ogni spostamento (gli import nei test
      possono cambiare, le asserzioni no).
- [ ] Esempio (Given/When/Then): Given dispositivo A con voce "ls" aggiornata alle 10:00 e remoto con stessa uuid
      aggiornata alle 09:00, When A esegue sync, Then il JSON pushato contiene "ls" versione A ed entries_pushed == 1.
- [ ] Esempio errore: Given remoto con content "{rotto", When sync, Then SyncResult(success=False) e messaggio
      che inizia con "Dati remoti corrotti", nessuna eccezione propagata.
- [ ] `grep -rn "db.queries" command_quiver tests` vuoto (se D1 = B).
- [ ] CLAUDE.md sezione Struttura aggiornata ai nuovi moduli.

## Assunzioni
- A1 Metrica dei limiti = righe fisiche con docstring (la più severa). Se l'utente intende righe di codice
  il piano non cambia, cambia solo il margine.
- A2 Lingua: commenti e docstring in italiano come da CLAUDE.md di progetto (prevale sul default globale inglese);
  identificatori e commit in inglese.
- A3 Test GTK eseguiti con display (qui DISPLAY=:1, in CI xvfb-run). Senza display i test UI si skippano e la
  copertura R6 non è misurabile: la misura vale solo con display.
- A4 Nessun consumatore esterno di command_quiver.db.queries (app, non libreria): il re-export serve solo agli
  import interni.
- A5 Le file UI fra 265 e 298 righe sono sotto soglia: non si toccano (tabella decisione: guadagno nullo, righe in
  più -> scarta). Le classi UI > 200 righe sono D2.
- A6 [BLOCCANTE da confermare] I bug di prodotto trovati (B1-B3 sotto) restano fuori dal refactor e vanno in
  commit `fix(...)` separati solo dopo una decisione sulla spec.


## Decisioni dell'orchestratore (2026-10-19, autonomia concessa dall'utente)

- A6: i bug B1-B5 si correggono, uno per commit `fix(...)` con test di regressione, prima del
  refactor del sync. Richiesta dell'utente: "se in questo flusso trovi errori o problemi,
  risolvili tutti prima di proseguire". R10 resta valido per il refactor: nessun fix mescolato
  a uno spostamento.
- B1 default: al pull, una sezione remota con nome già presente in locale e uuid diverso
  adotta l'uuid remoto sulla sezione locale (fusione per nome, nessuna voce persa).
- D2: classi UI valutate a fine lavoro, una per una; si estrae solo logica pura con guadagno reale.
- D5: DC1 semplificato; DC4 loggato invece di ingoiato.

## Registro bug (validazione database-reviewer + probe, 2026-10-19)

| Id | Difetto | BASIS | Decisione |
|---|---|---|---|
| B1 | Sezione remota con nome già presente in locale e uuid diverso: IntegrityError UNIQUE(name), sync fallito con "Errore interno" | measured | fix: adozione uuid remoto; conflitto da rename concorrente loggato e saltato |
| B2 | Timestamp misti (UTC con spazio vs locale con "T") confrontati come stringhe nel LWW | measured | fix: parse_ts normalizzato nei confronti, scritture nuove in UTC ISO |
| B3 | Il pull applica le tombstone remote senza confrontarle con updated_at locale; salta entità remote più recenti della tombstone (B3b); ricrea voci cancellate in locale perché ignora le tombstone locali (B7) | measured | fix unico: il pull usa le tombstone unite e la stessa regola del merge |
| B4 | Tombstone registrata anche quando la delete remota della sezione di default viene rifiutata | measured | fix: registrare solo se la delete è avvenuta |
| B5 | position e is_default delle sezioni remote ignorati al pull | measured | non si corregge: onorare position senza riordino sezioni dà ordinamenti non deterministici |
| B6 | Sezioni del seed senza uuid/updated_at fino al secondo avvio | measured | fix: uuid assegnati anche dopo il seed |
| B8 | Delete e scrittura tombstone in due commit separati | measured | fix: stessa transazione |
| B9 | _recreate non esegue migrazioni né assegna uuid | inferred | verificare, poi fix |
| B10 | Voce remota la cui sezione è stata cancellata finisce con section_id NULL, invisibile | inferred | fix: risolvere alla sezione Generale, come la delete locale |
| B11 | PUT 404 (repo errato o privato senza accesso) diventava errore con status 0: l'utente leggeva "controlla la rete" | measured | fix: status_code 404, messaggio "repository non trovato" |
| B12 | create/create_with_uuid restituivano una Section senza created_at | measured | fix: restituiscono la riga salvata |

## D2: classi UI e funzioni lunghe (valutazione architect, 2026-10-19)

Si scompone solo dove emerge logica pura o si toglie codice:
- U1 SyncCoordinator estratto da app.py (invariante "una sola sync alla volta" testabile con scheduler ed engine finti) + _replace_sidebar
- U2 SectionCreateDialog e SectionRenameDialog fusi in un dialog unico + validate_section_name pura
- U3 EntryRow/EntryListWidget: via la doppia API di callback legacy (solo RowCallbacks)
- U4 section_panel: visible_counts e row_index_for pure, menu della sezione in section_row
- U5 SidebarPanel riceve SidebarCallbacks invece di 4 callback, _install_actions estratto
- U6 entry_editor: TypeSelector in editor_widgets, _submit(copy) al posto dei due salvataggi gemelli, editor_command pura
- U7 github_client: _build_request pura
Restano sopra i limiti, come eccezione dichiarata: SidebarPanel (~240, composizione della finestra),
EntryEditorDialog (~215), costruttori dichiarativi di widget, firme imposte da GTK, funzioni lunghe
per sola docstring.

| B13 | EntryRepository.get_all tronca a 500 voci senza avviso, il conteggio "Tutti" no | inferred | decisione utente: togliere il cap, paginare o avvisare |
| B14 | La suite di test scriveva il vero ~/.config/command-quiver/settings.json (sync disattivato) | measured | fix: fixture autouse di isolamento |
| B15 | Un comando con "# commento" finale chiudeva subito il terminale | measured | fix: epilogo su riga nuova |
| B16 | Database occupato ("locked") ricreato come se fosse corrotto; -wal/-shm lasciati orfani | inferred | fix: niente ricreazione sul lock, journal spostati col backup |
| B17 | Sync finale, timeout di rete in lettura, timestamp e backup parziali: errori fuori dal log o eccezioni grezze | inferred | fix: log ed errori applicativi (silent-failure-hunter) |
