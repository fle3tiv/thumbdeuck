import sys
import traceback
import subprocess
from Xlib import X, XK, Xatom, display, error
from Xlib.protocol import event

TITLE_H = 30
BW = 8
BTN = 34
MIN_W, MIN_H = 160, 90

d = display.Display()
screen = d.screen()
root = screen.root
cm = screen.default_colormap


def col(r, g, b):
    return cm.alloc_color(r * 257, g * 257, b * 257).pixel


C_BODY = col(24, 24, 30)
C_TITLE = col(36, 40, 56)
C_FOCUS = col(48, 72, 130)
C_WHITE = col(255, 255, 255)
C_DIM = col(160, 160, 172)
C_HOVER = col(80, 90, 120)
C_RED = col(200, 60, 50)
font = d.open_font('fixed')

WM_PROTOCOLS = d.intern_atom('WM_PROTOCOLS')
WM_DELETE = d.intern_atom('WM_DELETE_WINDOW')

# claim the screen and report if we cannot
catch = error.CatchError(error.BadAccess)
root.change_attributes(
    event_mask=X.SubstructureRedirectMask | X.SubstructureNotifyMask,
    onerror=catch)
d.sync()
if catch.get_error():
    print("wm: another window manager owns the screen", flush=True)
    sys.exit(1)
print("wm: got the screen", flush=True)

for button in (1, 3):
    root.grab_button(
        button, X.Mod4Mask, True,
        X.ButtonPressMask | X.ButtonReleaseMask | X.PointerMotionMask,
        X.GrabModeAsync, X.GrabModeAsync, X.NONE, X.NONE)

KEY_RETURN = d.keysym_to_keycode(XK.XK_Return)
KEY_Q = d.keysym_to_keycode(XK.XK_q)
KEY_TAB = d.keysym_to_keycode(XK.XK_Tab)
KEY_UP = d.keysym_to_keycode(XK.XK_Up)
for key in (KEY_RETURN, KEY_Q, KEY_TAB, KEY_UP):
    root.grab_key(key, X.Mod4Mask, True,
                  X.GrabModeAsync, X.GrabModeAsync)

clients = {}
frames = {}
hidden = []
focused = None
count = 0
drag = None
last = [0, 0]


def get_title(client):
    try:
        name = client.get_wm_name()
    except Exception:
        name = None
    if isinstance(name, bytes):
        name = name.decode('latin-1')
    return name or 'window'


def draw(info):
    fr, gc = info['frame'], info['gc']
    w = info['geo'][2]
    m = info['max']
    foc = focused is not None and focused.id == info['client'].id
    gc.change(foreground=C_FOCUS if foc else C_TITLE)
    fr.fill_rectangle(gc, 0, 0, w, TITLE_H)
    gc.change(foreground=C_WHITE if foc else C_DIM)
    room = max(0, (w - 3 * BTN - 24) // 6)
    fr.draw_text(gc, 12, 20, get_title(info['client'])[:room])
    for i, name in enumerate(('min', 'max', 'close')):
        bx = w - (3 - i) * BTN
        if info['hover'] == name:
            gc.change(foreground=C_RED if name == 'close' else C_HOVER)
            fr.fill_rectangle(gc, bx + 3, 4, BTN - 6, TITLE_H - 8)
        gc.change(foreground=C_WHITE)
        cx, cy = bx + BTN // 2, TITLE_H // 2
        if name == 'min':
            fr.line(gc, cx - 5, cy + 4, cx + 5, cy + 4)
        elif name == 'max':
            if m:
                fr.rectangle(gc, cx - 5, cy - 2, 8, 8)
                fr.line(gc, cx - 2, cy - 5, cx + 5, cy - 5)
                fr.line(gc, cx + 5, cy - 5, cx + 5, cy + 2)
            else:
                fr.rectangle(gc, cx - 5, cy - 5, 10, 10)
        else:
            fr.line(gc, cx - 5, cy - 5, cx + 5, cy + 5)
            fr.line(gc, cx - 5, cy + 5, cx + 5, cy - 5)


def place(info):
    fr, cl = info['frame'], info['client']
    x, y, w, h = info['geo']
    bw = 0 if info['max'] else BW
    fr.configure(x=x, y=y, width=w, height=h)
    cl.configure(x=bw, y=TITLE_H, width=max(1, w - 2 * bw),
                 height=max(1, h - TITLE_H - bw))
    draw(info)


def focus_client(client):
    global focused
    old = focused
    focused = client
    try:
        client.set_input_focus(X.RevertToPointerRoot, X.CurrentTime)
    except Exception:
        pass
    for c in (old, client):
        if c is not None and c.id in clients:
            draw(clients[c.id])


def close_client(client):
    try:
        protos = client.get_wm_protocols()
    except Exception:
        protos = []
    if WM_DELETE in protos:
        msg = event.ClientMessage(
            window=client, client_type=WM_PROTOCOLS,
            data=(32, [WM_DELETE, X.CurrentTime, 0, 0, 0]))
        client.send_event(msg)
    else:
        client.destroy()


def toggle_max(info):
    if info['max']:
        info['max'] = False
        info['geo'] = info['restore']
    else:
        info['restore'] = info['geo']
        g = root.get_geometry()
        info['max'] = True
        info['geo'] = (0, 0, g.width, g.height)
    place(info)
    info['frame'].configure(stack_mode=X.Above)


def minimize(info):
    global focused
    info['frame'].unmap()
    hidden.append(info)
    update_strip()
    if focused is not None and focused.id == info['client'].id:
        focused = None


def restore_last():
    if hidden:
        info = hidden.pop()
        update_strip()
        info['frame'].map()
        info['frame'].configure(stack_mode=X.Above)
        focus_client(info['client'])


def zone(info, x, y):
    if info['max']:
        return None
    w, h = info['geo'][2], info['geo'][3]
    e = 16
    ends_x = x < BW or x >= w - BW
    lf = x < BW or (x < e and (y < 5 or y >= h - BW))
    rt = x >= w - BW or (x >= w - e and (y < 5 or y >= h - BW))
    tp = y < 5 or (y < e and ends_x)
    bt = y >= h - BW or (y >= h - e and ends_x)
    if lf or rt or tp or bt:
        return (int(lf), int(rt), int(tp), int(bt))
    return None


def button_at(info, x, y):
    w = info['geo'][2]
    if y < 0 or y >= TITLE_H or x >= w:
        return None
    i = (w - 1 - x) // BTN
    if 0 <= i < 3:
        return ('close', 'max', 'min')[i]
    return None


cursors = {}
try:
    cf = d.open_font('cursor')

    def mk(g):
        return cf.create_glyph_cursor(
            cf, g, g + 1, (0, 0, 0), (0xffff, 0xffff, 0xffff))

    cursors[(1, 0, 0, 0)] = cursors[(0, 1, 0, 0)] = mk(108)
    cursors[(0, 0, 1, 0)] = cursors[(0, 0, 0, 1)] = mk(116)
    cursors[(1, 0, 1, 0)] = mk(134)
    cursors[(0, 1, 1, 0)] = mk(136)
    cursors[(1, 0, 0, 1)] = mk(12)
    cursors[(0, 1, 0, 1)] = mk(14)
except Exception as e:
    print("wm: no resize cursors:", e, flush=True)


def set_cursor(info, z):
    cur = cursors.get(z, X.NONE) if z else X.NONE
    if info.get('cur', X.NONE) != cur:
        info['cur'] = cur
        info['frame'].change_attributes(cursor=cur)


STRIP_H = 34
CHIP_W = 170
strip = None
strip_gc = None


def update_strip():
    global strip, strip_gc
    n = len(hidden)
    if n == 0:
        if strip is not None:
            strip.unmap()
        return
    g = root.get_geometry()
    w = n * (CHIP_W + 4) + 4
    x = (g.width - w) // 2
    y = g.height - STRIP_H - 8
    if strip is None:
        strip = root.create_window(
            x, y, w, STRIP_H, 0, screen.root_depth, X.InputOutput,
            X.CopyFromParent, background_pixel=C_BODY,
            override_redirect=1,
            event_mask=X.ExposureMask | X.ButtonPressMask)
        strip_gc = strip.create_gc(foreground=C_WHITE, font=font)
    else:
        strip.configure(x=x, y=y, width=w, height=STRIP_H)
    strip.map()
    strip.configure(stack_mode=X.Above)
    draw_strip()


def draw_strip():
    if strip is None:
        return
    strip.clear_area()
    for i, info in enumerate(hidden):
        cx = 4 + i * (CHIP_W + 4)
        strip_gc.change(foreground=C_TITLE)
        strip.fill_rectangle(strip_gc, cx, 4, CHIP_W, STRIP_H - 8)
        strip_gc.change(foreground=C_WHITE)
        title = get_title(info['client'])[:(CHIP_W - 40) // 6]
        strip.draw_text(strip_gc, cx + 8, 20, title)
        strip_gc.change(foreground=C_RED)
        strip.fill_rectangle(strip_gc, cx + CHIP_W - 24, 4, 24,
                             STRIP_H - 8)
        strip_gc.change(foreground=C_WHITE)
        bx = cx + CHIP_W - 12
        strip.line(strip_gc, bx - 4, 12, bx + 4, 20)
        strip.line(strip_gc, bx - 4, 20, bx + 4, 12)


def strip_event(ev):
    if strip is None or ev.window.id != strip.id:
        return False
    if ev.type == X.Expose:
        if ev.count == 0:
            draw_strip()
    elif ev.type == X.ButtonPress:
        i = (ev.event_x - 4) // (CHIP_W + 4)
        if 0 <= i < len(hidden):
            info = hidden.pop(i)
            cx = 4 + i * (CHIP_W + 4)
            info['frame'].map()
            info['frame'].configure(stack_mode=X.Above)
            focus_client(info['client'])
            if ev.event_x >= cx + CHIP_W - 24:
                close_client(info['client'])
            update_strip()
    return True


# ---- macOS-style minimised strip (overrides the plain one above) ----
STRIP_H = 44
CHIP_W = 190
CHIP_H = 32
PAD = 8
STRIP_BOTTOM = 14
C_PILL = col(40, 42, 54)
C_CHIP = col(62, 66, 86)
C_CHIP_HOT = col(88, 96, 130)
C_ICON = col(90, 130, 220)
C_CLOSE_DOT = col(255, 95, 87)
strip_hover = [None]


def rrect(win, gc, x, y, w, h, r):
    r = min(r, w // 2, h // 2)
    win.fill_rectangle(gc, x + r, y, w - 2 * r, h)
    win.fill_rectangle(gc, x, y + r, w, h - 2 * r)
    for ax, ay in ((x, y), (x + w - 2 * r, y),
                   (x, y + h - 2 * r), (x + w - 2 * r, y + h - 2 * r)):
        win.fill_arc(gc, ax, ay, 2 * r, 2 * r, 0, 360 * 64)


def round_shape(win, w, h, r):
    try:
        from Xlib.ext import shape
        pm = win.create_pixmap(w, h, 1)
        g0 = pm.create_gc(foreground=0, background=0)
        pm.fill_rectangle(g0, 0, 0, w, h)
        g1 = pm.create_gc(foreground=1, background=1)
        rrect(pm, g1, 0, 0, w, h, r)
        win.shape_mask(shape.SO.Set, shape.SK.Bounding, 0, 0, pm)
        pm.free()
    except Exception as e:
        print("wm: no rounded strip:", e, flush=True)


def strip_width():
    return len(hidden) * (CHIP_W + PAD) + PAD


def update_strip():
    global strip, strip_gc
    n = len(hidden)
    if n == 0:
        if strip is not None:
            strip.unmap()
        return
    g = root.get_geometry()
    w = strip_width()
    x = (g.width - w) // 2
    y = g.height - STRIP_H - STRIP_BOTTOM
    if strip is None:
        strip = root.create_window(
            x, y, w, STRIP_H, 0, screen.root_depth, X.InputOutput,
            X.CopyFromParent, background_pixel=C_PILL,
            override_redirect=1,
            event_mask=(X.ExposureMask | X.ButtonPressMask
                        | X.PointerMotionMask | X.LeaveWindowMask))
        strip_gc = strip.create_gc(foreground=C_WHITE, font=font)
    else:
        strip.configure(x=x, y=y, width=w, height=STRIP_H)
    round_shape(strip, w, STRIP_H, STRIP_H // 2)
    strip.map()
    strip.configure(stack_mode=X.Above)
    draw_strip()


def draw_strip():
    if strip is None:
        return
    w = strip_width()
    strip_gc.change(foreground=C_PILL)
    strip.fill_rectangle(strip_gc, 0, 0, w, STRIP_H)
    cy = (STRIP_H - CHIP_H) // 2
    for i, info in enumerate(hidden):
        cx = PAD + i * (CHIP_W + PAD)
        hot = strip_hover[0] == i
        strip_gc.change(foreground=C_CHIP_HOT if hot else C_CHIP)
        rrect(strip, strip_gc, cx, cy, CHIP_W, CHIP_H, 16)
        strip_gc.change(foreground=C_ICON)
        strip.fill_arc(strip_gc, cx + 6, cy + 5, 22, 22, 0, 360 * 64)
        title = get_title(info['client'])
        strip_gc.change(foreground=C_WHITE)
        strip.draw_text(strip_gc, cx + 13, cy + 20, title[:1].upper())
        room = max(0, (CHIP_W - 36 - 34) // 6)
        strip.draw_text(strip_gc, cx + 36, cy + 20, title[:room])
        dx = cx + CHIP_W - 26
        strip_gc.change(foreground=C_CLOSE_DOT)
        strip.fill_arc(strip_gc, dx, cy + 8, 16, 16, 0, 360 * 64)
        if hot:
            strip_gc.change(foreground=C_BODY)
            strip.line(strip_gc, dx + 5, cy + 13, dx + 11, cy + 19)
            strip.line(strip_gc, dx + 5, cy + 19, dx + 11, cy + 13)


def strip_event(ev):
    if strip is None or ev.window.id != strip.id:
        return False
    if ev.type == X.Expose:
        if ev.count == 0:
            draw_strip()
    elif ev.type == X.MotionNotify:
        i = (ev.event_x - PAD) // (CHIP_W + PAD)
        if not (0 <= i < len(hidden)):
            i = None
        if i != strip_hover[0]:
            strip_hover[0] = i
            draw_strip()
    elif ev.type == X.LeaveNotify:
        if strip_hover[0] is not None:
            strip_hover[0] = None
            draw_strip()
    elif ev.type == X.ButtonPress:
        i = (ev.event_x - PAD) // (CHIP_W + PAD)
        if 0 <= i < len(hidden):
            info = hidden.pop(i)
            cx = PAD + i * (CHIP_W + PAD)
            strip_hover[0] = None
            info['frame'].map()
            info['frame'].configure(stack_mode=X.Above)
            focus_client(info['client'])
            if ev.event_x >= cx + CHIP_W - 34:
                close_client(info['client'])
            update_strip()
    return True


# ---- translucent strip (overrides the solid one above) ----
def find_argb():
    for dp in screen.allowed_depths:
        if dp.depth == 32:
            for v in dp.visuals:
                if v.visual_class == X.TrueColor:
                    return v.visual_id
    return None


s_vis = find_argb()
s_cmap = root.create_colormap(s_vis, X.AllocNone) if s_vis else None


def argb(r, g, b, a):
    f = a / 255.0
    return ((a << 24) | (int(r * f) << 16)
            | (int(g * f) << 8) | int(b * f))


if s_vis:
    A_CLEAR = 0
    A_PILL = argb(24, 26, 38, 90)
    A_CHIP = argb(92, 100, 134, 150)
    A_CHIP_HOT = argb(125, 136, 178, 215)
    A_ICON = argb(90, 130, 220, 240)
    A_TEXT = argb(255, 255, 255, 255)
    A_DOT = argb(255, 95, 87, 255)
    A_DOTX = argb(70, 20, 20, 255)
else:
    A_CLEAR = C_BODY
    A_PILL = C_PILL
    A_CHIP = C_CHIP
    A_CHIP_HOT = C_CHIP_HOT
    A_ICON = C_ICON
    A_TEXT = C_WHITE
    A_DOT = C_CLOSE_DOT
    A_DOTX = C_BODY


def update_strip():
    global strip, strip_gc
    n = len(hidden)
    if n == 0:
        if strip is not None:
            strip.unmap()
        return
    g = root.get_geometry()
    w = strip_width()
    x = (g.width - w) // 2
    y = g.height - STRIP_H - STRIP_BOTTOM
    if strip is None:
        mask = (X.ExposureMask | X.ButtonPressMask
                | X.PointerMotionMask | X.LeaveWindowMask)
        if s_vis:
            strip = root.create_window(
                x, y, w, STRIP_H, 0, 32, X.InputOutput, s_vis,
                colormap=s_cmap, background_pixel=0, border_pixel=0,
                override_redirect=1, event_mask=mask)
        else:
            strip = root.create_window(
                x, y, w, STRIP_H, 0, screen.root_depth, X.InputOutput,
                X.CopyFromParent, background_pixel=C_PILL,
                override_redirect=1, event_mask=mask)
        strip.set_wm_name('tdstrip')
        strip_gc = strip.create_gc(foreground=A_TEXT, font=font)
    else:
        strip.configure(x=x, y=y, width=w, height=STRIP_H)
    strip.map()
    strip.configure(stack_mode=X.Above)
    draw_strip()


def draw_strip():
    if strip is None:
        return
    w = strip_width()
    strip_gc.change(foreground=A_CLEAR)
    strip.fill_rectangle(strip_gc, 0, 0, w, STRIP_H)
    strip_gc.change(foreground=A_PILL)
    rrect(strip, strip_gc, 0, 0, w, STRIP_H, STRIP_H // 2)
    cy = (STRIP_H - CHIP_H) // 2
    for i, info in enumerate(hidden):
        cx = PAD + i * (CHIP_W + PAD)
        hot = strip_hover[0] == i
        strip_gc.change(foreground=A_CHIP_HOT if hot else A_CHIP)
        rrect(strip, strip_gc, cx, cy, CHIP_W, CHIP_H, 16)
        strip_gc.change(foreground=A_ICON)
        strip.fill_arc(strip_gc, cx + 6, cy + 5, 22, 22, 0, 360 * 64)
        title = get_title(info['client'])
        strip_gc.change(foreground=A_TEXT)
        strip.draw_text(strip_gc, cx + 13, cy + 20, title[:1].upper())
        room = max(0, (CHIP_W - 36 - 34) // 6)
        strip.draw_text(strip_gc, cx + 36, cy + 20, title[:room])
        dx = cx + CHIP_W - 26
        strip_gc.change(foreground=A_DOT)
        strip.fill_arc(strip_gc, dx, cy + 8, 16, 16, 0, 360 * 64)
        if hot:
            strip_gc.change(foreground=A_DOTX)
            strip.line(strip_gc, dx + 5, cy + 13, dx + 11, cy + 19)
            strip.line(strip_gc, dx + 5, cy + 19, dx + 11, cy + 13)



# ---- translucent rounded title bars (overrides draw above) ----
FRAME_ARGB = bool(s_vis)
RAD = 12

if FRAME_ARGB:
    A_TF = argb(52, 78, 140, 175)
    A_TU = argb(30, 32, 44, 140)
    A_BTN_HOT = argb(120, 130, 175, 215)
    A_BTN_RED = argb(215, 70, 60, 240)
    A_FG = argb(255, 255, 255, 255)
    A_FG_DIM = argb(185, 185, 198, 235)
else:
    A_TF, A_TU = C_FOCUS, C_TITLE
    A_BTN_HOT, A_BTN_RED = C_HOVER, C_RED
    A_FG, A_FG_DIM = C_WHITE, C_DIM


def make_frame(x, y, fw, fh, mask):
    if FRAME_ARGB:
        return root.create_window(
            x, y, fw, fh, 0, 32, X.InputOutput, s_vis,
            colormap=s_cmap, background_pixel=0, border_pixel=0,
            event_mask=mask)
    return root.create_window(
        x, y, fw, fh, 0, screen.root_depth, X.InputOutput,
        X.CopyFromParent, background_pixel=C_BODY, event_mask=mask)


def draw(info):
    fr, gc = info['frame'], info['gc']
    w, h = info['geo'][2], info['geo'][3]
    m = info['max']
    bw = 0 if m else BW
    r = RAD if (FRAME_ARGB and not m) else 0
    foc = focused is not None and focused.id == info['client'].id
    if FRAME_ARGB:
        gc.change(foreground=0)
        fr.fill_rectangle(gc, 0, 0, w, TITLE_H)
    gc.change(foreground=A_TF if foc else A_TU)
    if r:
        fr.fill_arc(gc, 0, 0, 2 * r, 2 * r, 0, 360 * 64)
        fr.fill_arc(gc, w - 2 * r, 0, 2 * r, 2 * r, 0, 360 * 64)
        fr.fill_rectangle(gc, r, 0, w - 2 * r, r)
        fr.fill_rectangle(gc, 0, r, w, TITLE_H - r)
    else:
        fr.fill_rectangle(gc, 0, 0, w, TITLE_H)
    if bw:
        fr.fill_rectangle(gc, 0, TITLE_H, bw, h - TITLE_H)
        fr.fill_rectangle(gc, w - bw, TITLE_H, bw, h - TITLE_H)
        fr.fill_rectangle(gc, 0, h - bw, w, bw)
    gc.change(foreground=A_FG if foc else A_FG_DIM)
    room = max(0, (w - 3 * BTN - 28) // 6)
    fr.draw_text(gc, 14, 20, get_title(info['client'])[:room])
    for i, name in enumerate(('min', 'max', 'close')):
        bx = w - (3 - i) * BTN
        if info['hover'] == name:
            gc.change(foreground=A_BTN_RED if name == 'close'
                      else A_BTN_HOT)
            fr.fill_rectangle(gc, bx + 3, 4, BTN - 6, TITLE_H - 8)
        gc.change(foreground=A_FG)
        cx, cy = bx + BTN // 2, TITLE_H // 2
        if name == 'min':
            fr.line(gc, cx - 5, cy + 4, cx + 5, cy + 4)
        elif name == 'max':
            if m:
                fr.rectangle(gc, cx - 5, cy - 2, 8, 8)
                fr.line(gc, cx - 2, cy - 5, cx + 5, cy - 5)
                fr.line(gc, cx + 5, cy - 5, cx + 5, cy + 2)
            else:
                fr.rectangle(gc, cx - 5, cy - 5, 10, 10)
        else:
            fr.line(gc, cx - 5, cy - 5, cx + 5, cy + 5)
            fr.line(gc, cx - 5, cy + 5, cx + 5, cy - 5)


# ---- neutral glass, rounded on all corners (overrides draw above) ----
if FRAME_ARGB:
    A_TF = argb(70, 72, 80, 120)
    A_TU = argb(26, 26, 30, 100)
    A_FG = argb(255, 255, 255, 255)
    A_FG_DIM = argb(200, 200, 208, 235)
    A_BTN_HOT = argb(140, 144, 160, 190)
    A_BTN_RED = argb(215, 70, 60, 235)


def draw(info):
    fr, gc = info['frame'], info['gc']
    w, h = info['geo'][2], info['geo'][3]
    m = info['max']
    bw = 0 if m else BW
    r = RAD if (FRAME_ARGB and not m) else 0
    foc = focused is not None and focused.id == info['client'].id
    if FRAME_ARGB:
        gc.change(foreground=0)
        fr.fill_rectangle(gc, 0, 0, w, h)
    gc.change(foreground=A_TF if foc else A_TU)
    if r:
        fr.fill_arc(gc, 0, 0, 2 * r, 2 * r, 0, 360 * 64)
        fr.fill_arc(gc, w - 2 * r, 0, 2 * r, 2 * r, 0, 360 * 64)
        fr.fill_arc(gc, 0, h - 2 * r, 2 * r, 2 * r, 0, 360 * 64)
        fr.fill_arc(gc, w - 2 * r, h - 2 * r, 2 * r, 2 * r,
                    0, 360 * 64)
        fr.fill_rectangle(gc, r, 0, w - 2 * r, r)
        fr.fill_rectangle(gc, 0, r, w, TITLE_H - r)
        fr.fill_rectangle(gc, 0, TITLE_H, bw, h - TITLE_H - r)
        fr.fill_rectangle(gc, w - bw, TITLE_H, bw, h - TITLE_H - r)
        fr.fill_rectangle(gc, r, h - bw, w - 2 * r, bw)
    else:
        fr.fill_rectangle(gc, 0, 0, w, TITLE_H)
        if bw:
            fr.fill_rectangle(gc, 0, TITLE_H, bw, h - TITLE_H)
            fr.fill_rectangle(gc, w - bw, TITLE_H, bw, h - TITLE_H)
            fr.fill_rectangle(gc, 0, h - bw, w, bw)
    gc.change(foreground=A_FG if foc else A_FG_DIM)
    room = max(0, (w - 3 * BTN - 28) // 6)
    fr.draw_text(gc, 14, 20, get_title(info['client'])[:room])
    for i, name in enumerate(('min', 'max', 'close')):
        bx = w - (3 - i) * BTN
        if info['hover'] == name:
            gc.change(foreground=A_BTN_RED if name == 'close'
                      else A_BTN_HOT)
            fr.fill_rectangle(gc, bx + 3, 4, BTN - 6, TITLE_H - 8)
        gc.change(foreground=A_FG)
        cx, cy = bx + BTN // 2, TITLE_H // 2
        if name == 'min':
            fr.line(gc, cx - 5, cy + 4, cx + 5, cy + 4)
        elif name == 'max':
            if m:
                fr.rectangle(gc, cx - 5, cy - 2, 8, 8)
                fr.line(gc, cx - 2, cy - 5, cx + 5, cy - 5)
                fr.line(gc, cx + 5, cy - 5, cx + 5, cy + 2)
            else:
                fr.rectangle(gc, cx - 5, cy - 5, 10, 10)
        else:
            fr.line(gc, cx - 5, cy - 5, cx + 5, cy + 5)
            fr.line(gc, cx - 5, cy + 5, cx + 5, cy - 5)


# ---- genie-style animation (overrides minimize / restore) ----
import time

ANIM = [False]
GENIE_DUR = 0.30
ghost = None
ghost_gc = None

if FRAME_ARGB:
    G_CLEAR = 0
    G_FILL = argb(120, 124, 140, 120)
    G_EDGE = argb(235, 235, 245, 235)
else:
    G_CLEAR = C_BODY
    G_FILL = C_TITLE
    G_EDGE = C_WHITE


def ghost_win():
    global ghost, ghost_gc
    if ghost is None:
        if s_vis:
            ghost = root.create_window(
                0, 0, 10, 10, 0, 32, X.InputOutput, s_vis,
                colormap=s_cmap, background_pixel=0, border_pixel=0,
                override_redirect=1)
        else:
            ghost = root.create_window(
                0, 0, 10, 10, 0, screen.root_depth, X.InputOutput,
                X.CopyFromParent, background_pixel=C_BODY,
                override_redirect=1)
        ghost.set_wm_name('tdghost')
        ghost_gc = ghost.create_gc(foreground=0)
    return ghost


def lerp(a, b, t):
    return a + (b - a) * t


def ease(t):
    return t * t * (3 - 2 * t)


def run_genie(src, dst, reverse, dur):
    gw = ghost_win()
    sx, sy, sw, sh = src
    dx, dy, dw, dh = dst
    scx = sx + sw / 2.0
    dcx = dx + dw / 2.0
    t0 = time.monotonic()
    mapped = False
    while True:
        el = (time.monotonic() - t0) / dur
        if el >= 1.0:
            break
        t = 1.0 - el if reverse else el
        et = ease(t)
        eb = ease(min(1.0, t * 1.6))
        tcx = lerp(scx, dcx, et)
        tw = lerp(sw, dw, et)
        ty = lerp(sy, dy, et)
        bcx = lerp(scx, dcx, eb)
        bw = lerp(sw, dw, eb)
        by = max(lerp(sy + sh, dy + dh, eb), ty + 3)
        pts = [(tcx - tw / 2, ty), (tcx + tw / 2, ty),
               (bcx + bw / 2, by), (bcx - bw / 2, by)]
        minx = int(min(p[0] for p in pts))
        maxx = int(max(p[0] for p in pts)) + 1
        miny = int(ty)
        maxy = int(by) + 1
        wd = max(1, maxx - minx + 1)
        ht = max(1, maxy - miny + 1)
        gw.configure(x=minx, y=miny, width=wd, height=ht,
                     stack_mode=X.Above)
        if not mapped:
            gw.map()
            mapped = True
        local = [(int(px - minx), int(py - miny)) for px, py in pts]
        ghost_gc.change(foreground=G_CLEAR)
        gw.fill_rectangle(ghost_gc, 0, 0, wd, ht)
        ghost_gc.change(foreground=G_FILL)
        gw.fill_poly(ghost_gc, X.Convex, X.CoordModeOrigin, local)
        ghost_gc.change(foreground=G_EDGE)
        gw.poly_line(ghost_gc, X.CoordModeOrigin, local + [local[0]])
        d.sync()
        time.sleep(0.008)


def genie(src, dst, reverse=False, dur=GENIE_DUR):
    try:
        run_genie(src, dst, reverse, dur)
    except Exception:
        traceback.print_exc()
    try:
        if ghost is not None:
            ghost.unmap()
        d.sync()
    except Exception:
        pass


def chip_rect(i, n):
    g = root.get_geometry()
    sw = n * (CHIP_W + PAD) + PAD
    sx = (g.width - sw) // 2
    sy = g.height - STRIP_H - STRIP_BOTTOM
    return (sx + PAD + i * (CHIP_W + PAD),
            sy + (STRIP_H - CHIP_H) // 2, CHIP_W, CHIP_H)


def genie_open(info):
    if not ANIM[0]:
        return
    g = root.get_geometry()
    ow, oh = 140, 24
    origin = ((g.width - ow) // 2, g.height - STRIP_BOTTOM - oh - 10,
              ow, oh)
    genie(info['geo'], origin, reverse=True)


def minimize(info):
    global focused
    src = info['geo']
    info['frame'].unmap()
    hidden.append(info)
    if focused is not None and focused.id == info['client'].id:
        focused = None
    update_strip()
    genie(src, chip_rect(len(hidden) - 1, len(hidden)))


def restore_last():
    if hidden:
        n = len(hidden)
        rect = chip_rect(n - 1, n)
        info = hidden.pop()
        update_strip()
        genie(info['geo'], rect, reverse=True)
        info['frame'].map()
        info['frame'].configure(stack_mode=X.Above)
        focus_client(info['client'])


def strip_event(ev):
    if strip is None or ev.window.id != strip.id:
        return False
    if ev.type == X.Expose:
        if ev.count == 0:
            draw_strip()
    elif ev.type == X.MotionNotify:
        i = (ev.event_x - PAD) // (CHIP_W + PAD)
        if not (0 <= i < len(hidden)):
            i = None
        if i != strip_hover[0]:
            strip_hover[0] = i
            draw_strip()
    elif ev.type == X.LeaveNotify:
        if strip_hover[0] is not None:
            strip_hover[0] = None
            draw_strip()
    elif ev.type == X.ButtonPress:
        n = len(hidden)
        i = (ev.event_x - PAD) // (CHIP_W + PAD)
        if 0 <= i < n:
            rect = chip_rect(i, n)
            info = hidden.pop(i)
            cx = PAD + i * (CHIP_W + PAD)
            strip_hover[0] = None
            closing = ev.event_x >= cx + CHIP_W - 34
            update_strip()
            if not closing:
                genie(info['geo'], rect, reverse=True)
            info['frame'].map()
            info['frame'].configure(stack_mode=X.Above)
            focus_client(info['client'])
            if closing:
                close_client(info['client'])
    return True


# ---- genie starts from the clicked icon ----
import os


def read_origin():
    try:
        with open("/tmp/td_origin") as f:
            t, x, y, w, h = f.read().split()
        os.remove("/tmp/td_origin")
        if time.time() - float(t) < 5:
            return (int(x), int(y), int(w), int(h))
    except Exception:
        pass
    return None


def genie_open(info):
    if not ANIM[0]:
        return
    origin = read_origin()
    print("wm: origin", origin, flush=True)
    if origin is None:
        g = root.get_geometry()
        ow, oh = 140, 24
        origin = ((g.width - ow) // 2,
                  g.height - STRIP_BOTTOM - oh - 10, ow, oh)
    genie(info['geo'], origin, reverse=True)


def manage(client):
    global count
    if client.id in clients:
        return
    g = client.get_geometry()
    fw = g.width + 2 * BW
    fh = g.height + TITLE_H + BW
    x = 40 + (count % 8) * 30
    y = 40 + (count % 8) * 30
    count += 1
    mask = (X.ExposureMask | X.ButtonPressMask | X.ButtonReleaseMask
            | X.PointerMotionMask | X.EnterWindowMask
            | X.LeaveWindowMask)
    frame = make_frame(x, y, fw, fh, mask)
    gc = frame.create_gc(foreground=C_WHITE, font=font)
    client.configure(border_width=0)
    client.change_attributes(
        event_mask=X.StructureNotifyMask | X.PropertyChangeMask)
    client.change_save_set(X.SetModeInsert)
    client.reparent(frame, BW, TITLE_H)
    info = {'frame': frame, 'client': client, 'gc': gc,
            'geo': (x, y, fw, fh), 'restore': (x, y, fw, fh),
            'max': False, 'hover': None}
    clients[client.id] = info
    frames[frame.id] = client.id
    genie_open(info)
    frame.map()
    client.map()
    focus_client(client)
    print("wm: framed", client.id, flush=True)


def handle(ev):
    global focused, drag
    t = ev.type
    if strip_event(ev):
        return

    if t == X.MapRequest:
        manage(ev.window)

    elif t == X.ConfigureRequest:
        info = clients.get(ev.window.id)
        if info:
            if info['max']:
                return
            x, y, w, h = info['geo']
            if ev.value_mask & X.CWWidth:
                w = ev.width + 2 * BW
            if ev.value_mask & X.CWHeight:
                h = ev.height + TITLE_H + BW
            info['geo'] = (x, y, w, h)
            place(info)
        else:
            ev.window.configure(x=ev.x, y=ev.y,
                                width=ev.width, height=ev.height)

    elif t == X.Expose:
        cid = frames.get(ev.window.id)
        if cid and ev.count == 0:
            draw(clients[cid])

    elif t == X.PropertyNotify:
        info = clients.get(ev.window.id)
        if info and ev.atom == Xatom.WM_NAME:
            draw(info)

    elif t == X.EnterNotify:
        cid = frames.get(ev.window.id)
        if cid:
            focus_client(clients[cid]['client'])

    elif t == X.LeaveNotify:
        cid = frames.get(ev.window.id)
        if cid:
            set_cursor(clients[cid], None)
        if cid and clients[cid]['hover']:
            clients[cid]['hover'] = None
            draw(clients[cid])

    elif t == X.DestroyNotify:
        info = clients.pop(ev.window.id, None)
        if info:
            frames.pop(info['frame'].id, None)
            if info in hidden:
                hidden.remove(info)
                update_strip()
            info['frame'].destroy()
            if focused is not None and focused.id == ev.window.id:
                focused = None

    elif t == X.KeyPress:
        if ev.detail == KEY_RETURN:
            subprocess.Popen(["sh", "-c", "$HOME/tdterm.sh"])
        elif ev.detail == KEY_Q and focused:
            close_client(focused)
        elif ev.detail == KEY_TAB:
            restore_last()
        elif ev.detail == KEY_UP and focused:
            if focused.id in clients:
                toggle_max(clients[focused.id])

    elif t == X.ButtonPress:
        flags = None
        if ev.window.id == root.id:
            if ev.child == X.NONE or ev.child.id not in frames:
                return
            info = clients[frames[ev.child.id]]
            if info['max']:
                return
            mode = 'move' if ev.detail == 1 else 'edge'
            flags = (0, 1, 0, 1)
        elif ev.window.id in frames:
            if ev.detail != 1:
                return
            info = clients[frames[ev.window.id]]
            z = zone(info, ev.event_x, ev.event_y)
            b = button_at(info, ev.event_x, ev.event_y)
            if z:
                mode = 'edge'
                flags = z
            elif b == 'close':
                close_client(info['client'])
                return
            elif b == 'max':
                toggle_max(info)
                return
            elif b == 'min':
                minimize(info)
                return
            else:
                fid = info['frame'].id
                if ev.time - last[0] < 400 and last[1] == fid:
                    last[0] = 0
                    toggle_max(info)
                    return
                last[0], last[1] = ev.time, fid
                if info['max']:
                    return
                mode = 'move'
        else:
            return
        info['frame'].configure(stack_mode=X.Above)
        focus_client(info['client'])
        drag = dict(info=info, mode=mode, flags=flags,
                    px=ev.root_x, py=ev.root_y, geo=info['geo'])

    elif t == X.MotionNotify:
        if drag:
            dx = ev.root_x - drag['px']
            dy = ev.root_y - drag['py']
            info = drag['info']
            ox, oy, ow, oh = drag['geo']
            if drag['mode'] == 'move':
                info['geo'] = (ox + dx, oy + dy, ow, oh)
                info['frame'].configure(x=ox + dx, y=oy + dy)
            else:
                lf, rt, tp, bt = drag['flags']
                nx, ny, nw, nh = ox, oy, ow, oh
                if lf:
                    nw = max(MIN_W, ow - dx)
                    nx = ox + ow - nw
                if rt:
                    nw = max(MIN_W, ow + dx)
                if tp:
                    nh = max(MIN_H, oh - dy)
                    ny = oy + oh - nh
                if bt:
                    nh = max(MIN_H, oh + dy)
                info['geo'] = (nx, ny, nw, nh)
                place(info)
        elif ev.window.id in frames:
            info = clients[frames[ev.window.id]]
            z = zone(info, ev.event_x, ev.event_y)
            set_cursor(info, z)
            hv = None if z else button_at(info, ev.event_x, ev.event_y)
            if hv != info['hover']:
                info['hover'] = hv
                draw(info)

    elif t == X.ButtonRelease:
        drag = None


for w in root.query_tree().children:
    try:
        a = w.get_attributes()
        if a.map_state == X.IsViewable and not a.override_redirect:
            manage(w)
    except Exception:
        traceback.print_exc()

ANIM[0] = True
print("wm: running", flush=True)
while True:
    ev = d.next_event()
    try:
        handle(ev)
    except Exception:
        traceback.print_exc()
        sys.stderr.flush()
