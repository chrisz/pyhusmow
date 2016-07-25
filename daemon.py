from threading import Thread, Lock
from time import sleep, time
from datetime import datetime
import logging
import argparse

from requests.exceptions import HTTPError

from husmow import API

logger = logging.getLogger("main")
logger.setLevel(logging.DEBUG)

formatter = logging.Formatter('%(asctime)s :: %(levelname)s :: %(message)s')
steam_handler = logging.StreamHandler()
steam_handler.setLevel(logging.DEBUG)
logger.addHandler(steam_handler)

logger.info('Logger configured')


class Command:
    START = "START"
    PARK = "PARK"
    STOP = "STOP"


class Status:
    PARKED = "parked"
    CHARGING = "charging"
    MOWING = "mowing"
    SEARCHING = "searching"
    PAUSED = "paused"
    ERROR = "error"
    UNKNOWN = "unknown"


class Automower(Thread):
    def __init__(self, username, password):
        Thread.__init__(self, name="Automower")
        self.daemon = True
        self.logger = logging.getLogger("main.automower")
        self.username = username
        self.password = password
        self.delay = 10
        self.api = API()
        self.lock = Lock()
        self.stop = False
        self.command = None
        self.status = None

    def run(self):
        self.logger.info("I start to supervise your automower...")

        self._connect()

        while True:
            try:
                self._process_status()
            except HTTPError as ex:
                self.logger.warning("Oh! Something goes wrong with "
                                 "Husqvarna server, I will try to "
                                 "reconnect to them")
                self._connect()

            with self.lock:
                if self.stop:
                    break

            # FIXME lock ?
            sleep(self.delay)

        self.logger.info("I leave your automower alone")

    def _connect(self):
        try:
            self.api.login(self.username, self.password)
            self.logger.info("I am connected to Husqvarna server")
        except HTTPError as ex:
            self.logger.warning("I failed to connect to Husqvarna server")

    def _process_status(self):
        data = self.api.status()

        # self.logger.info("Current status: " + str(status))

        last_status_date = datetime.fromtimestamp(
            float(data['mowerInfo']['storedTimestamp'])/1000)

        self.logger.warning("Your automower sent its last status at %s"
                         % last_status_date.strftime("%d/%m/%Y %H:%M:%S"))

        mower_status = data['mowerInfo']['mowerStatus']
        if mower_status == "PAUSED":
            self.logger.info("Your automower is stopped")
            self.status = Status.PAUSED
        elif mower_status in ("OK_CUTTING", "OK_LEAVING", "OK_CUTTING_NOT_AUTO"):
            self.logger.info("Your automower is mowing")
            self.status = Status.MOWING
        elif mower_status == "OK_SEARCHING":
            self.logger.info("Your automower is searching")
            self.status = Status.SEARCHING
        elif mower_status == "OK_CHARGING":
            self.logger.info("Your automower is charging")
            self.status = Status.CHARGING
        elif mower_status == "PARKED_TIMER":
            self.logger.info("Your automower is parked due to timer")
            self.status = Status.PARKED
        elif mower_status == "PARKED_AUTOTIMER":
            self.logger.info("Your automower is parker due to weather timer")
            self.status = Status.PARKED
        elif mower_status in ("PARKED_PARKED_SELECTED", "PARKED_DAILY_LIMIT"):
            self.logger.info("Your automower is parked")
            self.status = Status.PARKED
        elif mower_status in ("ERROR", "ERROR_AT_POWER_UP"):
            self.logger.info("Your automower has a problem")
            self.status = Status.ERROR
        else:
            self.logger.warning("I don't understand your automower status: " + mower_status)
            self.status = Status.UNKNOWN

        self.logger.info("Your automower is at position %s,%s"
                         % (data['mowerInfo']['latitude'], data['mowerInfo']['longitude']))

        self.logger.info("The battery is %s%%", data['mowerInfo']['batteryPercent'])

        last_error_code = int(data['mowerInfo']['lastErrorCode'])
        if last_error_code != 0:
            last_error_date = datetime.fromtimestamp(
                float(data['mowerInfo']['lastErrorCodeTimestamp'])/1000)
            self.logger.warning("Your automower needs your help since %s"
                             % last_error_date.strftime("%d/%m/%Y %H:%M:%S"))

        if self.command is not None:
            if self.status == Status.ERROR:
                self.logger.error("Your automower has a problem, it can't execute the command")
            elif self.status == Status.UNKNOWN:
                self.logger.error("Your automower has a unknown status, it can't execute the command")
            else:
                if self.command == Command.START:
                    if self.status == Status.MOWING:
                        self.logger.info("Command has been applied successfully")
                        self.command = None
                    elif self.status in (Status.SEARCHING, Status.CHARGING):
                        self.logger.info("You automower can't be started now (it is searching or charging)")
                    else:
                        self.api.control("START")
                        self.logger.info("Your automower is starting...")
                elif self.command == Command.STOP:
                    if self.status in (Status.CHARGING, Status.PARKED, Status.PAUSED):
                        self.logger.info("Command has been applied successfully")
                        self.command = None
                    else:
                        self.api.control("STOP")
                        self.logger.info("Your automower is stopping...")
                elif self.command == Command.PARK:
                    if self.status in (Status.CHARGING, Status.PARKED, Status.SEARCHING):
                        self.logger.info("Command has been applied successfully")
                        self.command = None
                    else:
                        self.api.control("PARK")
                        self.logger.info("Your automower is parking...")

    def shutdown(self):
        self.logger.info("Shutdown requested")
        with self.lock:
            self.stop = True

    def control(self, command, timeout=0):
        self.logger.info("Received command: " + command)
        with self.lock:
            self.command = command

        begin = time()
        while time() < begin + timeout:
            if command == Command.START:
                if self.status == Status.MOWING:
                    return True
            elif command == Command.STOP:
                if self.status in (Status.PARKED,
                                   Status.PAUSED,
                                   Status.CHARGING):
                    return True
            else: # PARK
                if self.status in (Status.PARKED,
                                   Status.SEARCHING,
                                   Status.CHARGING):
                    return True

            sleep(self.delay / 2)
        return False

    def get_status(self, timeout=0):
        # FIXME lock
        begin = time()
        while time() < begin + timeout:
            if self.status is not None:
                return self.status
            sleep(self.delay / 2)
        return self.status

    def set_delay(self, new_delay):
        with self.lock:
            self.delay = new_delay


if __name__ == '__main__':

    parser = argparse.ArgumentParser(description='Speak with your automower')
    subparsers = parser.add_subparsers(dest='command')

    parser_control = subparsers.add_parser('control', help='Send command to your automower')
    parser_control.add_argument('action', choices=[Command.START, Command.STOP, Command.PARK],
                                help='the command')
    parser_control.add_argument('--timeout', dest="timeout", type=int, default=60,
                                help='Max time to wait for executing the command')

    parser_status = subparsers.add_parser('status', help='Get the status of your automower')
    parser_status.add_argument('--timeout', dest="timeout", type=int, default=60,
                               help='Max time to wait for getting status')

    parser_monitor = subparsers.add_parser('monitor', help='Monitor the state of your automower')

    parser.add_argument('--login', dest='login', help='Your login', required=True)
    parser.add_argument('--password', dest='password', help='Your password', required=True)

    args = parser.parse_args()

    begin = datetime.now()

    moumou = Automower(args.login, args.password)

    if args.command == 'control':
        moumou.set_delay = 5
        moumou.start()
        if moumou.control(args.action, args.timeout):
            exit(0)
        else:
            exit(1)
    elif args.command == 'status':
        moumou.set_delay = 5
        moumou.start()
        s = moumou.get_status(args.timeout)
        if s is not None:
            print(s)
            exit(0)
        else:
            exit(1)
    elif args.command == 'monitor':
        moumou.start()
        # FIXME loop forever
        sleep(120)

    exit(0)

    moumou.start()

    sleep(10)

    moumou.control(Command.START)

    sleep(600)

    moumou.shutdown()

    moumou.join()
