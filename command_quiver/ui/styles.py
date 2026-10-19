"""CSS dell'applicazione Command Quiver."""

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, Gtk

# I colori dei badge sono espliciti: @accent_color non esiste nel tema GTK4
# predefinito e il badge PROMPT risultava trasparente (invisibile).
APP_CSS = """
@define-color cq_blue #3584e4;
@define-color cq_green #26a269;
@define-color cq_toast_bg #303030;

.sidebar-panel {
    background-color: @theme_bg_color;
}
.section-list {
    background-color: transparent;
}
.section-list row {
    border-radius: 8px;
    margin: 1px 6px;
}
.section-row {
    padding: 7px 8px;
}
.section-count {
    font-size: 0.8em;
    font-weight: 600;
    padding: 0 7px;
    border-radius: 99px;
    background-color: alpha(@theme_fg_color, 0.08);
}
.section-menu-btn {
    min-height: 20px;
    min-width: 20px;
    padding: 0 4px;
    opacity: 0;
}
.section-list row:hover .section-menu-btn,
.section-list row:selected .section-menu-btn,
.section-menu-btn:checked {
    opacity: 1;
}
.entry-list row {
    border-bottom: 1px solid alpha(@theme_fg_color, 0.08);
}
.entry-list row:hover {
    background-color: alpha(@cq_blue, 0.08);
}
.entry-row {
    padding: 8px 6px 8px 10px;
}
.entry-name {
    font-weight: 700;
}
.entry-preview {
    font-family: monospace;
    font-size: 0.85em;
    opacity: 0.6;
}
.entry-tag {
    font-size: 0.75em;
    padding: 0 8px;
    min-height: 18px;
    border-radius: 99px;
    border: 1px solid alpha(@theme_fg_color, 0.15);
    background: none;
    box-shadow: none;
}
.entry-badge {
    font-size: 0.75em;
    font-weight: 700;
    padding: 2px 8px;
    border-radius: 5px;
}
.badge-shell {
    background-color: alpha(@cq_green, 0.18);
    color: @cq_green;
}
.badge-prompt {
    background-color: alpha(@cq_blue, 0.18);
    color: @cq_blue;
}
.entry-action {
    opacity: 0.75;
}
.entry-action:hover {
    opacity: 1;
}
.copy-success {
    color: @cq_green;
    opacity: 1;
}
.drag-handle {
    opacity: 0.4;
}
.toast {
    background-color: @cq_toast_bg;
    color: #ffffff;
    border-radius: 99px;
    padding: 6px 8px 6px 16px;
    margin: 8px;
}
.toast button {
    color: #ffffff;
    background-image: none;
    background-color: alpha(#ffffff, 0.18);
    border: none;
    box-shadow: none;
    border-radius: 99px;
    min-height: 24px;
    padding: 0 12px;
    font-weight: 700;
}
.toast button:hover {
    background-color: alpha(#ffffff, 0.3);
}
.welcome-card {
    padding: 18px;
    border-radius: 12px;
    border: 1px solid alpha(@theme_fg_color, 0.12);
    background-color: @theme_base_color;
}
.welcome-title {
    font-weight: 700;
    font-size: 1.15em;
}
.empty-title {
    font-weight: 700;
}
.type-card {
    padding: 8px 10px;
    border-radius: 10px;
}
.type-card:checked {
    background-image: none;
    background-color: alpha(@cq_blue, 0.12);
    color: @theme_fg_color;
    box-shadow: inset 0 0 0 2px @cq_blue;
}
.type-desc {
    font-size: 0.85em;
    opacity: 0.75;
}
.tag-chip {
    font-size: 0.85em;
    padding: 0 4px 0 10px;
    border-radius: 99px;
    background-color: alpha(@cq_blue, 0.15);
}
.tag-chip button {
    min-height: 18px;
    min-width: 18px;
    padding: 0;
}
.tag-suggestion {
    font-size: 0.85em;
    padding: 0 8px;
    min-height: 22px;
}
.kbd-hint {
    font-size: 0.75em;
    opacity: 0.7;
}
.sync-intro {
    padding: 10px 12px;
    border-radius: 8px;
    background-color: alpha(@cq_blue, 0.08);
}
.status-bar {
    font-size: 0.85em;
    padding: 2px 8px 4px 10px;
}
.status-dot {
    min-width: 8px;
    min-height: 8px;
    border-radius: 99px;
    background-color: alpha(@theme_fg_color, 0.3);
}
.status-dot.ok {
    background-color: @cq_green;
}
.status-dot.error {
    background-color: @error_color;
}
.command-preview {
    font-family: monospace;
    padding: 8px 10px;
    border-radius: 6px;
    background-color: #241f31;
    color: #f6f5f4;
}
.error-label {
    color: @error_color;
    font-size: 0.85em;
}
.success-label {
    color: @cq_green;
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
.search-row {
    margin: 8px;
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
