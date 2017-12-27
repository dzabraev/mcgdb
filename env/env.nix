with import <nixpkgs> { };
let
  python2_dbg = python.overrideAttrs (oldAttrs : rec {
    dontStrip = true;
    separateDebugInfo = false;

#    preConfigure = ''
#      export CFLAGS="$EXTRA_CFLAGS -g3 -O0 -fdebug-prefix-map=$(pwd)=$out/src"
#    '' + oldAttrs.preConfigure;

    NIX_CFLAGS_COMPILE="-g3 -O0";
    preConfigure = ''
      export CFLAGS="$CFLAGS -g3 -O0"
      export EXTRA_CFLAGS="-g3 -O0 "
      export CXXFLAGS=$CFLAGS
    '' + oldAttrs.preConfigure;


#    postUnpack = ''
#      mkdir -p $out/src1
#      cp -r ./Python-$version/* $out/src/
#    '';

    configureFlags = oldAttrs.configureFlags ++ [
      "EXTRA_CFLAGS='-DPy_DEBUG'"
      "--with-pydebug"
    ];
  });
  my_python2_dbg = stdenv.mkDerivation {
    src = python.src;
    name = python.name;
    preConfigure = ''
      export CFLAGS="$CFLAGS -g3 -O0"
    '';
    dontStrip = true;
    separateDebugInfo = false;
    configureFlags = [
      "--with-pydebug"
    ];
    buildInputs = python.buildInputs;
    enableParallelBuilding = true;
  };
  gdb_dbg = (gdb.overrideAttrs (oldAttrs : rec {
    #separateDebugInfo = true;
    dontStrip = true;
    preConfigure = ''
      export CXXFLAGS="-g3 -O0 -fdebug-prefix-map=$(pwd)=$out/src"
      export CFLAGS=$CXXFLAGS
    '';
    postUnpack = ''
      mkdir -p $out/src
      cp -r ./$name/* $out/src/
    '';
  })).override {python = python2_dbg;};
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
      #gdb_dbg
      #python2_dbg
      my_python2_dbg

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

