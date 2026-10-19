# Spec: scomposizione dei moduli, fase 2

Data: 2026-10-19. Repo: command-quiver, main @ be4fb4d (pulito). Segue specs/001-god-module-split.

## Contesto

La fase 1 ha scomposto i god-module (queries, sync_engine, database) e le classi UI più grandi (U1-U7).
Restano 17 violazioni dei limiti di code-standards misurate in righe fisiche, docstring incluse.
Misurate in righe di codice (escluse righe vuote, commenti e docstring) ne restano 8; le due classi
sopra 200 righe fisiche (SidebarPanel 195 righe di codice, EntryEditorDialog 181) rientrano.

Baseline: 862 test verdi, righe 99,9%, rami ~97,7% (522 rami, 12 parziali), floor CI 95% rami, nessuna
funzione con nesting > 3 (misurato).

## Requisiti

- R1 Nessuna regressione: dopo ogni commit `uv run pytest -q` verde con display, test passati >= commit
  precedente (baseline 862).
- R2 Metrica dei limiti = righe di codice: righe non vuote, non commento, non docstring, dalla `def` (o
  `class`) all'ultima riga. Funzione <= 30, classe <= 200, parametri <= 4 (esclusi `self`/`cls`, contati
  `*args`/`**kwargs`), nesting <= 3, file <= 300 righe fisiche.
- R3 Gate eseguibile dei limiti: `tests/test_code_limits.py` misura R2 su `command_quiver/` e fallisce su
  (a) una violazione non registrata, (b) un'eccezione registrata che non viola più (registro sempre vero).
  Ogni eccezione porta il motivo. Gira in CI con il resto della suite.
- R4 Una violazione si scompone solo se il guadagno è nominabile (logica pura testabile senza GTK, stato
  illegale eliminato, indici posizionali sostituiti da campi, codice tolto, pattern già presente nel repo).
  Mai separare un gruppo coeso (un widget e il suo placeholder, una firma imposta da GTK, un composition root
  fatto di wiring da 1-5 righe).
- R5 Registro finale delle eccezioni: solo `SectionPanelWidget._on_right_click` (firma GTK del gesture più
  user_data) ed `EntryRepository.get_all` (in attesa della decisione B13). Nessun'altra voce.
- R6 Rami: i 12 rami parziali della baseline sono chiusi, ciascuno con un test che lo attraversa oppure con la
  rimozione della guardia se il ramo è irraggiungibile, provata nel commit (evidenza: chi costruisce il
  valore). Nessun `# pragma: no cover`.
- R7 Qualità test: ogni test nuovo visto rosso (mutazione manuale, poi ripristino) nello stesso task; nessuna
  asserzione solo `is not None`; ogni asserzione negativa con caso positivo appaiato; SQLite reale su
  tmp_path, GTK reale in tests/ui; finti solo rete e orologio.
- R8 Contratti invariati: messaggi utente e chiavi i18n, `SidebarPanel.update_sync_status(result)` chiamata da
  app.py, formato JSON del sync, schema DB, comportamento di "non chiedere più" e del tasto destro sulle
  sezioni. Le asserzioni dei test esistenti non cambiano; cambiano solo i costruttori dove cambia la firma.
- R9 Floor CI rialzato al TOTAL rami misurato a fine T10, arrotondato per difetto all'intero, meno 1.
- R10 Audit di qualità dei test sui gruppi core, db, ui con la skill `test-audit` (lanciata
  dall'orchestratore, non dal planner); i finding scelti chiusi in task successivi, ripianificati sui finding.
- R11 Commit atomici su main, Conventional Commits in inglese, identificatori inglesi, commenti e docstring in
  italiano come il resto del repo; `uv run ruff check .` e `uv run ruff format --check .` verdi. Nessun push.

## Definition of Done

- [ ] R1: `uv run pytest -q > run.log 2>&1; grep -E "passed|failed" run.log` riporta 0 failed e passed >= 862
      a ogni commit.
- [ ] R3/R5: `uv run pytest tests/test_code_limits.py -q` verde; il registro `LIMIT_EXCEPTIONS` contiene
      esattamente le 2 voci di R5.
- [ ] R3 prova del rosso: aggiungere a mano un parametro a una funzione conforme fa fallire il gate con il nome
      della funzione; registrare un'eccezione per una funzione conforme lo fa fallire come "stale".
- [ ] R6: `uv run pytest --cov=command_quiver --cov-branch --cov-report=term-missing` non mostra rami parziali
      (colonna BrPart = 0 su tutti i file).
- [ ] R9: il comando di `.github/workflows/ci.yml` eseguito in locale con DISPLAY esce 0 con il nuovo floor.
- [ ] R10: tre report test-audit (core, db, ui) consegnati; per ogni finding scelto, test corretto e visto rosso.
- [ ] Esempio (sync status): Given `SyncSettings(enabled=True, last_sync=<5 minuti fa>)` e
      `SyncResult(success=True, entries_pulled=2, entries_pushed=0)`, When `describe_sync_status`, Then
      `state is SyncState.OK` e testo "Sincronizzato 5 minuti fa: 2 ricevute, 0 inviate" (it).
- [ ] Esempio (editor): Given nessuna voce in modifica, nome vuoto e contenuto "\n  git status --short\n",
      When `build_entry_payload`, Then `EntryCreate` con `name == "git status --short"`; Given voce id 7 in
      modifica, Then `EntryUpdate` con `id == 7`.
- [ ] Esempio (riga sezione): Given `Section(id=7, name="Git")`, When `SectionRow(label="Git", section=s,
      count=3)`, Then `row.section_id == 7`; la riga "Tutti" (`section=None`) ha `section_id is None`.

## Assunzioni

- A1 La metrica R2 (righe di codice) è quella voluta: lo dice la richiesta ("una funzione 35 righe di cui 15
  docstring non va spezzata"). Con la metrica fisica le due classi tornerebbero violazioni da trattare.
- A2 I test GTK girano con display (qui DISPLAY=:1, in CI xvfb-run). Senza display si skippano e R6/R9 non sono
  misurabili.
- A3 B13 (cap a 500 voci in get_all) resta una decisione utente aperta: get_all non si tocca in questa fase.
  Se la decisione è "togliere il cap", `limit`/`offset` (oggi usati solo dai test) spariscono e la violazione
  si chiude togliendo codice, in un task a parte.
- A4 Il gate dei limiti è un meta-test, non un test di comportamento: vive in `tests/` perché deve girare in CI,
  e le sue funzioni di misura hanno test propri su sorgenti di esempio.
- A5 Nessun consumatore esterno delle firme UI cambiate (app desktop, non libreria).

## Decisioni

| # | Violazione (fisiche / codice) | Decisione | Motivo |
|---|---|---|---|
| V1 | classe SidebarPanel 252 / 195 | NON SCOMPORRE | composition root della finestra, wiring da 1-5 righe; sotto 200 in righe di codice. Unico ritocco in V8: `update_sync_status` passa il risultato senza spacchettarlo |
| V2 | classe EntryEditorDialog 227 / 181 | SCOMPONI parziale | `_collect_data` contiene logica pura (nome dedotto dal contenuto, scelta create/update): `build_entry_payload` testabile senza finestra |
| V3 | execute_in_terminal 41 / 14 | NON SCOMPORRE | 20 righe di docstring; il codice è 14 righe |
| V4 | GitHubClient._request 36 / 21 | NON SCOMPORRE | docstring + 3 except coesi della stessa chiamata |
| V5 | GitHubClient.put_file 40 / 15 | NON SCOMPORRE | docstring |
| V6 | i18n.t 36 / 15 | NON SCOMPORRE | docstring |
| V7 | reorder_positions 35 / 13 | NON SCOMPORRE | docstring |
| V8 | describe_sync_status 5 parametri | SCOMPONI firma | `(sync: SyncSettings, *, pending, outcome: SyncResult \| None, now)`: via la tupla `outcome[1]`/`outcome[2]`, campi con nome; StatusBar conserva il SyncResult invece di ricostruire la tupla |
| V9 | ContentField.__init__ 35 / 30 | NON SCOMPORRE | al limite in righe di codice; TextView, placeholder sovrapposto e overlay sono un solo gruppo |
| V10 | RunConfirmDialog.__init__ 51 / 44 | SCOMPONI | `_build_buttons` e `_setup_keyboard_shortcuts`, stesso schema di entry_editor e sync_dialog; anteprima, pulsanti e tastiera sono gruppi distinti |
| V11 | SyncSetupDialog._build_ui 36 / 31 | SCOMPONI minimo | il controller di tastiera esce in `_setup_keyboard_shortcuts` (precedente in entry_editor); il layout resta intero |
| V12 | install_window_actions 37 / 25 | NON SCOMPORRE | docstring; elenco dichiarativo di azioni |
| V13 | EntryRepository.get_all 5 parametri | RIMANDATO (B13) | un oggetto query per un solo chiamante di produzione è indirezione; se B13 toglie il cap si scende a 3 togliendo codice |
| V14 | EntryEditorDialog.__init__ 7 parametri | SCOMPONI | `EditorRequest` frozen (entry, initial_section_id, sections, known_tags): è l'insieme che `LibraryController.open_editor` costruisce già; firma `(parent, request, on_save, on_delete)` |
| V15 | confirm_and_run 5 parametri | SCOMPONI (togliendo) | chiamata solo dalla closure di `request_run`, nessun test la chiama: il corpo entra nella closure, la funzione sparisce |
| V16 | SectionPanelWidget._on_right_click 5 parametri | NON SCOMPORRE | firma del segnale `pressed` di GestureClick più user_data, imposta da GTK |
| V17 | SectionRow.__init__ 5 parametri | SCOMPONI (togliendo) | `section_id` ridondante con `section.id`: oggi si può costruire una riga con id e sezione discordi; derivarlo elimina lo stato illegale e un parametro |

## Esito dell'implementazione (2026-10-19)

Deviazioni dal piano, decise dall'orchestratore durante l'implementazione:

- R3, R5 (gate `tests/test_code_limits.py`): non realizzato. Un meta-test con registro di eccezioni non era
  richiesto dall'utente, e i limiti sono già misurati dallo script AST usato in questa fase. Resta una proposta.
- V15 (togliere `confirm_and_run`): rifiutata. La premessa "nessun test la chiama" era falsa: tre test di
  `tests/ui/test_run_confirm.py` la chiamano direttamente, e metterla nella closure toglieva testabilità.
- V2 (editor): realizzata come `entry_payload(draft: EntryCreate, entry_id)`. La bozza riusa `EntryCreate`
  invece di un nuovo `EditorFields`, che ne avrebbe duplicato i campi.
- V11 (dialog sync): oltre alla tastiera esce anche il campo token con il suo link (`_append_token_field`),
  così `_build_ui` scende sotto le 30 righe; il link ora ha un test.
- R6 (rami): chiusi con un test solo i rami con comportamento utente (tasto destro sulla sezione, "Annulla"
  dopo la scadenza del toast). I rami irraggiungibili sono segnalati e non rimossi, come chiede la consegna
  ("se trovi codice morto, segnalalo invece di testarlo"): `db/schema.py:212`, `ui/entry_list.py:276/281`,
  `ui/section_panel.py:191`, `ui/sync_dialog.py:222`, `ui/library_controller.py:93`. Restano scoperti a basso
  valore: `ui/entry_list.py:261`, `ui/section_panel.py:181`, `ui/sidebar.py:270`.
- R9: `--cov-fail-under` controlla la copertura combinata righe+rami, non i soli rami. Misurata 99,7%
  (righe 99,97%, rami 98,09%); floor portato da 95 a 98.
- R10: audit eseguito sui gruppi core, sync, db, ui-A, ui-B con 5 worker; 50 mutanti sopravvissuti
  confermati e tutti chiusi da test visti fallire sotto il loro mutante.

Difetti di produzione emersi e corretti, ciascuno con test visto rosso: terminale chiuso su errore di
sintassi, import interrotto da sezioni che differiscono per maiuscole, token GitHub creato con i permessi
dell'umask, app che non parte con settings.json non valido, `_` e `%` usati come jolly nella ricerca,
debounce di ricerca riarmato dopo `cancel()`. Emerso anche un difetto dei test: le eccezioni negli handler
GTK erano invisibili, ora fanno fallire il test.
