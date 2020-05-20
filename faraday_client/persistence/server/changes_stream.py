#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""
Faraday Penetration Test IDE
Copyright (C) 2016  Infobyte LLC (http://www.infobytesec.com/)
See the file 'doc/LICENSE' for the license information

"""
from __future__ import absolute_import
from __future__ import print_function

import os

from past.builtins import basestring

import json
import logging
import threading
from queue import Queue, Empty
import requests
import websocket
import ssl
from urllib.parse import urlparse

from faraday_client.persistence.server.server_io_exceptions import (
    ChangesStreamStoppedAbruptly
)
logger = logging.getLogger(__name__)


class ChangesStream:

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        return False

    def __next__(self):
        return self

    def __iter__(self):
        raise NotImplementedError('Abstract class')

    def _get_object_type_and_name_from_change(self, change):
        try:
            id = change['id']
            response = requests.get("{0}/{1}".format(self._base_url, id), **self._params)
            object_json = response.json()
        except Exception:
            return None, None
        return object_json.get('type'), object_json.get('name')

    def _sanitize(self, raw_line):
        if not isinstance(raw_line, basestring):
            return None
        line = raw_line.strip()
        if not line or line in ('{"results":', '],'):
            return None
        if line.startswith('"last_seq"'):
            line = '{' + line
        if line.endswith(","):
            line = line[:-1]
        return line

    def _parse_change(self, line):
        try:
            obj = json.loads(line)
            return obj
        except ValueError:
            return None

    def stop(self):
        if self._response is not None:
            self._response.close()
            self._response = None
        self._stop = True


class WebsocketsChangesStream(ChangesStream):

    def __init__(self, workspace_name, server_url, **params):
        server_url_info = urlparse(server_url)
        self.changes_queue = Queue()
        self.workspace_name = workspace_name
        self._response = None
        ws_port = 9000
        self._base_url = server_url_info.hostname
        ws_kwargs = {'ping_interval': 30}
        if server_url_info.scheme == "https":
            if server_url_info.port:
                # Using HTTPS but not for standard 443 port
                websockets_url = f"wss://{server_url_info.hostname}:{server_url_info.port}/websockets"
                test_ws_url = f"https://{server_url_info.hostname}:{server_url_info.port}/websockets"
            else:
                websockets_url = f"wss://{server_url_info.hostname}/websockets"
                test_ws_url = f"https://{server_url_info.hostname}/websockets"
            try:
                ws_response = requests.get(test_ws_url)
                if ws_response.status_code == 404:
                    # Using HTTPS but not for websockets
                    websockets_url = f"ws://{server_url_info.hostname}:{ws_port}/"
                else:
                    cert_path = os.environ.get("REQUESTS_CA_BUNDLE", None)
                    if cert_path:
                        ws_kwargs["sslopt"] = {"ca_certs": cert_path}
                        logger.info("Using self signed certificate for WSS")
            except requests.exceptions.ConnectionError:
                logger.warning("Faraday server is over https but websockets are not")
                websockets_url = f"ws://{server_url_info.hostname}:{ws_port}/"
        else:
            websockets_url = f"ws://{server_url_info.hostname}:{ws_port}/"
        logger.info('Connecting to websocket url %s', websockets_url)
        self.ws = websocket.WebSocketApp(
                websockets_url,
                on_message=self.on_message,
                on_error=self.on_error,
                on_open=self.on_open,
                on_close=self.on_close
        )
        # ws.run_forever will call on_message, on_error, on_close and on_open
        # see websocket client python docs on:
        # https://github.com/websocket-client/websocket-client
        thread = threading.Thread(target=self.ws.run_forever, args=(), kwargs=ws_kwargs, name='WebsocketsChangesStream')
        thread.daemon = True
        thread.start()

    def stop(self):
        self.ws.close()
        super(WebsocketsChangesStream, self).stop()

    def on_open(self):
        from faraday_client.persistence.server.server import _create_server_api_url, _post  # pylint:disable=import-outside-toplevel

        response = _post(
            _create_server_api_url() +
            '/ws/{}/websocket_token/'.format(self.workspace_name),
            expected_response=200)
        token = response['token']
        self.ws.send(json.dumps({
            'action': 'JOIN_WORKSPACE',
            'workspace': self.workspace_name,
            'token': token,
        }))

    def on_message(self, message):
        logger.debug('New message {0}'.format(message))
        self.changes_queue.put(message)

    def on_error(ws, error):
        logger.error('Websocket connection error: {0}'.format(error))

    def on_close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        return False

    def __next__(self):
        return self

    def __iter__(self):
        try:
            data = json.loads(self.changes_queue.get_nowait())
        except Empty:
            return
        yield data

    def _get_object_type_and_name_from_change(self, change):
        try:
            id = change['id']
            response = requests.get("{0}/{1}".format(self._base_url, id), **self._params)
            object_json = response.json()
        except Exception:
            return None, None
        return object_json.get('type'), object_json.get('name')
