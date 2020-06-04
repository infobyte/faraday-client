{ buildPythonPackage, fetchPypi, lib }:
buildPythonPackage rec {
  pname = "xlsxwriter";
  version = "1.2.9";

  src = builtins.fetchurl {
    url =
      "https://files.pythonhosted.org/packages/0c/bc/82d6783f83f65f56d8b77d052773c4a2f952fa86385f0cd54e1e006658d7/XlsxWriter-1.2.9.tar.gz";
    sha256 = "0xrfvwwph6sd9rhcdzbqafyqiwqwncas19j635dmy44mzj2k52w2";
  };

  # TODO FIXME
  doCheck = false;

  buildInputs = [ ];
  propagatedBuildInputs = [ ];

  meta = {
    description = "A Python module for creating Excel XLSX files.";
    homepage = "https://github.com/jmcnamara/XlsxWriter";
  };
}
