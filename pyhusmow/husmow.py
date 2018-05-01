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
        self.user_id = ""
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
    def user_id(self):
        return self['husqvarna.net']['user_id']

    @user_id.setter
    def user_id(self, value):
        self['husqvarna.net']['user_id'] = value

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
    _API_SG = 'https://sg-api.dss.husqvarnagroup.net/sg-1/' # gardena mowers
    _HEADERS = {'Accept': 'application/json', 'Content-type': 'application/json'}

    def __init__(self):
        self.logger = logging.getLogger("main.automower")
        self.session = requests.Session()
        self.device_id = None
        self.device_type = None
        self.location_id = None
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
        self.set_token(json["data"]["id"], json["data"]["attributes"]["provider"], json["data"]["attributes"]["user_id"])
        return json["data"]["attributes"]["expires_in"]

    def logout(self):
        response = self.session.delete(self._API_IM + 'token/%s' % self.token)
        response.raise_for_status()
        self.device_id = None
        self.token = None
        del (self.session.headers['Authorization'])
        self.logger.info('Logged out successfully')

    def set_token(self, token, provider, user_id):
        self.token = token
        self.provider = provider
        self.user_id = user_id
        self.session.headers.update({
            'Authorization': "Bearer " + self.token,
            'Authorization-Provider': provider
        })

    def __find_by_name(self, arr, name):
        for entry in arr:
            if "name" in entry and entry["name"] == name:
                return entry
        return None

    def list_robots(self):
        response = self.session.get(self._API_TRACK + 'mowers', headers=self._HEADERS)
        response.raise_for_status()
        mowers_husqvarna = response.json()
        for mower in mowers_husqvarna:
            mower["_husmow_type"] = "husqvarna"

        response = self.session.get(self._API_SG + 'locations?user_id={}'.format(self.user_id), headers=self._HEADERS)
        response.raise_for_status()
        mowers_gardena = []
        for location in response.json()["locations"]:
            response = self.session.get(self._API_SG + 'devices?locationId={}'.format(location["id"]),
                                        headers=self._HEADERS)
            response.raise_for_status()
            for device in response.json()["devices"]:
                if device["category"] == "mower":
                    device["_husmow_type"] = "gardena"
                    device["_husmow_location_id"] = location["id"]
                    device["model"] = self.__find_by_name(self.__find_by_name(device["abilities"], "mower_type")["properties"],"device_type")["value"],
                    mowers_gardena.append(device)

        return mowers_husqvarna + mowers_gardena

    def select_robot(self, mower):
        result = self.list_robots()
        if not len(result):
            raise CommandException('No mower found')
        if mower:
            for item in result:
                if item['name'] == mower or item['id'] == mower:
                    self.device_id = item['id']
                    self.device_type = item['_husmow_type']
                    self.location_id = item['_husmow_location_id']
                    break
            if self.device_id is None:
                raise CommandException('Could not find a mower matching %s' % mower)
        else:
            self.device_id = result[0]['id']
            self.device_type = result[0]['_husmow_type']
            self.location_id = result[0]['_husmow_location_id']

    def status(self):
        if self.device_type == "gardena":
            url = self._API_SG + 'devices/{}?locationId={}'.format(self.device_id, self.location_id)
        elif self.device_type == "husqvarna":
            url = self._API_TRACK + 'mowers/%s/status' % self.device_id
        response = self.session.get(url, headers=self._HEADERS)
        response.raise_for_status()

        data = response.json()

        if self.device_type == "husqvarna":
            return data
        elif self.device_type == "gardena":
            device = data["devices"]
            status = self.__find_by_name(self.__find_by_name(device["abilities"], "mower")["properties"], "status")
            return {
                "id": device["id"],
                "name": device["name"],
                "model": self.__find_by_name(self.__find_by_name(device["abilities"], "mower_type")["properties"], "device_type")["value"],
                "storedTimestamp": status["timestamp"],
                "mowerStatus": status["value"].upper(),
                "batteryPercent": self.__find_by_name(self.__find_by_name(device["abilities"], "battery")["properties"], "level")["value"]
            }

    def geo_status(self):
        if self.device_type == "gardena":
            raise CommandException("unsupported for gardena mowers")

        response = self.session.get(self._API_TRACK + 'mowers/%s/geofence' % self.device_id, headers=self._HEADERS)
        response.raise_for_status()

        return response.json()

    def control(self, command):
        if command not in ['PARK', 'STOP', 'START']:
            raise CommandException("Unknown command")
        if self.device_type == "gardena":
            url = self._API_SG + 'devices/{}/abilities/mower/command/?locationId={}'.format(self.device_id, self.location_id)
            if command == 'START':
                command_gardena = 'start_resume_schedule'
            elif command == 'PARK':
                command_gardena = 'park_until_further_notice'
            else:
                raise CommandException("unsupported for gardena mowers")
            body = {"name": command_gardena}
        elif self.device_type == "husqvarna":
            url = self._API_TRACK + 'mowers/%s/control' % self.device_id
            body = {"action": command}
        response = self.session.post(url,
                                     headers=self._HEADERS,
                                     json=body)
        response.raise_for_status()


def as_json(**kwargs):
    from json import dumps
    print(dumps(kwargs, indent=2))


_errors = []


def log_error(args, msg):
    if args.json:
        _errors.append(str(msg))
    else:
        logger.error(msg)


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
        log_error(args, 'Missing login or password')
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
        mow.set_token(tokenConfig.token, tokenConfig.provider, tokenConfig.user_id)
    else:
        expire = mow.login(config.login, config.password)
        if args.token:
            tokenConfig.token = mow.token
            tokenConfig.provider = mow.provider
            tokenConfig.expire_on = datetime.now() + timedelta(0, expire)
            tokenConfig.user_id = mow.user_id
            tokenConfig.save_config()
            logger.info('Updated token')
    mow.select_robot(args.mower)
    return mow


def run_cli(config, tokenConfig, args):
    retry = 3
    if args.json:
        out = lambda res: as_json(**{args.command: res})
    else:
        pp = pprint.PrettyPrinter(indent=2)
        out = pp.pprint
    while retry > 0:
        try:
            mow = setup_api(config, tokenConfig, args)
            if args.command == 'control':
                mow.control(args.action)
            elif args.command == 'status':
                out(mow.status())
            elif args.command == 'list':
                out(mow.list_robots())

            retry = 0
        except CommandException as ce:
            log_error(args, "[ERROR] Wrong parameters: %s" % ce)
            break
        except Exception as ex:
            retry -= 1
            if retry > 0:
                log_error(args, "[ERROR] %s. Retrying to send the command %d" % (ex, 3- retry))
            else:
                log_error(args, "[ERROR] Failed to send the command")
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
    parser = argparse.ArgumentParser(description='Speak with your automower',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    subparsers = parser.add_subparsers(dest='command')
    ask_password = argparse.Namespace()

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
    parser.add_argument('--password', dest='password', nargs='?', const=ask_password,
                        help='Your password. If used without arguments it will promp')
    parser.add_argument('--save', dest='save', action='store_true',
                        help='Save command line information in automower.cfg. NOTE: the passwords is saved in cleartext')
    parser.add_argument('--no-token', dest='token', action='store_false',
                        help='Disabled the use of the token')
    parser.add_argument('--logout', dest='logout', action='store_true',
                        help='Logout an existing token saved in token.cfg')
    parser.add_argument('--mower', dest='mower',
                        help='Select the mower to use. It can be the name or the id of the mower. If not provied the first mower will be used.')
    parser.add_argument('--log-level', dest='log_level', choices=['INFO', 'ERROR'],
                        help='Display all logs or just in case of error')
    parser.add_argument('--json', action='store_true',
                        help='Enable json output. Logger will be set to "ERROR"')

    args = parser.parse_args()
    if args.password == ask_password:
        import getpass
        args.password = getpass.getpass()

    if args.json:
        args.log_level = 'ERROR'

    config, tokenConfig = create_config(args)
    if not config:
        if args.json:
            as_json(errors=_errors)
        else:
            parser.print_help()
        exit(1)

    configure_log(config)

    if args.logout and tokenConfig.token_valid():
        mow = API()
        mow.set_token(tokenConfig.token, tokenConfig.provider, tokenConfig.user_id)
        mow.logout()
        tokenConfig = TokenConfig()
        tokenConfig.save_config()
    elif args.command == 'server':
        run_server(config, tokenConfig, args)
    else:
        run_cli(config, tokenConfig, args)
        if args.json and _errors:
            as_json(errors=_errors)

    exit(0)