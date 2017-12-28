let
  nixpkgs = ((import <nixpkgs> {}).fetchFromGitHub { 
    owner = "NixOS";
    repo = "nixpkgs-channels";
    rev = "ade98dc442ea78e9783d5e26954e64ec4a1b2c94";
    sha256 = "1ymyzrsv86mpmiik9vbs60c1acyigwnvl1sx5sd282gndzwcjiyr";
  });
in
with import nixpkgs { };
let
  python2_dbg = callPackage ./python2_dbg.nix {};
  gdb_dbg = (gdb.overrideAttrs (oldAttrs : rec {
    dontStrip = true;
    hardeningDisable = ["all"];

    preConfigure = ''
      export CXXFLAGS="-g3 -O0 -fdebug-prefix-map=$(pwd)=$out/src"
      export CFLAGS=$CXXFLAGS
    '' + (if builtins.hasAttr "preConfigure" oldAttrs then oldAttrs.preConfigure else "");

    postUnpack = ''
      mkdir -p /tmp/tmpsrc
      cp -r ./$name/* /tmp/tmpsrc/
    '' + (if builtins.hasAttr "postUnpack" oldAttrs then oldAttrs.postUnpack else "");

    postInstall = ''
      mkdir -p $out/src
      cp -r /tmp/tmpsrc/* $out/src/
      rm -rf /tmp/tmpsrc
    '' + (if builtins.hasAttr "postInstall" oldAttrs then oldAttrs.postInstall else "");

  })).override {python = python2_dbg;};
in
  stdenv.mkDerivation {
    hardeningDisable = ["all"];
    name = "mcgdb-env";
    buildInputs = [
      python2_dbg
      gcc
      automake
      autoconf
      gettext
      pkgconfig
      glib
      jansson
      slang
      xterm
      git
      valgrind
      (callPackage ./pysigset.nix {})
      gdb_dbg

      #packages for testing
      (callPackage ./pyte.nix {})
      pythonPackages.termcolor
      pythonPackages.pexpect
    ];
    shellHook = ''
    export PS1='\e[?2004l\[\033[1;32m\][nix-shell:\W]$\[\033[0m\] ' 
    alias grep="grep --color"
    '';
  }