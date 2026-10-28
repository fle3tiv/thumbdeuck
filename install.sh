#!/bin/sh
set -e
cd "$(dirname "$0")"

echo "Installing packages..."
sudo pacman -S --needed python python-xlib python-gobject gtk3 \
    xorg-server xorg-xrandr xorg-xsetroot xorg-xcursorgen \
    picom feh alacritty figlet fastfetch xterm xorg-fonts-misc

echo "Copying ThumbDEuck files..."
for f in mywm.py startde.sh panel.py launcher.py glass.py origin.py \
         apply_bg.py settings_gui.py power.py desktop.py tdterm.sh tdbanner.sh \
         liquid.css cursor.png; do
    cp "$f" "$HOME/$f"
done
chmod +x "$HOME/startde.sh" "$HOME/tdterm.sh" "$HOME/tdbanner.sh"

install_cfg() {
    mkdir -p "$(dirname "$2")"
    [ -f "$2" ] && cp "$2" "$2.before-thumbdeuck"
    cp "$1" "$2"
}
install_cfg picom.conf "$HOME/.config/picom.conf"
install_cfg alacritty.toml "$HOME/.config/alacritty/alacritty.toml"
install_cfg fastfetch.jsonc "$HOME/.config/fastfetch/config.jsonc"

echo "24 6 6 $HOME/cursor.png" > "$HOME/cursor.cfg"
xcursorgen "$HOME/cursor.cfg" "$HOME/dotcursor"

mkdir -p "$HOME/.config/thumbdeuck"
if [ ! -f "$HOME/.config/thumbdeuck/settings.json" ]; then
    echo '{"bg_use": "color", "bg_color": "#1e2a44"}' \
        > "$HOME/.config/thumbdeuck/settings.json"
fi

echo "Installing the login-screen session..."
sudo cp td-session.sh /usr/local/bin/thumbdeuck-session
sudo chmod +x /usr/local/bin/thumbdeuck-session
sudo cp thumbdeuck.desktop /usr/share/xsessions/thumbdeuck.desktop

echo "Done. Log out and pick ThumbDEuck from the session menu."
