import subprocess
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gtk, Gdk
import glass

CSS = b"""
.tdpow { background-color: rgba(10,12,22,0.55); border-radius: 16px;
    border: 1px solid rgba(255,255,255,0.25); }
.tdpow button { background-image: none; box-shadow: none; border: none;
    color: #ffffff; border-radius: 12px; padding: 18px 26px;
    font-weight: bold; font-size: 12pt; }
.tdpow button.out { background-color: #2f7bff; }
.tdpow button.rst { background-color: #ffb300; color: #1a1d2b; }
.tdpow button.off { background-color: #ff2e4d; }
.tdpow button:hover { background-image: none;
    background-color: rgba(255,255,255,0.35); }
"""


def go(cmd):
    subprocess.Popen(cmd)


win = Gtk.Window(title="Power")
glass.apply(win)
css = Gtk.CssProvider()
css.load_from_data(CSS)
Gtk.StyleContext.add_provider_for_screen(
    Gdk.Screen.get_default(), css, 950)

box = Gtk.Box(spacing=14)
box.set_border_width(22)
box.get_style_context().add_class("tdpow")
win.add(box)

for text, cls, cmd in (
        ("Log out", "out", ["pkill", "-f", "mywm.py"]),
        ("Restart", "rst", ["systemctl", "reboot"]),
        ("Shut down", "off", ["systemctl", "poweroff"])):
    b = Gtk.Button(label=text)
    b.get_style_context().add_class(cls)
    b.connect("clicked", lambda _b, c=cmd: go(c))
    box.pack_start(b, True, True, 0)


def on_key(_w, ev):
    if ev.keyval == Gdk.KEY_Escape:
        win.destroy()


win.connect("key-press-event", on_key)
win.connect("destroy", Gtk.main_quit)
win.show_all()
Gtk.main()
