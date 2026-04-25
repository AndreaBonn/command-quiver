[English](README.md) | **Italiano**

# Command Quiver

Libreria personale di prompt AI e comandi shell, accessibile dalla system tray di GNOME. Cerca, organizza in sezioni, copia negli appunti o esegui nel terminale.

<div align="center">

[![CI](https://github.com/AndreaBonn/command-quiver/actions/workflows/ci.yml/badge.svg)](https://github.com/AndreaBonn/command-quiver/actions/workflows/ci.yml)
[![Tests](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/AndreaBonn/command-quiver/main/badges/test-badge.json)](https://github.com/AndreaBonn/command-quiver/actions/workflows/ci.yml)
[![Coverage](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/AndreaBonn/command-quiver/main/badges/coverage-badge.json)](https://github.com/AndreaBonn/command-quiver/actions/workflows/ci.yml)
[![Ruff](https://img.shields.io/badge/linter-ruff-261230.svg)](https://docs.astral.sh/ruff/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Security Policy](https://img.shields.io/badge/security-policy-blueviolet.svg)](SECURITY.md)

</div>

## Panoramica

Command Quiver vive nella system tray di GNOME e offre accesso rapido a prompt AI e comandi shell usati di frequente. Le voci sono salvate in un database SQLite locale, organizzate in sezioni e ricercabili per nome. I prompt vengono copiati negli appunti; i comandi shell possono essere eseguiti direttamente in gnome-terminal.

## Funzionalità

- Icona nella system tray con menu contestuale (mostra/nascondi, nuova voce, esci)
- Pannello laterale con ricerca e ordinamento multiplo (alfabetico, cronologico, personalizzato)
- Due tipi di voce: prompt AI (copia negli appunti) e comandi shell (esegui nel terminale)
- Sezioni per organizzare le voci, con riordinamento drag-and-drop
- Interfaccia bilingue (italiano / inglese) con cambio lingua live
- Persistenza SQLite con WAL mode e recovery automatico da corruzione
- Singola istanza garantita via D-Bus
- Impostazioni persistenti (ordinamento, dimensione finestra, lingua, tema)

## Requisiti

- Python >= 3.10
- GTK4 e PyGObject
- AyatanaAppIndicator3 (per icona nella system tray)
- gnome-terminal (per esecuzione comandi shell)
- pycairo (per generazione icona)

Su Ubuntu/Debian:

```bash
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-4.0 \
    gir1.2-ayatanaappindicator3-0.1 gnome-terminal
```

## Installazione

```bash
git clone https://github.com/AndreaBonn/command-quiver.git
cd command-quiver
uv sync
```

## Utilizzo

Avvia l'applicazione:

```bash
uv run python command_quiver/main.py
```

L'icona tray appare nella barra superiore di GNOME. Click sinistro per mostrare/nascondere la sidebar, click destro per il menu contestuale.

Dalla sidebar:

- Click su **+ Nuova voce** per creare un prompt o un comando shell
- Click su una voce per copiarla negli appunti (prompt) o eseguirla (comandi shell)
- Usa la barra di ricerca per filtrare le voci per nome
- Cambia ordinamento dal dropdown (Recenti, A-Z, Z-A, Personale)
- Gestisci le sezioni con **+ Sezione**, oppure click destro su una sezione per rinominare/eliminare

### Percorsi dei dati

| Percorso | Contenuto |
|---|---|
| `~/.local/share/command-quiver/vault.db` | Database SQLite |
| `~/.config/command-quiver/settings.json` | Impostazioni utente |
| `~/.local/share/command-quiver/logs/` | Log applicazione |

## Test

```bash
uv run pytest
```

Con copertura:

```bash
uv run pytest --cov=command_quiver
```

Lint:

```bash
uv run ruff check .
```

## Contribuire

I contributi sono benvenuti. Apri una issue per discutere la modifica prima di inviare un pull request. Segui lo stile del codice esistente (configurazione ruff in `pyproject.toml`) e includi test per le nuove funzionalità.

## Sicurezza

Per segnalare vulnerabilità, consulta la [policy di sicurezza](SECURITY.it.md).

## Licenza

Rilasciato sotto licenza MIT -- vedi [LICENSE](LICENSE).

## Autore

Andrea Bonacci -- [@AndreaBonn](https://github.com/AndreaBonn)

---

Se questo progetto ti è utile, una stella su GitHub è apprezzata.
