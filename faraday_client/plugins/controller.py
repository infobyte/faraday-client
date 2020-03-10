"""
Faraday Penetration Test IDE
Copyright (C) 2013  Infobyte LLC (http://www.infobytesec.com/)
See the file 'doc/LICENSE' for the license information

"""
import json

import requests
from past.builtins import basestring
from builtins import range

import os
import time
import shlex
import logging
from threading import Thread
from multiprocessing import JoinableQueue, Process

from faraday_client.config.configuration import getInstanceConfiguration
from faraday_client.persistence.server.server import _conf, _get_base_server_url
from faraday_client.plugins.plugin import PluginProcess
import faraday_client.model.api
from faraday_client.model.commands_history import CommandRunInformation
from faraday_client.model import Modelactions

from faraday_client.config.constant import (
    CONST_FARADAY_ZSH_OUTPUT_PATH,
)

from faraday_client.start_client import (
    CONST_FARADAY_HOME_PATH,
)

CONF = getInstanceConfiguration()

logger = logging.getLogger(__name__)


class PluginController(Thread):
    """
    TODO: Doc string.
    """
    def __init__(self, id, plugin_manager, mapper_manager, pending_actions, end_event=None):
        super(PluginController, self).__init__(name="PluginControllerThread")
        self.plugin_manager = plugin_manager
        self._plugins = list(plugin_manager.plugins())
        self.id = id
        self._actionDispatcher = None
        self._setupActionDispatcher()
        self._mapper_manager = mapper_manager
        self.output_path = os.path.join(
            os.path.expanduser(CONST_FARADAY_HOME_PATH),
            CONST_FARADAY_ZSH_OUTPUT_PATH)
        self._active_plugins = {}
        self.plugin_sets = {}
        self.plugin_manager.addController(self, self.id)
        self.stop = False
        self.pending_actions = pending_actions
        self.end_event = end_event

    def _find_plugin(self, plugin_id):
        return self._plugins.get(plugin_id, None)

    def _is_command_malformed(self, original_command, modified_command):
        """
        Checks if the command to be executed is safe and it's not in the
        block list defined by the user. Returns False if the modified
        command is ok, True if otherwise.
        """
        block_chars = {"|", "$", "#"}

        if original_command == modified_command:
            return False

        orig_cmd_args = shlex.split(original_command)

        if not isinstance(modified_command, basestring):
            modified_command = ""
        mod_cmd_args = shlex.split(modified_command)

        block_flag = False
        orig_args_len = len(orig_cmd_args)
        for index in range(0, len(mod_cmd_args)):
            if (index < orig_args_len and
                    orig_cmd_args[index] == mod_cmd_args[index]):
                continue

            for char in block_chars:
                if char in mod_cmd_args[index]:
                    block_flag = True
                    break

        return block_flag

    def _get_plugins_by_input(self, cmd, plugin_set):
        for plugin_id, plugin in plugin_set:
            if isinstance(cmd, bytes):
                cmd = cmd.decode()
            if plugin.canParseCommandString(cmd):
                return plugin
        return None

    def getAvailablePlugins(self):
        """
        Return a dictionary with the available plugins.
        Plugin ID's as keys and plugin instences as values
        """
        return self._plugins

    def stop(self):
        self.plugin_process.stop()
        self.stop = True

    def processOutput(self, plugin, output, command, isReport=False):
        """
            Process the output of the plugin. This will start the PluginProcess
            and also PluginCommiter (thread) that will informa to faraday server
            when the command finished.

        :param plugin: Plugin to execute
        :param output: read output from plugin or term
        :param command_id: command id that started the plugin
        :param isReport: Report or output from shell
        :return: None
        """
        plugin.processOutput(output.decode('utf8'))
        base_url = _get_base_server_url()
        cookies = _conf().getDBSessionCookies()
        command.duration = time.time() - command.itime
        plugin_result = plugin.get_json()
        self.send_data(command.workspace, plugin_result)
        command_id = command.getID()
        data = command.toDict()
        data['tool'] = data['command']
        data.pop('id_available')
        res = requests.put(
            f'{base_url}/_api/v2/ws/{command.workspace}/commands/{command_id}/',
            json=data,
            cookies=cookies)
        logger.info('Sent command duration {res.status_code}')

    def send_data(self, workspace, data):
        cookies = _conf().getDBSessionCookies()
        base_url = _get_base_server_url()
        res = requests.post(
            f'{base_url}/_api/v2/ws/{workspace}/bulk_create/',
            cookies=cookies,
            json=json.loads(data))
        if res.status_code != 201:
            logger.error('Server responded with status code {0}. API response was {1}'.format(res.status_code, res.text))
            return False
        return True

    def _processAction(self, action, parameters):
        """
        decodes and performs the action given
        It works kind of a dispatcher
        """
        logger.debug("_processAction - %s - parameters = %s", action, parameters)
        self._actionDispatcher[action](*parameters)

    def _setupActionDispatcher(self):
        self._actionDispatcher = {
            Modelactions.ADDHOST: faraday_client.model.api.addHost,
            Modelactions.ADDSERVICEHOST: faraday_client.model.api.addServiceToHost,
            #Vulnerability
            Modelactions.ADDVULNHOST: faraday_client.model.api.addVulnToHost,
            Modelactions.ADDVULNSRV: faraday_client.model.api.addVulnToService,
            #VulnWeb
            Modelactions.ADDVULNWEBSRV: faraday_client.model.api.addVulnWebToService,
            #Note
            Modelactions.ADDNOTEHOST: faraday_client.model.api.addNoteToHost,
            Modelactions.ADDNOTESRV: faraday_client.model.api.addNoteToService,
            Modelactions.ADDNOTENOTE: faraday_client.model.api.addNoteToNote,
            #Creds
            Modelactions.ADDCREDSRV:  faraday_client.model.api.addCredToService,
            #LOG
            Modelactions.LOG: faraday_client.model.api.log,
            Modelactions.DEVLOG: faraday_client.model.api.devlog,
            # Plugin state
            Modelactions.PLUGINSTART: faraday_client.model.api.pluginStart,
            Modelactions.PLUGINEND: faraday_client.model.api.pluginEnd
        }

    def updatePluginSettings(self, plugin_id, new_settings):
        for plugin_set in self.plugin_sets.values():
            if plugin_id in plugin_set:
                plugin_set[plugin_id].updateSettings(new_settings)
        if plugin_id in self._plugins:
            self._plugins[plugin_id].updateSettings(new_settings)

    def createPluginSet(self, pid):
        self.plugin_sets[pid] = [plugin for plugin in self.plugin_manager.plugins()]

    def processCommandInput(self, pid, cmd, pwd):
        """
        This method tries to find a plugin to parse the command sent
        by the terminal (identiefied by the process id).
        """
        if pid not in self.plugin_sets:
            self.createPluginSet(pid)

        plugin = self._get_plugins_by_input(cmd, self.plugin_sets[pid])

        if plugin:
            plugin.data_path = CONF.getDataPath()
            modified_cmd_string = plugin.processCommandString("", pwd, cmd)
            if not self._is_command_malformed(cmd, modified_cmd_string):

                cmd_info = CommandRunInformation(
                    **{'workspace': faraday_client.model.api.getActiveWorkspace().name,
                        'itime': time.time(),
                        'import_source': 'shell',
                        'command': cmd.split()[0],
                        'params': ' '.join(cmd.split()[1:])})
                cmd_info.setID(self._mapper_manager.save(cmd_info))

                self._active_plugins[pid] = plugin, cmd_info

                return plugin.id, modified_cmd_string

        return None, None

    def onCommandFinished(self, pid, exit_code, term_output):
        if pid not in list(self._active_plugins.keys()):
            return False
        if exit_code != 0:
            del self._active_plugins[pid]
            return False

        plugin, cmd_info = self._active_plugins.get(pid)

        cmd_info.duration = time.time() - cmd_info.itime
        self._mapper_manager.update(cmd_info)

        self.processOutput(plugin, term_output, cmd_info)
        del self._active_plugins[pid]
        return True

    def processReport(self, plugin_id, filepath, ws_name=None):
        if plugin_id not in [plugin[0] for plugin in self._plugins]:
            logger.warning("Unknown Plugin ID: %s", plugin_id)
            return False
        if not ws_name:
            ws_name = faraday_client.model.api.getActiveWorkspace().name

        cmd_info = CommandRunInformation(
            **{'workspace': ws_name,
               'itime': time.time(),
               'import_source': 'report',
               'command': plugin_id,
               'params': filepath,
            })

        self._mapper_manager.createMappers(ws_name)
        command_id = self._mapper_manager.save(cmd_info)
        cmd_info.setID(command_id)

        if plugin_id in [plugin[0] for plugin in self._plugins]:
            logger.info('Processing report with plugin {0}'.format(plugin_id))
            with open(filepath, 'rb') as output:
                plugin = [plugin[1] for plugin in self._plugins if plugin[0] == plugin_id].pop()
                self.processOutput(plugin, output.read(), cmd_info, True)
            return command_id

        # Plugin to process this report not found, update duration of plugin process
        cmd_info.duration = time.time() - cmd_info.itime
        self._mapper_manager.update(cmd_info)
        return False

    def clearActivePlugins(self):
        self._active_plugins = {}
