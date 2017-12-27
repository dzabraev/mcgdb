{pythonPackages , fetchurl}:

pythonPackages.buildPythonPackage ( rec {
    version = "0.3.2";
    name = "pysigset-${version}";

    src = fetchurl {
      url = "https://pypi.python.org/packages/9f/ce/789466fea28561b0a38f233b74f84701407872a8c636c40f9f3a8bb4debe/pysigset-0.3.2.tar.gz";
      sha256 = "0ym44z3nwp8chfi7snmknkqnl2q9bghzv9p923r8w748i5hvyxx8";
    };
})