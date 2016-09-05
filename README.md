# pyhusmow
Control your Husqvarna automower using Automower connect API.

# Requirements
  + python 3
  + requests
  + (optional) dicttoxml if you want xml format for `status` command

# Commands
## Read status of your automower
    python husmow.py --login yourmaillogin --password yourpassword status

## Start your automower
    python husmow.py --login yourmaillogin --password yourpassword control START

## Stop your automower
    python husmow.py --login yourmaillogin --password yourpassword control STOP

## Park your automower
    python husmow.py --login yourmaillogin --password yourpassword control PARK

# Save configuration in configuration file

You can save `login`, `password`, `output_format`, `log_level` in `automower.cfg` in the directory where you run this script to omit these information from the command line for the next run.

To save information, just type your command with all information and add the option `--save` to command line:

    python husmow.py --login yourmaillogin --password yourpassword --log-level INFO control PARK

And the next time you run the command, you can omit these information from the command line:

    python husmow.py control PARK

The file 'automower.cfg' is created in the current directory where you run the script and **THE PASSWORD IS STORED IN PLAIN TEXT**.

## XML output

If you want to print output of `status` command using XML format, you need to install the module `dicttoxml` and add option `--output-format XML` to command line. You should be interested to use the option '--log-level ERROR' to remove execution information from output.

# Warning
The API and command line are not stable and can change at any time.

# Contributors
* rost314 ([@rost314](https://github.com/rost314))

# Special Thanks
I thank moumou for mowing my lawn very well !
