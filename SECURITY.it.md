[English](SECURITY.md) | **Italiano**

# Policy di Sicurezza

## Versioni supportate

| Versione | Supportata |
|---|---|
| 1.0.x | Sì |

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

Command Quiver è un'applicazione desktop locale senza componenti esposti in rete. Non gestisce autenticazione, connessioni remote o credenziali utente. Le seguenti misure sono implementate:

- **Query parametrizzate**: tutte le operazioni database usano placeholder `?`, nessuna concatenazione di stringhe (`db/queries.py`)
- **Validazione input**: le impostazioni vengono validate al caricamento con valori limitati e controlli su insiemi ammessi (`core/settings.py:40-49`)
- **Vincoli database**: CHECK constraint sul tipo di voce, foreign key enforcement abilitato (`db/database.py:24, 80`)
- **Nessun shell=True nelle chiamate subprocess**: tutte le invocazioni subprocess passano argomenti come lista (`core/executor.py:50`, `app.py:150`)
- **Dependency lockfile**: `uv.lock` blocca le versioni di tutte le dipendenze

## Considerazioni di sicurezza per gli utenti

- Il database SQLite (`vault.db`) è salvato senza cifratura in `~/.local/share/command-quiver/`. Se salvi informazioni sensibili nelle voci, proteggi questa directory con permessi file appropriati.
- I comandi shell vengono eseguiti così come sono in gnome-terminal. Verifica i comandi prima dell'esecuzione, specialmente se importati da fonti esterne.
- I file di log in `~/.local/share/command-quiver/logs/` possono contenere nomi delle voci. Limita l'accesso se i nomi sono sensibili.

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
