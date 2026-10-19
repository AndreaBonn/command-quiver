# Report Attività

## 2026-06-23 | Sessione #1 [FEATURE] [BUILD]

### Richiesta
Creare un pacchetto `.deb` di Command Quiver, così da poter installare l'app come
un normale programma Ubuntu (apt / doppio clic) invece di eseguirla dal codice, e
renderla gestibile con systemd per l'avvio automatico e il riavvio.

### Azioni Eseguite
Lavoro svolto con workflow RPI (Research, Plan, Implement) con approvazione
esplicita tra le fasi.

- Creato il packaging Debian costruito con `dpkg-deb`, senza toolchain aggiuntiva.
- Scritto `scripts/build-deb.sh`: build riproducibile che legge la versione da
  `command_quiver/__init__.py`, genera le icone hicolor multi-size (32/48/64/128)
  da `icon.png`, assembla la struttura e produce `dist/command-quiver_1.0.0_all.deb`.
- Definito il layout del pacchetto: payload Python in `/usr/lib/command-quiver/`,
  wrapper eseguibile `/usr/bin/command-quiver` (imposta `PYTHONPATH`), desktop
  entry in `/usr/share/applications`, icone in `/usr/share/icons/hicolor`,
  `copyright` e `changelog.Debian.gz` in `/usr/share/doc`.
- Aggiunto un systemd user service installato disabilitato, con `Restart=on-failure`
  (riavvio solo su crash, non alla chiusura volontaria della finestra) e guardia
  anti restart-loop (`StartLimitBurst=3` / `StartLimitIntervalSec=30`). Si attiva
  con `systemctl --user enable --now command-quiver.service`.
- Dichiarate le dipendenze runtime risolte da apt: `python3 (>=3.10)`,
  `python3-gi`, `python3-gi-cairo`, `gir1.2-gtk-4.0`, `gnome-terminal`.
- Scritti i maintainer scripts `postinst`/`prerm`/`postrm` idempotenti (aggiornano
  cache icone e desktop database).
- Aggiunta la documentazione `docs/PACKAGING.md` (build, installazione, gestione
  systemd, disinstallazione).
- Gli script `install.sh`/`uninstall.sh` esistenti restano come metodo alternativo.

Verifiche superate: build OK, `dpkg-deb --info`/`--contents` corretti, permessi
normalizzati 644/755, payload importabile (`command_quiver.main --version` stampa
"Command Quiver 1.0.0"), `systemd-analyze verify` OK, syntax check bash su tutti
gli script, code-review (un finding errato sul tray respinto perché il tray è già
stato rimosso in precedenza; due finding validi applicati: estrazione versione
robusta e guardia restart-loop).

### File Modificati
| File | Tipo | Descrizione |
|------|------|-------------|
| `packaging/deb/control.in` | Crea | Metadata Debian e dipendenze (versione iniettata a build) |
| `packaging/deb/command-quiver` | Crea | Wrapper eseguibile con PYTHONPATH |
| `packaging/deb/command-quiver.service` | Crea | systemd user unit, Restart=on-failure + anti restart-loop |
| `packaging/deb/postinst` | Crea | Aggiorna cache icone e desktop database |
| `packaging/deb/prerm` | Crea | No-op sicuro (service fermato dall'utente) |
| `packaging/deb/postrm` | Crea | Cleanup cache su remove/purge |
| `packaging/deb/copyright` | Crea | Licenza Apache-2.0 in formato DEP-5 |
| `scripts/build-deb.sh` | Crea | Build riproducibile del .deb con dpkg-deb |
| `docs/PACKAGING.md` | Crea | Guida build, installazione, systemd, disinstallazione |

### Note per il Cliente
Adesso Command Quiver può essere distribuito come un normale file di
installazione di Ubuntu (il file `.deb`). Chi lo riceve lo installa come qualsiasi
altro programma, con un doppio clic o da terminale, e il sistema si occupa da solo
di scaricare i componenti necessari.

Dopo l'installazione è possibile far partire l'app automaticamente all'accesso al
computer. In quel caso l'app si riavvia da sola solo se va in errore in modo
imprevisto, mentre se sei tu a chiudere la finestra resta chiusa, come ti aspetti.
L'attivazione di questo avvio automatico è facoltativa e si fa con un solo comando,
spiegato nella guida tecnica.

I dati e le impostazioni personali non vengono toccati né dall'installazione né
dalla rimozione.

### Riepilogo
- Complessità: Media
- Stato: Completato (commit `604b631` su `main`; gli artefatti `dist/` e `build/`
  sono esclusi dal repository)

## 2026-10-19 | Sessione #2 [FEATURE] [FIX] [UX]

### Richiesta
Analizzare l'usabilità di Command Quiver con la skill `ux-improver` e applicare i
miglioramenti proposti all'interfaccia GTK4.

### Azioni Eseguite
**Analisi.** Prodotto un mockup interattivo con 40 proposte in
`docs/ux-proposte/index.html`. Le schermate sono ricostruite dal render reale
dell'app in GTK4.

**Implementazione.** Sul branch `feature/ux-improvements` sono state applicate 39
proposte su 40. Le modifiche sono ancora da committare.

- Barra del titolo GNOME con il pulsante "+ Nuova" e un menu (lingua,
  sincronizzazione, importa/esporta, scorciatoie, informazioni).
- Lista delle voci: anteprima del contenuto, tag cliccabili e badge "Comando" e
  "Prompt". Il badge "Prompt" era invisibile perché `@accent_color` non esiste nel
  tema GTK4.
- Avviso "Copiato" dopo la copia negli appunti.
- Conferma prima di eseguire un comando, con l'opzione "non chiedere più".
- Ordinamento accanto alla barra di ricerca. Esc ora svuota la ricerca e non chiude
  più l'app; per uscire si usa Ctrl+Q.
- Schermata di benvenuto con 6 esempi. Stati vuoti per una sezione senza voci e per
  una ricerca senza risultati. Le sezioni iniziali vengono create nella lingua
  scelta.
- Editor: nome facoltativo, tipo spiegato, sezione preimpostata, segnaposto e tag
  a etichette.
- Finestra di sincronizzazione: spiegazione, link per creare il token, campo unico
  utente/repository, errori specifici e pulsante "Sincronizza ora". Lo stato di
  sincronizzazione ora riflette l'esito reale: prima mostrava "Sync OK" prima di
  aver sincronizzato e "0 inviate" in ogni caso.
- Import ed export della libreria in JSON.

**Proposte M8 ed E7, approvate e implementate.**
- E7, eliminazione con Annulla: l'eliminazione non chiede conferma. La voce sparisce
  subito e per 5 secondi compare "Eliminata · Annulla". La cancellazione vera avviene
  alla scadenza dei 5 secondi, a una nuova eliminazione, al cambio lingua o alla
  chiusura dell'app. In questo modo la sincronizzazione non vede voci cancellate e
  poi ricreate.
- M8, riordino per trascinamento: nell'ordine Personale le voci si spostano
  trascinando la maniglia. Le frecce su/giù sono state sostituite da Alt+↑/↓ sulla
  riga selezionata.

**Non approvata** (1 proposta): Y6, creazione del repository da app.

**Bug preesistenti corretti**
- L'ordinamento "Più usati" non sopravviveva al riavvio, perché mancava in
  `VALID_SORT_ORDERS`.
- Le sezioni iniziali eliminate ricomparivano al riavvio, perché il seed girava a
  ogni avvio.
- La fixture `gtk_init` faceva saltare i test UI lanciati da soli.

**Fix emersi dalla code review**
- Import con `section_name` non testuale.
- Test di connessione senza esito in caso di timeout.
- Sincronizzazioni sovrapposte.

**Seconda code review.** Corretti 6 punti:
- cambio lingua con una cancellazione in attesa;
- l'avviso "Copiato" nascondeva Annulla;
- Alt+↑/↓ sullo stato vuoto;
- spostamento da tastiera con posizioni duplicate in "Tutti";
- conteggi delle sezioni dopo la modifica delle sezioni;
- sincronizzazione finale con una sincronizzazione già in corso.

**Scomposizione dei file.** I file dell'interfaccia sopra le 300 righe sono stati
scomposti nei nuovi moduli `library_controller`, `pending_delete`, `row_dnd`,
`search_bar` (con debounce), `editor_widgets` e `section_row`. Restano sopra le 300
righe i file preesistenti `db/queries.py`, `db/database.py` e `core/sync_engine.py`.

**Verifica.** 407 test verdi, ruff pulito. Click-through sull'app reale tramite GTK
Broadway e Chrome. Trascinamento, Elimina e Annulla, filtro per tag ed esempi sono
stati verificati anche con mouse reale su un display X virtuale (Xvfb + xdotool).
Importa/esporta è coperto da un test che percorre il flusso completo su database
reali; la finestra di scelta del file è simulata.

### File Modificati
| Area | Tipo | Descrizione |
|------|------|-------------|
| `docs/ux-proposte/` | Crea | Mockup interattivo con le 40 proposte |
| `command_quiver/ui/` | Crea/Modifica | Nuovi componenti (header, barra di ricerca, stato, toast, stati vuoti, conferma di esecuzione, scorciatoie, tag, azioni libreria) e modifiche a sidebar, lista, editor, pannello sezioni, stili, finestra di sync |
| `command_quiver/core/` | Crea/Modifica | Nuovi moduli `library_io`, `presentation`, `repo_ref`, `samples`, `sync_status`, `locales/`; modifiche a i18n, settings, sync engine, client GitHub |
| `command_quiver/app.py`, `command_quiver/db/database.py` | Modifica | Ciclo di vita dell'app, seed delle sezioni e ordinamento |
| `tests/` | Crea/Modifica | Nuovi test per i moduli aggiunti e per la finestra di sync; aggiornati conftest e test esistenti |
| `CLAUDE.md` | Modifica | Struttura aggiornata |

### Note per il Cliente
L'app è stata resa più facile da usare, partendo da un'analisi delle schermate
reali. Alla prima apertura compare una schermata di benvenuto con alcuni esempi da
cui partire. Ogni voce mostra un'anteprima e un'etichetta che dice se è un comando o
un prompt, e dopo ogni copia appare un avviso di conferma. Prima di eseguire un
comando l'app chiede conferma, ma si può scegliere di non vedere più la domanda.

Il tasto Esc ora cancella solo la ricerca invece di chiudere l'app, che si chiude
con Ctrl+Q. La finestra di sincronizzazione spiega i passaggi e ora mostra lo stato
reale, mentre prima poteva indicare un successo non ancora avvenuto.

Sono stati corretti anche due difetti già presenti: l'ordinamento scelto non veniva
ricordato dopo il riavvio e le sezioni iniziali cancellate tornavano da sole.

Ora le voci si riordinano trascinandole, e una voce eliminata si può recuperare
entro 5 secondi con il pulsante Annulla. Resta ferma una sola proposta, non ancora
approvata: creare il repository di sincronizzazione direttamente dall'app.

### Riepilogo
- Complessità: Alta
- Stato: Implementato e verificato, non ancora committato (branch
  `feature/ux-improvements`); 39 proposte su 40 applicate, Y6 non approvata

## 2026-10-19 | Sessione #3 [REFACTOR] [TEST] [FIX]

### Richiesta
Scomporre i moduli troppo grandi del progetto e coprirli con test comportamentali,
seguendo il workflow Research, Plan, Implement. Gli artefatti di piano sono in
`specs/001-god-module-split/`.

### Azioni Eseguite
**Scomposizione dei moduli.**
- `command_quiver/db/queries.py` (649 righe) è diviso in `section_repository`,
  `entry_repository`, `tombstone_repository`, `sync_repository` ed `entry_import`.
- `command_quiver/db/database.py` è diviso in `database`, `schema` e `backup`.
- In `command_quiver/core/sync_engine.py` le regole pure del sync (merge LWW,
  tombstone, piano del pull) sono in `sync_merge.py`.
- Il coordinamento del sync è estratto da `app.py` in `core/sync_coordinator.py`.
- UI: fusi i due dialog gemelli delle sezioni, estratta la logica pura da
  `section_panel` ed `entry_editor`, rimossa l'API legacy dei callback.
- Client GitHub: `build_request` è ora una funzione pura.

**Bug corretti**, ciascuno con test di regressione in un commit `fix` separato.
- B1: un secondo dispositivo con sezioni omonime falliva al primo sync.
- B2: timestamp in formati misti venivano confrontati come stringhe.
- B3, B3b, B7: il pull ignorava la regola delle tombstone, quindi voci cancellate
  risorgevano e alcune modifiche andavano perse.
- B4: la sezione di default poteva essere cancellata da remoto.
- B6, B9: sezioni del seed senza uuid e database ricreato non migrato.
- B8: delete e tombstone avvenivano in due transazioni diverse.
- B10: voci orfane senza sezione.
- B11: un repository errato veniva mostrato come errore di rete.
- B12: `created_at` vuoto.
- B14: la suite di test sovrascriveva il vero `~/.config/command-quiver/settings.json`.
- B15: un comando con commento finale chiudeva subito il terminale.
- B16: un database bloccato veniva ricreato come se fosse corrotto.
- B17: errori del sync finale, di rete in lettura, di timestamp e backup parziali
  non finivano nel log.
- `Gdk` veniva importato senza `require_version` in 9 moduli.

**Misure.**

| Voce | Prima | Dopo |
|------|-------|------|
| Test | 411 | 862 |
| Coverage | 85% (righe e rami combinati) | righe 99,9%, rami 97,1% |
| Floor CI | 70% righe | 95% rami |

In `ci.yml` sono stati anche ridotti i permessi al minimo e fissate le action a SHA.
Il lavoro è in circa 40 commit atomici su `main`, da `9799abc` a `c674f83`. Nessun
push.

### Aperti
- B13: la lista voci si tronca a 500 elementi senza avviso. La soluzione spetta a una
  decisione dell'utente.
- `SidebarPanel` ed `EntryEditorDialog` restano sopra le 200 righe per classe, come
  eccezioni dichiarate.
- Il test-audit finale ha coperto solo il gruppo app e utilità: gli altri 4 worker
  sono stati fermati dall'utente, quindi i restanti gruppi non hanno un audit
  completato.

### Azione richiesta all'utente
Il sync GitHub risulta disattivato dal 2 ottobre, perché i test riscrivevano
`~/.config/command-quiver/settings.json` (bug B14, ora corretto). Il token è ancora
presente. Nel dialog di sincronizzazione (menu ☰) vanno reinseriti owner e
repository. Finché non lo si fa, le voci non si sincronizzano tra dispositivi.

### File Modificati
| Area | Tipo | Descrizione |
|------|------|-------------|
| `command_quiver/db/` | Crea/Modifica | Repository separati, `schema.py`, `backup.py`, `entry_import.py`; rimosso `queries.py` |
| `command_quiver/core/` | Crea/Modifica | `sync_merge.py`, `sync_coordinator.py`, `build_request` puro nel client GitHub |
| `command_quiver/ui/`, `command_quiver/app.py` | Modifica | Dialog sezioni fusi, logica pura estratta, API callback legacy rimossa |
| `tests/` | Crea/Modifica | Da 411 a 862 test, con regressioni per ogni bug |
| `.github/workflows/ci.yml` | Modifica | Floor 95% rami, permessi minimi, action pinnate a SHA |
| `specs/001-god-module-split/` | Crea | Artefatti del workflow RPI |

### Note per il Cliente
Il codice è stato riorganizzato in parti più piccole, così da essere più semplice da
mantenere. Durante il lavoro sono emersi e sono stati corretti diversi difetti, tra
cui voci cancellate che ricomparivano dopo la sincronizzazione e modifiche che a volte
andavano perse. Anche i controlli automatici sono molto più estesi: da 411 a 862
verifiche.

Va fatta una cosa a mano: la sincronizzazione con GitHub è ferma dal 2 ottobre, per
un difetto dei test ora corretto. Basta aprire la finestra di sincronizzazione e
reinserire utente e repository. Il token è ancora salvato.

Resta aperta una decisione: la lista delle voci mostra al massimo 500 elementi senza
avvisare. Va deciso come comportarsi oltre quel limite.

### Riepilogo
- Complessità: Alta
- Stato: Completato su `main` (commit `9799abc`..`c674f83`, nessun push); aperti B13,
  due classi UI oltre i limiti e il test-audit incompleto

## 2026-10-19 | Sessione #4 [REFACTOR] [TEST] [FIX]

### Richiesta
Fase 2 della scomposizione dei moduli grandi e audit di qualità dei test (core, sync,
db, ui), per avere una copertura "vera": test che falliscono davvero quando il codice
sbaglia, non solo righe eseguite. Workflow Research, Plan, Implement; gli artefatti di
piano sono in `specs/002-god-module-split-phase2/`.

### Azioni Eseguite
**Audit dei test.** 5 worker hanno cercato mutanti sopravvissuti (modifiche al codice
che nessun test nota). Sono stati confermati 50 mutanti eseguendoli uno per uno; tutti
sono stati uccisi dai test nuovi, verificato rieseguendo i mutanti. Due finding dei
worker sono stati smentiti dall'esecuzione e scartati.

**Difetti di produzione corretti**, ognuno con un test visto rosso prima del fix.
- Un comando con errore di sintassi o con `exit` chiudeva il terminale prima di
  mostrare l'errore. Ora gira in una bash annidata.
- L'import si interrompeva a metà con sezioni che differiscono solo per le maiuscole
  ("git" e "Git").
- Il token GitHub veniva creato per un istante con i permessi dell'umask, prima del
  `chmod 600`. Ora il file nasce con permessi 600. Il `security-reviewer` non ha
  trovato problemi sfruttabili residui.
- L'app non partiva con un `settings.json` non valido (lista JSON, byte non UTF-8,
  path illeggibile), nonostante la docstring promettesse i valori di default. Stesso
  difetto nella lettura del token.
- Nella ricerca `_` e `%` facevano da jolly: cercare `my_var` trovava `myXvar`.
- `cancel()` della ricerca non annullava una ricerca digitata nei 150 ms precedenti
  (doppio debounce, GTK e nostro). Ora c'è un solo debounce da 250 ms e i risultati
  arrivano anche più rapidi.

**Difetto dei test.** Le eccezioni dentro gli handler GTK venivano stampate e ignorate
da PyGObject, quindi un clic che andava in crash dava comunque un test verde. Ora una
fixture autouse fa fallire il test. Attivarla ha fatto emergere timer lasciati da test
precedenti, che scattavano a database chiuso: ora vengono annullati nel teardown.

**Refactor.**
- `SectionRow` ricava l'id dalla sezione (eliminato uno stato incoerente).
- `describe_sync_status` riceve `SyncSettings` e `SyncResult` invece di una tupla
  posizionale.
- `RunConfirmDialog` e `SyncSetupDialog` sono spezzati in funzioni sotto le 30 righe.
- `entry_payload` (puro) ed `EditorRequest` (da 7 a 4 parametri) sono in
  `command_quiver/ui/editor_request.py`; `entry_editor.py` scende sotto le 300 righe.

**Misure.**

| Voce | Prima | Dopo |
|------|-------|------|
| Test | 862 | 962 |
| Copertura righe | 99,9% | 99,97% |
| Copertura rami | ~97,7% | 98,09% |
| Copertura combinata | - | 99,7% |
| Floor CI (`--cov-fail-under`, misura la combinata) | 95 | 98 |

**Gate.** `code-reviewer`: APPROVE, con rilievi applicati (file oltre 300 righe,
keyword argument, commento ripristinato). `type-design-analyzer`: APPROVE su
`EditorRequest`. `/analyze`: 1 CRITICAL (funzione a 33 righe), corretto, poi artefatti
allineati. Verifica runtime: avvio reale dell'app con HOME e D-Bus isolati, migrazioni,
finestra presentata e chiusura ordinata, senza errori nel log.

Il lavoro è in 27 commit su `main`, da `3a6aaf5` a `16bc4ad`. Nessun push.

### Non Fatto, con Motivo
- Gate automatico dei limiti dimensionali (T1): non richiesto, resta una proposta.
- Rimozione di `confirm_and_run`: rifiutata, tre test la usano direttamente.
- `SidebarPanel` non scomposta: è la composition root, 195 righe di codice.
- 5 rami irraggiungibili segnalati e non rimossi: `db/schema.py:212`,
  `ui/entry_list.py:276` e `281`, `ui/section_panel.py:191`, `ui/sync_dialog.py:222`,
  `ui/library_controller.py:93`.
- 3 rami a basso valore lasciati senza test: `ui/entry_list.py:261`,
  `ui/section_panel.py:181`, `ui/sidebar.py:270`.

### Aperti / Decisioni per l'Utente
- B13: la lista si tronca a 500 voci senza avviso, ancora aperto.
- La conferma di esecuzione mostra solo i primi 600 caratteri del comando ma esegue il
  comando intero: una voce importata può nascondere la coda. Da decidere tra scroll con
  il testo completo o un avviso di troncamento.
- Sync: se la versione locale è più vecchia di una tombstone e la remota è più nuova,
  la voce viene scartata invece di far vincere la remota (`sync_merge.py:81`). Scenario
  raro, da decidere.
- L'ordine delle sezioni non si propaga fra dispositivi (viene esportato ma non
  applicato al pull). È voluto?
- Il log "DB legacy rilevato con schema v1" compare anche su un database appena
  creato. Fuorviante, preesistente.

### File Modificati
| Area | Tipo | Descrizione |
|------|------|-------------|
| `command_quiver/core/` | Modifica | Esecuzione comandi in bash annidata, token creato con permessi 600, lettura robusta di `settings.json`, `describe_sync_status` con parametri tipizzati |
| `command_quiver/db/` | Modifica | Escape di `_` e `%` nella ricerca, import con sezioni che differiscono per maiuscole |
| `command_quiver/ui/` | Crea/Modifica | `editor_request.py`, debounce unico di ricerca, `SectionRow`, dialog spezzati |
| `tests/` | Crea/Modifica | Da 862 a 962 test, fixture autouse sulle eccezioni GTK, teardown dei timer |
| `.github/workflows/ci.yml` | Modifica | Floor di copertura da 95 a 98 |
| `specs/002-god-module-split-phase2/` | Crea | Piano, specifica e task del workflow RPI |

### Note per il Cliente
Il codice è più ordinato e i controlli automatici sono più severi: da 862 a 962
verifiche. Abbiamo anche controllato che questi controlli scoprano davvero gli errori,
introducendo di proposito dei difetti e verificando che venissero notati.

Sono stati corretti sei difetti. La ricerca con i simboli "_" e "%" restituiva
risultati sbagliati. L'app non si avviava se il file delle impostazioni era rovinato.
Per un istante molto breve il codice di accesso alla sincronizzazione poteva essere
letto da altri utenti dello stesso computer. Un comando con un errore chiudeva la
finestra prima di mostrarlo, e l'importazione si fermava a metà con sezioni dal nome
quasi uguale. Infine una ricerca scritta un attimo prima di cambiare lingua restava
in sospeso e partiva dopo; ora no, e i risultati compaiono anche un po' prima.

Restano da decidere alcuni comportamenti, elencati sopra.

### Riepilogo
- Complessità: Alta
- Stato: Completato su `main` (commit `3a6aaf5`..`16bc4ad`, nessun push); aperti B13 e
  le quattro decisioni elencate, più i rami irraggiungibili segnalati
