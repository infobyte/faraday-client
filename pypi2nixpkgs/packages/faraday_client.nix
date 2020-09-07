{ autobahn, buildPythonPackage, cairocffi, colorama, dateutil, deprecation
, faraday-plugins, fetchPypi, flask, flask-restless, future, html2text, ipy, lib
, lxml, mockito, pycairo, pygobject, pynacl, requests, tornado, tqdm
, websocket_client, whoosh, xlsxwriter }:
buildPythonPackage rec {
  pname = "faraday_client";
  version = "0.1dev";

  src = lib.cleanSource ../..;

  # TODO FIXME
  doCheck = false;

  buildInputs = [ ];
  propagatedBuildInputs = [
    websocket_client
    autobahn
    colorama
    deprecation
    pynacl
    dateutil
    flask
    ipy
    mockito
    requests
    tornado
    tqdm
    whoosh
    cairocffi
    pygobject
    flask-restless
    lxml
    html2text
    future
    xlsxwriter
    pycairo
    future
    faraday-plugins
  ];

  meta = {
    description = "Faraday GTK Client";
    homepage = "https://github.com/infobyte/faraday_client";
  };
}
