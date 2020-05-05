
    { fetchPypi, lib, buildPythonPackage }:
    buildPythonPackage rec {
        pname = "future";
        version = "0.18.2";

            src = builtins.fetchurl {
                url = "https://files.pythonhosted.org/packages/45/0b/38b06fd9b92dc2b68d58b75f900e97884c45bedd2ff83203d933cf5851c9/future-0.18.2.tar.gz";
                sha256 = "0zakvfj87gy6mn1nba06sdha63rn4njm7bhh0wzyrxhcny8avgmi";
            };
        

        # TODO FIXME
        doCheck = false;

        buildInputs = [];
        propagatedBuildInputs = [];
    }
    