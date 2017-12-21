{ stdenv, fetchFromGitHub, pkgconfig, glib, gpm, file, e2fsprogs,
  libX11, libICE, perl, zip, unzip, gettext, slang, gdb, jansson }:

  stdenv.mkDerivation rec {
    name = "mcgdb-${version}";
    version = "1.4";

    src = fetchFromGitHub {
      repo = "mcgdb";
      owner = "dzabraev";
      rev = "b658752fbd8aa67e7e1b8600a49f831cb3efd1b5";
      sha256 = "0ybn11bbcpn4crh39xk3h95rq6nbjf46qsnfrwxzjnnh8bq1krcy";
    };

    nativeBuildInputs = [ pkgconfig ];
    buildInputs = [ gdb jansson perl glib slang zip unzip file gettext libX11 libICE
      ] ++ stdenv.lib.optionals (!stdenv.isDarwin) [ e2fsprogs gpm ];

  }