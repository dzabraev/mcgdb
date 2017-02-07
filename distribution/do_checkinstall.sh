#!/bin/bash

echo 'Front-end for gdb based on mcedit'

checkinstall \
  --maintainer="Maxim Dzabraev \\<dzabraew@gmail.com\\>" \
  --pkgversion="1.2" \
  --pkgname=mcgdb \
  --requires="e2fslibs \(\>= 1.37\), libc6 \(\>= 2.15\), \
libglib2.0-0 \(\>= 2.35.9\), libgpm2 \(\>= 1.20.4\), \
libslang2 \(\>= 2.2.4\),  libjansson \(\>= 2.9\)"