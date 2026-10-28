# ThumbDEuck 1._

Made by a 12 year old in just 2 weeks (ThumbDEuck 1._) enjoy! :P
A small desktop environment made from scratch in Python: window manager,
glass panel, app menu, settings, desktop icons and clock widget.

**Hobby project.** Tested only on Arch Linux in a VirtualBox VM. The glass
look, blur and animations may behave differently on other hardware.

## Requirements
- Arch Linux with an Xorg login screen (LightDM, SDDM, GDM...)
- A user account with sudo

## Install
    sudo pacman -S --needed git
    git clone https://github.com/fle3tiv/thumbdeuck
    cd thumbdeuck
    less install.sh      # read it first, it uses sudo
    ./install.sh

Then log out, pick **ThumbDEuck** in the session menu, and log in.

## Update
    cd thumbdeuck
    git pull
    ./install.sh

## Keys
Super+Enter terminal, Super+Q close, Super+Up maximise,
Super+Tab restore a minimised window, Super+drag move/resize.
Menu > Power for log out, restart and shut down.

Your old desktop stays installed, so you can always pick it instead.
The installer backs up any picom, alacritty or fastfetch config you had.

## Uninstall
    sudo rm /usr/share/xsessions/thumbdeuck.desktop
    sudo rm /usr/local/bin/thumbdeuck-session
