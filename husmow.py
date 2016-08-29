import requests
import argparse
import pprint

from configparser import ConfigParser


class AutoMowerConfig(ConfigParser):
    def __init__(self):
        super(AutoMowerConfig, self).__init__()
        self['husqvarna.net'] = {}

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


class API:
    _API_IM = 'https://tracker-id-ws.husqvarna.net/imservice/rest/'
    _API_TRACK = 'https://tracker-api-ws.husqvarna.net/services/'
    _HEADERS = {'Accept': 'application/json', 'Content-type': 'application/xml'}

    def __init__(self):
        self.session = requests.Session()
        self.device_id = None
        self.push_id = None

    def login(self, login, password):
        request = ("<login>"
                   "  <email>%s</email>"
                   "  <password>%s</password><language>fr-FR</language>"
                   "</login>") % (login, password)
        response = self.session.post(self._API_IM + 'im/login',
                                     data=request, headers=self._HEADERS)

        response.raise_for_status()
        print('Logged in successfully')

        self.session.headers.update({'Session-Token': response.headers['Session-Token']})

        self.select_first_robot()

    def logout(self):
        response = self.session.post(self._API_IM + 'im/logout')
        response.raise_for_status()
        self.device_id = None
        del (self.session.headers['Session-Token'])
        print('Logged out successfully')

    def list_robots(self):
        response = self.session.get(self._API_TRACK + 'pairedRobots_v2', headers=self._HEADERS)
        response.raise_for_status()

        return response.json()

    def select_first_robot(self):
        result = self.list_robots()
        self.device_id = result['robots'][0]['deviceId']

    def status(self):
        response = self.session.get(self._API_TRACK + 'robot/%s/status_v2/' % self.device_id, headers=self._HEADERS)
        response.raise_for_status()

        return response.json()

    def geo_status(self):
        response = self.session.get(self._API_TRACK + 'robot/%s/geoStatus/' % self.device_id, headers=self._HEADERS)
        response.raise_for_status()

        return response.json()

    def get_mower_settings(self):
        request = ("<settings>"
                   "    <autoTimer/><gpsSettings/><drivePastWire/>"
                   "    <followWireOut><startPositionId>1</startPositionId></followWireOut>"
                   "    <followWireOut><startPositionId>2</startPositionId></followWireOut>"
                   "    <followWireOut><startPositionId>3</startPositionId></followWireOut>"
                   "    <followWireOut><startPositionId>4</startPositionId></followWireOut>"
                   "    <followWireOut><startPositionId>5</startPositionId></followWireOut>"
                   "    <followWireIn><loopWire>RIGHT_BOUNDARY_WIRE</loopWire></followWireIn>"
                   "    <followWireIn><loopWire>GUIDE_1</loopWire></followWireIn>"
                   "    <followWireIn><loopWire>GUIDE_2</loopWire></followWireIn>"
                   "    <followWireIn><loopWire>GUIDE_3</loopWire></followWireIn>"
                   "    <csRange/>"
                   "    <corridor><loopWire>RIGHT_BOUNDARY_WIRE</loopWire></corridor>"
                   "    <corridor><loopWire>GUIDE_1</loopWire></corridor>"
                   "    <corridor><loopWire>GUIDE_2</loopWire></corridor>"
                   "    <corridor><loopWire>GUIDE_3</loopWire></corridor>"
                   "    <exitAngles/><subareaSettings/>"
                   "</settings>")
        response = self.session.post(self._API_TRACK + 'robot/%s/settings/' % self.device_id,
                                     data=request, headers=self._HEADERS)
        response.raise_for_status()

        return response.json()

    def settingsUUID(self):
        response = self.session.get(self._API_TRACK + 'robot/%s/settingsUUID/' % self.device_id, headers=self._HEADERS)
        response.raise_for_status()

        result = response.json()
        return result

    def control(self, command):
        if command not in ['PARK', 'STOP', 'START']:
            raise Exception("Unknown command")

        request = ("<control>"
                   "   <action>%s</action>"
                   "</control>") % command

        response = self.session.put(self._API_TRACK + 'robot/%s/control/' % self.device_id,
                                    data=request, headers={'Content-type': 'application/xml'})
        response.raise_for_status()

    def add_push_id(self, id):
        request = "id=%s&platform=iOS" % id
        response = self.session.post(self._API_TRACK + 'addPushId', data=request,
                                     headers={'Content-type': 'application/x-www-form-urlencoded; charset=UTF-8'})
        response.raise_for_status()
        self.push_id = id

    def remove_push_id(self):
        request = "id=%s&platform=iOS" % id
        response = self.session.post(self._API_TRACK + 'removePushId', data=request,
                                     headers={'Content-type': 'application/x-www-form-urlencoded; charset=UTF-8'})
        response.raise_for_status()
        self.push_id = None


def create_config(args):
    config = AutoMowerConfig()
    if args.login and args.password:
        config.login = args.login
        config.password = args.password
        if not config.save_config():
            print('Could not save configuration.')
    else:
        if not config.load_config():
            print('Could not read configuration. Please provide login and password.')
            config = None
    return config


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Speak with your automower')
    subparsers = parser.add_subparsers(dest='command')

    parser_control = subparsers.add_parser('control', help='Send command to your automower')
    parser_control.add_argument('action', choices=['STOP', 'START', 'PARK'],
                                help='the command')

    parser_status = subparsers.add_parser('status', help='Get the status of your automower')

    parser.add_argument('--login', dest='login', help='Your login')
    parser.add_argument('--password', dest='password', help='Your password')

    args = parser.parse_args()

    config = create_config(args)
    if not config:
        parser.print_help()
        exit(1)

    retry = 5
    pp = pprint.PrettyPrinter(indent=4)
    while retry > 0:
        try:
            mow = API()

            mow.login(config.login, config.password)

            if args.command == 'control':
                mow.control(args.action)
            elif args.command == 'status':
                pp.pprint(mow.status())

            retry = 0
        except Exception as ex:
            retry -= 1
            if retry > 0:
                print(ex)
                print("[ERROR] Retrying to send the command %d" % retry)
            else:
                print("[ERROR] Failed to send the command")
                exit(1)

    print("Done")

    mow.logout()

    exit(0)