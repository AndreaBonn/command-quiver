**English** | [Italiano](README.it.md)

# Command Quiver

A personal library of AI prompts and shell commands, accessible from the GNOME system tray. Search, organize by sections, copy to clipboard or execute in terminal.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

## Overview

Command Quiver lives in your GNOME system tray and gives you quick access to frequently used AI prompts and shell commands. Entries are stored in a local SQLite database, organized into sections, and searchable by name. Prompts are copied to the clipboard; shell commands can be executed directly in gnome-terminal.

## Features

- System tray icon with context menu (show/hide, new entry, quit)
- Sidebar panel with search and multiple sort modes (alphabetical, chronological, custom)
- Two entry types: AI prompts (copy to clipboard) and shell commands (run in terminal)
- Sections for organizing entries, with drag-and-drop reordering
- Bilingual interface (Italian / English) with live language switching
- SQLite persistence with WAL mode and automatic recovery from corruption
- Single-instance enforcement via D-Bus
- Persistent settings (sort order, window size, language, theme)

## Requirements

- Python >= 3.10
- GTK4 and PyGObject
- AyatanaAppIndicator3 (for system tray icon)
- gnome-terminal (for shell command execution)
- pycairo (for icon generation)

On Ubuntu/Debian:

```bash
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-4.0 \
    gir1.2-ayatanaappindicator3-0.1 gnome-terminal
```

## Installation

```bash
git clone https://github.com/AndreaBonn/command-quiver.git
cd command-quiver
uv sync
```

## Usage

Start the application:

```bash
uv run python command_quiver/main.py
```

The tray icon appears in the GNOME top bar. Left-click to toggle the sidebar, right-click for the context menu.

From the sidebar:

- Click **+ New entry** to create a prompt or shell command
- Click an entry to copy it to the clipboard (prompts) or execute it (shell commands)
- Use the search bar to filter entries by name
- Switch sort mode with the dropdown (Recent, A-Z, Z-A, Custom)
- Manage sections with **+ Section**, or right-click a section to rename/delete

### Data locations

| Path | Content |
|---|---|
| `~/.local/share/command-quiver/vault.db` | SQLite database |
| `~/.config/command-quiver/settings.json` | User settings |
| `~/.local/share/command-quiver/logs/` | Application logs |

## Testing

```bash
uv run pytest
```

With coverage:

```bash
uv run pytest --cov=command_quiver
```

Lint:

```bash
uv run ruff check .
```

## Contributing

Contributions are welcome. Open an issue to discuss the change before submitting a pull request. Follow the existing code style (ruff configuration in `pyproject.toml`) and include tests for new functionality.

## Security

For reporting vulnerabilities, see the [security policy](SECURITY.md).

## License

Released under the MIT License -- see [LICENSE](LICENSE).

## Author

Andrea Bonacci -- [@AndreaBonn](https://github.com/AndreaBonn)

---

If this project is useful to you, a star on GitHub is appreciated.
