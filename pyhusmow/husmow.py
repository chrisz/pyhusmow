import argparse
import json
import logging
import pprint
import time
from configparser import ConfigParser
from datetime import datetime, timedelta
from dateutil.parser import parse
from http.server import BaseHTTPRequestHandler, HTTPServer

import requests

logger = logging.getLogger("main")


class AutoMowerConfig(ConfigParser):
    def __init__(self):
        super(AutoMowerConfig, self).__init__()
        self['husqvarna.net'] = {}
        self.login = ""
        self.password = ""
        self.log_level = 'INFO'
        self.expire_status = "30"

    def load_config(self):
        return self.read('automower.cfg')

    def save_config(self):
        with open('automower.cfg', mode='w') as f:
            return self.write(f)

    @property
    def login(self):
        return self['husqvarna.net']['login']

    @login.setter
    def login(self, value):
        self['husqvarna.net']['login'] = value

    @property
    def password(self):
        return self['husqvarna.net']['password']

    @password.setter
    def password(self, value):
        self['husqvarna.net']['password'] = value

    @property
    def log_level(self):
        return self['husqvarna.net']['log_level']

    @log_level.setter
    def log_level(self, value):
        self['husqvarna.net']['log_level'] = value

    @property
    def expire_status(self):
        return int(self['husqvarna.net']['expire_status'])

    @expire_status.setter
    def expire_status(self, value):
        self['husqvarna.net']['expire_status'] = str(value)


class TokenConfig(ConfigParser):
    def __init__(self):
        super(TokenConfig, self).__init__()
        self['husqvarna.net'] = {}
        self.token = ""
        self.provider = ""
        self.expire_on = datetime(1900, 1, 1)

    def load_config(self):
        return self.read('token.cfg')

    def save_config(self):
        with open('token.cfg', mode='w') as f:
            return self.write(f)

    @property
    def token(self):
        return self['husqvarna.net']['token']

    @token.setter
    def token(self, value):
        self['husqvarna.net']['token'] = value

    @property
    def provider(self):
        return self['husqvarna.net']['provider']

    @provider.setter
    def provider(self, value):
        self['husqvarna.net']['provider'] = value

    @property
    def expire_on(self):
        return parse(self['husqvarna.net']['expire_on'])

    @expire_on.setter
    def expire_on(self, value):
        self['husqvarna.net']['expire_on'] = value.isoformat()

    def token_valid(self):
        return True if self.token and self.expire_on > datetime.now() else False


class CommandException(Exception):
    pass


class API:
    _API_IM = 'https://iam-api.dss.husqvarnagroup.net/api/v3/'
    _API_TRACK = 'https://amc-api.dss.husqvarnagroup.net/v1/'
    _HEADERS = {'Accept': 'application/json', 'Content-type': 'application/json'}

    def __init__(self):
        self.logger = logging.getLogger("main.automower")
        self.session = requests.Session()
        self.device_id = None
        self.token = None
        self.provider = None

    def login(self, login, password):
        response = self.session.post(self._API_IM + 'token',
                                     headers=self._HEADERS,
                                     json={
                                         "data": {
                                             "attributes": {
                                                 "password": password,
                                                 "username": login
                                             },
                                             "type": "token"
                                         }
                                     })

        response.raise_for_status()
        self.logger.info('Logged in successfully')

        json = response.json()
        self.set_token(json["data"]["id"], json["data"]["attributes"]["provider"])
        return json["data"]["attributes"]["expires_in"]

    def logout(self):
        response = self.session.delete(self._API_IM + 'token/%s' % self.token)
        response.raise_for_status()
        self.device_id = None
        self.token = None
        del (self.session.headers['Authorization'])
        self.logger.info('Logged out successfully')

    def set_token(self, token, provider):
        self.token = token
        self.provider = provider
        self.session.headers.update({
            'Authorization': "Bearer " + self.token,
            'Authorization-Provider': provider
        })

    def list_robots(self):
        response = self.session.get(self._API_TRACK + 'mowers', headers=self._HEADERS)
        response.raise_for_status()

        return response.json()

    def select_robot(self, mower):
        result = self.list_robots()
        if not len(result):
            raise CommandException('No mower found')
        if mower:
            for item in result:
                if item['name'] == mower or item['id'] == mower:
                    self.device_id = item['id']
                    break
            if self.device_id is None:
                raise CommandException('Could not find a mower matching %s' % mower)
        else:
            self.device_id = result[0]['id']

    def status(self):
        response = self.session.get(self._API_TRACK + 'mowers/%s/status' % self.device_id, headers=self._HEADERS)
        response.raise_for_status()

        return response.json()

    def geo_status(self):
        response = self.session.get(self._API_TRACK + 'mowers/%s/geofence' % self.device_id, headers=self._HEADERS)
        response.raise_for_status()

        return response.json()

    def control(self, command):
        if command not in ['PARK', 'STOP', 'START']:
            raise CommandException("Unknown command")

        response = self.session.post(self._API_TRACK + 'mowers/%s/control' % self.device_id,
                                    headers=self._HEADERS,
                                    json={
                                        "action": command
                                    })
        response.raise_for_status()


def create_config(args):
    config = AutoMowerConfig()
    config.load_config()
    if args.login:
        config.login = args.login
    if args.password:
        config.password = args.password
    if args.log_level:
        config.log_level = args.log_level
    if hasattr(args, "expire_status") and args.expire_status:
        config.expire_status = args.expire_status
    tokenConfig = TokenConfig()
    tokenConfig.load_config()

    if (not args.token or not tokenConfig.token_valid()) and (not config.login or not config.password):
        logger.error('Missing login or password')
        return None, None

    if args.save:
        if config.save_config():
            logger.info('Configuration saved in "automower.cfg"')
        else:
            logger.info('Failed to saved configuration in "automower.cfg"')

    return config, tokenConfig


def configure_log(config):
    logger.setLevel(logging.INFO)
    if config.log_level == 'ERROR':
        logger.setLevel(logging.ERROR)

    steam_handler = logging.StreamHandler()
    logger.addHandler(steam_handler)

    logger.info('Logger configured')


def setup_api(config, tokenConfig, args):
    mow = API()
    if args.token and tokenConfig.token and not tokenConfig.token_valid():
        logger.warn('The token expired on %s. Will create a new one.' % tokenConfig.expire_on)
    if args.token and tokenConfig.token_valid():
        mow.set_token(tokenConfig.token, tokenConfig.provider)
    else:
        expire = mow.login(config.login, config.password)
        if args.token:
            tokenConfig.token = mow.token
            tokenConfig.provider = mow.provider
            tokenConfig.expire_on = datetime.now() + timedelta(0, expire)
            tokenConfig.save_config()
            logger.info('Updated token')
    mow.select_robot(args.mower)
    return mow


def run_cli(config, tokenConfig, args):
    retry = 3
    pp = pprint.PrettyPrinter(indent=2)
    while retry > 0:
        try:
            mow = setup_api(config, tokenConfig, args)
            if args.command == 'control':
                mow.control(args.action)
            elif args.command == 'status':
                pp.pprint(mow.status())
            elif args.command == 'list':
                pp.pprint(mow.list_robots())

            retry = 0
        except CommandException as ce:
            logger.error("[ERROR] Wrong parameters: %s" % ce)
            break
        except Exception as ex:
            retry -= 1
            if retry > 0:
                logger.error(ex)
                logger.error("[ERROR] Retrying to send the command %d" % retry)
            else:
                logger.error("[ERROR] Failed to send the command")
                break

    logger.info("Done")

    if not args.token:
        mow.logout()


class HTTPRequestHandler(BaseHTTPRequestHandler):
    config = None
    tokenConfig = None
    args = None
    last_status = ""
    last_status_check = 0

    def do_GET(self):
        logger.info("Try to execute " + self.path)

        # use cache for status command
        if self.path == '/status':
            # XXX where do we store status properly ? Class variables are not thread safe...
            if HTTPRequestHandler.last_status_check > time.time() - HTTPRequestHandler.config.expire_status:
                logger.info("Get status from cache")
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(HTTPRequestHandler.last_status).encode('ascii'))
                return

        retry = 3
        fatal = False
        while retry > 0:
            try:
                mow = setup_api(HTTPRequestHandler.config, HTTPRequestHandler.tokenConfig, HTTPRequestHandler.args)

                if self.path == '/start':
                    mow.control('START')
                    self.send_response(200)
                    self.end_headers()
                elif self.path == '/stop':
                    mow.control('STOP')
                    self.send_response(200)
                    self.end_headers()
                elif self.path == '/park':
                    mow.control('PARK')
                    self.send_response(200)
                    self.end_headers()
                elif self.path == '/status':
                    logger.info("Get status from Husqvarna servers")
                    HTTPRequestHandler.last_status = mow.status()
                    HTTPRequestHandler.last_status_check = time.time()
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps(HTTPRequestHandler.last_status).encode('ascii'))
                else:
                    self.send_response(400)
                    self.end_headers()

                retry = 0
            except CommandException as ce:
                msg = "[ERROR] Wrong parameters: %s" % ce
                logger.error(msg)
                self.send_response(500, msg)
                fatal = True
                break
            except Exception as ex:
                retry -= 1
                if retry > 0:
                    logger.error(ex)
                    logger.error("[ERROR] Retrying to send the command %d" % retry)
                else:
                    logger.error("[ERROR] Failed to send the command")
                    self.send_response(500)

            logger.info("Done")

            if not HTTPRequestHandler.args.token:
                mow.logout()
            if fatal:
                exit(1)


def run_server(config, tokenConfig, args):
    server_address = (args.address, args.port)
    HTTPRequestHandler.config = config
    HTTPRequestHandler.tokenConfig = tokenConfig
    HTTPRequestHandler.args = args
    httpd = HTTPServer(server_address, HTTPRequestHandler)
    httpd.serve_forever()


def main():
    parser = argparse.ArgumentParser(description='Speak with your automower')
    subparsers = parser.add_subparsers(dest='command')

    parser_control = subparsers.add_parser('control', help='Send command to your automower')
    parser_control.add_argument('action', choices=['STOP', 'START', 'PARK'],
                                help='the command')

    parser_list = subparsers.add_parser('list', help='List all the mowers connected to the account.')
    parser_status = subparsers.add_parser('status', help='Get the status of your automower')

    parser_server = subparsers.add_parser('server', help='Run an http server to handle commands')
    parser_server.add_argument('--address', dest='address', default='127.0.0.1',
                               help='IP address for server')
    parser_server.add_argument('--port', dest='port', type=int, default=1234,
                               help='port for server')
    parser_server.add_argument('--expire', dest='expire_status', type=int, default=30,
                               help='Status needs to be refreshed after this time')

    parser.add_argument('--login', dest='login', help='Your login')
    parser.add_argument('--password', dest='password', help='Your password')
    parser.add_argument('--save', dest='save', action='store_true',
                        help='Save command line information in automower.cfg')
    parser.add_argument('--no-token', dest='token', action='store_false',
                        help='Disabled the use of the token')
    parser.add_argument('--logout', dest='logout', action='store_true',
                        help='Logout an existing token saved in token.cfg')
    parser.add_argument('--mower', dest='mower',
                        help='Select the mower to use. It can be the name or the id of the mower. If not provied the first mower will be used.')

    parser.add_argument('--log-level', dest='log_level', choices=['INFO', 'ERROR'],
                        help='Display all logs or just in case of error')

    args = parser.parse_args()

    config, tokenConfig = create_config(args)
    if not config:
        parser.print_help()
        exit(1)

    configure_log(config)

    if args.logout and tokenConfig.token_valid():
        mow = API()
        mow.set_token(tokenConfig.token, tokenConfig.provider)
        mow.logout()
        tokenConfig = TokenConfig()
        tokenConfig.save_config()
    elif args.command == 'server':
        run_server(config, tokenConfig, args)
    else:
        run_cli(config, tokenConfig, args)

    exit(0)
