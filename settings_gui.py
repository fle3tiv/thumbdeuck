import json
import os
import platform
import subprocess
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gtk, Gdk, Gio, GLib
import glass

CONF = os.path.expanduser("~/.config/thumbdeuck/settings.json")
FITS = [("scale", "Stretch to screen"), ("fill", "Fill (crops edges)"),
        ("max", "Fit (keeps proportions)"), ("center", "Center"),
        ("tile", "Tile")]
WIN = [None]

CSS = b"""
.tdset { background-color: rgba(10,12,22,0.55); border-radius: 16px;
    border: 1px solid rgba(255,255,255,0.25); }
.tdset label { color: #ffffff; }
.tdset .title { font-size: 20pt; font-weight: bold; }
.tdset .dim { color: rgba(255,255,255,0.65); }
.tdset .side { background-color: rgba(255,255,255,0.07);
    border-radius: 12px; padding: 8px; }
.tdset .navbtn { background-image: none; box-shadow: none; border: none;
    background-color: transparent; border-radius: 10px;
    padding: 10px 14px; color: #ffffff; }
.tdset .navbtn:hover { background-color: rgba(255,255,255,0.14); }
.tdset .navbtn.on { background-color: #2f7bff; }
.tdset .card { background-color: rgba(255,255,255,0.09);
    border-radius: 12px; padding: 14px;
    border: 1px solid rgba(255,255,255,0.14); }
.tdset button.act { background-image: none; box-shadow: none;
    border: none; background-color: #2f7bff; color: #ffffff;
    border-radius: 10px; padding: 8px 16px; font-weight: bold; }
.tdset button.act:hover { background-color: #5a9bff; }
.tdset button.danger { background-image: none; box-shadow: none;
    border: none; background-color: #ff2e4d; color: #ffffff;
    border-radius: 10px; padding: 6px 14px; font-weight: bold; }
.tdset button.danger:hover { background-color: #ff6b80; }
"""


def load():
    try:
        with open(CONF) as f:
            return json.load(f)
    except Exception:
        return {}


def save(cfg):
    os.makedirs(os.path.dirname(CONF), exist_ok=True)
    with open(CONF, "w") as f:
        json.dump(cfg, f, indent=2)


def lab(text, cls=None):
    l = Gtk.Label(label=text, xalign=0)
    if cls:
        l.get_style_context().add_class(cls)
    return l


def btn(text, cls, cb):
    b = Gtk.Button(label=text)
    b.get_style_context().add_class(cls)
    b.connect("clicked", lambda _b: cb())
    return b


def card():
    b = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    b.get_style_context().add_class("card")
    return b


def page(title, sub):
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
    box.set_border_width(24)
    box.pack_start(lab(title, "title"), False, False, 0)
    box.pack_start(lab(sub, "dim"), False, False, 0)
    return box


def run_bg():
    subprocess.Popen(["python", os.path.expanduser("~/apply_bg.py")])


def hexcol(c):
    return "#%02x%02x%02x" % (int(c.red * 255 + .5),
                              int(c.green * 255 + .5),
                              int(c.blue * 255 + .5))


def page_bg():
    cfg = load()
    box = page("Background", "Pick a picture or a solid colour.")

    c1 = card()
    cur = lab(cfg.get("bg_image", "~/duck.png"), "dim")
    c1.pack_start(lab("Picture"), False, False, 0)
    c1.pack_start(cur, False, False, 0)

    def choose():
        dlg = Gtk.FileChooserDialog(
            title="Choose a picture", parent=WIN[0],
            action=Gtk.FileChooserAction.OPEN)
        dlg.add_buttons("Cancel", Gtk.ResponseType.CANCEL,
                        "Open", Gtk.ResponseType.OK)
        flt = Gtk.FileFilter()
        flt.set_name("Images")
        flt.add_mime_type("image/*")
        dlg.add_filter(flt)
        dlg.set_current_folder(os.path.expanduser("~"))
        if dlg.run() == Gtk.ResponseType.OK:
            p = dlg.get_filename()
            c = load()
            c["bg_image"] = p
            c["bg_use"] = "image"
            save(c)
            cur.set_text(p)
            run_bg()
        dlg.destroy()

    c1.pack_start(btn("Choose picture...", "act", choose),
                  False, False, 0)
    box.pack_start(c1, False, False, 0)

    c2 = card()
    c2.pack_start(lab("Fit"), False, False, 0)
    keys = [k for k, _ in FITS]
    combo = Gtk.ComboBoxText()
    for _, name in FITS:
        combo.append_text(name)
    fit = cfg.get("bg_fit", "scale")
    combo.set_active(keys.index(fit) if fit in keys else 0)

    def fit_changed(cb):
        i = cb.get_active()
        if i < 0:
            return
        c = load()
        c["bg_fit"] = keys[i]
        c["bg_use"] = "image"
        save(c)
        run_bg()

    combo.connect("changed", fit_changed)
    c2.pack_start(combo, False, False, 0)
    box.pack_start(c2, False, False, 0)

    c3 = card()
    c3.pack_start(lab("Solid colour"), False, False, 0)
    cb = Gtk.ColorButton()
    rgba = Gdk.RGBA()
    rgba.parse(cfg.get("bg_color", "#1e2a44"))
    cb.set_rgba(rgba)

    def picked(b):
        c = load()
        c["bg_color"] = hexcol(b.get_rgba())
        c["bg_use"] = "color"
        save(c)
        run_bg()

    cb.connect("color-set", picked)
    c3.pack_start(cb, False, False, 0)
    box.pack_start(c3, False, False, 0)
    return box


def installed():
    apps = [a for a in Gio.AppInfo.get_all()
            if a.should_show() and a.get_id()]
    apps.sort(key=lambda a: a.get_name().lower())
    return apps


def page_tray():
    box = page("Tray", "Choose the apps in your pill and how big it is.")
    apps = installed()
    names = {a.get_id(): a.get_name() for a in apps}
    ids = [a.get_id() for a in apps]

    c1 = card()
    c1.pack_start(lab("Size"), False, False, 0)
    scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL,
                                     70, 200, 5)
    scale.set_value(load().get("tray_scale", 100))
    scale.set_draw_value(True)
    pend = [None]

    def commit():
        c = load()
        c["tray_scale"] = int(scale.get_value())
        save(c)
        pend[0] = None
        return False

    def changed(_s):
        if pend[0]:
            GLib.source_remove(pend[0])
        pend[0] = GLib.timeout_add(500, commit)

    scale.connect("value-changed", changed)
    c1.pack_start(scale, False, False, 0)
    box.pack_start(c1, False, False, 0)

    c2 = card()
    c2.pack_start(lab("Pinned apps"), False, False, 0)
    rows = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
    c2.pack_start(rows, False, False, 0)

    def refresh():
        for ch in rows.get_children():
            rows.remove(ch)
        tray = load().get("tray", [])
        if not tray:
            rows.pack_start(lab("Nothing pinned yet", "dim"),
                            False, False, 0)
        for t in tray:
            r = Gtk.Box(spacing=10)
            r.pack_start(lab(names.get(t, t)), True, True, 0)
            r.pack_end(btn("Remove", "danger", lambda t=t: remove(t)),
                       False, False, 0)
            rows.pack_start(r, False, False, 0)
        rows.show_all()

    def remove(t):
        c = load()
        c["tray"] = [x for x in c.get("tray", []) if x != t]
        save(c)
        refresh()

    add_row = Gtk.Box(spacing=10)
    combo = Gtk.ComboBoxText()
    for a in apps:
        combo.append_text(a.get_name())
    combo.set_active(0)

    def add():
        i = combo.get_active()
        if i < 0:
            return
        c = load()
        tray = c.get("tray", [])
        if ids[i] not in tray:
            tray.append(ids[i])
        c["tray"] = tray
        save(c)
        refresh()

    add_row.pack_start(combo, True, True, 0)
    add_row.pack_start(btn("Add", "act", add), False, False, 0)
    c2.pack_start(add_row, False, False, 0)
    box.pack_start(c2, False, False, 0)
    refresh()
    return box


def osname():
    try:
        for line in open("/etc/os-release"):
            if line.startswith("PRETTY_NAME="):
                return line.split("=", 1)[1].strip().strip('"')
    except Exception:
        pass
    return "Linux"


def page_about():
    box = page("About", "ThumbDEuck 1._")
    c = card()
    for k, v in (("OS", osname()), ("Kernel", platform.release()),
                 ("Host", platform.node()),
                 ("Python", platform.python_version())):
        r = Gtk.Box(spacing=10)
        r.pack_start(lab(k, "dim"), False, False, 0)
        r.pack_end(lab(v), False, False, 0)
        c.pack_start(r, False, False, 0)
    box.pack_start(c, False, False, 0)
    return box


SIZE_NAMES = ["Small", "Medium", "Large"]
CELLS = [("Compact", 96), ("Normal", 112), ("Large", 140)]


def page_desktop():
    box = page("Desktop", "Tiles snap to a grid. Right-click a tile on "
               "the desktop to make it bigger or smaller.")
    cfg = load()

    c1 = card()
    c1.pack_start(lab("Layout"), False, False, 0)

    r1 = Gtk.Box(spacing=10)
    r1.pack_start(lab("24-hour clock"), True, True, 0)
    sw = Gtk.Switch()
    sw.set_active(bool(cfg.get("clock_24h", True)))

    def toggled(s, _p):
        c = load()
        c["clock_24h"] = s.get_active()
        save(c)

    sw.connect("notify::active", toggled)
    r1.pack_end(sw, False, False, 0)
    c1.pack_start(r1, False, False, 0)

    r3 = Gtk.Box(spacing=10)
    r3.pack_start(lab("Clock background"), True, True, 0)
    sw3 = Gtk.Switch()
    sw3.set_active(bool(cfg.get("clock_bg", True)))

    def bg_toggled(s, _p):
        c = load()
        c["clock_bg"] = s.get_active()
        save(c)

    sw3.connect("notify::active", bg_toggled)
    r3.pack_end(sw3, False, False, 0)
    c1.pack_start(r3, False, False, 0)

    r2 = Gtk.Box(spacing=10)
    r2.pack_start(lab("Tile size"), True, True, 0)
    gcombo = Gtk.ComboBoxText()
    for nme, _px in CELLS:
        gcombo.append_text(nme)
    cur = cfg.get("grid_cell", 112)
    best = min(range(len(CELLS)), key=lambda k: abs(CELLS[k][1] - cur))
    gcombo.set_active(best)

    def grid_changed(cb):
        n = cb.get_active()
        if n >= 0:
            c = load()
            c["grid_cell"] = CELLS[n][1]
            save(c)

    gcombo.connect("changed", grid_changed)
    r2.pack_end(gcombo, False, False, 0)
    c1.pack_start(r2, False, False, 0)
    box.pack_start(c1, False, False, 0)

    apps = installed()
    names = {a.get_id(): a.get_name() for a in apps}
    names["@clock"] = "Clock widget"
    ids = ["@clock"] + [a.get_id() for a in apps]

    c2 = card()
    c2.pack_start(lab("On the desktop"), False, False, 0)
    rows = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
    c2.pack_start(rows, False, False, 0)

    def set_size(i, n):
        if n < 0:
            return
        c = load()
        for e in c.get("desktop", []):
            if e.get("id") == i:
                e["size"] = n + 1
        save(c)

    def remove(i):
        c = load()
        c["desktop"] = [e for e in c.get("desktop", [])
                        if e.get("id") != i]
        save(c)
        refresh()

    def refresh():
        for ch in rows.get_children():
            rows.remove(ch)
        desk = load().get("desktop", [])
        if not desk:
            rows.pack_start(lab("Nothing on the desktop yet", "dim"),
                            False, False, 0)
        for e in desk:
            i = e.get("id", "")
            default = 2 if i == "@clock" else 1
            r = Gtk.Box(spacing=10)
            r.pack_start(lab(names.get(i, i)), True, True, 0)
            sc = Gtk.ComboBoxText()
            for nme in SIZE_NAMES:
                sc.append_text(nme)
            try:
                idx = int(e.get("size", default)) - 1
            except Exception:
                idx = default - 1
            sc.set_active(min(2, max(0, idx)))
            sc.connect("changed",
                       lambda cb, i=i: set_size(i, cb.get_active()))
            r.pack_start(sc, False, False, 0)
            r.pack_end(btn("Remove", "danger", lambda i=i: remove(i)),
                       False, False, 0)
            rows.pack_start(r, False, False, 0)
        rows.show_all()

    add_row = Gtk.Box(spacing=10)
    combo = Gtk.ComboBoxText()
    for i in ids:
        combo.append_text(names[i])
    combo.set_active(0)

    def add():
        n = combo.get_active()
        if n < 0:
            return
        c = load()
        desk = c.get("desktop", [])
        if not any(e.get("id") == ids[n] for e in desk):
            desk.append({"id": ids[n]})
        c["desktop"] = desk
        save(c)
        refresh()

    add_row.pack_start(combo, True, True, 0)
    add_row.pack_start(btn("Add", "act", add), False, False, 0)
    c2.pack_start(add_row, False, False, 0)
    box.pack_start(c2, False, False, 0)
    refresh()
    return box


PAGES = [("Background", page_bg), ("Tray", page_tray),
         ("Desktop", page_desktop), ("About", page_about)]


def main():
    screen = Gdk.Screen.get_default()
    css = Gtk.CssProvider()
    css.load_from_data(CSS)
    Gtk.StyleContext.add_provider_for_screen(screen, css, 950)

    win = Gtk.Window(title="Settings")
    win.set_default_size(820, 540)
    WIN[0] = win
    glass.apply(win)

    root = Gtk.Box()
    root.get_style_context().add_class("tdset")
    win.add(root)

    side = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
    side.get_style_context().add_class("side")
    side.set_size_request(190, -1)
    side.set_margin_start(14)
    side.set_margin_top(14)
    side.set_margin_bottom(14)
    root.pack_start(side, False, False, 0)

    stack = Gtk.Stack()
    stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
    stack.set_transition_duration(150)
    root.pack_start(stack, True, True, 0)

    buttons = {}

    def show(name):
        stack.set_visible_child_name(name)
        for n, b in buttons.items():
            ctx = b.get_style_context()
            if n == name:
                ctx.add_class("on")
            else:
                ctx.remove_class("on")

    for name, builder in PAGES:
        stack.add_named(builder(), name)
        b = Gtk.Button(label=name)
        b.set_relief(Gtk.ReliefStyle.NONE)
        b.get_style_context().add_class("navbtn")
        b.connect("clicked", lambda _b, n=name: show(n))
        side.pack_start(b, False, False, 0)
        buttons[name] = b

    def on_key(_w, ev):
        if ev.keyval == Gdk.KEY_Escape:
            win.destroy()
        return False

    win.connect("key-press-event", on_key)
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    show(PAGES[0][0])
    Gtk.main()


main()
