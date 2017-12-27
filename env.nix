{ nixpkgs ? (import ./nixpkgs.nix) }:
with (import nixpkgs {}) ;
  pythonPackages.buildPythonPackage {
    name = "mcgdb";
    propagatedBuildInputs = [
      editdist
    ];
  }