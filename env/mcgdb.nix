let
  pysigset = {pythonPackages , fetchurl}:
    pythonPackages.buildPythonPackage ( rec {
      version = "0.3.2";
      name = "pysigset-${version}";

      src = fetchurl {
        url = "https://pypi.python.org/packages/9f/ce/789466fea28561b0a38f233b74f84701407872a8c636c40f9f3a8bb4debe/pysigset-0.3.2.tar.gz";
        sha256 = "0ym44z3nwp8chfi7snmknkqnl2q9bghzv9p923r8w748i5hvyxx8";
      };
    });
  mcgdb = { stdenv, fetchFromGitHub, pkgconfig, glib, gpm, file, e2fsprogs,
    libX11, libICE, perl, zip, unzip, gettext, slang, gdb, jansson, pythonPackages, 
    fetchurl, pysigset, makeWrapper}:
      stdenv.mkDerivation rec {
      name = "mcgdb-${version}";
      version = "1.4";

      src = fetchFromGitHub {
        repo = "mcgdb";
        owner = "dzabraev";
        rev = "7c71f9562aacd8c3e2fc7765644ece0137c14dc6";
        sha256 = "1qam2nja7gqdly550ls6rjxp8prxgc103anrn6xlnijrwyjf2w82";
      };

      nativeBuildInputs = [ pkgconfig makeWrapper];
      propagatedBuildInputs = [ gdb jansson perl glib slang zip unzip file gettext libX11 libICE
      ] ++ stdenv.lib.optionals (!stdenv.isDarwin) [ e2fsprogs gpm ] ++ [
        pysigset
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

  nixpkgs = ((import <nixpkgs> {}).fetchFromGitHub { 
    owner = "NixOS";
    repo = "nixpkgs-channels";
    rev = "ade98dc442ea78e9783d5e26954e64ec4a1b2c94";
    sha256 = "1ymyzrsv86mpmiik9vbs60c1acyigwnvl1sx5sd282gndzwcjiyr";
  });
in with (import nixpkgs {});
  let
    mcgdb_drv = callPackage mcgdb {
      pysigset = callPackage pysigset {};
    };

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
