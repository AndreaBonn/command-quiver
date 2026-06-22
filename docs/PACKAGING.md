# Pacchetto Debian (.deb)

Guida alla costruzione, installazione e gestione del pacchetto `.deb` di Command
Quiver. Il pacchetto installa l'applicazione a livello di sistema e include un
servizio systemd a livello utente per l'avvio al login e il riavvio automatico
in caso di crash.

## Requisiti di build

- `dpkg-deb` (pacchetto `dpkg`, presente di default su Debian/Ubuntu)
- `python3` con GdkPixbuf (pacchetto `python3-gi`), usato per generare le icone
- `gzip`

## Costruzione

```bash
./scripts/build-deb.sh
```

Lo script legge la versione da `command_quiver/__init__.py`, assembla la struttura
del pacchetto in `build/deb/` e produce il file in `dist/`:

```
dist/command-quiver_<versione>_all.deb
```

L'architettura è `all` perché l'applicazione è pure-Python e non contiene codice
compilato.

## Contenuto del pacchetto

| Percorso installato | Contenuto |
|---|---|
| `/usr/lib/command-quiver/command_quiver/` | Codice dell'applicazione |
| `/usr/bin/command-quiver` | Wrapper che imposta `PYTHONPATH` e avvia l'app |
| `/usr/share/applications/com.github.commandquiver.desktop` | Voce di menu GNOME |
| `/usr/share/icons/hicolor/{32,48,64,128}x.../apps/` | Icone applicazione |
| `/usr/lib/systemd/user/command-quiver.service` | Servizio systemd (utente) |
| `/usr/share/doc/command-quiver/` | `copyright` e `changelog.Debian.gz` |

Le dipendenze runtime (`python3`, `python3-gi`, `python3-gi-cairo`,
`gir1.2-gtk-4.0`, `gnome-terminal`) sono dichiarate nel pacchetto e risolte
automaticamente da apt.

I dati utente (`~/.local/share/command-quiver/`, `~/.config/command-quiver/`) non
sono toccati dal pacchetto: restano intatti dopo installazione e rimozione.

## Installazione

```bash
sudo apt install ./dist/command-quiver_1.0.0_all.deb
```

`apt install` con un percorso locale installa il pacchetto e risolve le
dipendenze. In alternativa `sudo dpkg -i ...` seguito da `sudo apt -f install`
per le dipendenze mancanti.

Dopo l'installazione l'app è avviabile dal menu GNOME o da terminale con
`command-quiver`.

## Servizio systemd (avvio automatico e riavvio)

Il pacchetto installa il servizio **disabilitato**: nessun avvio automatico
finché non lo attivi esplicitamente. È un servizio a livello utente perché
l'applicazione è una GUI che gira nella sessione grafica.

Attivazione (avvio al login + riavvio su crash):

```bash
systemctl --user enable --now command-quiver.service
```

Il servizio usa `Restart=on-failure`: viene riavviato solo in caso di crash
(uscita con errore), non quando chiudi volontariamente la finestra (uscita
regolare).

Comandi utili:

```bash
systemctl --user status command-quiver.service     # stato
systemctl --user restart command-quiver.service    # riavvio manuale
systemctl --user disable --now command-quiver.service  # disattiva e ferma
journalctl --user -u command-quiver.service         # log del servizio
```

I log applicativi restano comunque in `~/.local/share/command-quiver/logs/`.

## Disinstallazione

Prima disattiva il servizio (se attivato), poi rimuovi il pacchetto:

```bash
systemctl --user disable --now command-quiver.service
sudo apt remove command-quiver
```

I dati utente non vengono rimossi. Per eliminarli manualmente:

```bash
rm -rf ~/.local/share/command-quiver ~/.config/command-quiver
```

## Note

- **Sessione grafica**: il servizio dipende da `graphical-session.target`,
  fornito dalla sessione utente systemd (standard su Ubuntu GNOME). Se in una
  configurazione particolare l'avvio automatico non parte, sostituisci
  `WantedBy=graphical-session.target` con `WantedBy=default.target` nell'unit.
- **Coesistenza con `install.sh`**: il pacchetto installa l'eseguibile in
  `/usr/bin/command-quiver`, mentre `install.sh` usa `/usr/local/bin/command-quiver`.
  I due metodi non si sovrascrivono, ma installarli entrambi crea due copie
  dell'applicazione. Usa un metodo solo.
