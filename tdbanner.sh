#!/bin/sh
figlet -f slant ThumbDEuck 1._ | awk '
BEGIN { split("0;229;255 47;123;255 224;64;255 255;46;77 255;212;0 24;255;128", c, " ") }
{ i = (NR - 1) % 6 + 1
  printf "\033[1;38;2;%sm%s\033[0m\n", c[i], $0 }'
fastfetch
