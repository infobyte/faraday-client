#!/usr/bin/env python
# -*- coding: utf-8 -*-

'''
Faraday Penetration Test IDE
Copyright (C) 2013  Infobyte LLC (http://www.infobytesec.com/)
See the file 'doc/LICENSE' for the license information

'''
from __future__ import absolute_import
from __future__ import print_function
from __future__ import with_statement
from faraday.client.plugins import core
from faraday.client.model import api

try:
    from urlparse import urlsplit
except ImportError:
    from urllib.parse import urlsplit

import socket
import sys
import re
import os

try:
    import xml.etree.cElementTree as ET
    import xml.etree.ElementTree as ET_ORIG
    ETREE_VERSION = ET_ORIG.VERSION
except ImportError:
    import xml.etree.ElementTree as ET
    ETREE_VERSION = ET.VERSION

ETREE_VERSION = [int(i) for i in ETREE_VERSION.split(".")]

current_path = os.path.abspath(os.getcwd())

__author__ = "Francisco Amato"
__copyright__ = "Copyright (c) 2013, Infobyte LLC"
__credits__ = ["Francisco Amato"]
__version__ = "1.0.0"
__maintainer__ = "Francisco Amato"
__email__ = "famato@infobytesec.com"
__status__ = "Development"


class AcunetixXmlParser(object):
    """
    The objective of this class is to parse an xml file generated by
    the acunetix tool.

    TODO: Handle errors.
    TODO: Test acunetix output version. Handle what happens if
    the parser doesn't support it.
    TODO: Test cases.

    @param acunetix_xml_filepath A proper xml generated by acunetix
    """

    def __init__(self, xml_output):

        tree = self.parse_xml(xml_output)

        if tree:
            self.sites = [data for data in self.get_items(tree)]
        else:
            self.sites = []

    def parse_xml(self, xml_output):
        """
        Open and parse an xml file.

        TODO: Write custom parser to just read the nodes that we need instead
        of reading the whole file.

        @return xml_tree An xml tree instance. None if error.
        """
        try:
            tree = ET.fromstring(xml_output)
        except SyntaxError, err:
            print("SyntaxError: %s. %s" % (err, xml_output))
            return None

        return tree

    def get_items(self, tree):
        """
        @return items A list of Host instances
        """

        for node in tree.findall('Scan'):
            yield Site(node)


def get_attrib_from_subnode(xml_node, subnode_xpath_expr, attrib_name):
    """
    Finds a subnode in the item node and the retrieves a value from it

    @return An attribute value
    """
    global ETREE_VERSION
    node = None

    if ETREE_VERSION[0] <= 1 and ETREE_VERSION[1] < 3:

        match_obj = re.search(
            "([^\@]+?)\[\@([^=]*?)=\'([^\']*?)\'",
            subnode_xpath_expr)

        if match_obj is not None:
            node_to_find = match_obj.group(1)
            xpath_attrib = match_obj.group(2)
            xpath_value = match_obj.group(3)
            for node_found in xml_node.findall(node_to_find):
                if node_found.attrib[xpath_attrib] == xpath_value:
                    node = node_found
                    break
        else:
            node = xml_node.find(subnode_xpath_expr)

    else:
        node = xml_node.find(subnode_xpath_expr)

    if node is not None:
        return node.get(attrib_name)

    return None


class Site(object):

    def __init__(self, item_node):
        self.node = item_node
        url_data = self.get_url(self.node)

        self.protocol = url_data.scheme
        self.host = url_data.hostname

        # Use the port in the URL if it is defined, or 80 or 443 by default
        self.port = url_data.port or (443 if url_data.scheme == "https"
                                      else 80)

        self.ip = self.resolve(self.host)
        self.os = self.get_text_from_subnode('Os')
        self.banner = self.get_text_from_subnode('Banner')
        self.items = []
        for alert in self.node.findall('ReportItems/ReportItem'):
            self.items.append(Item(alert))

    def get_text_from_subnode(self, subnode_xpath_expr):
        """
        Finds a subnode in the host node and the retrieves a value from it.

        @return An attribute value
        """
        sub_node = self.node.find(subnode_xpath_expr)
        if sub_node is not None:
            return sub_node.text

        return None

    def resolve(self, host):
        try:
            return socket.gethostbyname(host)
        except:
            api.log(
                '[ERROR] Acunetix XML Plugin: Ip of host unknown ' + host,
                level='ERROR')
            return None
        return host

    def get_url(self, node):
        url = self.get_text_from_subnode('StartURL')
        url_data = urlsplit(url)
        if not url_data.scheme:
            # Getting url from subnode 'Crawler'
            url_aux = get_attrib_from_subnode(node, 'Crawler', 'StartUrl')
            url_data = urlsplit(url_aux)

        return url_data


class Item(object):
    """
    An abstract representation of a Item


    @param item_node A item_node taken from an acunetix xml tree
    """

    def __init__(self, item_node):
        self.node = item_node

        self.name = self.get_text_from_subnode('Name')
        self.severity = self.get_text_from_subnode('Severity')
        self.request = self.get_text_from_subnode('TechnicalDetails/Request')
        self.response = self.get_text_from_subnode('TechnicalDetails/Response')
        self.parameter = self.get_text_from_subnode('Parameter')
        self.uri = self.get_text_from_subnode('Affects')
        self.desc = self.get_text_from_subnode('Description')

        if self.get_text_from_subnode('Recommendation'):
            self.resolution = self.get_text_from_subnode('Recommendation')
        else:
            self.resolution = ""

        if self.get_text_from_subnode('reference'):
            self.desc += "\nDetails: " + self.get_text_from_subnode('Details')
        else:
            self.desc += ""

        # Add path and params to the description to create different IDs if at
        # least one of this fields is different
        if self.uri:
            self.desc += '\nPath: ' + self.uri
        if self.parameter:
            self.desc += '\nParameter: ' + self.parameter

        self.ref = []
        for n in item_node.findall('References/Reference'):
            n2 = n.find('URL')
            self.ref.append(n2.text)

    def get_text_from_subnode(self, subnode_xpath_expr):
        """
        Finds a subnode in the host node and the retrieves a value from it.

        @return An attribute value
        """
        sub_node = self.node.find(subnode_xpath_expr)
        if sub_node is not None:
            return sub_node.text

        return None


class AcunetixPlugin(core.PluginBase):
    """
    Example plugin to parse acunetix output.
    """

    def __init__(self):
        core.PluginBase.__init__(self)
        self.id = "Acunetix"
        self.name = "Acunetix XML Output Plugin"
        self.plugin_version = "0.0.1"
        self.version = "9"
        self.framework_version = "1.0.0"
        self.options = None
        self._current_output = None
        self.target = None
        self._command_regex = re.compile(
            r'^(acunetix|sudo acunetix|\.\/acunetix).*?')

        global current_path
        self._output_file_path = os.path.join(
            self.data_path,
            "acunetix_output-%s.xml" % self._rid)

    def parseOutputString(self, output, debug=False):
        """
        This method will discard the output the shell sends, it will read it
        from the xml where it expects it to be present.

        NOTE: if 'debug' is true then it is being run from a test case and the
        output being sent is valid.
        """

        parser = AcunetixXmlParser(output)

        for site in parser.sites:

            if site.ip is None:
                continue

            host = []
            if site.host != site.ip:
                host = [site.host]

            h_id = self.createAndAddHost(site.ip, site.os)
            i_id = self.createAndAddInterface(
                h_id,
                site.ip,
                ipv4_address=site.ip,
                hostname_resolution=host)

            s_id = self.createAndAddServiceToInterface(
                h_id,
                i_id,
                "http",
                "tcp",
                ports=[site.port],
                version=site.banner,
                status='open')

            n_id = self.createAndAddNoteToService(h_id, s_id, "website", "")
            self.createAndAddNoteToNote(h_id, s_id, n_id, site.host, "")

            for item in site.items:
                self.createAndAddVulnWebToService(
                    h_id,
                    s_id,
                    item.name,
                    item.desc,
                    website=site.host,
                    severity=item.severity,
                    resolution=item.resolution,
                    path=item.uri,
                    params=item.parameter,
                    request=item.request,
                    response=item.response,
                    ref=item.ref)

        del parser

    def processCommandString(self, username, current_path, command_string):
        return None

    def setHost(self):
        pass


def createPlugin():
    return AcunetixPlugin()

if __name__ == '__main__':
    parser = AcunetixXmlParser(sys.argv[1])
    for item in parser.items:
        if item.status == 'up':
            print(item)
# I'm Py3