**English** | [Italiano](SECURITY.it.md)

# Security Policy

## Supported Versions

| Version | Supported |
|---|---|
| 2.1.x | Yes |
| < 2.1 | No |

## Reporting a Vulnerability

To report a security vulnerability, use [GitHub Security Advisories](https://github.com/AndreaBonn/command-quiver/security/advisories/new). Do not open a public issue.

Your report should include:

- Description of the vulnerability
- Steps to reproduce
- Affected version(s)
- Potential impact

**Response timeline:**

- Acknowledgment within 72 hours
- Fix for critical vulnerabilities within 30 days
- Coordinated public disclosure after the fix is released

## Security Measures

Command Quiver by Bonn is a local desktop application. Its only network traffic is the optional GitHub sync, which talks to `api.github.com` over HTTPS with a token you provide. The following measures are implemented:

- **Parameterized queries**: every value that comes from the user, from an import file or from sync is bound with `?` placeholders, never concatenated into SQL (`db/*_repository.py`)
- **Input validation**: settings are validated on load with bounded values and allowed-set checks (`core/settings.py`); imported files are capped at 10,000 entries and 100,000 characters per field (`db/entry_import.py`)
- **Database constraints**: CHECK constraints on entry and tombstone types, foreign key enforcement enabled (`db/schema.py`, `db/database.py`)
- **No shell=True in subprocess calls**: the terminal is started with an argument list, and the command is quoted with `shlex.quote` (`core/executor.py`)
- **Confirmation before running**: a shell command runs only after a confirmation dialog, which can be turned off one entry at a time (`ui/run_confirm.py`)
- **Sync token stored owner-only**: the GitHub token lives in its own file, created with permissions 600 rather than tightened afterwards (`core/settings.py`)
- **Dependency lockfile**: `uv.lock` pins all dependency versions

## Security Considerations for Users

- The SQLite database (`vault.db`) and its automatic backups are stored unencrypted in `~/.local/share/command-quiver/`. If you store sensitive information in entries, protect this directory with appropriate file permissions.
- With sync enabled, your entries are copied as plain JSON to the GitHub repository you choose. Keep that repository private, and give the token access to that repository only, with Contents read and write and nothing more.
- Shell commands are executed as-is in gnome-terminal. Review commands before running them, especially if imported or synced from elsewhere, and keep the confirmation on for entries you did not write.
- Log files in `~/.local/share/command-quiver/logs/` contain entry names and the first 80 characters of the commands you run. Restrict access if those are sensitive.
- The app registers on the D-Bus session bus as a standard `Gtk.Application` (`com.github.commandquiver`) to enforce a single instance. Any process running under the same user session can activate it, as with any desktop application.
- **JSON import trust model**: the import accepts entries of type `shell` whose content runs verbatim in the terminal. The run confirmation shows the command first, unless it has been turned off for that entry. Only import files from sources you trust.

## Out of Scope

The following are not considered vulnerabilities for the purposes of this policy:

- Attacks requiring physical access to the machine
- Social engineering
- Vulnerabilities in third-party dependencies already publicly disclosed (report these to the upstream project)
- Self-inflicted damage from shell commands the user chooses to execute
- Data exposure when the user's home directory permissions are misconfigured

## Acknowledgments

Security researchers who report valid vulnerabilities will be credited here upon request.

---

[Back to README](README.md)
