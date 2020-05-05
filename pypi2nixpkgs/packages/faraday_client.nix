
    { fetchPypi, ipy, websocket_client, pygobject, pycairo, xlsxwriter, mockito, lib, future, html2text, flask, colorama, whoosh, pynacl, dateutil, cairocffi, lxml, autobahn, tornado, flask-restless, buildPythonPackage, deprecation, requests, tqdm }:
    buildPythonPackage rec {
        pname = "faraday_client";
        version = "0.1dev";

            src = lib.cleanSource ../..;
        

        # TODO FIXME
        doCheck = false;

        buildInputs = [];
        propagatedBuildInputs = [websocket_client autobahn colorama deprecation pynacl dateutil flask ipy mockito requests tornado tqdm whoosh cairocffi pycairo pygobject flask-restless lxml html2text future xlsxwriter];
    }
    