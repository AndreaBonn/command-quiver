"""CSS dell'applicazione Command Quiver."""

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, Gtk

APP_CSS = """
.sidebar-panel {
    background-color: @theme_bg_color;
}
.section-list {
    background-color: transparent;
}
.section-row {
    padding: 6px 12px;
    border-radius: 6px;
}
.section-row:selected, .section-row.active {
    background-color: alpha(@theme_selected_bg_color, 0.3);
}
.section-count {
    font-size: 0.85em;
    opacity: 0.6;
}
.entry-list row {
    border-bottom: 1px solid alpha(@theme_fg_color, 0.08);
}
.entry-list row:hover {
    background-color: alpha(@theme_selected_bg_color, 0.1);
}
.entry-name {
    font-weight: 500;
}
.entry-badge {
    font-size: 0.75em;
    font-weight: 700;
    padding: 2px 6px;
    border-radius: 4px;
}
.badge-shell {
    background-color: alpha(#2ecc71, 0.2);
    color: #27ae60;
}
.badge-prompt {
    background-color: alpha(#3498db, 0.2);
    color: #2980b9;
}
.copy-success {
    color: #27ae60;
}
.error-label {
    color: #e74c3c;
    font-size: 0.85em;
}
.content-editor {
    font-family: monospace;
    font-size: 0.95em;
}
.content-scroll {
    border: 1px solid alpha(@theme_fg_color, 0.15);
    border-radius: 6px;
}
.search-entry {
    margin: 8px;
}
.bottom-bar {
    padding: 8px 12px;
    border-top: 1px solid alpha(@theme_fg_color, 0.1);
}
"""


def load_app_css() -> None:
    """Carica il CSS dell'applicazione nel display corrente."""
    css_provider = Gtk.CssProvider()
    css_provider.load_from_string(APP_CSS)
    Gtk.StyleContext.add_provider_for_display(
        Gdk.Display.get_default(),
        css_provider,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
    )
