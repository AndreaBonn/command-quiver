[English](SECURITY.md) | **Italiano**

# Policy di Sicurezza

## Versioni supportate

| Versione | Supportata |
|---|---|
| 2.1.x | Sì |
| < 2.1 | No |

## Segnalare una vulnerabilità

Per segnalare una vulnerabilità di sicurezza, usa [GitHub Security Advisories](https://github.com/AndreaBonn/command-quiver/security/advisories/new). Non aprire una issue pubblica.

Il report dovrebbe includere:

- Descrizione della vulnerabilità
- Passi per riprodurla
- Versione/i interessate
- Impatto potenziale

**Tempi di risposta:**

- Conferma di ricezione entro 72 ore
- Fix per vulnerabilità critiche entro 30 giorni
- Disclosure pubblica coordinata dopo il rilascio del fix

## Misure di sicurezza

Command Quiver by Bonn è un'applicazione desktop locale. L'unico traffico di rete è la sincronizzazione GitHub, facoltativa, che parla con `api.github.com` in HTTPS usando un token fornito da te. Le misure adottate sono:

- **Query parametrizzate**: ogni valore che arriva dall'utente, da un file di import o dal sync viene passato con placeholder `?`, mai concatenato nell'SQL (`db/*_repository.py`)
- **Validazione input**: le impostazioni vengono validate al caricamento con valori limitati e controlli su insiemi ammessi (`core/settings.py`); i file importati hanno un tetto di 10.000 voci e 100.000 caratteri per campo (`db/entry_import.py`)
- **Vincoli database**: CHECK constraint sui tipi di voce e di tombstone, foreign key enforcement abilitato (`db/schema.py`, `db/database.py`)
- **Nessun shell=True nelle chiamate subprocess**: il terminale viene avviato con una lista di argomenti e il comando è protetto con `shlex.quote` (`core/executor.py`)
- **Conferma prima di eseguire**: un comando shell parte solo dopo una finestra di conferma, che si può disattivare una voce alla volta (`ui/run_confirm.py`)
- **Token di sync leggibile solo dal proprietario**: il token GitHub sta in un file a parte, creato direttamente con permessi 600 e non ristretto dopo (`core/settings.py`)
- **Dependency lockfile**: `uv.lock` blocca le versioni di tutte le dipendenze

## Considerazioni di sicurezza per gli utenti

- Il database SQLite (`vault.db`) e i suoi backup automatici sono salvati senza cifratura in `~/.local/share/command-quiver/`. Se memorizzi informazioni sensibili nelle voci, proteggi questa directory con permessi adeguati.
- Con la sincronizzazione attiva, le voci vengono copiate in JSON in chiaro nel repository GitHub che scegli. Tieni quel repository privato e dai al token accesso solo a quel repository, con Contents in lettura e scrittura e nient'altro.
- I comandi shell vengono eseguiti così come sono in gnome-terminal. Controllali prima di eseguirli, soprattutto se importati o sincronizzati da altrove, e lascia attiva la conferma per le voci che non hai scritto tu.
- I file di log in `~/.local/share/command-quiver/logs/` contengono i nomi delle voci e i primi 80 caratteri dei comandi eseguiti. Limita l'accesso se sono informazioni sensibili.
- L'app si registra sul session bus D-Bus come `Gtk.Application` standard (`com.github.commandquiver`) per garantire l'istanza singola. Qualsiasi processo della stessa sessione utente può attivarla, come per ogni applicazione desktop.
- **Trust model import JSON**: l'import accetta voci di tipo `shell` il cui contenuto viene eseguito così com'è nel terminale. La conferma di esecuzione mostra prima il comando, a meno che non sia stata disattivata per quella voce. Importa solo file da fonti di cui ti fidi.

## Fuori ambito

I seguenti casi non sono considerati vulnerabilità ai fini di questa policy:

- Attacchi che richiedono accesso fisico alla macchina
- Social engineering
- Vulnerabilità in dipendenze di terze parti già divulgate pubblicamente (segnalale al progetto upstream)
- Danni auto-inflitti da comandi shell che l'utente sceglie di eseguire
- Esposizione dati quando i permessi della home directory dell'utente sono configurati male

## Riconoscimenti

I ricercatori di sicurezza che segnalano vulnerabilità valide verranno accreditati qui su richiesta.

---

[Torna al README](README.it.md)
