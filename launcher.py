import difflib
import origin
import fcntl
import json
import os
import subprocess
import sys

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gtk, Gdk, Gio, GLib, Pango

# only one menu at a time
lock = open("/tmp/thumbdeuck_menu.lock", "w")
try:
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
except OSError:
    sys.exit(0)

BAR_H = 44
WIDTH = 620
COLS = 6
CONF = os.path.expanduser("~/.config/thumbdeuck/settings.json")
TERM = ["xterm", "-bg", "black", "-fg", "white", "-geometry", "100x40",
        "-e", "bash", "-c",
        "figlet -f slant ThumbDEuck 1._; fastfetch; exec bash"]
SETTINGS = ["sh", "-c", "python -W ignore $HOME/settings_gui.py"]
PINNED = ["firefox.desktop", "thunar.desktop",
          "org.xfce.mousepad.desktop", "xfce4-terminal.desktop"]

TERM = ["sh", "-c", "$HOME/tdterm.sh"]
css = Gtk.CssProvider()
css.load_from_data(b"""
.tdmenu { background-color: #1f1f23; border: 1px solid #3a3a42; }
.tdmenu label { color: #e8e8ee; }
.tdmenu .dim { color: #9a9aa6; }
.tdmenu .head { font-weight: bold; font-size: 11pt; }
.tdmenu .search { background-color: #2b2b31; background-image: none;
    color: white; border: 1px solid #3a3a42; border-radius: 18px;
    padding: 6px 14px; min-height: 24px; }
.tdmenu .search:focus { border-bottom: 2px solid #5b8def; }
.tdmenu button { background-image: none; box-shadow: none; border: none;
    background-color: transparent; border-radius: 6px; }
.tdmenu button:hover { background-color: #2e2e36; }
.tdmenu .tile { padding: 10px 4px; }
.tdmenu .link { background-color: #2b2b31; padding: 3px 12px; }
.tdmenu scrolledwindow, .tdmenu viewport, .tdmenu list {
    background-color: transparent; }
.tdmenu row { border-radius: 6px; }
.tdmenu row:hover { background-color: #2e2e36; }
.tdmenu row:selected { background-color: #3b5b9d; }
.tdmenu .footer { background-color: #17171a;
    border-top: 1px solid #2e2e36; }
.tdmenu .avatar { background-color: #3b5b9d; border-radius: 16px;
    min-width: 32px; min-height: 32px; font-weight: bold; }
""")
Gtk.StyleContext.add_provider_for_screen(
    Gdk.Screen.get_default(), css, 800)


def load_conf():
    try:
        with open(CONF) as f:
            return json.load(f)
    except Exception:
        return {}


def remember(key):
    cfg = load_conf()
    rec = [k for k in cfg.get("recent", []) if k != key]
    cfg["recent"] = ([key] + rec)[:6]
    try:
        os.makedirs(os.path.dirname(CONF), exist_ok=True)
        with open(CONF, "w") as f:
            json.dump(cfg, f, indent=2)
    except Exception:
        pass


def app_item(a):
    return (a.get_id() or a.get_name(), a.get_name(), a.get_icon(),
            lambda: a.launch([], None))


def cmd_item(key, name, icon, cmd):
    return (key, name, Gio.ThemedIcon.new(icon),
            lambda: subprocess.Popen(cmd))


customs = [
    cmd_item("td-terminal", "Terminal", "utilities-terminal", TERM),
    cmd_item("td-settings", "Settings", "preferences-system", SETTINGS),
    cmd_item("td-power", "Power", "system-shutdown", ["sh", "-c", "python -W ignore $HOME/power.py"]),
]
apps = [a for a in Gio.AppInfo.get_all() if a.should_show()]
apps.sort(key=lambda a: a.get_name().lower())
items_all = [app_item(a) for a in apps]
by_id = {it[0]: it for it in items_all}
universe = customs + items_all
lookup = {it[0]: it for it in universe}

pinned, seen = [], set()
for it in customs + [by_id[p] for p in PINNED if p in by_id] + items_all:
    if it[0] in seen:
        continue
    seen.add(it[0])
    pinned.append(it)
pinned = pinned[:12]
recent = [lookup[k] for k in load_conf().get("recent", []) if k in lookup]


def launch(item):
    remember(item[0])
    try:
        item[3]()
    except Exception as e:
        print("launch failed:", e)
    GLib.timeout_add(150, Gtk.main_quit)


def score(item, q):
    name = item[1].lower()
    if name.startswith(q):
        return 3
    if q in name:
        return 2
    return max(difflib.SequenceMatcher(None, q, w).ratio()
               for w in name.split())


def icon_widget(icon, size):
    if icon is not None:
        img = Gtk.Image.new_from_gicon(icon, Gtk.IconSize.DIALOG)
    else:
        img = Gtk.Image.new_from_icon_name(
            "application-x-executable", Gtk.IconSize.DIALOG)
    img.set_pixel_size(size)
    return img


def add_class(widget, name):
    widget.get_style_context().add_class(name)


def header(text, button_text=None, callback=None):
    row = Gtk.Box()
    lab = Gtk.Label(label=text, xalign=0)
    add_class(lab, "head")
    row.pack_start(lab, True, True, 0)
    if button_text:
        b = Gtk.Button(label=button_text)
        add_class(b, "link")
        b.connect("clicked", lambda _b: callback())
        row.pack_end(b, False, False, 0)
    return row


def tile(item):
    b = Gtk.Button()
    add_class(b, "tile")
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
    box.pack_start(icon_widget(item[2], 40), False, False, 0)
    lab = Gtk.Label(label=item[1])
    lab.set_ellipsize(Pango.EllipsizeMode.END)
    lab.set_max_width_chars(11)
    box.pack_start(lab, False, False, 0)
    b.add(box)
    b.connect("clicked", lambda _b: (origin.mark(_b), launch(item)))
    attach_pin(b, item)
    return b


def rec_button(item):
    b = Gtk.Button()
    add_class(b, "tile")
    box = Gtk.Box(spacing=10)
    box.pack_start(icon_widget(item[2], 28), False, False, 0)
    lab = Gtk.Label(label=item[1], xalign=0)
    lab.set_ellipsize(Pango.EllipsizeMode.END)
    box.pack_start(lab, True, True, 0)
    b.add(box)
    b.connect("clicked", lambda _b: (origin.mark(_b), launch(item)))
    attach_pin(b, item)
    return b


def make_row(item):
    row = Gtk.ListBoxRow()
    row.item = item
    box = Gtk.Box(spacing=12)
    box.set_border_width(6)
    box.pack_start(icon_widget(item[2], 28), False, False, 0)
    box.pack_start(Gtk.Label(label=item[1], xalign=0), True, True, 0)
    row.add(box)
    attach_pin(row, item)
    return row


def fill(listbox, items):
    for r in listbox.get_children():
        listbox.remove(r)
    for it in items:
        listbox.add(make_row(it))
    if not items:
        row = Gtk.ListBoxRow()
        row.item = None
        row.set_selectable(False)
        row.add(Gtk.Label(label="No apps found", margin=12))
        listbox.add(row)
    listbox.show_all()
    first = listbox.get_row_at_index(0)
    if first and first.get_selectable():
        listbox.select_row(first)


def scrolled(listbox):
    sw = Gtk.ScrolledWindow()
    sw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
    sw.add(listbox)
    return sw


def tray_list():
    return list(load_conf().get("tray", []))


def set_tray(lst):
    cfg = load_conf()
    cfg["tray"] = lst
    try:
        os.makedirs(os.path.dirname(CONF), exist_ok=True)
        with open(CONF, "w") as f:
            json.dump(cfg, f, indent=2)
    except Exception as e:
        print("save failed:", e)


def attach_pin(widget, item):
    key = item[0]
    if key.startswith("td-"):
        return

    def on_press(w, ev):
        if ev.button != 3:
            return False
        pop = Gtk.Popover.new(w)
        pop.set_border_width(6)
        pinned_now = key in tray_list()
        b = Gtk.Button(
            label="Unpin from tray" if pinned_now else "Pin to tray")
        b.set_relief(Gtk.ReliefStyle.NONE)

        def toggle(_b):
            t = tray_list()
            if key in t:
                t.remove(key)
            else:
                t.append(key)
            set_tray(t)
            pop.popdown()

        b.connect("clicked", toggle)
        pop.add(b)
        b.show()
        pop.popup()
        return True

    widget.connect("button-press-event", on_press)
# ---------- window ----------
mon = Gdk.Display.get_default().get_monitor(0).get_geometry()
H = min(620, mon.height - BAR_H - 24)
PX = mon.x + (mon.width - WIDTH) // 2
PY = mon.y + mon.height - BAR_H - 12 - H

win = Gtk.Window(type=Gtk.WindowType.POPUP)
import glass
glass.apply(win)
win.set_title("tdmenu")
win.set_default_size(WIDTH, H)
win.move(PX, PY)

outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
add_class(outer, "tdmenu")
win.add(outer)

top = Gtk.Box()
top.set_border_width(20)
entry = Gtk.SearchEntry()
entry.set_placeholder_text("Search for apps")
add_class(entry, "search")
top.pack_start(entry, True, True, 0)
outer.pack_start(top, False, False, 0)

stack = Gtk.Stack()
stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
stack.set_transition_duration(120)
outer.pack_start(stack, True, True, 0)

# home page: pinned + recommended
home = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
home.set_margin_start(24)
home.set_margin_end(24)
home.pack_start(header("Pinned", "All apps  \u203a",
                       lambda: stack.set_visible_child_name("all")),
                False, False, 0)
grid = Gtk.Grid(column_homogeneous=True, row_spacing=4)
for n, it in enumerate(pinned):
    grid.attach(tile(it), n % COLS, n // COLS, 1, 1)
home.pack_start(grid, False, False, 0)
rec_head = header("Recommended")
rec_head.set_margin_top(14)
home.pack_start(rec_head, False, False, 0)
if recent:
    rgrid = Gtk.Grid(column_homogeneous=True, row_spacing=2,
                     column_spacing=4)
    for n, it in enumerate(recent):
        rgrid.attach(rec_button(it), n % 2, n // 2, 1, 1)
    home.pack_start(rgrid, False, False, 0)
else:
    hint = Gtk.Label(label="Apps you open will show up here", xalign=0)
    add_class(hint, "dim")
    home.pack_start(hint, False, False, 0)
stack.add_named(home, "home")

# all apps page
allp = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
allp.set_margin_start(24)
allp.set_margin_end(24)
allp.pack_start(header("All apps", "\u2039  Back",
                       lambda: stack.set_visible_child_name("home")),
                False, False, 0)
all_list = Gtk.ListBox()
all_list.connect("row-activated",
                 lambda lb, r: r.item and launch(r.item))
fill(all_list, items_all)
allp.pack_start(scrolled(all_list), True, True, 0)
stack.add_named(allp, "all")

# results page
resp = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
resp.set_margin_start(24)
resp.set_margin_end(24)
resp.pack_start(header("Best match"), False, False, 0)
results = Gtk.ListBox()
results.connect("row-activated",
                lambda lb, r: r.item and launch(r.item))
resp.pack_start(scrolled(results), True, True, 0)
stack.add_named(resp, "results")

# footer
foot = Gtk.Box(spacing=10)
foot.set_border_width(14)
add_class(foot, "footer")
user = GLib.get_user_name()
av = Gtk.Label(label=user[:1].upper())
add_class(av, "avatar")
foot.pack_start(av, False, False, 0)
foot.pack_start(Gtk.Label(label=user), False, False, 0)
outer.pack_end(foot, False, False, 0)


# ---------- behaviour ----------
def on_search(e):
    q = e.get_text().strip().lower()
    if not q:
        stack.set_visible_child_name("home")
        return
    ranked = sorted(universe, key=lambda it: -score(it, q))
    shown = [it for it in ranked if score(it, q) > 0.6][:10]
    fill(results, shown)
    stack.set_visible_child_name("results")


def on_activate(_e):
    if stack.get_visible_child_name() != "results":
        return
    row = results.get_selected_row()
    if row is not None and row.item:
        launch(row.item)


def move_sel(d):
    rows = results.get_children()
    sel = results.get_selected_row()
    if not rows or sel is None:
        return
    i = max(0, min(len(rows) - 1, sel.get_index() + d))
    results.select_row(rows[i])


def on_key(_w, ev):
    if ev.keyval == Gdk.KEY_Escape:
        Gtk.main_quit()
        return True
    if stack.get_visible_child_name() == "results":
        if ev.keyval == Gdk.KEY_Down:
            move_sel(1)
            return True
        if ev.keyval == Gdk.KEY_Up:
            move_sel(-1)
            return True
    return False


def on_press(_w, ev):
    x, y = win.get_position()
    w, h = win.get_size()
    if not (x <= ev.x_root < x + w and y <= ev.y_root < y + h):
        Gtk.main_quit()
    return False


def grab():
    try:
        seat = Gdk.Display.get_default().get_default_seat()
        seat.grab(win.get_window(), Gdk.SeatCapabilities.ALL, True,
                  None, None, None)
    except Exception as e:
        print("grab failed:", e)
    entry.grab_focus()
    return False


def on_map(*_a):
    win.move(PX, PY)
    GLib.timeout_add(80, grab)


entry.connect("search-changed", on_search)
entry.connect("activate", on_activate)
win.connect("key-press-event", on_key)
win.connect("button-press-event", on_press)
win.connect("map-event", on_map)
win.connect("destroy", lambda _w: Gtk.main_quit())

stack.set_visible_child_name("home")
win.show_all()
Gtk.main()
