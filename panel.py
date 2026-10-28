import json
import os
import subprocess
import origin
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gtk, Gdk, Gio, GLib
import glass

BASE_H = 68
CONF = os.path.expanduser("~/.config/thumbdeuck/settings.json")
TERM = ["xterm", "-bg", "black", "-fg", "white", "-geometry", "100x40",
        "-e", "bash", "-c",
        "figlet -f slant ThumbDEuck 1._; fastfetch; exec bash"]
SETTINGS = ["sh", "-c", "python -W ignore $HOME/settings_gui.py"]
MENU = ["sh", "-c", "python $HOME/launcher.py"]
TERM = ["sh", "-c", "$HOME/tdterm.sh"]

state = {"tray": None, "scale": None, "h": BASE_H, "menu": None}


def load_conf():
    try:
        with open(CONF) as f:
            return json.load(f)
    except Exception:
        return {}


def save_conf(cfg):
    try:
        os.makedirs(os.path.dirname(CONF), exist_ok=True)
        with open(CONF, "w") as f:
            json.dump(cfg, f, indent=2)
    except Exception as e:
        print("save failed:", e)


def run_cmd(cmd):
    try:
        subprocess.Popen(cmd)
    except Exception as e:
        print("could not run", cmd, e)


def flatten(w):
    if isinstance(w, Gtk.Button):
        w.set_relief(Gtk.ReliefStyle.NONE)
    if isinstance(w, Gtk.Container):
        w.foreach(flatten)


def icon_px():
    return max(12, int(24 * state["scale"] / 100.0))


def make_button(icon, fallback, tip, cmd):
    b = Gtk.Button()
    if Gtk.IconTheme.get_default().has_icon(icon):
        img = Gtk.Image.new_from_icon_name(icon, Gtk.IconSize.LARGE_TOOLBAR)
        img.set_pixel_size(icon_px())
        b.set_image(img)
    else:
        b.set_label(fallback)
    b.set_tooltip_text(tip)
    b.connect("clicked", lambda _b: (origin.mark(_b), run_cmd(cmd)))
    return b


def unpin(app_id):
    cfg = load_conf()
    cfg["tray"] = [x for x in cfg.get("tray", []) if x != app_id]
    save_conf(cfg)


def tray_menu(w, ev, app_id):
    if ev.button != 3:
        return False
    menu = Gtk.Menu()
    item = Gtk.MenuItem(label="Remove from tray")
    item.connect("activate", lambda _i: unpin(app_id))
    menu.append(item)
    menu.show_all()
    state["menu"] = menu
    menu.popup_at_widget(w, Gdk.Gravity.NORTH, Gdk.Gravity.SOUTH, ev)
    return True


def app_button(app_id):
    app = Gio.DesktopAppInfo.new(app_id)
    if app is None:
        return None
    b = Gtk.Button()
    gicon = app.get_icon()
    if gicon is not None:
        img = Gtk.Image.new_from_gicon(gicon, Gtk.IconSize.LARGE_TOOLBAR)
    else:
        img = Gtk.Image.new_from_icon_name(
            "application-x-executable", Gtk.IconSize.LARGE_TOOLBAR)
    img.set_pixel_size(icon_px())
    b.set_image(img)
    b.set_tooltip_text(app.get_name() + "  (right-click to remove)")
    b.connect("clicked", lambda _b: (origin.mark(_b), app.launch([], None)))
    b.connect("button-press-event",
              lambda w, ev: tray_menu(w, ev, app_id))
    return b


bar = Gtk.Window(type=Gtk.WindowType.POPUP)
bar.set_title("tdpanel")
bar.set_default_size(330, BASE_H)
if not glass.apply(bar):
    fb = Gtk.CssProvider()
    fb.load_from_data(b".fb { background-color: #1e2a44; }"
                      b".fb button { color: white; }")
    Gtk.StyleContext.add_provider_for_screen(
        Gdk.Screen.get_default(), fb, 900)
    bar.get_style_context().add_class("fb")

scale_css = Gtk.CssProvider()
Gtk.StyleContext.add_provider_for_screen(
    Gdk.Screen.get_default(), scale_css, 950)

pill = Gtk.Box()
pill.get_style_context().add_class("tdbar")
pill.set_halign(Gtk.Align.START)
pill.set_valign(Gtk.Align.END)
pill.set_margin_start(8)
pill.set_margin_bottom(8)
bar.add(pill)

open_btn = Gtk.Button(label="\u203a")
rev_open = Gtk.Revealer()
rev_open.set_transition_type(Gtk.RevealerTransitionType.SLIDE_LEFT)
rev_open.set_transition_duration(350)
rev_open.set_reveal_child(True)
rev_open.add(open_btn)

icons_box = Gtk.Box()
close_btn = Gtk.Button(label="\u2039")
content = Gtk.Box()
content.pack_start(icons_box, False, False, 0)
content.pack_start(close_btn, False, False, 0)
rev = Gtk.Revealer()
rev.set_transition_type(Gtk.RevealerTransitionType.SLIDE_RIGHT)
rev.set_transition_duration(350)
rev.add(content)

pill.pack_start(rev_open, False, False, 0)
pill.pack_start(rev, False, False, 0)


def expand(_b):
    rev_open.set_reveal_child(False)
    rev.set_reveal_child(True)


def collapse(_b):
    rev.set_reveal_child(False)
    rev_open.set_reveal_child(True)


open_btn.connect("clicked", expand)
close_btn.connect("clicked", collapse)


def keep():
    g = Gdk.Display.get_default().get_monitor(0).get_geometry()
    bar.move(g.x, g.y + g.height - state["h"])
    if bar.get_window():
        bar.get_window().raise_()
    return True


# ---- clock at the end of the tray (hour on top, minute below) ----
import datetime

clock_lbl = Gtk.Label()
clock_lbl.set_justify(Gtk.Justification.CENTER)
clock_lbl.set_margin_start(10)
clock_lbl.set_margin_end(10)
clock_last = [None]


def clock_parts():
    now = datetime.datetime.now()
    if load_conf().get("clock_24h", True):
        hh = now.strftime("%H")
    else:
        hh = str(int(now.strftime("%I")))
    return hh, now.strftime("%M")


def tick(force=False):
    hh, mm = clock_parts()
    scale = state["scale"] or 100
    key = (hh, mm, scale)
    if key != clock_last[0] or force:
        clock_last[0] = key
        size = int(15 * scale / 100.0 * 1024)
        clock_lbl.set_markup(
            '<span foreground="#ffffff" weight="bold" size="%d">%s</span>\n'
            '<span foreground="#7fb2ff" weight="bold" size="%d">%s</span>'
            % (size, hh, size, mm))
    return True


GLib.timeout_add(1000, tick)


def apply_scale(s):
    def px(v):
        return max(1, int(round(v * s)))
    css = (".tdbar { padding: %dpx; border-radius: %dpx; }"
           ".tdbar button { min-height: 0; min-width: 0;"
           " padding: %dpx %dpx; margin: 0 %dpx;"
           " border-radius: %dpx; font-size: %dpx; }"
           % (px(6), px(20), px(6), px(12), px(3), px(12), px(14)))
    scale_css.load_from_data(css.encode())


def rebuild():
    s = state["scale"] / 100.0
    apply_scale(s)
    for c in icons_box.get_children():
        icons_box.remove(c)
    icons_box.pack_start(make_button(
        "preferences-system", "\u2699", "Settings", SETTINGS),
        False, False, 0)
    icons_box.pack_start(make_button(
        "utilities-terminal", ">_", "Terminal", TERM), False, False, 0)
    icons_box.pack_start(make_button(
        "open-menu-symbolic", "\u2261", "Menu", MENU), False, False, 0)
    n = 0
    for app_id in state["tray"]:
        b = app_button(app_id)
        if b:
            icons_box.pack_start(b, False, False, 0)
            n += 1
    tick(True)
    icons_box.pack_start(clock_lbl, False, False, 0)
    flatten(icons_box)
    icons_box.show_all()
    g = Gdk.Display.get_default().get_monitor(0).get_geometry()
    w = min(int(70 + (5 + n) * 58 * s), g.width)
    h = int(BASE_H * s)
    state["h"] = h
    bar.resize(w, h)
    keep()


def watch():
    cfg = load_conf()
    tray = list(cfg.get("tray", []))
    try:
        scale = max(50, min(250, int(cfg.get("tray_scale", 100))))
    except Exception:
        scale = 100
    if tray != state["tray"] or scale != state["scale"]:
        state["tray"] = tray
        state["scale"] = scale
        rebuild()
    return True


flatten(pill)
watch()
bar.show_all()
keep()
GLib.timeout_add(1000, watch)
GLib.timeout_add(500, keep)
GLib.timeout_add(40, lambda: pill.queue_draw() or True)
Gtk.main()
