"""
Faraday Penetration Test IDE
Copyright (C) 2013  Infobyte LLC (http://www.infobytesec.com/)
See the file 'doc/LICENSE' for the license information
"""
from past.builtins import cmp

import functools

from netaddr import IPNetwork, IPRange
from os import path
from tempfile import NamedTemporaryFile
from re import match
from socket import inet_aton
from struct import unpack

from faraday_client.persistence.server import models
from faraday_client.config.configuration import getInstanceConfiguration

__description__ = 'Show networks'
__prettyname__ = 'Show networks'

# FIXME Update when persistence API changes
COLUMNS = {
    'netblock': lambda netblock, workspace: str(netblock.range),
    'hosts': lambda netblock, workspace: str(netblock.hosts),
    'vulns': lambda netblock, workspace: str(netblock.vulns),
    'owneds': lambda netblock, workspace: str(netblock.owneds)
}

CONF = getInstanceConfiguration()

class Netblock:
    def __init__(self, netblock):
        if netblock.find('/') != -1:
            self.range = IPNetwork(netblock)
        elif netblock.find('-') != -1:
            host_from,host_to = netblock.split('-')
            self.range = IPRange(host_from.strip(), host_to.strip())
        else:
            self.range = IPNetwork(netblock)
        self.hosts = 0
        self.vulns = 0
        self.owneds = 0

def get_default_columns():
    try:
        with open(path.join(CONF.getConfigPath(),'columns-networks.txt'), 'r') as f:
            columns = f.read()
    except:
        columns = "netblock,hosts,vulns,owneds"
    return columns

def set_default_columns(columns):
    with open(path.join(CONF.getConfigPath(),'columns-networks.txt'), 'w') as f:
        f.write(columns)

def get_netblock(ip):
    for netblock in netblocks:
        if ip in netblock.range:
            return netblock

def add_netblock(net):
    global netblocks
    netblock = Netblock(net)
    netblocks.append(netblock)
    return netblock

def parse_netbloks(netblock):
    netblocks = []
    if path.isfile(netblock):
        with open(netblock) as f:
            for netblock in f:
                netblocks += parse_netbloks(netblock.split()[0])
    else:
        netblocks.append(Netblock(netblock))
    return netblocks

hosts = []
def select(host, vulns):
    global hosts 
    netblock = get_netblock(host.name)
    if not netblock:
        netblock = add_netblock(f"{host.name}/{netsize}")
    netblock.hosts += 1 if not host.name in hosts else 0
    netblock.vulns += vulns
    netblock.owneds += 1 if host.owned else 0
    if not host.name in hosts:
        hosts.append(host.name)

def cast(value):
    value = value.strip()
    if value.isdigit():
        return int(value)
    elif match("^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", value):
        return unpack("!I", inet_aton(value) )[0]
    else:
        return value

netblocks = []
netsize = None
def main(workspace='', args=None, parser=None):
    global netblocks, netsize
    parser.add_argument('netblocks', nargs='*', help='List of Netblocks', default=[])
    parser.add_argument('-n', type=int, metavar='netsize', help='CIDR size', default=24)
    parser.add_argument('-p', type=str, metavar='ports', help='List of ports comma separated to filter', default="")
    parser.add_argument('-Sh', type=str, metavar='text', help='Search Hosts', default='')
    parser.add_argument('-Ss', type=str, metavar='text', help='Search Services', default='')
    parser.add_argument('-Sv', type=str, metavar='text', help='Search Vulnerabilities', default='')
    parser.add_argument('--severity', metavar='text', help='Comma separated list of columns to show.',
                        default="")

    parser.add_argument('-c', metavar='columns', help='Comma separated list of columns to show.',
                        default=get_default_columns())
    parser.add_argument('-C', metavar='columns', help='Set default comma separated list of columns to show.',
                        default='')
    parser.add_argument('-s', type=str, metavar='column', help='Sort order by column name or column number', default='netblock')
    parser.add_argument('-r', action='store_true', help='Reverse sort ordering', default=False)
    parser.add_argument('-R', action='store_true', help='Save IP\'s to file', default=False)
    parser.add_argument('-o', type=str, metavar='file', help='Save columns to file', default='')

    parser.add_argument('--dump', action='store_true', help='Dump all available fields', default=False)

    parser.add_argument('--options', action='store_true', help='Show help', default=False)
    parser.add_argument('--usage', action='store_true', help='Show help', default=False)

    parsed_args = parser.parse_args(args)
    if parsed_args.options:
        print(parser.format_help())
        return 0, None
    if parsed_args.usage:
        print(parser.format_usage())
        return 0, None

    for netblock in parsed_args.netblocks:
        netblocks += parse_netbloks(netblock)
    netsize = parsed_args.n
    search_host = parsed_args.Sh
    search_service = parsed_args.Ss
    search_vuln = parsed_args.Sv
    port_list = list( map(int, filter(lambda p:p, parsed_args.p.split(',')) ) )

    if parsed_args.C:
        columns = list(filter(None, parsed_args.C.split(',')))
        set_default_columns(parsed_args.C)
    elif parsed_args.c:
        columns = list(filter(None, parsed_args.c.split(',')))
    sort_col = columns.index(parsed_args.s) if COLUMNS.get(parsed_args.s) else int(parsed_args.s)-1

    if parsed_args.R:
        tmp = NamedTemporaryFile(mode="w", delete=False)
    hosts_to_export = set()

    hosts = models.get_hosts(workspace)
    for host in hosts:
        #import ipdb;ipdb.set_trace()
        if (not search_host or list(filter(lambda h:h.lower().find(search_host.lower())!=-1, host.getHostnames()))\
        or host.os.lower().find(search_host.lower())!=-1 or host.description.lower().find(search_host.lower())!=-1\
        or ('owned' if host.owned else '').find(search_host.lower())!=-1 )\
        and not port_list and not search_service and not search_vuln and not parsed_args.severity:
            select(host, vulns=host.getVulnsAmount())
        elif port_list or search_service or search_vuln or parsed_args.severity:
            for service in host.getServices():
                if search_service and service.getName() in search_service:
                    select(host, vulns=service.getVulnsAmount())
                    continue
                elif port_list or search_vuln or parsed_args.severity:
                    if port_list and (set(port_list) & set(service.getPorts())):
                        select(host, vulns=service.getVulnsAmount())
                        continue
                    elif search_vuln or parsed_args.severity:
                        for vuln in service.getVulns():
                            if search_vuln and (vuln.getDescription().lower().find(search_vuln.lower()) != -1 or vuln.getName().lower().find(search_vuln.lower()) != -1):
                                select(host, vulns=1)
                                continue
                            if vuln.severity in parsed_args.severity:
                                select(host, vulns=1)
                                continue

    lines = []
    for netblock in netblocks:
        column_data = []

        for column in columns:
            column_data += [COLUMNS[column](netblock, workspace)]

        lines += [column_data]

        if parsed_args.R and not host.getName() in hosts_to_export:
            tmp.write("{host}\n".format(host=host.getName()))
            hosts_to_export.add(host.getName())

    if not lines:
        return 0, None

    col_widths = {i:len(columns[i]) for i in range(len(columns))}
    for row in lines:
        for i in range(len(row)):
            col_widths[i] = len(row[i]) if len(row[i]) >= col_widths[i] else col_widths[i]

    sorting = lambda l1,l2: cmp(cast(l1[sort_col]), cast(l2[sort_col]))
    sorting_reverse = lambda l1,l2: cmp(cast(l2[sort_col]), cast(l1[sort_col]))

    print("".join(columns[i].ljust(col_widths[i]+2) for i in range(len(columns))))
    print("".join(("-"*len(columns[i])).ljust(col_widths[i]+2) for i in range(len(columns))))
    for row in sorted(lines, key=functools.cmp_to_key(sorting_reverse if parsed_args.r else sorting)):
        print("".join(row[i].ljust(col_widths[i]+2) for i in range(len(row))))

    if parsed_args.R:
        print(tmp.name)
    if parsed_args.o:
        with open(parsed_args.o, 'w') as o:
            for row in sorted(lines, key=functools.cmp_to_key(sorting_reverse if parsed_args.r else sorting)):
                o.write(",".join(word for word in row) + '\n')

    return 0, None


# I'm Py3
