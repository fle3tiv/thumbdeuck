import json
import os
import subprocess

conf = os.path.expanduser("~/.config/thumbdeuck/settings.json")
try:
    with open(conf) as f:
        cfg = json.load(f)
except Exception:
    cfg = {}

if cfg.get("bg_use", "image") == "color":
    subprocess.run(["xsetroot", "-solid", cfg.get("bg_color", "#000000")])
else:
    flags = {"scale": "--bg-scale", "fill": "--bg-fill", "max": "--bg-max",
             "center": "--bg-center", "tile": "--bg-tile"}
    flag = flags.get(cfg.get("bg_fit", "scale"), "--bg-scale")
    img = os.path.expanduser(cfg.get("bg_image", "~/duck.png"))
    subprocess.run(["feh", flag, img])
