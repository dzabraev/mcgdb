{pythonPackages , fetchFromGitHub}:

pythonPackages.buildPythonPackage ( rec {
    version = "0.7.0";
    name = "pyte-${version}";

    src = fetchFromGitHub {
      repo = "pyte";
      owner = "selectel";
      rev = "3389949426236022f6bc9fc9e741673b2feba627";
      sha256 = "0k9n8a1dlmjdiag538bcl2hb2yqn78adrg5kx36dwbm9x4x620xh";
    };

    buildInputs =  [ pythonPackages.pytestrunner ];
    propagatedBuildInputs = [ pythonPackages.wcwidth ];
})