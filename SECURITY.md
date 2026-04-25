**English** | [Italiano](SECURITY.it.md)

# Security Policy

## Supported Versions

| Version | Supported |
|---|---|
| 1.0.x | Yes |

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

Command Quiver is a local desktop application with no network-facing components. It does not handle authentication, remote connections, or sensitive user credentials. The following measures are implemented:

- **Parameterized queries**: all database operations use `?` placeholders, no string concatenation (`db/queries.py`)
- **Input validation**: settings are validated on load with bounded values and allowed-set checks (`core/settings.py:40-49`)
- **Database constraints**: CHECK constraint on entry type, foreign key enforcement enabled (`db/database.py:24, 80`)
- **No shell=True in subprocess calls**: all subprocess invocations pass arguments as lists (`core/executor.py:50`, `app.py:150`)
- **Dependency lockfile**: `uv.lock` pins all dependency versions

## Security Considerations for Users

- The SQLite database (`vault.db`) is stored unencrypted in `~/.local/share/command-quiver/`. If you store sensitive information in entries, protect this directory with appropriate file permissions.
- Shell commands are executed as-is in gnome-terminal. Review commands before execution, especially if imported from external sources.
- Log files in `~/.local/share/command-quiver/logs/` may contain entry names. Restrict access if entry names are sensitive.
- The D-Bus interface (`com.github.commandquiver.App`) is registered on the session bus without sender verification. Any process running under the same user session can invoke methods such as Toggle, NewEntry, ChangeLanguage, and Quit. This is standard for desktop applications but means a compromised local process could control the application.
- **JSON import trust model**: the import feature (`db/queries.py:import_entries`) accepts entries of type `shell` whose content is executed verbatim when the user clicks "Run". Imported JSON files are treated as trusted input — there is no confirmation dialog or sandboxing before execution. Only import files from sources you trust.

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
