# pyhusmow

*This repository is no longer maintained. Husqvarna provides an official api now, you can easily use it: https://developer.1689.cloud/apis/Automower+Connect+API*

Control your Husqvarna automower using Automower connect API.

## For french people

Si vous n'avez pas encore acheté votre automower, n'hésitez pas à me contacter via le site des ambassadeurs Husqvarna pour obtenir un chèque cadeau de 150 euros : https://www.lesambassadeurshusqvarna.fr/ambassadeur-3202.html

(Et j'aurai moi aussi une récompense qui me motivera à maintenir ce projet ;-) )

# Requirements
  + python 3
  + requests
  + python-dateutil

# One way to configure the environment to run pyhusmow

pyhusmow requires a recent version of requests so you can use virtualenv to install dependencies without modifying your system:

    virtualenv -p python3 husmow_venv
    source husmow_venv/bin/activate
    pip3 install pyhusmow
    husmow --help
    husmow_logger --help

Then you can run pyhusmow without loading the virtual environment explicitly:

    ./husmow_venv/bin/husmow --help

# Commands
## Read status of your automower
    husmow --login yourmaillogin --password yourpassword status

## Start your automower
    husmow --login yourmaillogin --password yourpassword control START

## Stop your automower
    husmow --login yourmaillogin --password yourpassword control STOP

## Park your automower
    husmow --login yourmaillogin --password yourpassword control PARK

# Run HTTP server

You can run a tiny webserver to command your automower using HTTP commands (can be useful for home automation boxes...):

    husmow --login yourmaillogin --password yourpassword server

Then you can use GET requests to:
* start your automower: `http://127.0.0.1:1234/start`
* stop your automower: `http://127.0.0.1:1234/stop`
* park your automower: `http://127.0.0.1:1234/park`
* get the status of your automower: `http://127.0.0.1:1234/status` returns status as json in the response body

All of these HTTP requests return 200 if the command was successfully sent to Husqvarna server and 500 in case of problem.

You can change the IP address or port using options `--address` and `--port` but **you shouldn't open this server outside of you local network** because this tiny server is not designed to be as secure as common web server.

    husmow --login yourmaillogin --password yourpassword server --address 0.0.0.0 --port 2345

To avoid sending too much status requests to Husqvarna server, status is not refreshed before 30 seconds (can be configured using `--expire` option in seconds).

# Save configuration in configuration file

You can save `login`, `password`, `output_format`, `log_level` in `automower.cfg` in the directory where you run this script to omit these information from the command line for the next run.

To save information, just type your command with all information and add the option `--save` to command line:

    husmow --login yourmaillogin --password yourpassword --log-level INFO --save control PARK

And the next time you run the command, you can omit these information from the command line:

    husmow control PARK

The file 'automower.cfg' is created in the current directory where you run the script and **THE PASSWORD IS STORED IN PLAIN TEXT**.

# Warning
The API and command line are not stable and can change at any time.

# Contributors
* rost314 ([@rost314](https://github.com/rost314))
* Federico Caselli ([@CaselIT](https://github.com/CaselIT))
* Jan Schulz-Hofen ([@yeah](https://github.com/yeah))

# Special Thanks
I thank moumou for mowing my lawn very well !
