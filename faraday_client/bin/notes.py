from past.builtins import cmp

import functools

from netaddr import IPNetwork, IPRange
from os import path
from tempfile import NamedTemporaryFile
from colorama import Fore
from re import match, compile
from socket import inet_aton
from struct import unpack

from faraday_client.model.common import factory
from faraday_client.persistence.server import models
from faraday_client.config.configuration import getInstanceConfiguration

__description__ = 'Show info similar to `notes` metasploit'
__prettyname__ = 'Show info'

# FIXME Update when persistence API changes
COLUMNS = {
    'host': lambda search, vuln, service, workspace: models.get_host(workspace, service.getParent()).name,
    'service': lambda search, vuln, service, workspace: service.name,
    'port': lambda search, vuln, service, workspace: ','.join(map(str, service.ports)),
    'protocol': lambda search, vuln, service, workspace: service.protocol,
    'status': lambda search, vuln, service, workspace: service.status,
    'version': lambda search, vuln, service, workspace: service.version,
    'name': lambda search, vuln, service, workspace: vuln.name,
    'description': lambda search, vuln, service, workspace: grep(vuln.description, search),
}

CONF = getInstanceConfiguration()

def get_default_columns():
    try:
        with open(path.join(CONF.getConfigPath(),'columns-notes.txt'), 'r') as f:
            columns = f.read()
    except:
        columns = "host,port,service,name,description"
    return columns

def set_default_columns(columns):
    with open(path.join(CONF.getConfigPath(),'columns-notes.txt'), 'w') as f:
        f.write(columns)

def create_info(models, workspace, service, vuln):
    for (key,val) in vuln.items():
        if val.startswith('@') and path.isfile(val[1:]):
            with open(val[1:]) as f:
                val = f.read()
        vuln[key] = val
    try:
        models.create_vuln(workspace, factory.createModelObject(models.Vuln.class_signature,
                                    vuln['name'],
                                    workspace,
                                    ref=vuln.get('reference',''),
                                    severity='info',
                                    resolution=vuln.get('resolution',''),
                                    confirmed=False,
                                    desc=vuln.get('description',''),
                                    parent_id=service.getID(),
                                    parent_type='Service'
                                    ))
    except ConflictInDatabase as ex:
        if ex.answer.status_code == 409:
            try:
                old_id = ex.answer.json()['object']['_id']
            except KeyError:
                print("Vulnerability already exists. Couldn't fetch ID")
                return 2, None
            else:
                print("A vulnerability with ID %s already exists!" % old_id)
                return 2, None
        else:
            print("Unknown error while creating the vulnerability")
            return 2, None
    except CantCommunicateWithServerError as ex:
        print("Error while creating vulnerability:", ex.response.text)
        return 2, None

def delete_info(workspace, vuln):
	models.delete_vuln(workspace, vuln.id)

def change_info(workspace, vuln, what):
	for (key,val) in what.items():
		if val.startswith('@') and path.isfile(val[1:]):
			with open(val[1:]) as f:
				val = f.read()
		setattr(vuln, key, val)
	models.update_vuln(workspace, vuln)

def dump(vuln):
    for attr,val in vuln.__dict__.items():
        print(attr + ": " + str(val))

def grep(haystack, needle):
	result = ''
	if needle.lower() in haystack.lower() != -1:
		for line in haystack.split('\n'):
			if needle.lower() in line.lower():
				result += line + '\n' if result else line
	else:
		result = haystack
	return result

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
	parser.add_argument('hosts', nargs="*", help='Info text', default=[])
	parser.add_argument('-p', type=str, metavar='ports', help='List of ports comma separated to filter', default="")
	parser.add_argument('--protocol', type=str, metavar='protocol', help='Only this protocol', default='')
	parser.add_argument('--up', action='store_true', help='Only open ports', default=False)
	parser.add_argument('-a', metavar='key=value', help='Add new Info', type=lambda opt: opt.split(","))
	parser.add_argument('-d', action='store_true', help='Delete Info', default=False)
	parser.add_argument('-e', action='append', metavar='key=value', help='Edit Info', type=lambda kv: kv.split("="))
	parser.add_argument('-S', type=str, metavar='text', help='Search Info', default="")

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
	port_list = list( map(int, filter(lambda p:p, parsed_args.p.split(',')) ) )

	protocol = parsed_args.protocol
	search = parsed_args.S

	if parsed_args.C:
		columns = list(filter(None, parsed_args.C.split(',')))
		set_default_columns(parsed_args.C)
	elif parsed_args.c:
		columns = list(filter(None, parsed_args.c.split(',')))

	sort_col = columns.index(parsed_args.s) if COLUMNS.get(parsed_args.s) else int(parsed_args.s)-1

	port_list = list( map(int, filter(lambda p:p, parsed_args.p.split(',')) ) )
	if parsed_args.R:
		tmp = NamedTemporaryFile(mode="w", delete=False)
	hosts_to_export = set()

	lines = []
	added = 0
	deleted = 0
	changed = 0
	hosts = models.get_hosts(workspace)
	for host in hosts:
		#import ipdb; ipdb.set_trace()
		if not ip_list or host.getName() in ip_list:
			for service in host.getServices():
				if not port_list or set(port_list) & set(service.getPorts()):
					if parsed_args.a:
						create_info(models, workspace, service, dict([x.split('=') for x in parsed_args.a]))
						added += 1
					else:
						for vuln in service.getVulns():
							if vuln.severity == 'info':
								if (not search or vuln.getDescription().lower().find(search.lower()) != -1 or vuln.getName().lower().find(search.lower()) != -1):
									if parsed_args.d:
										delete_info(workspace, vuln)
										deleted += 1
									elif parsed_args.e:
										change_info(workspace, vuln, dict(parsed_args.e))
										changed += 1
									elif parsed_args.dump:
										dump(vuln)
									else:
										column_data = []

										for column in columns:
											column_data += [COLUMNS[column](search, vuln, service, workspace)]

										lines += [column_data]
										if parsed_args.R and not host.getName() in hosts_to_export:
											tmp.write("{host}\n".format(host=host.getName()))
											hosts_to_export.add(host.getName())
	if added:
		print("added %d info"%added)
	elif deleted:
		print("deleted %d info"%deleted)
	elif changed:
		print("changed %d info"%changed)

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
		