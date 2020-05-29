{ beautifulsoup4, buildPythonPackage, click, dateutil, fetchPypi, html2text, lib
, lxml, pytz, requests, simplejson, colorama }:
buildPythonPackage rec {
  pname = "faraday-plugins";
  version = "1.1";

  # If this path doesn't exist, the build will fail. This is a
  # workaround until a new version of faraday-plugins is released
  src = builtins.fetchGit ~/faraday/plugins;

  # TODO FIXME
  doCheck = false;

  buildInputs = [ ];
  propagatedBuildInputs =
    [ click simplejson requests lxml html2text beautifulsoup4 pytz dateutil colorama ];
}
