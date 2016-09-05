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

# Options

To save the login and password in 'automower.cfg' file, you can add the option --save:

    python husmow.py --login yourmaillogin --password yourpassword control PARK

And the next time you run the command, you can omit these information from the command line:

    python husmow.py control PARK

The file 'automower.cfg' is created in the current directory where you run the script and **THE PASSWORD IS STORED IN PLAIN TEXT**.

# Warning
The API and command line are not stable and can change at any time.

# Special Thanks
I thank moumou for mowing my lawn very well !
