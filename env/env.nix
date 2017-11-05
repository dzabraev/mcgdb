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
    shellHook = '' export PS1='\[\033[1;32m\][nix-shell:\w]$\[\033[0m\] ' '';
  }

