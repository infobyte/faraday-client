"""
Faraday Penetration Test IDE
Copyright (C) 2013  Infobyte LLC (http://www.infobytesec.com/)
See the file 'doc/LICENSE' for the license information

"""
from __future__ import absolute_import

import os
import re
import sys
import traceback
import logging

from importlib.machinery import SourceFileLoader

from faraday_plugins.plugins.manager import PluginsManager, CommandAnalyzer

from faraday_client.config.configuration import getInstanceConfiguration

CONF = getInstanceConfiguration()

logger = logging.getLogger(__name__)

class PluginManager:

    def __init__(self, plugin_repo_path, pending_actions=None):
        self._controllers = {}
        self._plugin_modules = {}
        self._plugin_instances = {}
        self._plugin_settings = {}
        self.pending_actions = pending_actions
        self._plugins_manager = PluginsManager()
        self.commands_analyzer = CommandAnalyzer(self._plugins_manager)
        self._loadSettings()

    def addController(self, controller, id):
        self._controllers[id] = controller

    def _loadSettings(self):
        _plugin_settings = CONF.getPluginSettings()
        if _plugin_settings:
            self._plugin_settings = _plugin_settings

        activep = self.plugins()
        for plugin_id, plugin in activep:
            if plugin_id in _plugin_settings:
                plugin.updateSettings(_plugin_settings[plugin_id]["settings"])
            self._plugin_settings[plugin_id] = {
                "name": plugin.name,
                "description": plugin.description,
                "version": plugin.version,
                "plugin_version": plugin.plugin_version,
                "settings": dict(plugin.getSettings())
                }

        dplugins = []
        for k, v in self._plugin_settings.items():
            if k not in activep:
                dplugins.append(k)

        for d in dplugins:
            del self._plugin_settings[d]

        CONF.setPluginSettings(self._plugin_settings)
        CONF.saveConfig()

    def getSettings(self):
        return self._plugin_settings

    def updateSettings(self, settings):
        self._plugin_settings = settings
        CONF.setPluginSettings(settings)
        CONF.saveConfig()
        for plugin_id, params in settings.items():
            new_settings = params["settings"]
            for c_id, c_instance in self._controllers.items():
                c_instance.updatePluginSettings(plugin_id, new_settings)

    def plugins(self):
        plugins = self._plugins_manager.get_plugins()
        for plugin_id, plugin in plugins:
            if plugin_id in self._plugin_settings:
                plugin.updateSettings(self._plugin_settings[plugin_id]["settings"])
        return plugins
