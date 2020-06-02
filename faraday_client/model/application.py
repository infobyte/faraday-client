"""
Faraday Penetration Test IDE
Copyright (C) 2013  Infobyte LLC (http://www.infobytesec.com/)
See the file 'doc/LICENSE' for the license information

"""
from __future__ import absolute_import
from __future__ import print_function

import os
import sys
import json
import signal
import logging

import faraday_client.apis.rest.api as restapi

from queue import Queue

import faraday_client.model.api
import faraday_client.model.guiapi
import faraday_client.model.log
from faraday_client.config.configuration import getInstanceConfiguration

from faraday_client.plugins.manager import PluginManager
from faraday_client.managers.mapper_manager import MapperManager
from faraday_client.managers.workspace_manager import WorkspaceManager
from faraday_client.model.controller import ModelController
from faraday_client.persistence.server.server import login_user
from faraday_client.plugins.controller import PluginController
from faraday_client.utils.error_report import exception_handler
from faraday_client.utils.error_report import installThreadExcepthook

from faraday_client.gui.gui_app import UiFactory
from faraday_client.model.cli_app import CliApp


CONF = getInstanceConfiguration()
logger = logging.getLogger(__name__)


class MainApplication:

    def __init__(self, args):
        self._original_excepthook = sys.excepthook

        self.args = args

        self._mappers_manager = MapperManager()
        pending_actions = Queue()
        self._model_controller = ModelController(self._mappers_manager, pending_actions)

        self._plugin_manager = PluginManager(
            None,
            pending_actions=pending_actions,
        )

        self._workspace_manager = WorkspaceManager(
            self._mappers_manager)

        # Create a PluginController and send this to UI selected.
        self._plugin_controller = PluginController(
            'PluginController',
            self._plugin_manager,
            self._mappers_manager,
            pending_actions
        )

        if self.args.cli:

            self.app = CliApp(self._workspace_manager, self._plugin_controller)

            CONF.setMergeStrategy("new")

        else:
            self.app = UiFactory.create(self._model_controller,
                                        self._plugin_manager,
                                        self._workspace_manager,
                                        self._plugin_controller,
                                        self.args.gui)


    def on_connection_lost(self):
        """All it does is send a notification to the notification center"""
        faraday_client.model.guiapi.notification_center.DBConnectionProblem()

    def enableExceptHook(self):
        sys.excepthook = exception_handler
        installThreadExcepthook()

    def start(self):
        try:
            signal.signal(signal.SIGINT, self.ctrlC)

            faraday_client.model.api.devlog("Starting application...")
            faraday_client.model.api.devlog("Setting up remote API's...")

            if not self.args.workspace:
                workspace = CONF.getLastWorkspace()
                self.args.workspace = workspace

            faraday_client.model.api.setUpAPIs(
                self._model_controller,
                self._workspace_manager,
                CONF.getApiConInfoHost(),
                CONF.getApiConInfoPort())
            faraday_client.model.guiapi.setUpGUIAPIs(self._model_controller)

            faraday_client.model.api.devlog("Starting model controller daemon...")

            self._model_controller.start()
            faraday_client.model.api.startAPIServer()
            restapi.startAPIs(
                self._plugin_controller,
                self._model_controller,
                CONF.getApiConInfoHost(),
                CONF.getApiRestfulConInfoPort()
            )

            faraday_client.model.api.devlog("Faraday ready...")

            exit_code = self.app.run(self.args)

        except Exception as exception:
            print("There was an error while starting Faraday:")
            print("*" * 3)
            print(exception) # instead of traceback.print_exc()
            print("*" * 3)
            exit_code = -1

        finally:
            return self.__exit(exit_code)

    def __exit(self, exit_code=0):
        """
        Exits the application with the provided code.
        It also waits until all app threads end.
        """
        faraday_client.model.api.log("Closing Faraday...")
        faraday_client.model.api.devlog("stopping model controller thread...")
        faraday_client.model.api.stopAPIServer()
        restapi.stopServer()
        self._model_controller.stop()
        if self._model_controller.isAlive():
            # runs only if thread has started, i.e. self._model_controller.start() is run first
            self._model_controller.join()
        faraday_client.model.api.devlog("Waiting for controller threads to end...")
        return exit_code

    def quit(self):
        """
        Redefined quit handler to nicely end up things
        """
        self.app.quit()

    def ctrlC(self, signal, frame):
        logger.info("Exiting...")
        self.app.quit()


# I'm Py3
