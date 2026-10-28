import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gtk, Gdk

CSS = b"""
.tdmenu { background-color: rgba(28,28,34,0.72);
    border: 1px solid rgba(255,255,255,0.14); border-radius: 16px; }
.tdmenu .footer { background-color: rgba(0,0,0,0.25);
    border-top: 1px solid rgba(255,255,255,0.08);
    border-radius: 0 0 16px 16px; }
.tdmenu .search { background-color: rgba(255,255,255,0.10);
    border: 1px solid rgba(255,255,255,0.12); }
.tdmenu .link { background-color: rgba(255,255,255,0.10); }
.tdmenu button:hover { background-color: rgba(255,255,255,0.12); }
.tdmenu row:hover { background-color: rgba(255,255,255,0.10); }
.tdmenu row:selected { background-color: rgba(91,141,239,0.55); }
.tdbar { background-color: rgba(28,28,34,0.62);
    border: 1px solid rgba(255,255,255,0.16);
    border-radius: 20px; padding: 6px; }
.tdbar button { background-image: none; box-shadow: none; border: none;
    background-color: transparent; color: white;
    border-radius: 12px; padding: 6px 12px; margin: 0 3px; }
.tdbar button:hover { background-color: rgba(255,255,255,0.24); }
"""


def apply(win):
    """Make win see-through. Returns False if no compositor is running."""
    screen = Gdk.Screen.get_default()
    visual = screen.get_rgba_visual()
    if visual is None or not screen.is_composited():
        return False
    win.set_visual(visual)
    win.set_app_paintable(True)
    css = Gtk.CssProvider()
    css.load_from_data(CSS)
    Gtk.StyleContext.add_provider_for_screen(screen, css, 900)
    return True
