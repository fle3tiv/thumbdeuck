import time


def mark(w):
    try:
        top = w.get_toplevel()
        ok, ox, oy = top.get_window().get_origin()
        r = w.translate_coordinates(top, 0, 0)
        tx, ty = r if r else (0, 0)
        a = w.get_allocation()
        with open("/tmp/td_origin", "w") as f:
            f.write("%f %d %d %d %d" % (
                time.time(), ox + tx, oy + ty, a.width, a.height))
    except Exception as e:
        print("origin:", e)
