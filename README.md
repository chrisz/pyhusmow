# pyhusmow
Control your Husqvarna automower using Automower connect API.

# Requirements
  + python 2 or python 3
  + requests

# Commands
## Read status of your automower
    python husmow.py --login yourmaillogin --password yourpassword status

## Start your automower
    python husmow.py --login yourmaillogin --password yourpassword control START

## Stop your automower
    python husmow.py --login yourmaillogin --password yourpassword control STOP

## Park your automower
    python husmow.py --login yourmaillogin --password yourpassword control PARK

# Warning
The API and command line are not stable and can change at any time.

# Special Thanks
I thank moumou for mowing my lawn very well !
