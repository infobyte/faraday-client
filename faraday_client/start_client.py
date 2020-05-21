#!/usr/bin/env python3
"""
Faraday Penetration Test IDE
Copyright (C) 2018  Infobyte LLC (http://www.infobytesec.com/)
See the file 'doc/LICENSE' for the license information
"""

from __future__ import absolute_import
from __future__ import print_function

from builtins import input

import os
import sys
import shutil
import getpass
import argparse
import requests
import requests.exceptions
import logging


from faraday_client.config.configuration import getInstanceConfiguration
from faraday_client.config.constant import (
    CONST_USER_HOME,
    CONST_FARADAY_IMAGES,
    CONST_FARADAY_USER_CFG,
    CONST_FARADAY_BASE_CFG,
    CONST_USER_ZSHRC,
    CONST_FARADAY_ZSHRC,
    CONST_ZSH_PATH,
    CONST_FARADAY_ZSH_FARADAY,
    CONST_REQUIREMENTS_FILE,
    CONST_FARADAY_FOLDER_LIST,
)
from faraday_client.persistence.server.exceptions import Required2FAError
from faraday_client.utils.logger import set_logging_level

CONST_FARADAY_HOME_PATH = os.path.expanduser('~/.faraday')

from faraday_client import __version__
from faraday_client.persistence.server.server import login_user, get_user_info, is_authenticated

import faraday_client

from colorama import init, Fore, Back, Style
init(autoreset=True)
from urllib.parse import urlparse, urljoin

USER_HOME = os.path.expanduser(CONST_USER_HOME)
# find_module returns if search is successful, the return value is a 3-element tuple (file, pathname, description):
FARADAY_BASE = os.path.dirname(faraday_client.__file__)
os.path.dirname(os.path.dirname(os.path.realpath(__file__)))  # Use double dirname to obtain parent directory
FARADAY_CLIENT_BASE = FARADAY_BASE

FARADAY_USER_HOME = os.path.expanduser(CONST_FARADAY_HOME_PATH)

FARADAY_BASE_IMAGES = os.path.join(FARADAY_CLIENT_BASE, "data", CONST_FARADAY_IMAGES)

FARADAY_USER_CONFIG_XML = os.path.join(FARADAY_USER_HOME, CONST_FARADAY_USER_CFG)

FARADAY_BASE_CONFIG_XML = os.path.join(FARADAY_BASE, CONST_FARADAY_BASE_CFG)

USER_ZSHRC = os.path.expanduser(CONST_USER_ZSHRC)

FARADAY_USER_ZSHRC = os.path.join(FARADAY_USER_HOME, CONST_FARADAY_ZSHRC)
FARADAY_USER_ZSH_PATH = os.path.join(FARADAY_USER_HOME, CONST_ZSH_PATH)
FARADAY_BASE_ZSH = os.path.join(FARADAY_CLIENT_BASE, CONST_FARADAY_ZSH_FARADAY)

FARADAY_REQUIREMENTS_FILE = os.path.join(FARADAY_BASE, CONST_REQUIREMENTS_FILE)

REQUESTS_CA_BUNDLE_VAR = "REQUESTS_CA_BUNDLE"
FARADAY_DEFAULT_PORT_XMLRPC = 9876
FARADAY_DEFAULT_PORT_REST = 9977
FARADAY_DEFAULT_HOST = "localhost"

logger = logging.getLogger(__name__)


def getParserArgs():
    """
    Parser setup for faraday launcher arguments.
    """

    parser = argparse.ArgumentParser(
        description="Faraday's launcher parser.",
        fromfile_prefix_chars='@')

    parser_connection = parser.add_argument_group('connection')

    parser_connection.add_argument('-n', '--hostname',
                                   action="store",
                                   dest="host",
                                   default=None,
                                   help="The hostname where both server APIs will listen (XMLRPC and RESTful). Default = localhost")

    parser_connection.add_argument('-px',
                                   '--port-xmlrpc',
                                   action="store",
                                   dest="port_xmlrpc",
                                   default=None,
                                   type=int,
                                   help="Sets the port where the API XMLRPC Server will listen. Default = 9876")

    parser_connection.add_argument('-pr',
                                   '--port-rest',
                                   action="store",
                                   dest="port_rest",
                                   default=None,
                                   type=int,
                                   help="Sets the port where the API RESTful Server will listen. Default = 9977")

    parser.add_argument('--disable-excepthook',
                        action="store_true",
                        dest="disable_excepthook",
                        default=False,
                        help="Disable the application exception hook that allows to send error \
                        reports to developers.")

    parser.add_argument('--login',
                        action="store_true",
                        dest="login",
                        default=False,
                        help="Force to ask for credentials")

    parser.add_argument('--dev-mode', action="store_true", dest="dev_mode",
                        default=False,
                        help="Enable dev mode. This will use the user config and plugin folder.")

    parser.add_argument('--cert',
                        action="store",
                        dest="cert_path",
                        default=None,
                        help="Path to the valid Faraday server certificate")

    parser.add_argument('--gui',
                        action="store",
                        dest="gui",
                        default="gtk",
                        help="Select interface to start faraday. Supported values are "
                              "gtk and 'no' (no GUI at all). Defaults to GTK")

    parser.add_argument('--cli',
                        action="store_true",
                        dest="cli",
                        default=False,
                        help="Set this flag to avoid GUI and use Faraday as a CLI.")

    parser.add_argument('-w',
                        '--workspace',
                        action="store",
                        dest="workspace",
                        default=None,
                        help="Workspace to be opened")

    parser.add_argument('-r',
                        '--report',
                        action="store",
                        dest="filename",
                        default=None,
                        help="Report to be parsed by the CLI")

    parser.add_argument('-d',
                        '--debug',
                        action="store_true",
                        default=False,
                        help="Enables debug mode. Default = disabled")

    parser.add_argument('--creds-file',
                        action="store",
                        dest="creds_file",
                        default=None,
                        help="File containing user's credentials to be used in CLI mode")

    parser.add_argument('--nodeps',
                        action="store_true",
                        help='Skip dependency check')
    parser.add_argument('--keep-old', action='store_true', help='Keep old object in CLI mode if Faraday find a conflict')
    parser.add_argument('--keep-new', action='store_true', help='Keep new object in CLI mode if Faraday find a conflict (DEFAULT ACTION)')

    parser.add_argument('--license-path',
                        help='Path to the licence .tar.gz',
                        default=None)

    parser.add_argument('-v', '--version', action='version',
                        version='Faraday Client v{version}'.format(version=__version__))

    return parser.parse_args()


def setConf():
    """
    User configuration management and instantiation.
    Setting framework configuration based either on previously user saved
    settings or default ones.
    """

    logger.info("Setting configuration.")

    CONF = getInstanceConfiguration()
    CONF.setDebugStatus(args.debug)
    if args.debug:
        set_logging_level(logging.DEBUG)

    host = CONF.getApiConInfoHost() if str(CONF.getApiConInfoHost()) != "None" else FARADAY_DEFAULT_HOST
    port_xmlrpc = CONF.getApiConInfoPort() if str(CONF.getApiConInfoPort()) != "None" else FARADAY_DEFAULT_PORT_XMLRPC
    port_rest = CONF.getApiRestfulConInfoPort() if str(
        CONF.getApiRestfulConInfoPort()) != "None" else FARADAY_DEFAULT_PORT_REST

    host = args.host if args.host else host
    port_xmlrpc = args.port_xmlrpc if args.port_xmlrpc else port_xmlrpc
    port_rest = args.port_rest if args.port_rest else port_rest

    CONF.setApiConInfoHost(host)
    CONF.setApiConInfoPort(port_xmlrpc)
    CONF.setApiRestfulConInfoPort(port_rest)


def start_faraday_client():
    """Application startup.

    Starts a MainApplication with the previously parsed arguments, and handles
    a profiler if requested.

    Returns application status.

    """
    from faraday_client.model.application import MainApplication  # pylint:disable=import-outside-toplevel

    logger.info("All done. Opening environment.")
    # TODO: Handle args in CONF and send only necessary ones.

    main_app = MainApplication(args)

    if not args.disable_excepthook:
        logger.info("Main application ExceptHook enabled.")
        main_app.enableExceptHook()

    logger.info("Starting main application.")
    start = main_app.start

    serverURL = getInstanceConfiguration().getServerURI()
    if serverURL:
        url = "%s/_ui" % serverURL
        print(Fore.WHITE + Style.BRIGHT + "\n* " + "Faraday UI is ready")
        print(
            Fore.WHITE + Style.BRIGHT + "Point your browser to: \n[%s]" % url)

    print(Fore.RESET + Back.RESET + Style.RESET_ALL)

    exit_status = start()

    return exit_status


def setupZSH():
    """
    Checks and handles Faraday's integration with ZSH.

    If the user has a .zshrc file, it gets copied and integrated with
    faraday's zsh plugin.
    """

    if os.path.isfile(USER_ZSHRC):
        shutil.copy(USER_ZSHRC, FARADAY_USER_ZSHRC)
    else:
        open(FARADAY_USER_ZSHRC, 'w').close()

    with open(FARADAY_USER_ZSHRC, "r+") as f:
        content = f.read()
        f.seek(0, 0)
        f.write('ZDOTDIR=$OLDZDOTDIR' + '\n' + content)
    with open(FARADAY_USER_ZSHRC, "a") as f:
        f.write("source \"%s\"" % FARADAY_BASE_ZSH)

    # Don't use shutil.copy to ensure the destination file will be writable
    with open(os.path.join(FARADAY_USER_ZSH_PATH, 'faraday.zsh'), 'w') as dst:
        with open(FARADAY_BASE_ZSH) as src:
            dst.write(src.read())


def setupXMLConfig():
    """
    Checks user configuration file status.

    If there is no custom config the default one will be copied as a default.
    """

    if not os.path.isfile(FARADAY_USER_CONFIG_XML):
        logger.info("Copying default configuration from project.")
        shutil.copy(FARADAY_BASE_CONFIG_XML, FARADAY_USER_CONFIG_XML)
    else:
        logger.info("Using custom user configuration.")


def checkConfiguration(gui_type):
    """
    Checks if the environment is ready to run Faraday.

    Checks different environment requirements and sets them before starting
    Faraday. This includes checking for plugin folders, libraries,
    and ZSH integration.
    """
    logger.info("Checking configuration.")
    logger.info("Setting up ZSH integration.")
    setupZSH()
    logger.info("Setting up user configuration.")
    setupXMLConfig()


def setupFolders(folderlist):
    """
    Checks if a list of folders exists and creates them otherwise.
    """

    for folder in folderlist:
        fp_folder = os.path.join(FARADAY_USER_HOME, folder)
        checkFolder(fp_folder)


def checkFolder(folder):
    """
    Checks whether a folder exists and creates it if it doesn't.
    """

    if not os.path.isdir(folder):
        if logger:
            logger.info("Creating %s" % folder)
        os.makedirs(folder)


def printBanner():
    """
    Prints Faraday's ascii banner.
    """
    print (Fore.RED + """
  _____                           .___
_/ ____\_____  ____________     __| _/_____   ___.__.
\   __\ \__  \ \_  __ \__  \   / __ | \__  \ <   |  |
 |  |    / __ \_|  | \// __ \_/ /_/ |  / __ \_\___  |
 |__|   (____  /|__|  (____  /\____ | (____  // ____|
             \/            \/      \/      \/ \/
    """)

    print(Fore.WHITE + Back.RED + Style.BRIGHT + "[*[       Open Source Penetration Test IDE       ]*]")
    print(Back.RESET + "            Where pwnage goes multiplayer")
    print(Fore.RESET + Back.RESET + Style.RESET_ALL)
    logger.info("Starting Faraday IDE.")



def try_login_user(server_uri, api_username, api_password, u2fa_token=None):
    try:
        session_cookie = login_user(server_uri, api_username, api_password, u2fa_token)
    except requests.exceptions.SSLError:
        print("SSL certificate validation failed.\nYou can use the --cert option in Faraday to set the path of the cert")
        sys.exit(-1)
    except requests.exceptions.MissingSchema:
        print("The Faraday Server URL is incorrect, please try again.")
        sys.exit(-2)
    except Required2FAError as e:
        raise e
    except Exception as e:
        print(e)
    else:
        return session_cookie


def login(ask_for_credentials):
    """
    Sets the username and passwords from the command line.
    If --login flag is set then username and password is set
    """
    CONF = getInstanceConfiguration()
    server_url = CONF.getAPIUrl()
    try:
        if not server_url:
            server_url = input("\nPlease enter the Faraday Server URL (Press enter for https://localhost): ") \
                         or "https://localhost"
        else:
            if ask_for_credentials:
                server_url = input(f"\nPlease enter the Faraday Server URL (Press enter for last used: {server_url}): ") \
                             or server_url
        parsed_url = urlparse(server_url)
        try:
            if parsed_url.scheme == "https":
                logger.debug("Validate server ssl certificate [%s]", server_url)
            login_url = urljoin(server_url, "/_api/login")
            test_server_response = requests.get(login_url)
            if test_server_response.status_code != 200:
                logger.error("Faraday server returned invalid response: %s", test_server_response.status_code)
                sys.exit(1)
        except requests.exceptions.SSLError as e:
            logger.error("Invalid SSL Certificate, use --cert CERTIFICATE for self signed certificates")
            print(f"{Fore.RED}Invalid SSL Certificate, use --cert CERTIFICATE_PATH for self signed certificates")
            sys.exit(1)
        except requests.exceptions.ConnectionError as e:
            logger.error("Connection to Faraday server FAILED: %s", e)
            sys.exit(1)
        CONF.setAPIUrl(server_url)
        if not ask_for_credentials:
            session_cookies = CONF.getFaradaySessionCookies()
            if session_cookies and server_url:
                if is_authenticated(server_url, session_cookies):
                    logger.debug("Valid Previous session cookie found")
                    return True
        print(f"""\nPlease provide your valid Faraday credentials for {server_url}\nYou have 3 attempts.""")
        MAX_ATTEMPTS = 3
        for attempt in range(1, MAX_ATTEMPTS + 1):
            api_username = input("Username (press enter for faraday): ") or "faraday"
            api_password = getpass.getpass('Password: ')
            try:
                session_cookie = try_login_user(server_url, api_username, api_password)
            except Required2FAError as e:
                print(f"{Fore.YELLOW}2FA Authentication enabled!!")
                u2fa_token = None
                while not u2fa_token:
                    u2fa_token = input("2FA Token: ")
                session_cookie = try_login_user(server_url, api_username, api_password, u2fa_token)
            if session_cookie:
                CONF.setFaradaySessionCookies(session_cookie)
                user_info = get_user_info()
                if not user_info:
                    continue
                else:
                    if 'roles' in user_info:
                        if 'client' in user_info['roles']:
                            print(f"You can't login as a client. You have {MAX_ATTEMPTS - attempt} attempt(s) left.")
                            continue
                    logger.info('Login successful: {0}'.format(api_username))
                    CONF.saveConfig()
                    break
            print(f'Login failed, please try again. You have {MAX_ATTEMPTS - attempt} more attempts')
        else:
            logger.fatal(f'Invalid credentials, {MAX_ATTEMPTS} attempts failed. Quitting Faraday...')
            sys.exit(-1)
    except KeyboardInterrupt:
        sys.exit(0)

def main():
    """
    Main function for launcher.
    """
    global args

    args = getParserArgs()
    setupFolders(CONST_FARADAY_FOLDER_LIST)
    printBanner()
    logger.info("Dependencies met.")
    if args.cert_path:
        if not os.path.isfile(args.cert_path):
            logger.error("Certificate Path Don't exists [%s]", args.cert_path)
            sys.exit(1)
        os.environ[REQUESTS_CA_BUNDLE_VAR] = args.cert_path
    checkConfiguration(args.gui)
    setConf()
    login(args.login)
    start_faraday_client()


if __name__ == '__main__':
    main()
