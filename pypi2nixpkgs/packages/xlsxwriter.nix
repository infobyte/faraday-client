
    { fetchPypi, lib, buildPythonPackage }:
    buildPythonPackage rec {
        pname = "xlsxwriter";
        version = "1.2.8";

            src = builtins.fetchurl {
                url = "https://files.pythonhosted.org/packages/6a/50/77a5d3377e0b5caff56609a9075160f57951015c274e6ba891e5ad96f61f/XlsxWriter-1.2.8.tar.gz";
                sha256 = "0sv553dj5h3qxbn8xfaqxr3bx2lglp85cxlcsnf3mzqnmf41k3j8";
            };
        

        # TODO FIXME
        doCheck = false;

        buildInputs = [];
        propagatedBuildInputs = [];
    }
    