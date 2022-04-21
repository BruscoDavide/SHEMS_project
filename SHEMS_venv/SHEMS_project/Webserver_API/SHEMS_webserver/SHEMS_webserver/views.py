import json
import logging
import datetime
import os

from argparse import Action
from urllib import response
from django.http.response import HttpResponse
from django.shortcuts import render

commands_path = 'C:\\Users\\davide.brusco\\Documents\\Coding\\SHEMS\\SHEMS_project\\SHEMS_venv\\shems_project\\files\\GUI_thread_commands.json'
data_path = 'C:\\Users\\davide.brusco\\Documents\\Coding\\SHEMS\\SHEMS_project\\SHEMS_venv\\shems_project\\files\\GUI_thread_data.json'

def append_commands(command, flag_payload, payload=None):
    """Once a command is recevied from HTTP protocol, it is written in the GUI_thread_command.json file
    A new dictionary 'data' is appended to the list: 'command_list':[]
    data: {
        'command': command string
        'timestamp': timestamp string (h:m:s)
        'payload': payload dictionary of any
    }

    Args:
        command (string): 'home', 'appliances', 'scheduling', 'changeScheduling', 'summary', 'settings', 'community', 'registration'
    Returns:
        code (string): timestamp (h:m:s)
    """
    commands = ['home', 'appliances', 'scheduling', 'changeScheduling', 'summary', 'settings', 'community', 'registration']
    if command in commands:
        try:
            fp = open(commands_path, 'r')
            file = json.load(fp)
            fp.close()
            
            code = str(datetime.datetime.now()).split('.')[0]
            data = {
                "command": command,
                "timestamp": code
            }
            if flag_payload:
                data['payload']=payload
            file['command_list'].append(data)

            fp = open(commands_path, 'w')
            json.dump(file,fp)
            fp.close()
            return code
        except:
            logging.info('GUI_thread_commands.json error')
    else:
        logging.info('Command error')

def read_data(command, code):
    """Reading response from 'main.py' to a specific command

    Args:
        command (string): 'home', 'appliances', 'scheduling', 'changeScheduling', 'summary', 'settings', 'community', 'registration' 
        code (string): timestamp (h:m:s) when the command is received from the webserver
    Returns:
        dictionary: data response of a specific command
    """
    flag = True
    c = 0
    t = 100 # da testare 
    while flag:
        fp = open(data_path, 'r')
        file = json.load(fp)
        fp.close()
        
        try:
            data = file['responses'][code]
            del file['response'][code]
            fp = open(data_path, 'w')
            json.dump(file, fp)
            fp.close()

            flag = False

            return data
        except:
            c += 1
            if c==t:
                logging.info('Command request cannot be satisfy: error "code" or "main.py" offline') 
                flag = False
                return 'Command request cannot be satisfy: error "code" or "main.py" offline'
                
def home(request):
    """Application home page 

    Args:
        request (HTTP request): GET request
    Returns:
        HttpResponse object
    """
    code = append_commands(command='home', flag_payload=False)
    data = read_data(command='home', code=code)
    return HttpResponse(data)
        
def scheduling(request):
    """ Actual appliances scheduling

    Args:
        request (HTTP request): GET request
    Returns:
        HttpResponse object
    """
    code = append_commands(command='scheduling', flag_payload=False)
    data = read_data(command='scheduling', code=code)
    return HttpResponse(data)

def changeScheduling(request):
    """ Change the schedule of one appliance, it requires when move the schedule and which appliance will be moved
        when = -1 it means now
    Args:
        request (HTTP request): POST request
        POST body:
        {
            "which":"",
            "when":""            
        }
    Returns:
        HttpResponse object
    """
    try:
        payload = {}
        payload['start_time'] = request.POST['when']
        payload['appliance'] = request.POST['which']
        code = append_commands(command='changeScheduling', flag_payload=True, payload=payload)
        data = read_data(command='changeScheduling', code=code)
        return HttpResponse(data)
    except:
        return HttpResponse('Error "which" or "when" field missing')

def summary(request):
    """Provide statistic plots data

    Args:
        request (HTTP request): GET request
        SHEMS/summary?period=day&object=power
    Returns:
        HttpResponse object
    """
    try:
        payload = {}
        payload['when'] = request.GET['period']
        payload['which'] = request.GET['object']
        append_commands(command='summary', flag_payload=True, payload=payload)
        data = read_data(command='summary')
        return HttpResponse(data)
    except:
        return HttpResponse('Error "which" or "when" field missing')

def settings(request):
    """ Allows to update or change home configuration setpoints, delete or add home appliances 

    Args:
        request (HTTP request): POST request
        {
            action
            appliance
            new_value
            applianceData
        }
    Returns:
        HttpResponse object
    """
    if request.POST['action'] == 'changeSetpoints':
        try:
            payload = {}
            payload['appliance'] = request.POST['object']
            payload['new_value'] = request.POST['new_value']
            code = append_commands(command='changeSetpoints', flag_payload=True, payload=payload)
            data = read_data(command='changeSetpoints')
            return HttpResponse(data)
        except:
            return HttpResponse('Error "action" or "new_value" field missing')
    elif request.POST['action'] == 'addAppliances':
        try:
            payload = {}
            payload = request.POST['applianceData']
            code = append_commands(command='change_setpoints', flag_payload=True, payload=payload)
            data = read_data(command='addAppliances')
            return HttpResponse(data)
        except:
            return HttpResponse('Error "applianceData" field missing')
    elif request.POST['action'] == 'deleteAppliances':
        try:
            payload = {}
            payload = request.POST['applianceData']
            data = append_commands(command='delete_appliances', flag_payload=True, payload=payload)
            data = read_data(command='deleteAppliances')
            return HttpResponse(data)
        except:
            return HttpResponse('Error "applianceData" field missing')
    else:
        return HttpResponse('Error "action" field missing or wrong')

def community(request):
    """Statistical information about prosumer community

    Args:
        request (HTTP request): GET request
    Returns:
        HttpResponse object
    """
    try:
        payload = {}
        payload['period'] = request.GET['period']
        payload['object'] = request.GET['object']
        code = append_commands(command='community', flag_payload=True, payload=payload)
        data = read_data(command='community', code=code)
        return HttpResponse(data)
    except:
        return HttpResponse('Error "period" or "object" field missing')

def registration(request):
    """Home registration in the system

    Args:
        request (HTTP request): POST request
        {"setpoints":[{"object":"", "new_value":""},{....}],
        "EV":{"time":"8:00","minum":"0.30"} # from 0.10 to 1
        "applianceData":["","",""]
        }
    Returns:
        HttpResponse object
    """
    try:
        payload = {}
        payload['EV'] = request.POST['EV']
        payload['setpoints'] = request.POST['setpoints']
        payload['appliances'] = request.POST['applianceData']
        code = append_commands(command='registration', flag_payload=True, payload=payload)
        data = read_data(command='registration', code=code)
        return HttpResponse(data)
    except:
        return HttpResponse('Error "new_home" field missing')