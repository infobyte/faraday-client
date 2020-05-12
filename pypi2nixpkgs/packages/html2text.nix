
    { fetchPypi, lib, buildPythonPackage }:
    buildPythonPackage rec {
        pname = "html2text";
        version = "2020.1.16";

            src = builtins.fetchurl {
                url = "https://files.pythonhosted.org/packages/6c/f9/033a17d8ea8181aee41f20c74c3b20f1ccbefbbc3f7cd24e3692de99fb25/html2text-2020.1.16.tar.gz";
                sha256 = "1fvv4z6dblii2wk1x82981ag8yhxbim1v2ksgywxsndh2s7335p2";
            };
        

        # TODO FIXME
        doCheck = false;

        buildInputs = [];
        propagatedBuildInputs = [];
    }
    