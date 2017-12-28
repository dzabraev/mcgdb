{ python }:

python.overrideAttrs (oldAttrs : rec {
  dontStrip = true;
  hardeningDisable = ["all"];

  preConfigure = ''
    export CFLAGS="$CFLAGS -g3 -O0"
    export EXTRA_CFLAGS="-g3 -O0 "
  '' + oldAttrs.preConfigure;

  configureFlags = oldAttrs.configureFlags ++ [
    "EXTRA_CFLAGS='-DPy_DEBUG'"
    "--with-pydebug"
  ];
})
