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

__description__ = 'Show hosts similar to `hosts` metasploit'
__prettyname__ = 'Show hosts'

# FIXME Update when persistence API changes
COLUMNS = {
    'host': lambda host, workspace: host.name,
    'mac': lambda host, workspace: host.mac,
    'hostname': lambda host, workspace: ','.join(host.getHostnames()),
    'os': lambda host, workspace: host.os,
    'description': lambda host, workspace: host.description,
    'vulns': lambda host, workspace: str(host.vuln_amount),
    'owned': lambda host, workspace: 'owned' if host.owned else ''
}

CONF = getInstanceConfiguration()

def get_default_columns():
    try:
        with open(path.join(CONF.getConfigPath(),'columns-hosts.txt'), 'r') as f:
            columns = f.read()
    except:
        columns = "host,mac,hostname,os,description"
    return columns

def set_default_columns(columns):
    with open(path.join(CONF.getConfigPath(),'columns-hosts.txt'), 'w') as f:
        f.write(columns)

def create_host(models, workspace, ip):
    columns = {
        "name" : ip,
    }
    host = models.Host(columns, workspace)
    models.create_host(workspace, host)

def delete_host(workspace, host):
    models.delete_host(workspace, host.id)

def change_host(workspace, host, what):
    for (key,val) in what.items():
        if val.startswith('@') and path.isfile(val[1:]):
            with open(val[1:]) as f:
                val = f.read()
        if key == 'hostname':
            host.hostnames.append(val)
        elif key == 'hostnames':
            host.hostnames = val.split(',')
        else:
            setattr(host, key, val)
    models.update_host(workspace, host, None)

def dump(host):
    for attr,val in host.__dict__.items():
        print(attr + ": " + str(val))

def parse_host(host):
    hosts = []
    if path.isfile(host):
        with open(host) as f:
            for host in f:
                hosts += parse_host(host.split()[0])
    else:
        if host.find('/') != -1:
            for ip in IPNetwork(host):
                hosts.append(str(ip))
        elif host.find('-') != -1:
            host_from,host_to = host.split('-')
            for ip in IPRange(host_from.strip(), host_to.strip()):
                hosts.append(str(ip))
        else:
            hosts.append(host)
    return hosts

def cast(value):
    value = value.strip()
    if value.isdigit():
        return int(value)
    elif match("^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", value):
        return unpack("!I", inet_aton(value) )[0]
    else:
        return value

def main(workspace='', args=None, parser=None):
    parser.add_argument('hosts', nargs='*', help='List of Hosts names', default=[])
    parser.add_argument('-a', action='store_true', help='Add new Host', default=False)
    parser.add_argument('-d', action='store_true', help='Delete Host', default=False)
    parser.add_argument('-e', action='append', metavar='key=value', help='Edit Host', type=lambda kv: kv.split("="))
    parser.add_argument('-S', type=str, metavar='text', help='Search Hosts', default='')
    parser.add_argument('-c', metavar='columns', help='Comma separated list of columns to show.',
                        default=get_default_columns())
    parser.add_argument('-C', metavar='columns', help='Set default comma separated list of columns to show.',
                        default='')
    parser.add_argument('-s', type=str, metavar='column', help='Sort order by column name or column number', default='host')
    parser.add_argument('-r', action='store_true', help='Reverse sort ordering', default=False)
    parser.add_argument('-R', action='store_true', help='Save IP\'s to file', default=False)
    parser.add_argument('-o', type=str, metavar='file', help='Save columns to file', default='')

    parser.add_argument('--dump', action='store_true', help='Dump all available fields', default=False)

    parser.add_argument('--options', action='store_true', help='Show options', default=False)
    parser.add_argument('--usage', action='store_true', help='Show usage', default=False)

    parsed_args = parser.parse_args(args)
    if parsed_args.options:
        print(parser.format_help())
        return 0, None
    if parsed_args.usage:
        print(parser.format_usage())
        return 0, None

    ip_list = []
    for host in parsed_args.hosts:
        ip_list += parse_host(host)
    search = parsed_args.S

    if parsed_args.C:
        columns = list(filter(None, parsed_args.C.split(',')))
        set_default_columns(parsed_args.C)
    elif parsed_args.c:
        columns = list(filter(None, parsed_args.c.split(',')))
    sort_col = columns.index(parsed_args.s) if COLUMNS.get(parsed_args.s) else int(parsed_args.s)-1

    if parsed_args.R:
        tmp = NamedTemporaryFile(mode="w", delete=False)
    hosts_to_export = set()
    
    added = 0
    if parsed_args.a:
        for ip in ip_list:
            create_host(models, workspace, ip=ip)
            added += 1
        if added:
            print("added %d hosts"%added)
        return 0, None

    lines = []
    deleted = 0
    changed = 0
    hosts = models.get_hosts(workspace)
    for host in hosts:
        #import ipdb;ipdb.set_trace()
        if not ip_list or host.name in ip_list:
            if not search or list(filter(lambda h:h.lower().find(search.lower())!=-1, host.getHostnames()))\
            or host.os.lower().find(search.lower())!=-1 or host.description.lower().find(search.lower())!=-1\
            or ('owned' if host.owned else '').find(search.lower())!=-1:
                if parsed_args.d:
                    delete_host(workspace, host)
                    deleted += 1
                elif parsed_args.e:
                    change_host(workspace, host, dict(parsed_args.e))
                    changed += 1
                elif parsed_args.dump:
                    dump(host)
                else:
                    column_data = []

                    for column in columns:
                        column_data += [COLUMNS[column](host, workspace)]

                    lines += [column_data]

                    if parsed_args.R and not host.getName() in hosts_to_export:
                        tmp.write("{host}\n".format(host=host.getName()))
                        hosts_to_export.add(host.getName())
    if deleted:
        print("deleted %d hosts"%deleted)
    elif changed:
        print("changed %d hosts"%changed)

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
