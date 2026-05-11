## What's Changed in v1.0.0

> The initial release of Command Quiver, a desktop prompt and shell command library.

### ✨ New Features
- Aggiunta la possibilità di copiare il contenuto facendo clic sulla riga di una voce e aggiunto un pulsante di modifica (f69ebf8)
- Implementati miglioramenti per la produzione (303090a)
- Aggiunto un file desktop e uno script di installazione per il menu GNOME (539e7bb)
- Sostituito l'icona Q generata con un'icona personalizzata per l'app (21dcb61)
- Aggiunto supporto bilingue con cambio di lingua in tempo reale (c06b3cb)
- Utilizzata un'icona SVG simbolica per il ridimensionamento corretto della barra di sistema GNOME (0c80f52)
- Inizializzato Command Quiver — prompt desktop e libreria di comandi shell (70b07b4)

### 🐛 Bug Fixes
- Abilitati i pacchetti di sistema per PyGObject nell'ambiente di test virtuale (#2)
- Eseguita la correzione della sicurezza, dei test e della qualità del codice (#1)
- Reso più sicuro lo script di installazione per la distribuzione tra colleghi (1c16a51)
- Abilitati i pacchetti di sistema per PyGObject nell'ambiente di test virtuale (6873153)
- Aggiornata la finestra del titolo in "Command Quiver by Bonn" (9067e43)
- Aggiunte limitazioni di importazione per impedire l'esaurimento della memoria da file JSON troppo grandi (1ac432f)
- Reindirizzato l'errore dello helper della barra di sistema al file di registro invece di DEVNULL (30e5cb6)
- Rimossa la lettura ridondante del buffer nell'azione di salvataggio e copia (b46e6fc)
- Aggiunte firme di tipo complete ai parametri di callback delle funzioni richiamabili (6933499)
- Reso più sicuro l'app per la produzione (45865a5)
- Utilizzata l'API icon-name di GTK4 e corretta il file desktop non valido (535939b)
- Impedita la ricorsione infinita nel percorso di ripristino del database (35303ac)
- Utilizzato ANSI-C per citare il messaggio shell per prevenire l'iniezione (b4c807e)
- Utilizzato un nome di backup con timestamp per impedire la sovrascrittura silenziosa (81d613c)
- Rimosso il parametro _on_delete_request non utilizzato (078d7f3)
- Aggiunta un'annotazione di tipo mancante sul parametro section (a8269c8)
- Restringenti i blocchi di cattura da Exception a GLib.Error (ddf46b2)
- Sostituito print() con il modulo di registrazione (d3576be)
- Sostituito SNI D-Bus con il processo helper AyatanaAppIndicator3 (4b3d477)
- Riparato lo script di installazione e le stringhe di formato GVariant (6ec9ff7)

### 📚 Documentation
- Rinomina in "Command Quiver by Bonn" in tutta la documentazione (d16e72a)
- Documentato il modello di fiducia per l'importazione JSON per le voci shell (7b8fd51)
- Documentata l'esposizione del bus sessione D-Bus nelle considerazioni di sicurezza (83684a1)
- Chiarito che PRAGMA user_version non può utilizzare parametri associati (66114bf)
- Aggiunto un badge CI al README (bd159dd)
- Aggiunta documentazione open source e licenza MIT (4ba1e3f)

### 🔧 Maintenance
- Aggiunto il generatore di changelog AI al workflow CI (e42012f)
- Aggiunto il workflow di revisione PR AI (65dc2ea)
- Modificata la licenza da MIT ad Apache 2.0 (c867fd2)
- Aggiornati i badge [salta ci] (83efb0a)
- Aggiornati i badge [salta ci] (2eaf85c)
- Aggiunti badge dinamici per il conteggio dei test e la copertura (8bcf65d)
- Ridimensionata icon.png da 1254x1254 a 256x256 (1,2 MB → 49 KB) (2ee7d39)
- Aggiunto un limite di copertura (70%) per impedire la regressione silenziosa (cd23669)
- Allineato il classificatore con lo stato di rilascio v1.0.0 (413adaf)
- Aggiunto il controllo del formato e i metadati del progetto (c8ae059)
- Unificati i fix di rimediazione dell'audit (6b278f3)
- Aggiunto il workflow GitHub Actions per lint e test (5c0fc14)
- Aggiunto il sistema di build hatchling per l'installabilità del pacchetto (985add1)
- Rimosso doc_progetto dal monitoraggio e aggiunto a gitignore (3ede3ae)

### Other changes
- Aggiunti 60 test, aumentata la copertura dal 77% all'85% (bcf9672)
- Aggiunti test unitari per le callback della helper della barra di sistema e la comunicazione D-Bus (b4c841b)
- Integraati i fix di rimediazione dell'audit e i refactoring (fb8f5f9)
- Chiusi i gap di copertura nei moduli settings, i18n e database (1cf5ecf)
- Aggiunta una suite di test completa che copre l'87% del codice (f54e906)