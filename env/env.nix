with import <nixpkgs> { };
  stdenv.mkDerivation {
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
      gdb
      xterm

      #packages for testing
      (callPackage ./pyte.nix {})
      pythonPackages.termcolor
      pythonPackages.pexpect
    ];
  }
