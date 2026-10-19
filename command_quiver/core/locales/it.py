"""Traduzioni italiane dell'interfaccia (lingua di default)."""

STRINGS: dict[str, str] = {
    # --- Barra del titolo e menu ---
    "header.new_entry": "Nuova",
    "header.new_entry_tooltip": "Nuova voce (Ctrl+N)",
    "header.menu_tooltip": "Menu principale",
    "menu.language": "Lingua",
    "menu.sync": "Sincronizzazione…",
    "menu.import": "Importa voci…",
    "menu.export": "Esporta voci…",
    "menu.shortcuts": "Scorciatoie da tastiera",
    "menu.about": "Informazioni",
    "menu.quit": "Esci",
    "about.comments": "Libreria personale di prompt AI e comandi shell.",
    # --- Sidebar ---
    "sidebar.search_placeholder": "Cerca in nomi, contenuti e tag",
    "sidebar.sort_tooltip": "Ordina le voci",
    "sidebar.sort_recent_desc": "Più recenti",
    "sidebar.sort_oldest_asc": "Meno recenti",
    "sidebar.sort_alpha_asc": "Nome A-Z",
    "sidebar.sort_alpha_desc": "Nome Z-A",
    "sidebar.sort_personal": "Personale",
    "sidebar.sort_usage": "Più usati",
    "sidebar.new_entry": "+ Nuova voce",
    "sidebar.sections_header": "SEZIONI",
    "sidebar.new_section": "+ Sezione",
    "sidebar.all_entries": "Tutti",
    "sidebar.section_actions": "Azioni sulla sezione {name}",
    "sidebar.rename": "Rinomina",
    "sidebar.delete": "Elimina",
    "sidebar.default_not_deletable": "Elimina: non disponibile, è la sezione predefinita",
    "sidebar.language": "Lingua",
    # --- Lista voci ---
    "entry_list.copy_tooltip": "Copia",
    "entry_list.row_tooltip": "Clic sulla riga per copiare",
    "entry_list.edit_tooltip": "Modifica",
    "entry_list.execute_tooltip": "Esegui nel terminale",
    "entry_list.tag_tooltip": "Mostra le voci con il tag {tag}",
    "entry_list.drag_tooltip": "Trascina per riordinare (oppure Alt+↑/↓)",
    "entry_list.terminal_not_found": "Terminale non trovato",
    "badge.shell": "Comando",
    "badge.prompt": "Prompt",
    "run.title": "Eseguire nel terminale?",
    "run.dont_ask": "Non chiedere più per questa voce",
    "run.run": "Esegui",
    # --- Avvisi temporanei ---
    "toast.copied": "Copiato: {name}",
    "toast.samples_added": "Aggiunte {count} voci di esempio",
    "toast.imported": "Importate {count} voci",
    "toast.exported": "Esportate {count} voci",
    "toast.import_failed": "Il file non è un export valido di Command Quiver",
    "toast.export_failed": "Impossibile scrivere il file",
    "toast.deleted": "Eliminata: {name}",
    "toast.undo": "Annulla",
    # --- Stati vuoti ---
    "empty.welcome_title": "Tieni a portata di mano i tuoi prompt e comandi",
    "empty.welcome_prompt": "Prompt AI: un clic e il testo è negli appunti, pronto da incollare.",
    "empty.welcome_shell": "Comandi: si copiano, oppure si lanciano nel terminale con ▶.",
    "empty.welcome_sections": (
        "Le sezioni a sinistra li tengono in ordine; la ricerca li trova tutti."
    ),
    "empty.create_first": "Crea la prima voce",
    "empty.add_samples": "Prova con 6 esempi",
    "empty.samples_note": "Gli esempi si eliminano come le altre voci.",
    "empty.section_title": "Ancora niente in {section}",
    "empty.section_hint": "Le voci che crei qui restano raggruppate in questa sezione.",
    "empty.section_add": "Aggiungi in {section}",
    "empty.search_title": "Nessun risultato per «{query}»",
    "empty.search_title_in": "Nessun risultato per «{query}» in {section}",
    "empty.search_hint_section": "La ricerca guarda solo nella sezione selezionata.",
    "empty.search_all": "Cerca in tutte le sezioni",
    "empty.search_clear": "Cancella ricerca",
    # --- Stato sincronizzazione (barra in basso) ---
    "status.local": "Salvato solo su questo computer",
    "status.local_action": "Sincronizza tra dispositivi",
    "status.pending": "Sincronizzazione in corso…",
    "status.ok": "Sincronizzato {when}",
    "status.ok_counts": "Sincronizzato {when}: {pulled} ricevute, {pushed} inviate",
    "status.error": "Sincronizzazione non riuscita",
    "status.details": "Dettagli",
    # --- Scorciatoie ---
    "shortcuts.title": "Scorciatoie da tastiera",
    "shortcuts.search": "Vai alla ricerca",
    "shortcuts.new": "Nuova voce",
    "shortcuts.copy_first": "Copia la prima voce trovata",
    "shortcuts.clear": "Svuota la ricerca",
    "shortcuts.reorder": "Sposta la voce selezionata (ordine Personale)",
    "shortcuts.quit": "Esci",
    "shortcuts.save": "Salva (nella finestra della voce)",
    "shortcuts.save_copy": "Salva e copia (nella finestra della voce)",
    "shortcuts.help": "Mostra questo elenco",
    # --- Editor voce ---
    "editor.title_edit": "Modifica voce",
    "editor.title_new": "Nuova voce",
    "editor.name_label": "Nome (facoltativo)",
    "editor.name_placeholder": "Nome della voce...",
    "editor.name_hint": "Se lo lasci vuoto, usiamo la prima riga del contenuto.",
    "editor.type_prompt": "Prompt AI",
    "editor.type_prompt_desc": "Testo da incollare in ChatGPT, Claude e simili. Si copia.",
    "editor.type_shell": "Comando",
    "editor.type_shell_desc": "Riga da terminale. Si copia o si esegue con ▶.",
    "editor.section_label": "Sezione",
    "editor.content_label": "Contenuto",
    "editor.content_placeholder_prompt": (
        "Es. Riassumi il testo seguente in 5 punti, con tono neutro:"
    ),
    "editor.content_placeholder_shell": "Es. git log --oneline -10",
    "editor.tags_label": "Tag",
    "editor.tags_placeholder": "Scrivi un tag e premi Invio",
    "editor.tags_used": "Già usati:",
    "editor.tag_remove": "Rimuovi il tag {tag}",
    "editor.btn_delete": "Elimina",
    "editor.btn_cancel": "Annulla",
    "editor.btn_save_copy": "Salva e Copia",
    "editor.btn_save": "Salva",
    "editor.error_content_required": "Il contenuto è obbligatorio",
    # --- Gestione sezioni ---
    "section.title_new": "Nuova sezione",
    "section.name_label": "Nome sezione",
    "section.name_placeholder": "Nome della sezione...",
    "section.error_name_required": "Il nome è obbligatorio",
    "section.error_name_duplicate": 'La sezione "{name}" esiste già',
    "section.title_rename": "Rinomina sezione",
    "section.new_name_label": "Nuovo nome",
    "section.btn_rename": "Rinomina",
    "section.btn_create": "Crea",
    "section.confirm_delete_title": 'Eliminare la sezione "{name}"?',
    "section.confirm_delete_detail": (
        "Le voci contenute verranno spostate nella sezione 'Generale'."
    ),
    # --- Esecuzione ---
    "executor.terminal_not_found": (
        "gnome-terminal non trovato. Installalo con: sudo apt install gnome-terminal"
    ),
    "executor.press_enter": "\n--- Premere INVIO per chiudere ---",
    # --- Finestra sincronizzazione ---
    "sync.title": "Sincronizzazione GitHub",
    "sync.intro": (
        "Facoltativa. Copia le tue voci in un repository GitHub privato, così le "
        "ritrovi su un altro computer. Senza, tutto resta solo qui."
    ),
    "sync.repo": "Repository",
    "sync.repo_placeholder": "utente/nome-repository",
    "sync.repo_hint": "Accetta anche l'indirizzo copiato da GitHub.",
    "sync.token": "Token GitHub",
    "sync.token_placeholder": "github_pat_...",
    "sync.token_link": "Crea un token su GitHub",
    "sync.token_hint": (
        "Tipo «fine-grained», solo questo repository, permesso Contents in lettura e scrittura."
    ),
    "sync.btn_test": "Testa connessione",
    "sync.btn_enable": "Attiva sincronizzazione",
    "sync.btn_disable": "Disattiva sincronizzazione",
    "sync.btn_sync_now": "Sincronizza ora",
    "sync.testing": "Verifico…",
    "sync.conn_ok": "Connessione riuscita: il repository è raggiungibile.",
    "sync.conn_missing_fields": "Compila repository e token.",
    "sync.conn_bad_repo": (
        "Scrivi il repository come utente/nome, oppure incolla l'indirizzo GitHub."
    ),
    "sync.conn_bad_token": (
        "GitHub rifiuta il token: è scaduto o non valido. Creane uno nuovo e incollalo qui."
    ),
    "sync.conn_forbidden": (
        "Il token non ha i permessi su questo repository: serve Contents in lettura e scrittura."
    ),
    "sync.conn_not_found": (
        "Repository non trovato: controlla il nome, o che il token possa vederlo."
    ),
    "sync.conn_network": "GitHub non risponde: controlla la connessione a Internet.",
    "sync.conn_unknown": "GitHub ha risposto con un errore inatteso. Riprova tra poco.",
    "sync.saved": "Sincronizzazione attiva: la prima parte adesso.",
    "sync.disabled_info": "Sincronizzazione disattivata: le voci restano su questo computer.",
    "sync.last_sync": "Ultima sincronizzazione: {time}",
    "sync.never": "Non ancora sincronizzato",
    # --- Tempo relativo ---
    "time.now": "adesso",
    "time.minute": "1 minuto fa",
    "time.minutes": "{n} minuti fa",
    "time.hour": "1 ora fa",
    "time.hours": "{n} ore fa",
    "time.day": "1 giorno fa",
    "time.days": "{n} giorni fa",
    "time.date_format": "%d/%m/%Y",
    # --- Comuni ---
    "common.cancel": "Annulla",
    "common.delete": "Elimina",
}
