# Piano RPI: scomposizione dei moduli, fase 2, Command Quiver

Data: 2026-10-19. Repo: command-quiver, main @ be4fb4d (pulito). Requisiti in spec.md, task in tasks.md.

## Obiettivo
Ogni violazione residua dei limiti di code-standards è scomposta dove il guadagno è nominabile, o registrata
come eccezione motivata in un gate eseguibile che gira in CI; i 12 rami parziali sono chiusi; i test di core,
db e ui passano da un audit di qualità. Nessun commit lascia la suite rossa o meno test di prima.

## Definition of Done
Vedi spec.md § Definition of Done (9 voci, tre esempi Given/When/Then con valori).

## Assunzioni
Vedi spec.md § Assunzioni. La sola che cambia il piano se sbagliata è A1 (metrica in righe di codice): con la
metrica fisica SidebarPanel (252) ed EntryEditorDialog (227) tornano violazioni, e la prima richiederebbe di
spezzare un composition root di wiring, cosa che R4 vieta. Non bloccante: la richiesta la indica.

## Approccio

### D1 Come si dimostra che le violazioni non tornano
Prima elenco le opzioni, poi le valuto.
- A: test di repository `tests/test_code_limits.py` (ast + tokenize, stdlib) con registro delle eccezioni.
- B: `.size-baseline.json` + `~/.claude/scripts/size-ratchet.py` (ratchet globale già letto da verify.sh).
- C: nessun gate, misura a mano in scratchpad come nella fase 1.

Valutazione: B misura le funzioni con PLR0915 (statement, non righe), non misura le classi e non gira in CI:
un approssimato, solo locale. C è come la fase 1 e lascia la regressione possibile al primo commit futuro.
A misura esattamente R2, gira in CI, e il registro rende ogni eccezione una riga con motivo (forma a
marcatore). Raccomandata A. Il gate entra per primo (T1) con le 8 voci di oggi: ogni task successivo toglie la
sua voce, così il gate verde senza quella voce È la verifica del task.

### D2 Criterio per violazione
Tabella di decisione di code-standards: si scompone se il guadagno è nominabile (logica pura testabile senza
GTK, stato illegale eliminato, tupla posizionale sostituita da campi, codice tolto, schema già presente nel
repo). Le funzioni sopra 30 righe solo per docstring non si toccano. Decisioni V1-V17 in spec.md § Decisioni.

Sintesi: 7 SCOMPONI (V2, V8, V10, V11, V14, V15, V17; V15 e V17 togliendo codice), 9 NON SCOMPORRE (V1, V3-V7,
V9, V12, V16), 1 RIMANDATO a B13 (V13).

### D3 Ordine
Gate -> scomposizioni (piccole, una voce per commit) -> rami parziali -> floor CI -> audit dei test.
Gli audit vengono dopo i refactor perché un finding su codice che sta per cambiare è stantio; la rete di
sicurezza dei refactor sono i test esistenti più la mutazione richiesta in ogni task.

### D4 Rami parziali: test o rimozione
Per ogni ramo si dimostra prima se è raggiungibile. Gli `isinstance(child, EntryRow/SectionRow)` in
entry_list e section_panel sembrano difese: lo sono solo se nessuna riga ha un figlio di altro tipo (lo stato
vuoto potrebbe esserlo). Raggiungibile -> test; irraggiungibile -> guardia tolta (meno codice: si tiene),
evidenza nel commit. Mai un test scritto per un ramo che non può accadere.

## Sub-task
In tasks.md: T0-T12 (Fase A gate, B scomposizioni, C rami, chiusura) e Q1-Q3 + F* (audit, orchestratore).

## Fuori scope
- get_all / B13: cap a 500 voci, decisione utente. Se si toglie il cap, task a parte che rimuove limit/offset.
- Riscrivere le funzioni lunghe per sola docstring (V3-V7, V12) o accorciare le docstring NumPy.
- Scrivere i test suggeriti dagli audit prima che i finding siano scelti (il planner non lancia test-audit).
- Push su origin (non autorizzato).

## File impattati
| File | Tipo | Scopo |
|---|---|---|
| tests/test_code_limits.py | nuovo | gate dei limiti + registro eccezioni |
| command_quiver/ui/section_row.py, ui/section_panel.py | modifica | V17, rami 183/193/220 |
| command_quiver/ui/run_confirm.py | modifica | V15, V10 |
| command_quiver/ui/sync_dialog.py | modifica | V11, ramo 217 |
| command_quiver/core/sync_status.py, ui/status_bar.py, ui/sidebar.py | modifica | V8, ramo sidebar 271 |
| command_quiver/ui/entry_editor.py, ui/library_controller.py | modifica | V2, V14, rami 296 e 90 |
| command_quiver/db/schema.py, ui/tag_input.py, ui/toast.py, ui/entry_list.py | modifica o solo test | rami parziali |
| tests/ui/test_*.py, tests/core/test_sync_status.py, tests/test_app.py | modifica | firme cambiate, test nuovi |
| .github/workflows/ci.yml | modifica | floor rami |

## Rischi e mitigazioni
- Il gate misura con una metrica che "assolve" codice lungo (righe di commento contate fuori) -> i commenti
  restano solo per il perché (convenzione già nel repo); il registro è visibile in review.
- Gate fragile fra Python 3.10 e 3.12 (tokenize e posizioni AST) -> funzioni di misura testate su sorgenti di
  esempio; CI su 3.10 e locale su 3.12 lo verificano entrambe.
- Rimuovere una guardia `isinstance` su un ramo raggiungibile fa crashare un clic -> la raggiungibilità si
  dimostra prima (test o lettura del costruttore), mai per ipotesi.
- `sync_status.py` che importa da `sync_engine` porta urllib in un modulo puro -> import sotto TYPE_CHECKING,
  grep nel verify di T6.
- Churn sui test dell'editor (9 costruttori) -> cambiano solo i costruttori; un'asserzione cambiata è un
  segnale di regressione da fermare (R8).
- Senza display i test UI si skippano e la copertura è falsa -> misure solo con DISPLAY o xvfb-run (A2).
- Gli audit possono produrre molti finding -> si scelgono e si ripianificano (F*), non si chiudono tutti a
  scatola chiusa.

## Criteri di verifica
Suite verde e in crescita a ogni commit; `tests/test_code_limits.py` verde con 2 sole eccezioni; BrPart 0 in
term-missing; comando CI locale verde col nuovo floor; tre report test-audit con i finding scelti chiusi;
code-reviewer e /analyze eseguiti (riga `CHECKS:`).

## Handoff
Fase A e B: `tdd-guide` (gate test-first e mutazioni per task), due-tre task per invocazione (T1; T2-T4; T5-T6;
T7-T8). Fase C: `tdd-guide`. Fase D: orchestratore con la skill `test-audit`. UI renderizzata non cambia
(nessun cambio visivo previsto): a11y-gate N/A salvo diff che tocchi il layout.

> Nota finale (2026-10-19): T1 e V15 non sono stati eseguiti; la motivazione e lo stato di ogni task
> sono in `spec.md` § Esito dell'implementazione e in `tasks.md` § Stato finale.
