#!/bin/sh
exec >> "$HOME/td-session.log" 2>&1
echo "--- session start $(date)"

# give the session its own message bus if the login manager did not
if [ -z "$DBUS_SESSION_BUS_ADDRESS" ] && command -v dbus-run-session >/dev/null 2>&1; then
    exec dbus-run-session -- "$0" "$@"
fi

export XDG_CURRENT_DESKTOP=ThumbDEuck
export XDG_SESSION_DESKTOP=ThumbDEuck

# VirtualBox: resize with the window, shared clipboard
command -v VBoxClient-all >/dev/null 2>&1 && VBoxClient-all &

pgrep -x picom >/dev/null || picom --config "$HOME/.config/picom.conf" &
sleep 1

# the panel starts a few seconds after the window manager
( sleep 3; python -W ignore "$HOME/panel.py" ) &

# when the window manager ends, the session ends
exec "$HOME/startde.sh"
