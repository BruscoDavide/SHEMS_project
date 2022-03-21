# SHEMS_project

Hi, i will try to explain you the folder and project organization

SHEMS_venv is a virtual environment, created with the python function 'virtualenv': inside it, only SHEMS_project is useful, the others folders are only configuration file. Could be useful from command line type inside SHEMS_venv: >.\Scripts\activate in order to activate the vitutal environment.

SHEMS_project try to copy the softaware structure shown in the presentation, lots of folders need to be modify but for this could be a starting point. The folders are: GUI, MMOngoDB, Optimization_model, Prosumer_community, Sensors_actuators_smart_meter, Statistics, Webserver_API. Except for Webserver_API the others folder should contain only classes, the main files are instead: main.py, prosumer_comm.py. There is also a folder call 'Examples' with some example code inside, temporary folder.
