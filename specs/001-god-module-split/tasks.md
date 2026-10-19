# Tasks

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


## Stato finale (2026-10-19)

- Fix eseguiti in commit `fix(...)` separati, ciascuno con test di regressione: B1, B2, B3 (con B3b e B7), B4,
  B6, B8, B9, B10, B11, B12, B14, B15, B16, B17. B5 non si corregge (decisione nella spec). B13 aperto: decisione utente.
- T1-T18 eseguiti. T19: code-reviewer a ogni commit, /analyze eseguito, test-audit eseguito sul solo gruppo 5
  (i worker degli altri 4 gruppi sono stati fermati dall'utente), REPORT_ATTIVITA aggiornato a fine lavoro.
- T20 (D2): U1-U7 eseguiti (spec.md § D2).
