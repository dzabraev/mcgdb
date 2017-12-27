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
  python2_dbg = python.overrideAttrs (oldAttrs : rec {
    dontStrip = true;
    separateDebugInfo = false;

    postBuild = ''
      #mkdir -p /home/dza/tmp/python-build
      cp -r ./* /home/dza/tmp/python-build
    '';

#    preConfigure = ''
#      export CFLAGS="$EXTRA_CFLAGS -g3 -O0 -fdebug-prefix-map=$(pwd)=$out/src"
#    '' + oldAttrs.preConfigure;

    preConfigure = ''
      export CFLAGS="$CFLAGS -g3 -O0 --save-temps"
      export EXTRA_CFLAGS="-g3 -O0 "
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
    src = fetchurl {
      url = "https://www.python.org/ftp/python/2.7.14/Python-2.7.14.tar.xz";
      sha256 = "0ym44z3nwp8chfi7snmknkqnl2q9bghzv9p923r8w748i5hvyxx8";
    };
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
      gdb
      #gdb_dbg
      
      #my_python2_dbg

      #packages for testing
      (callPackage ./pyte.nix {})
      pythonPackages.termcolor
      pythonPackages.pexpect
    ];
#    propagatedBuildInputs = [
#      python2_dbg
#    ];
    shellHook = ''
    export PS1='\e[?2004l\[\033[1;32m\][nix-shell:\W]$\[\033[0m\] ' 
    alias grep="grep --color"
    '';
  }