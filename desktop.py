import datetime
import json
import os
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gtk, Gdk, Gio, GLib, Pango
import glass
import origin

CONF = os.path.expanduser("~/.config/thumbdeuck/settings.json")
MARGIN_X = 24
MARGIN_TOP = 56
RESERVE_BOTTOM = 120
GAP = 8
CLOCK_ID = "@clock"

holder = [None]
wins = {}
LAYOUT = {}
GRID = {"cell": 112, "cols": 1, "rows": 1}
dragging = [None]
clock = {"lbl": None, "fs": 0, "last": None}

CSS = b"""
.tdicon { background-color: rgba(255,255,255,0.0); border-radius: 16px; }
.tdicon.hot { background-color: rgba(255,255,255,0.20); }
.tdicon label { color: #ffffff; font-weight: bold;
    text-shadow: 0 1px 3px rgba(0,0,0,0.9); }
.tdclockw { background-color: rgba(10,12,22,0.45); border-radius: 22px;
    border: 1px solid rgba(255,255,255,0.28); }
.tdclockw.hot { background-color: rgba(10,12,22,0.58); }
.tdclockw.nobg { background-color: rgba(0,0,0,0);
    border-color: rgba(0,0,0,0); }
.tdclockw.nobg label { text-shadow: 0 2px 8px rgba(0,0,0,0.85); }
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


def screen_size():
    g = Gdk.Display.get_default().get_monitor(0).get_geometry()
    return g.width, g.height


def size_of(e):
    try:
        s = int(e.get("size", 2 if e.get("id") == CLOCK_ID else 1))
    except Exception:
        s = 1
    return max(1, min(3, s))


def update_grid(cfg):
    try:
        cell = int(cfg.get("grid_cell", 112))
    except Exception:
        cell = 112
    cell = max(80, min(200, cell))
    sw, sh = screen_size()
    GRID["cell"] = cell
    GRID["cols"] = max(1, (sw - 2 * MARGIN_X) // cell)
    GRID["rows"] = max(1, (sh - MARGIN_TOP - RESERVE_BOTTOM) // cell)


def fits(c, r, s, ignore, layout):
    if c < 0 or r < 0 or c + s > GRID["cols"] or r + s > GRID["rows"]:
        return False
    for key, (c2, r2, s2) in layout.items():
        if key == ignore:
            continue
        if c < c2 + s2 and c2 < c + s and r < r2 + s2 and r2 < r + s:
            return False
    return True


def first_free(s, ignore, layout):
    for c in range(GRID["cols"]):
        for r in range(GRID["rows"]):
            if fits(c, r, s, ignore, layout):
                return (c, r)
    return None


def nearest_free(c0, r0, s, ignore, layout):
    best = None
    for c in range(GRID["cols"]):
        for r in range(GRID["rows"]):
            if fits(c, r, s, ignore, layout):
                k = ((c - c0) ** 2 + (r - r0) ** 2, c, r)
                if best is None or k < best:
                    best = k
    return None if best is None else (best[1], best[2])


def cell_xy(c, r):
    return (MARGIN_X + c * GRID["cell"], MARGIN_TOP + r * GRID["cell"])


def tile_px(s):
    return s * GRID["cell"] - GAP


def set_entry(entry_id, **fields):
    cfg = load()
    for e in cfg.get("desktop", []):
        if e.get("id") == entry_id:
            e.update(fields)
    save(cfg)


def bump(entry_id, delta):
    cfg = load()
    for e in cfg.get("desktop", []):
        if e.get("id") == entry_id:
            e["size"] = max(1, min(3, size_of(e) + delta))
    save(cfg)


def drop(entry_id):
    cfg = load()
    cfg["desktop"] = [e for e in cfg.get("desktop", [])
                      if e.get("id") != entry_id]
    save(cfg)


def tick():
    lbl = clock["lbl"]
    if lbl is None:
        return True
    now = datetime.datetime.now()
    cfg = load()
    cbox = clock.get("box")
    if cbox is not None:
        cctx = cbox.get_style_context()
        if cfg.get("clock_bg", True):
            cctx.remove_class("nobg")
        else:
            cctx.add_class("nobg")
    if cfg.get("clock_24h", True):
        hh = now.strftime("%H")
    else:
        hh = str(int(now.strftime("%I")))
    mm = now.strftime("%M")
    key = (hh, mm, clock["fs"])
    if key != clock["last"]:
        clock["last"] = key
        fs = clock["fs"]
        lbl.set_markup(
            '<span foreground="#ffffff" weight="bold" size="%d">%s</span>\n'
            '<span foreground="#7fb2ff" weight="bold" size="%d">%s</span>'
            % (fs, hh, fs, mm))
    return True


def interactive(win, box, key, entry_id, size, menu, double=None):
    win.add_events(Gdk.EventMask.BUTTON_PRESS_MASK
                   | Gdk.EventMask.BUTTON_RELEASE_MASK
                   | Gdk.EventMask.POINTER_MOTION_MASK
                   | Gdk.EventMask.ENTER_NOTIFY_MASK
                   | Gdk.EventMask.LEAVE_NOTIFY_MASK)
    st = {"drag": None, "moved": False, "target": None}
    ctx = box.get_style_context()

    def press(w, ev):
        if ev.button == 3:
            m = Gtk.Menu()
            for label, cb in menu:
                it = Gtk.MenuItem(label=label)
                it.connect("activate", lambda _i, cb=cb: cb())
                m.append(it)
            m.show_all()
            holder[0] = m
            m.popup_at_pointer(ev)
            return True
        if ev.button != 1:
            return False
        if ev.type == Gdk.EventType._2BUTTON_PRESS:
            if double:
                double()
            return True
        if ev.type == Gdk.EventType.BUTTON_PRESS:
            x, y = w.get_position()
            st["drag"] = (ev.x_root, ev.y_root, x, y)
            st["moved"] = False
            st["target"] = None
        return True

    def motion(w, ev):
        if not st["drag"]:
            return False
        px, py, ox, oy = st["drag"]
        dx, dy = ev.x_root - px, ev.y_root - py
        if not st["moved"] and abs(dx) + abs(dy) <= 3:
            return False
        st["moved"] = True
        dragging[0] = key
        cell = float(GRID["cell"])
        c = int(round((ox + dx - MARGIN_X) / cell))
        r = int(round((oy + dy - MARGIN_TOP) / cell))
        c = max(0, min(GRID["cols"] - size, c))
        r = max(0, min(GRID["rows"] - size, r))
        if (c, r) != st["target"] and fits(c, r, size, key, LAYOUT):
            st["target"] = (c, r)
            x, y = cell_xy(c, r)
            w.move(x, y)
        return False

    def release(w, ev):
        if st["drag"] and st["moved"] and st["target"]:
            c, r = st["target"]
            set_entry(entry_id, col=c, row=r)
            LAYOUT[key] = (c, r, size)
        st["drag"] = None
        dragging[0] = None
        return False

    def enter(w, ev):
        ctx.add_class("hot")
        return False

    def leave(w, ev):
        ctx.remove_class("hot")
        return False

    win.connect("button-press-event", press)
    win.connect("motion-notify-event", motion)
    win.connect("button-release-event", release)
    win.connect("enter-notify-event", enter)
    win.connect("leave-notify-event", leave)


def make_icon(e, s):
    app = Gio.DesktopAppInfo.new(e["id"])
    if app is None:
        return None
    entry_id = e["id"]
    key = "app:" + entry_id
    tile = tile_px(s)
    win = Gtk.Window(type=Gtk.WindowType.POPUP)
    win.set_title("tdicon")
    glass.apply(win)
    win.set_default_size(tile, tile)
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
    box.set_border_width(6)
    box.set_size_request(tile, tile)
    box.get_style_context().add_class("tdicon")
    gicon = app.get_icon()
    if gicon is not None:
        img = Gtk.Image.new_from_gicon(gicon, Gtk.IconSize.DIALOG)
    else:
        img = Gtk.Image.new_from_icon_name(
            "application-x-executable", Gtk.IconSize.DIALOG)
    img.set_pixel_size(int(tile * 0.5))
    name = Gtk.Label()
    pt = 10 + 4 * (s - 1)
    name.set_markup('<span size="%d">%s</span>' % (
        pt * 1024, GLib.markup_escape_text(app.get_name())))
    name.set_ellipsize(Pango.EllipsizeMode.END)
    name.set_max_width_chars(1)
    box.pack_start(img, True, True, 0)
    box.pack_start(name, False, False, 0)
    win.add(box)

    def launch():
        origin.mark(box)
        try:
            app.launch([], None)
        except Exception as ex:
            print("launch failed:", ex)

    menu = [("Bigger", lambda: bump(entry_id, 1)),
            ("Smaller", lambda: bump(entry_id, -1)),
            ("Remove from desktop", lambda: drop(entry_id))]
    interactive(win, box, key, entry_id, s, menu, launch)
    return win


def make_clock(s):
    tile = tile_px(s)
    win = Gtk.Window(type=Gtk.WindowType.POPUP)
    win.set_title("tdwidget")
    glass.apply(win)
    win.set_default_size(tile, tile)
    box = Gtk.Box()
    box.set_size_request(tile, tile)
    box.get_style_context().add_class("tdclockw")
    lbl = Gtk.Label()
    lbl.set_justify(Gtk.Justification.CENTER)
    lbl.set_halign(Gtk.Align.CENTER)
    lbl.set_valign(Gtk.Align.CENTER)
    box.pack_start(lbl, True, True, 0)
    win.add(box)
    clock["lbl"] = lbl
    clock["box"] = box
    clock["fs"] = int(tile * 0.25 * 1024)
    clock["last"] = None
    tick()
    menu = [("Bigger", lambda: bump(CLOCK_ID, 1)),
            ("Smaller", lambda: bump(CLOCK_ID, -1)),
            ("Remove clock", lambda: drop(CLOCK_ID))]
    interactive(win, box, CLOCK_ID, CLOCK_ID, s, menu)
    return win


def key_of(e):
    return CLOCK_ID if e["id"] == CLOCK_ID else "app:" + e["id"]


def drop_window(key):
    w = wins.pop(key, None)
    if w is not None:
        w["win"].destroy()
    if key == CLOCK_ID:
        clock["lbl"] = None


def sync():
    cfg = load()
    desk = cfg.get("desktop", [])
    changed = False
    if "desk_clock" in cfg:
        if cfg.pop("desk_clock") and not any(
                e.get("id") == CLOCK_ID for e in desk):
            desk.append({"id": CLOCK_ID, "size": 2})
        cfg.pop("desk_clock_pos", None)
        changed = True
    update_grid(cfg)
    cell = GRID["cell"]
    entries = [e for e in desk if e.get("id")]

    def is_stable(e):
        w = wins.get(key_of(e))
        return (w is not None and w["size"] == size_of(e)
                and w["cell"] == cell and "col" in e and "row" in e)

    ordered = ([e for e in entries if is_stable(e)]
               + [e for e in entries if not is_stable(e)])
    layout = {}
    for e in ordered:
        key = key_of(e)
        want = size_of(e)
        c, r = e.get("col"), e.get("row")
        placed = None
        if c is not None and r is not None and fits(c, r, want, key, layout):
            placed = (c, r, want)
        else:
            for s in range(want, 0, -1):
                if c is not None and r is not None:
                    spot = nearest_free(c, r, s, key, layout)
                else:
                    spot = first_free(s, key, layout)
                if spot:
                    placed = (spot[0], spot[1], s)
                    break
        if placed is None:
            continue
        if (e.get("col"), e.get("row"), size_of(e)) != placed:
            e["col"], e["row"], e["size"] = placed
            changed = True
        layout[key] = placed

    LAYOUT.clear()
    LAYOUT.update(layout)
    for key in list(wins):
        if key not in layout:
            drop_window(key)
    by_key = {key_of(e): e for e in entries}
    for key, (c, r, s) in layout.items():
        e = by_key[key]
        w = wins.get(key)
        if w is not None and (w["size"] != s or w["cell"] != cell):
            drop_window(key)
            w = None
        x, y = cell_xy(c, r)
        if w is None:
            win = make_clock(s) if key == CLOCK_ID else make_icon(e, s)
            if win is None:
                continue
            win.move(x, y)
            win.show_all()
            wins[key] = {"win": win, "size": s, "cell": cell}
        elif dragging[0] != key:
            if tuple(w["win"].get_position()) != (x, y):
                w["win"].move(x, y)

    if changed:
        cfg["desktop"] = desk
        save(cfg)
    for w in wins.values():
        gw = w["win"].get_window()
        if gw is not None:
            gw.lower()
    return True


css = Gtk.CssProvider()
css.load_from_data(CSS)
Gtk.StyleContext.add_provider_for_screen(
    Gdk.Screen.get_default(), css, 950)

sync()
GLib.timeout_add(1000, sync)
GLib.timeout_add(1000, tick)
Gtk.main()
