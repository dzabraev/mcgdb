with import <nixpkgs> { };
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
      gdb
      xterm
      git
      valgrind

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

