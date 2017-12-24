with import <nixpkgs> { };
let
  gdb_dbg = gdb.overrideAttrs (oldAttrs : rec {
    #separateDebugInfo = true;
    dontStrip = true;
    preConfigure = ''
      export CXXFLAGS='-g3 -O0 -fdebug-prefix-map=..=$out'
      export CFLAGS=$CXXFLAGS
    '';
    postUnpack = ''
      mkdir -p $out/src
      cp -r ./$name/* $out/src/
    '';
  });
in
  stdenv.mkDerivation {
    hardeningDisable = ["all"];
    name = "mcgdb-env";
    buildInputs = [
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
      gdb

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

