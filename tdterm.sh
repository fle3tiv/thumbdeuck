#!/bin/sh
exec alacritty -T Terminal \
  -o window.opacity=0.72 \
  -o 'window.dimensions={columns=100,lines=35}' \
  -e bash -c "$HOME/tdbanner.sh; exec bash"
