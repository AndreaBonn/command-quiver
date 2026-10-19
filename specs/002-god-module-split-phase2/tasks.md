# Tasks

Formato: stima / verify / dip / par / rollback / requisiti. Un commit per task salvo T0 e Q1-Q3.
Comando di suite (redirect, poi grep del marcatore):
`uv run pytest -q > run.log 2>&1; grep -E "^FAILED|^ERROR| passed| failed" run.log`.
Ogni task che rimuove una violazione toglie la sua voce da `LIMIT_EXCEPTIONS` nello stesso commit: per questo
tutti i task di scomposizione sono `par: seq` sul file del gate.

## Fase A: gate

- [ ] T0 Baseline in scratchpad: `coverage.json` con `--cov-branch`, numero di test passati, elenco dei 12 rami
  parziali. Nessun commit. 10m.
  verify: `grep -E " passed" run.log` = 862 passed; file json presente | dip - | par ok | rollback nessuno | R1,R6
- [ ] T1 Gate dei limiti `tests/test_code_limits.py`: funzioni pure di misura (righe di codice di una def/classe,
  parametri, nesting) con test su sorgenti di esempio, poi il test di repository su `command_quiver/` con
  `LIMIT_EXCEPTIONS = {"<path>::<Qualname>": "<motivo>"}` iniziale di 8 voci (V8, V10, V11, V13, V14, V15, V16,
  V17). Fallisce su violazione non registrata e su eccezione stale. Solo stdlib (ast, tokenize). 30m.
  verify: `uv run pytest tests/test_code_limits.py -q` verde; rosso visto due volte: (1) aggiungere un parametro a
  `name_from_content` -> fallisce nominandola; (2) aggiungere un'eccezione per `name_from_content` -> fallisce
  come stale; ripristino | dip T0 | par seq | rollback revert | R2,R3,R7
  commit: `test(limits): add a gate for the size limits of code-standards`

## Fase B: scomposizioni (ognuna chiude una voce del registro)

- [ ] T2 V17 SectionRow: `section_id` derivato da `section` (`None` per "Tutti"); aggiornare i due costruttori in
  `ui/section_panel.py` e `tests/ui/test_section_row.py`. Test prima: riga di sezione ha `section_id ==
  section.id`, riga "Tutti" ha `None`. 20m.
  verify: `uv run pytest tests/ui/test_section_row.py tests/ui/test_section_panel.py -q` verde; mutazione
  (`section_id = None` fisso) -> rosso in test_section_panel (selezione sezione); gate verde senza la voce V17
  | dip T1 | par seq | rollback revert | R4,R8
  commit: `refactor(ui): derive the section row id from its section`
- [ ] T3 V15 run_confirm: il corpo di `confirm_and_run` entra nella closure `on_confirm` di `request_run`;
  la funzione sparisce. 15m.
  verify: `uv run pytest tests/ui/test_run_confirm.py tests/ui/test_sidebar_ux.py -q` verde; mutazione (ignorare
  `remember`) -> rosso in test_sidebar_ux (skip_run_confirm == [uuid]); `grep -rn confirm_and_run command_quiver
  tests` vuoto | dip T1 | par seq | rollback revert | R4,R8
  commit: `refactor(ui): fold confirm_and_run into the run confirmation callback`
- [ ] T4 V10 RunConfirmDialog.__init__: estrarre `_build_buttons() -> Gtk.Box` e
  `_setup_keyboard_shortcuts()`; focus e default widget restano in `__init__` dopo i pulsanti. 15m.
  verify: test_run_confirm verde (Invio esegue, Esc chiude, focus su Esegui); gate verde senza V10
  | dip T3 | par seq | rollback revert | R4,R8
  commit: `refactor(ui): split the run confirmation dialog builder`
- [ ] T5 V11 SyncSetupDialog: controller di tastiera da `_build_ui` a `_setup_keyboard_shortcuts()`. 10m.
  verify: `uv run pytest tests/ui/test_sync_dialog.py -q` verde, incluso Esc; mutazione (non registrare il
  controller) -> rosso sul test di Esc (se manca, scriverlo prima); gate verde senza V11
  | dip T1 | par seq | rollback revert | R4,R8
  commit: `refactor(ui): move the sync dialog key handling out of the layout`
- [ ] T6 V8 stato sync tipizzato: `describe_sync_status(sync: SyncSettings, *, pending: bool, outcome:
  SyncResult | None, now: datetime)`; `StatusBar.set_result(result: SyncResult)` conserva il risultato
  (tooltip da `result.message`); `SidebarPanel.update_sync_status(result)` lo passa intero. Import di SyncResult
  sotto `TYPE_CHECKING` in sync_status.py. Test esistenti: cambiano gli argomenti, non i testi attesi. 30m.
  verify: `uv run pytest tests/core/test_sync_status.py tests/ui/test_status_bar.py tests/test_app.py -q` verde;
  `grep -nE "^(from|import) .*(sync_engine|urllib|sqlite3)" command_quiver/core/sync_status.py` vuoto (solo sotto
  TYPE_CHECKING); mutazione (pulled/pushed invertiti) -> rosso; gate verde senza V8
  | dip T1 | par seq | rollback revert | R4,R8
  commit: `refactor(sync): pass typed sync results to the status text`
- [ ] T7 V2 `build_entry_payload(*, entry_id: int | None, fields: EditorFields) -> EntryCreate | EntryUpdate`
  pura in `ui/entry_editor.py` (accanto a `editor_command`), con `EditorFields` frozen (name, content,
  section_id, type, tags); `_collect_data` legge i widget e la chiama. Test senza finestra: nome vuoto -> prima
  riga non vuota, nome scritto vince, entry_id None -> EntryCreate, entry_id 7 -> EntryUpdate(id=7). 25m.
  verify: `uv run pytest tests/ui/test_entry_editor.py -q` verde; mutazione (ignorare il nome scritto) -> rosso
  | dip T1 | par seq | rollback revert | R4,R7
  commit: `refactor(ui): extract the entry editor payload as a pure function`
- [ ] T8 V14 `EditorRequest` frozen (entry, initial_section_id, sections, known_tags) in `ui/entry_editor.py`;
  firma `EntryEditorDialog(parent, request, on_save, on_delete)`; aggiornare `LibraryController.open_editor` e i 9
  costruttori in tests/ui/test_entry_editor.py (asserzioni invariate). 25m.
  verify: `uv run pytest tests/ui/test_entry_editor.py tests/ui/test_library_controller.py tests/ui/test_sidebar_ux.py -q`
  verde; gate verde senza V14 | dip T7 | par seq | rollback revert | R4,R8
  commit: `refactor(ui): group the entry editor inputs in an EditorRequest`

## Fase C: rami parziali

Regola per ogni ramo: prima si dimostra se è raggiungibile (chi costruisce il valore). Raggiungibile -> test che
lo attraversa, visto rosso. Irraggiungibile -> si toglie la guardia, con l'evidenza nel corpo del commit.
Test e rimozioni vanno in commit separati (`test(...)` / `refactor(...)`).

- [ ] T9 Rami db e controller: `db/schema.py:212` (`elif sql` falso), `ui/library_controller.py:90` (commit di una
  voce diversa da `pending_entry`), `ui/tag_input.py:69` (testo in attesa vuoto), `ui/toast.py:81` (chiusura senza
  callback). 20m.
  verify: term-missing senza rami parziali sui 4 file | dip T8 | par seq | rollback revert | R6,R7
- [ ] T10 Rami UI: `ui/entry_list.py:261/276/281` (le righe hanno sempre un EntryRow? lo stato vuoto è una riga?),
  `ui/entry_editor.py:296`, `ui/section_panel.py:183/193/220-221`, `ui/sidebar.py:271`, `ui/sync_dialog.py:217`.
  30m.
  verify: `uv run pytest --cov=command_quiver --cov-branch --cov-report=term-missing` con BrPart 0 ovunque
  | dip T9 | par seq | rollback revert | R6,R7
- [ ] T11 Floor CI: `--cov-fail-under` in `.github/workflows/ci.yml` a (TOTAL misurato, per difetto) - 1. 10m.
  verify: comando CI eseguito in locale con DISPLAY esce 0 | dip T10 | par seq | rollback revert | R9
  commit: `ci: raise the branch coverage floor`

## Fase D: audit dei test (orchestratore)

- [ ] Q1 skill `test-audit` sul gruppo core (`command_quiver/core`, `tests/core`). Nessun commit. dip T11.
- [ ] Q2 skill `test-audit` sul gruppo db (`command_quiver/db`, `tests/db`). dip T11, par ok con Q1.
- [ ] Q3 skill `test-audit` sul gruppo ui (`command_quiver/ui`, `tests/ui`). dip T11, par ok con Q1/Q2.
- [ ] F* Un task per finding scelto (15-30m ciascuno), ripianificati dopo i report: test corretto, visto rosso,
  commit `test(<scope>): ...`. verify: il finding non si riproduce al rilancio mirato della skill.

## Chiusura

- [ ] T12 code-reviewer sul diff complessivo, `/analyze` su questa cartella, REPORT_ATTIVITA via doc-writer;
  CLAUDE.md solo se cambia la struttura (non previsto). 20m.
  verify: riga `CHECKS:` compilata; gate e suite verdi | dip F* | par seq | rollback revert | R11

Stima: T0-T12 = 4h10m. Refactor su codice esistente: range 4h30m-5h30m + buffer 20% = 5h30m-6h30m.
Q1-Q3 e F* esclusi: dipendono dal numero di finding, si stimano dopo i report.

## Stato finale (2026-10-19)

Esito e deviazioni motivate in `spec.md` § Esito dell'implementazione.

| Task | Stato | Commit |
|---|---|---|
| T0 baseline | fatto (862 test, rami 97,7%) | - |
| T1 gate dei limiti | non fatto: deviazione dichiarata, proposta aperta | - |
| T2 V17 SectionRow | fatto | e9e85df |
| T3 V15 confirm_and_run | rifiutato: tre test la chiamano direttamente | - |
| T4 V10 RunConfirmDialog | fatto in due passi (il secondo dopo /analyze A1) | 1ba7b26, 1d5cb97 |
| T5 V11 SyncSetupDialog | fatto, con il campo token estratto | 1168a46, 0716878 |
| T6 V8 stato sync tipizzato | fatto | 334205f |
| T7 V2 payload puro | fatto come `entry_payload(draft: EntryCreate)` | eada67a, 279b592 |
| T8 V14 EditorRequest | fatto, spostato in `ui/editor_request.py` | e85dbf0, 279b592 |
| T9-T10 rami parziali | parziale: 2 rami con test, 5 irraggiungibili segnalati, 3 a basso valore | ef446be, b13d9a9 |
| T11 floor CI | fatto, 98 sulla copertura combinata | 69a095a |
| Q1-Q3 + F* audit | fatto: 50 mutanti chiusi | 78647aa..ed432ee |
| T12 chiusura | code-reviewer APPROVE, /analyze eseguito | - |
