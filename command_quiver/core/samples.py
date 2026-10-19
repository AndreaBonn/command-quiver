"""Voci di esempio proposte al primo avvio, per provare l'app senza inventarsi nulla."""

# I comandi di esempio sono di sola lettura: l'utente li può eseguire con un clic.
_SAMPLES: dict[str, list[dict[str, str]]] = {
    "it": [
        {"name": "Spazio libero sul disco", "content": "df -h", "type": "shell", "tags": "sistema"},
        {
            "name": "Cartelle più pesanti qui",
            "content": "du -sh * | sort -h",
            "type": "shell",
            "tags": "disco",
        },
        {
            "name": "Ultimi 10 commit",
            "content": "git log --oneline -10",
            "type": "shell",
            "tags": "git",
        },
        {
            "name": "Riassumi in 5 punti",
            "content": "Riassumi il testo seguente in 5 punti chiave, con tono neutro:\n\n",
            "type": "prompt",
            "tags": "scrittura",
        },
        {
            "name": "Rispondi a un'email",
            "content": (
                "Scrivi una risposta cortese e breve a questa email, accettando la proposta:\n\n"
            ),
            "type": "prompt",
            "tags": "email",
        },
        {
            "name": "Spiega un comando",
            "content": (
                "Spiegami passo per passo cosa fa questo comando e se è sicuro eseguirlo:\n\n"
            ),
            "type": "prompt",
            "tags": "terminale",
        },
    ],
    "en": [
        {"name": "Free disk space", "content": "df -h", "type": "shell", "tags": "system"},
        {
            "name": "Largest folders here",
            "content": "du -sh * | sort -h",
            "type": "shell",
            "tags": "disk",
        },
        {
            "name": "Last 10 commits",
            "content": "git log --oneline -10",
            "type": "shell",
            "tags": "git",
        },
        {
            "name": "Summarize in 5 points",
            "content": "Summarize the following text in 5 key points, neutral tone:\n\n",
            "type": "prompt",
            "tags": "writing",
        },
        {
            "name": "Reply to an email",
            "content": "Write a short, polite reply to this email accepting the proposal:\n\n",
            "type": "prompt",
            "tags": "email",
        },
        {
            "name": "Explain a command",
            "content": (
                "Explain step by step what this command does and whether it is safe to run:\n\n"
            ),
            "type": "prompt",
            "tags": "terminal",
        },
    ],
}


def sample_entries(language: str) -> list[dict[str, str]]:
    """Restituisce una copia delle voci di esempio nella lingua indicata (fallback italiano)."""
    return [dict(item) for item in _SAMPLES.get(language, _SAMPLES["it"])]
