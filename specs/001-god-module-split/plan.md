# Piano RPI: scomposizione god-module e copertura comportamentale, Command Quiver

Data: 2026-10-19. Repo: /home/bonn/Documenti/00_Lavoro/ProgettiPersonali/command-quiver (main @ 9799abc, pulito).

## Obiettivo
I tre god-module (db/queries.py, core/sync_engine.py, db/database.py) sono scomposti in moduli coesi entro i limiti
di code-standards, la logica di merge del sync è un functional core puro, e la copertura line+branch arriva a >= 95%
totale con 100% sui moduli dati/sync, con test che falliscono se il comportamento cambia. Ogni commit su main lascia
la suite verde.

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
- R10 Anomalie trovate segnalate nel report, non corrette in silenzio dentro un refactor.
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

## Approccio e decisioni
### D1 Facciata db/queries.py: NO a regime, SÌ transitoria dentro la fase 2
- Opzione A, facciata permanente: zero churn sui 21 file importatori (11 prod, 10 test); resta un secondo percorso
  di import senza significato, e il file esiste già come shim "per backward compatibility" dei modelli.
- Opzione B, import aggiornati e queries.py eliminato: un percorso solo per ogni simbolo, modelli importati da
  db.models; costo un commit meccanico su 21 file, verificabile con grep.
- Raccomandata B con passaggio transitorio: T7-T10 spostano il codice lasciando queries.py come re-export (suite
  verde a ogni commit), T11 aggiorna gli import e cancella il file. Motivo: nessun consumatore esterno (A4), lo
  shim permanente è quello che code-standards scoraggia, e la modifica è tracciabile alla richiesta.

### D2 Classi UI > 200 righe (CommandQuiverApp 237, EntryEditorDialog 261, SectionPanelWidget 231, SidebarPanel 251)
Sono widget GTK sotto soglia di file, non god-module. Default: fuori scope di questo piano, lista nel report.
Se l'utente le vuole dentro, servono un piano dedicato e test GTK di caratterizzazione prima.
**Superato (2026-10-19)**: l'utente ha chiesto di scomporre tutto ciò che è scomponibile; dopo i test GTK di
caratterizzazione sono state eseguite U1-U7 (spec.md § D2). Restano eccezioni dichiarate SidebarPanel ed EntryEditorDialog.

### D3 Separazione dei repository
Il confine di consumo è netto: la UI usa solo operazioni per id, il sync solo operazioni per uuid. Si separa su
questo confine, non per entità:
- db/section_repository.py SectionRepository (UI: get_all, get_by_id, get_default_section_id, exists, create,
  rename, delete) ~150 righe
- db/entry_repository.py EntryRepository (UI: get_all, get_by_id, bump_usage, create, update, delete,
  update_position, count_all, export_all) + costante ENTRY_SELECT condivisa ~190 righe
- db/tombstone_repository.py TombstoneRepository (get_all, add, cleanup); i due `_add_tombstone` duplicati
  diventano chiamate a TombstoneRepository.add ~40 righe
- db/sync_repository.py SyncRepository (uuid: get_section/entry_by_uuid, create_section_with_uuid,
  update_section/entry_from_sync, create_entry_from_sync, delete_*_by_uuid, export_for_sync). delete section per
  uuid delega a SectionRepository.delete (composizione) per conservare l'invariante "voci spostate in Generale".
  I parametri 8 e 7 diventano un dataclass SyncedEntry in db/models.py ~170 righe
- db/entry_import.py import_entries(data, *, entry_repo, section_repo) + funzione pura normalize_import_item
  (troncamento, fallback di tipo) ~70 righe
Restano insieme: delete + scrittura tombstone (stesso invariante), get_all + _SORT_CLAUSES.

### D4 sync_engine: core puro e shell
- core/sync_merge.py (puro, `now` iniettato): FORMAT_VERSION, build_sync_state(sections, entries, tombstones, *, now),
  merge_tombstones, merge_entities (LWW, tie -> locale, tombstone vince solo se strettamente più recente),
  merge_states(local, remote, *, now), count_pushed, plan_remote_changes(local, remote) -> RemoteChangePlan
  (tombstones da applicare, sezioni da creare/aggiornare, voci da creare/aggiornare, con section_uuid).
- core/sync_engine.py (shell): humanize_github_error (testo d'errore, resta qui), SyncResult, SyncEngine con
  _create_client, sync() spezzato in _pull_and_apply / _push / _record_success, _export_local (legge repo, chiama
  build_sync_state), _apply_plan (esegue il piano in ordine tombstone -> sezioni -> refresh mappa uuid->id -> voci).

## Sub-task (stima / verify / dip / rollback / requisiti)
T0 Baseline su file: coverage json + misura limiti in scratchpad. 10m.
  verify: scratchpad/baseline-cov.json esiste, TOTAL 85% | dip - | par ok | rollback nessuno | R1,R6
T1a Caratterizzazione sync, propagazione: FakeRemote in-memory stateful (get_file/put_file con sha) condiviso da due
  Database tmp (dispositivi A e B); casi: primo sync pusha tutto (entries_pushed = n), voce creata su A arriva a B,
  cancellazione su A propaga tombstone a B, last_sha/last_sync aggiornati, tombstone > 90gg rimossa. Primo passo:
  scenario "B con seed proprio" per verificare B1. File tests/core/test_sync_engine_flows.py. 45m.
  verify: `uv run pytest tests/core/test_sync_engine_flows.py -q` verde; mutazione (invertire >= in LWW) -> rosso
  | dip T0 | par ok | rollback revert | R1,R6,R7,R8
T1b Caratterizzazione sync, conflitti ed errori: LWW remoto più nuovo vince e conta entries_pulled, locale più nuovo
  vince ed è pushato, pareggio -> locale, tombstone più vecchia della voce non cancella nel merge, JSON corrotto,
  KeyError su remoto senza "uuid", GitHubApiError su put -> messaggio umanizzato, _create_client None quando token
  vuoto (monkeypatch load_sync_token nel namespace sync_engine). 45m.
  verify: come T1a + coverage sync_engine >= 95% | dip T1a | par seq | rollback revert | R6,R7,R8
T2 Estrai merge puro in core/sync_merge.py (+ tests/core/test_sync_merge.py tabellari). Spostare count_pushed e
  aggiornare l'import in tests/core/test_sync_engine.py. Riscrittura di merge_entities senza i rami impossibili
  (vedi DC2). 40m.
  verify: T1a/T1b invariati verdi; grep R3 vuoto; coverage sync_merge 100% | dip T1b | par seq | rollback revert | R3,R5,R6
T3 Estrai plan_remote_changes (puro) + _apply_plan (shell) al posto di _apply_remote_changes (111 righe). 45m.
  verify: T1a/T1b verdi senza modifiche; test tabellari del piano; measure.py senza voci sync_* | dip T2 | par seq
  | rollback revert | R3,R5,R8
T4 Spezza sync() (78 righe) in _pull_and_apply/_push/_record_success. 25m.
  verify: T1 verdi; measure.py vuoto su sync_engine | dip T3 | par seq | rollback revert | R5
T5 Test github_client: urlopen finto nel namespace del modulo; 200 JSON, 404 -> None, HTTPError 401 con corpo,
  HTTPError con read() che solleva OSError, URLError senza status, header Authorization/Content-Type, get_file
  base64+sha, put_file con e senza sha. 40m.
  verify: coverage github_client 100% | dip T0 | par ok | rollback revert | R6,R7
T6a Caratterizzazione sezioni e tombstone (righe scoperte 64-70, 82-84, 140-150, 191-196, 221-240, 626-631):
  get_default_section_id nei tre rami, create_with_uuid, update_from_sync, delete di Generale rifiutato, delete con
  tombstone, delete_by_uuid assente, cleanup con tombstone vecchia e recente. 40m.
  verify: `uv run pytest tests/db -q` verde; coverage sezioni/tombstone 100% | dip T0 | par ok | rollback revert | R6,R7
T6b Caratterizzazione voci sync e import (338-351, 402-429, 461-470, 494-499): get_by_uuid, create_from_sync con e
  senza timestamp, update_from_sync, delete_by_uuid NON scrive tombstone (con caso positivo appaiato su delete),
  import: troncamento MAX_IMPORT_ENTRIES (monkeypatch del limite), tipo invalido -> prompt, sezione creata. 40m.
  verify: coverage queries.py 100% | dip T0 | par ok (file test diverso da T6a) | rollback revert | R6,R7
T7 Sposta le tre classi nei moduli D3 (solo move), queries.py diventa re-export transitorio. 25m.
  verify: suite verde con zero modifiche ai test | dip T6a,T6b,T4 | par seq | rollback revert | R2,R8
T8 Dedup: _add_tombstone -> TombstoneRepository.add; ENTRY_SELECT condivisa. 25m.
  verify: T6 verdi; `grep -c "_add_tombstone" command_quiver/db/*.py` = 0 | dip T7 | par seq | rollback revert | R2
T9 Estrai SyncRepository + dataclass SyncedEntry; sync_engine._apply_plan usa SyncRepository. 45m.
  verify: T1/T6 verdi (import dei test aggiornati, asserzioni no); measure.py vuoto su db/ | dip T8 | par seq
  | rollback revert | R2,R5,R8
T10 Estrai import_entries in db/entry_import.py + normalize_import_item puro; aggiorna ui/library_actions.py. 30m.
  verify: T6b verdi; tests/ui/test_library_actions.py verde | dip T9 | par seq | rollback revert | R2,R5
T11 Aggiorna tutti gli import (modelli da db.models, repo dai nuovi moduli), elimina db/queries.py. 25m.
  verify: grep "db.queries" vuoto; suite verde | dip T10 | par seq | rollback revert | R2,R9
T12 Caratterizzazione database via API pubblica: DB legacy senza user_version (v0 e con is_default),
  colonna duplicata in migrazione, file corrotto -> .db.bak.* e DB usabile, backup al 5° avvio e max 3 copie,
  contatore illeggibile riparte da 0, close() con errore. 45m.
  verify: coverage database.py 100% | dip T0 | par ok | rollback revert | R6,R7
T13 Estrai db/schema.py: DDL, seed, _MIGRATIONS, apply_migrations(conn), detect_schema_version(conn),
  populate_uuids(conn); _migrate (39 righe) spezzata. Aggiorna i test che chiamano db._migrate/_detect_schema_version. 35m.
  verify: T12 verdi; measure.py vuoto su database.py | dip T12 | par seq | rollback revert | R4,R5
T14 Estrai db/backup.py auto_backup(connection, db_path) spezzata in contatore/scrittura/pruning; aggiorna i target
  di patch dei test (command_quiver.db.backup...). 30m.
  verify: T12 verdi; Database <= 200 righe | dip T13 | par seq | rollback revert | R4,R5
T15 Gap settings + app: SYNC_TOKEN_PATH su tmp, save -> permessi 0o600 (stat), load con OSError -> "", delete
  assente; app: sync che solleva -> "Errore interno sync", sync già in corso ignorata, righe 54-73. 35m.
  verify: coverage settings 100%, app >= 95% | dip T4 | par ok | rollback revert | R6,R7
T16 Gap run_confirm (31-88) e shortcuts_dialog: conferma, annulla, Esc, "non chiedere più" persistito. 40m.
  verify: coverage run_confirm/shortcuts_dialog >= 95% | dip T11 | par ok | rollback revert | R6,R7
T17 Gap section_manager 166-182, row_dnd, sync_dialog, library_controller, library_actions. 50m.
  verify: TOTAL >= 95%; lista residui con motivo | dip T11 | par ok | rollback revert | R6
T18 Ratchet CI: ci.yml `--cov-branch --cov-fail-under=<TOTAL misurato - 1>`. 15m.
  verify: comando CI eseguito in locale (`xvfb-run` o DISPLAY) esce 0 | dip T17 | par seq | rollback revert | R11
T19 Chiusura: skill test-audit su tests/core e tests/db (nessun finding CRITICAL), code-reviewer sul diff complessivo,
  CLAUDE.md Struttura aggiornata, REPORT_ATTIVITA via doc-writer. 40m.
  verify: report test-audit senza CRITICAL; riga CHECKS: compilata | dip T18 | par seq | rollback revert | R7,R9

Stima: somma 13h10m. Refactor su codice esistente con test da costruire: range 13-16h + buffer 20% visibile =
16-19h (2-2,5 giornate). Cammino critico: T1a -> T1b -> T2 -> T3 -> T4 -> T7 -> ... -> T11. Parallelizzabili:
T5, T6a, T6b, T12 fin dall'inizio.

## Anomalie trovate (segnalate, non pianificate come fix) - R10
- B1 [prodotto, BASIS: inferred da codice] Due installazioni fresche hanno ciascuna "Git" e "Generale" con uuid
  diversi (seed + _populate_uuids). Al primo sync di B, create_with_uuid("Git") viola UNIQUE(name) ->
  sqlite3.IntegrityError, non catturata da sync() (cattura solo GitHubApiError/JSON/KeyError/TypeError) ->
  "Errore interno sync" in app.py, con tombstone già applicate e committate. T1a lo conferma o smentisce per primo.
  Spec mancante: sezione omonima con uuid diverso va fusa, rinominata o adotta l'uuid remoto?
- B2 [prodotto] Timestamp misti: entries.created_at/updated_at di create() vengono dal DEFAULT CURRENT_TIMESTAMP
  (UTC, "YYYY-MM-DD HH:MM:SS"), update()/sezioni/tombstone usano datetime.now().isoformat() (ora locale, "T").
  Il LWW confronta stringhe: a parità di data "T" > " " vince sempre, e l'offset UTC/locale sposta l'ordine.
  Non va fissato con un test di caratterizzazione (renderebbe permanente un difetto).
- B3 [spec] Modifica dopo cancellazione: _apply_remote_changes applica la tombstone remota a prescindere da
  updated_at locale, mentre _merge tiene l'entità se più recente della tombstone. La modifica locale si perde.
- B4 [spec] delete_by_uuid di una voce non scrive tombstone, quella di una sezione sì (via delete). Sezione di
  default cancellata da remoto: delete rifiuta e restituisce False, ma la tombstone remota viene comunque registrata.
- B5 [spec] Posizione e is_default delle sezioni remote ignorati al pull.

## Dead code / codice irraggiungibile (segnalato)
- DC1 TombstoneRepository.cleanup: `cutoff[:10].replace(cutoff[:10], _days_ago(n))` equivale a `_days_ago(n)`;
  `cutoff` è inutile. Semplificazione proposta in T8 solo se approvata (D5), protetta dal test di cleanup di T6a.
- DC2 _merge_entities: `if entity:` falso impossibile (uid viene dall'unione delle chiavi, le entità non sono dict
  vuoti) e il ramo finale dopo `elif remote_ent` irraggiungibile; lookup duplicati. Spariscono nella riscrittura
  pura di T2 (stesso comportamento, branch coverage 100% senza rami fantasma).
- DC3 _apply_remote_changes costruisce la mappa sezione uuid->id due volte; la prima è superflua. Assorbito da T3.
- DC4 database._auto_backup: `except OSError: pass` sul pruning ingoia l'errore (silent failure). Segnalato.
- DC5 SyncResult.success=True impostato due volte nel percorso di successo. Assorbito da T4.

## Fuori scope
- Fix di B1-B5 (cambiano comportamento: commit fix(...) separati dopo decisione sulla spec).
- Classi UI > 200 righe (D2) e funzioni lunghe fuori da db/ e sync (github_client._request 54, executor 39,
  i18n.t 36, ordering 35, window_actions 37, describe_sync_status 5 parametri).
- Callback GTK con > 4 parametri imposti dalla firma del segnale.
- Mutation testing con tool esterno: la qualità si verifica con mutazione manuale per test (R7) e test-audit.
- Push su origin.

## File impattati
| File | Tipo | Scopo |
|---|---|---|
| command_quiver/core/sync_merge.py | nuovo | core puro merge/piano |
| command_quiver/core/sync_engine.py | modifica | shell I/O |
| command_quiver/db/section_repository.py, entry_repository.py, tombstone_repository.py, sync_repository.py, entry_import.py | nuovi | repository |
| command_quiver/db/models.py | modifica | SyncedEntry |
| command_quiver/db/queries.py | eliminato (T11) | |
| command_quiver/db/schema.py, backup.py | nuovi | DDL/migrazioni, backup |
| command_quiver/db/database.py | modifica | lifecycle |
| command_quiver/ui/*.py (10 importatori), ui/library_actions.py | modifica | import |
| tests/core/test_sync_engine_flows.py, test_sync_merge.py, tests/db/test_*_repository.py, test_schema.py, test_backup.py | nuovi | |
| tests/core/test_sync_engine.py, test_github_client.py, test_settings.py, tests/db/*, tests/ui/*, tests/test_app.py | modifica | import, gap |
| .github/workflows/ci.yml | modifica | floor coverage |
| CLAUDE.md | modifica | struttura |

## Rischi
- Poiché B1 farà fallire il primo scenario a due dispositivi (causa), T1a può bloccarsi sul primo test (rischio):
  +30-60 min per ridisegnare lo scenario con B senza sezioni in conflitto e registrare il fallimento come finding
  (effetto). Mitigazione: primo passo di T1a dedicato a confermarlo.
- Test esistenti che toccano privati (db._migrate, _auto_backup, _recreate, engine._create_client) e target di patch
  per stringa -> si rompono allo spostamento. Mitigazione: caratterizzazione nuova solo via API pubblica; i test
  privati si aggiornano nello stesso commit dello spostamento, asserzioni invariate.
- Orologio: LWW e cleanup dipendono da datetime.now(). Mitigazione: nel core puro `now` è parametro; nei test di
  flusso timestamp scritti via SQL nell'Arrange.
- Coverage UI dipende dal display (A3). Mitigazione: misura R6 solo con DISPLAY o xvfb-run, dichiarato nel report.
- Thread di sync: SyncRepository deve nascere sulla connessione dedicata in sync(), come oggi. Test di regressione
  esistente test_sync_from_separate_thread_does_not_raise deve restare verde.

## Criteri di successo
Suite verde a ogni commit; measure.py vuoto su db/ e sync_*; coverage branch >= 95% totale e 100% sui moduli R6;
test-audit senza CRITICAL; B1-B5 e DC1-DC5 nel report con decisione richiesta.

Handoff: tdd-guide (T1-T6, T12, T15-T17 test-first) e refactor-cleaner (T7-T11, T13-T14), 2-4 task per invocazione.
