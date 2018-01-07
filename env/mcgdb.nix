let
  nixpkgs = ((import <nixpkgs> {}).fetchFromGitHub {
    owner = "NixOS";
    repo = "nixpkgs";
    rev = "27459e20209ec7e834b7b1bca5dca4cc5012e162";
    sha256 = "0xrh94zynp4zflb82bm2j4ymw9f738y1qgdlxl0nplqp64k1sd2f";
  });

  mcgdb = { stdenv, fetchFromGitHub, pkgconfig, glib, gpm, file, e2fsprogs,
    libX11, libICE, perl, zip, unzip, gettext, slang, gdb, jansson, pythonPackages, 
    fetchurl, makeWrapper, xterm }:
      stdenv.mkDerivation rec {
      name = "mcgdb-${version}";
      version = "1.4";

      src = fetchFromGitHub {
        repo = "mcgdb";
        owner = "dzabraev";
        rev = "7d7a3b5324ebc0ee59e3851eac7f7df0d6d1299c";
        sha256 = "0f4cv1di3gvfi814a06w7dg4p8i5jfnbclf347hq8nf5wcj7x4zi";
      };

      nativeBuildInputs = [ pkgconfig makeWrapper];
      propagatedBuildInputs = [ gdb jansson perl glib slang zip unzip file gettext libX11 libICE
      ] ++ stdenv.lib.optionals (!stdenv.isDarwin) [ e2fsprogs gpm ] ++ [
        pythonPackages.pysigset xterm
      ];

      preConfigure = ''
        mkdir build && cd build
      '';

      configureScript="../configure";

      postInstall = ''
        mv $out/bin/mcgdb $out/bin/mcgdb_unwrapped
        makeWrapper $out/bin/mcgdb_unwrapped $out/bin/mcgdb --prefix PYTHONPATH : "$PYTHONPATH" --set GDB ${gdb}/bin/gdb
      '';
  };
in with (import nixpkgs {});
  let
    mcgdb_drv = callPackage mcgdb {};

    mips64_gdb = gdb.overrideAttrs (oldAttrs: rec {
      configureFlags = oldAttrs.configureFlags ++ [
        "--target=mips64"
        "--program-prefix=mips64-"
      ];
    });

    mips64_mcgdb = {stdenv, mcgdb, mips64_gdb, makeWrapper} :
      stdenv.mkDerivation rec {
        name = "mips64-"+mcgdb.name;

        buildPhase = "true";
        unpackPhase = "true";

        nativeBuildInputs = [
          makeWrapper
        ];

        installPhase=''
          mkdir -p $out/bin
          makeWrapper ${mcgdb}/bin/mcgdb_unwrapped $out/bin/mips64-mcgdb --set GDB ${mips64_gdb}/bin/mips64-gdb --prefix PYTHONPATH : "$PYTHONPATH"
        '';

        propagatedBuildInputs = [
          mcgdb mips64_gdb
        ];
      };

    mips64_mcgdb_drv = callPackage mips64_mcgdb {mcgdb = mcgdb_drv; inherit mips64_gdb;};
  in
    {
      mcgdb = mcgdb_drv;
      mips64_mcgdb = mips64_mcgdb_drv;
    }
