"""
Faraday Penetration Test IDE
Copyright (C) 2013  Infobyte LLC (http://www.infobytesec.com/)
See the file 'doc/LICENSE' for the license information
"""
from faraday_client.plugins import core
from faraday_client.model import api
import re
import os

current_path = os.path.abspath(os.getcwd())

__author__ = "Francisco Amato"
__copyright__ = "Copyright (c) 2013, Infobyte LLC"
__credits__ = ["Francisco Amato"]
__version__ = "1.0.0"
__maintainer__ = "Francisco Amato"
__email__ = "famato@infobytesec.com"
__status__ = "Development"


class ListurlsParser:
    """
    The objective of this class is to parse an xml file generated by the listurls tool.

    TODO: Handle errors.
    TODO: Test listurls output version. Handle what happens if the parser doesn't support it.
    TODO: Test cases.

    @param listurls_filepath A proper simple report generated by listurls
    """

    def __init__(self, output):

        lists = output.split("\r\n")
        i = 0
        self.items = []

        if re.search("Could not reach", output) is not None:
            self.fail = True
            return

        for line in lists:
            if i > 8:
                print(line)
                item = {'link': line}
                self.items.append(item)
            i = i + 1


class ListurlsPlugin(core.PluginBase):
    """
    Example plugin to parse listurls output.
    """

    def __init__(self):
        super().__init__()
        self.id = "Listurls"
        self.name = "Listurls XML Output Plugin"
        self.plugin_version = "0.0.1"
        self.version = "6.3"
        self.options = None
        self._current_output = None
        self._current_path = None
        self._command_regex = re.compile(
            r'^(sudo list-urls\.py|list-urls\.py|perl list-urls\.py|\.\/list-urls\.py).*?')
        self.host = None
        self.port = None
        self.protocol = None
        self.fail = None
        self._completition = {
            "": "./list-urls.py <web-page>"}

        global current_path
        self.output_file_path = os.path.join(self.data_path,
                                             "listurls_output-%s.txt" % self._rid)

    def canParseCommandString(self, current_input):
        if self._command_regex.match(current_input.strip()):
            return True
        else:
            return False

    def parseOutputString(self, output, debug=False):
        return

    def processCommandString(self, username, current_path, command_string):

        host = re.search(
            "(http|https|ftp)\://([a-zA-Z0-9\.\-]+(\:[a-zA-Z0-9\.&amp;%\$\-]+)*@)*((25[0-5]|2[0-4][0-9]|[0-1]{1}[0-9]{2}|[1-9]{1}[0-9]{1}|[1-9])\.(25[0-5]|2[0-4][0-9]|[0-1]{1}[0-9]{2}|[1-9]{1}[0-9]{1}|[1-9]|0)\.(25[0-5]|2[0-4][0-9]|[0-1]{1}[0-9]{2}|[1-9]{1}[0-9]{1}|[1-9]|0)\.(25[0-5]|2[0-4][0-9]|[0-1]{1}[0-9]{2}|[1-9]{1}[0-9]{1}|[0-9])|localhost|([a-zA-Z0-9\-]+\.)*[a-zA-Z0-9\-]+\.(com|edu|gov|int|mil|net|org|biz|arpa|info|name|pro|aero|coop|museum|[a-zA-Z]{2}))[\:]*([0-9]+)*([/]*($|[a-zA-Z0-9\.\,\?\'\\\+&amp;%\$#\=~_\-]+)).*?$",
            command_string)

        self.protocol = host.group(1)
        self.host = host.group(4)
        if self.protocol == 'https':
            self.port = 443
        if host.group(11) is not None:
            self.port = host.group(11)

    def setHost(self):
        pass


def createPlugin():
    return ListurlsPlugin()


# I'm Py3
