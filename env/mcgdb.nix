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
    libX11, libICE, perl, zip, unzip, gettext, slang, gdb, jansson, pythonPackages, fetchurl, callPackage}:
      stdenv.mkDerivation rec {
      name = "mcgdb-${version}";
      version = "1.4";

      src = fetchFromGitHub {
        repo = "mcgdb";
        owner = "dzabraev";
        rev = "222d5c11521e4bf9621153051b5283f9273884be";
        sha256 = "0285iwi5zkc1763gd63b6xldjjp6w0w7hqzy86w0rq5fcng5a9as";
      };

      nativeBuildInputs = [ pkgconfig ];
      buildInputs = [ gdb jansson perl glib slang zip unzip file gettext libX11 libICE
      ] ++ stdenv.lib.optionals (!stdenv.isDarwin) [ e2fsprogs gpm ] ++ [
        (callPackage pysigset {})
      ];

      preConfigure = ''
        mkdir build && cd build
      '';
      configureScript="../configure";
  };
  nixpkgs = ((import <nixpkgs> {}).fetchFromGitHub { 
    owner = "NixOS";
    repo = "nixpkgs-channels";
    rev = "ade98dc442ea78e9783d5e26954e64ec4a1b2c94";
    sha256 = "1ymyzrsv86mpmiik9vbs60c1acyigwnvl1sx5sd282gndzwcjiyr";
  });
in with (import nixpkgs {});
  let
    mcgdb_drv = callPackage mcgdb {};
    mips64_gdb = gdb.overrideAttrs (oldAttrs: rec {
      configureFlags = oldAttrs.configureFlags ++ ["--target=mips64"];
    });

    mips64_mcgdb_drv = (callPackage mcgdb { gdb=mips64_gdb; }).overrideAttrs (oldAttrs: {
      configureFlags = ({configureFlags=[];} // oldAttrs).configureFlags ++ ["--program-prefix=mips64"];
      name = "mips64-"+oldAttrs.name;
      postInstall = ''
        mv $out/bin/mcgdb $out/bin/mips64-mcgdb
        mv $out/bin/mcgdb_mc $out/bin/mips64-mcgdb_mc
      '';
    });

#    mips64_mcgdb = {stdenv, mcgdb, mips64_gdb} :
#      stdenv.mkDerivation rec {
#        name = "mips64-"+mcgdb.name;
#        dontBuild=true;
#        src=mcgdb.src;
#        configureScript="123";
#        installPhase=''
#          mkdir -p $out/bin
#          echo "GDB=$mips64_gdb $mcgdb" > $out/bin/mips64_mcgdb
#          chmod +x $out/bin/mips64_mcgdb
#        '';
#        buildInputs = [
#          mcgdb mips64_gdb
#        ];
#      };

#    mips64_mcgdb_drv = callPackage mips64_mcgdb {mcgdb = mcgdb_drv; mips64_gdb=gdb;};
  in
    #mcgdb_drv
    mips64_mcgdb_drv
