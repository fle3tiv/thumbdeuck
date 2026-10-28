#!/bin/sh
xrandr >/dev/null 2>&1 || { echo "No display, stopping"; exit 1; }
python ~/mywm.py &
WM=$!
sleep 1
xsetroot -xcf $HOME/dotcursor 24
last=""
while kill -0 $WM 2>/dev/null; do
    size=$(xrandr 2>/dev/null | grep '\*' | head -1 | awk '{print $1}')
    [ -z "$size" ] && break
    if [ "$size" != "$last" ]; then
        python $HOME/apply_bg.py
        last="$size"
    fi
    sleep 1
done
