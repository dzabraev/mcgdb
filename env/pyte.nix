{pythonPackages , fetchFromGitHub}:

pythonPackages.buildPythonPackage ( rec {
    version = "0.7.0";
    name = "pyte-${version}";

    src = fetchFromGitHub {
      repo = "pyte";
      owner = "selectel";
      rev = "358dea5b9ea11eeab6c6ed8fb73c220550e17e26";
      sha256 = "0ybn11bbcpn4crh39xk3h95rq6nbjf46qsnfrwxzjnnh8bq1krcy";
    };

    buildInputs =  [ pythonPackages.pytestrunner ];
    propagatedBuildInputs = [ pythonPackages.wcwidth ];
})