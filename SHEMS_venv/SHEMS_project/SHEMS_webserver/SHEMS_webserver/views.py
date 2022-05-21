import json
import logging
import datetime
import time

from urllib import response
from django.db import DatabaseError
from django.http.response import HttpResponse
from django.shortcuts import render

fp = open('C:/Users/davide.brusco/Documents/Coding/SHEMS/SHEMS_project/SHEMS_venv/SHEMS_project/central_unit/files/starting_configuration.json')
data = json.load(fp)
fp.close()
commands_path = data['webserver_commands_path']
data_path = data['webserver_data_path']

append_commands_error = 0
read_data_error = 0


def append_commands(command, flag_payload, payload=None):
    """Once a command is recevied from HTTP protocol, it is written in the GUI_thread_command.json file
    A new dictionary 'data' is appended to the list: 'command_list':[]
    data: {
        'command': command string
        'timestamp': timestamp string (h:m:s)
        'payload': payload dictionary of any
    }

    Args:
        command (string): 'home', 'appliances', 'scheduling', 'changeScheduling', 'summary', 'settings', 'communityPlots', 'communityProsumers', 'registration', 'listDevice', 'oldParameters'
        flag_payload (boolean)
        payload (dict, None)
    Returns:
        code (string): timestamp (h:m:s)
    """
    logging.info('append_commands')

    commands = ['home', 'appliances', 'scheduling', 'changeScheduling', 'summary', 'settings', 'changeSetpoints', 'deleteAppliances', 'addAppliances'
                'communityPlots', 'communityProsumers', 'registration', 'listDevice', 'oldParameters']
    if command in commands:
        try:
            fp = open(commands_path)
            file = json.load(fp)
            fp.close()

            code = str(datetime.datetime.now()).split('.')[0]
            data = {
                "command": command,
                "timestamp": code
            }
            if flag_payload: data['payload'] = payload
            file['commands_list'].append(data)

            fp = open(commands_path, 'w')
            json.dump(file, fp)
            fp.close() 
            return code

        except:
            append_commands_error += 1
            if append_commands_error > 3:
                fp = open(commands_path)
                file = json.load(fp)
                fp.close
                file = {"commands_list": []}
                with open(commands_path, 'w') as outfile:
                    json.dump(file, outfile)

                fp = open(data_path)
                file = json.load(fp)
                fp.close
                file = {"responses": {}}
                with open(data_path, 'w') as outfile:
                    json.dump(file, outfile)
            
            logging.warning('Appending error, GUI_thread_data.json, GUI_thread_commands.json resetted')
            return None


def read_data(code):
    """Reading response from 'main.py' to a specific command

    Args:
        code (string): timestamp (h:m:s) when the command is received from the webserver
    Returns:
        dictionary: data response of a specific command
    """
    logging.info('read_data')

    flag = True
    c = 0
    t = 1000000  # tested

    while flag:
        try:
            fp = open(data_path)
            file = json.load(fp)
            fp.close()

            response = file['responses'][str(code)]
            del file['responses'][str(code)]
            flag = False
            
            fp = open(data_path, 'w')
            if len(file['responses']) > 3:
                file = {'responses':{}}
                json.dump(file, fp)
            else:
                json.dump(file, fp)
            fp.close()

            break
        except:
            c += 1
            if c == t:
                flag = False
    
    if c == t:
        read_data_error += 1
        if read_data_error > 3:
            fp = open(commands_path)
            file = json.load(fp)
            fp.close
            file = {"commands_list": []}
            with open(commands_path, 'w') as outfile:
                json.dump(file, outfile)

            fp = open(data_path)
            file = json.load(fp)
            fp.close
            file = {"responses": {}}
            with open(data_path, 'w') as outfile:
                json.dump(file, outfile)
        
        return 'Read data error, GUI_thread_data.json, GUI_thread_commands.json resetted'

    else:
        logging.info('Operation complete')
        return response


def home(request):
    """Application home page 

    Args:
        request (HTTP request): GET request
    Returns:
        HttpResponse object
    """
    logging.info('home')

    s = time.time()
    code = append_commands(command='home', flag_payload=False)
    if code != None:
        data = read_data(code=code)
        logging.info(data)
    else:
        data = {}
        data['message'] = 'Appending error, GUI_thread_data.json, GUI_thread_commands.json resetted'
        data['responseFlag'] = 'False'
        logging.info(data)
    e = time.time()
    logging.info(f'"home" timing {s-e}')

    return HttpResponse(str(data))


def scheduling(request):
    """ Actual appliances scheduling

    Args:
        request (HTTP request): GET request
    Returns:
        HttpResponse object
    """
    logging.info('scheduling')

    s = time.time()
    code = append_commands(command='scheduling', flag_payload=False)
    if code != None:
        data = read_data(code=code)
        logging.info(data)
    else:
        data = {}
        data['message'] = 'Appending error, GUI_thread_data.json, GUI_thread_commands.json resetted'
        data['responseFlag'] = 'False'
        logging.info(data)
    e = time.time()
    logging.info(f'"scheduling" timing {s-e}')

    return HttpResponse(str(data))


def listDevice(request):
    """ List of actual appliances scheduling

    Args:
        request (HTTP request): GET request
    Returns:
        HttpResponse object
    """
    logging.info('listDevice')

    s = time.time()
    code = append_commands(command='listDevice', flag_payload=False)
    if code != None:
        data = read_data(code=code)
        data['responseFlag'] = 'True'
        logging.info(data)
    else:
        data = {}
        data['message'] = 'Appending error, GUI_thread_data.json, GUI_thread_commands.json resetted'
        data['responseFlag'] = 'False'
        logging.info(data)
    e = time.time()
    logging.info(f'"listDevice" timing {s-e}')

    return HttpResponse(str(data))


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
    logging.info('changeScheduling')
    
    try:
        s = time.time()
        data = json.loads(request.body)
        payload = {}
        payload['start_time'] = data['when']
        payload['appliance'] = data['which']
        logging.info(f'Received data: {payload}')

        code = append_commands(command='changeScheduling', flag_payload=True, payload=payload)
        if code != None:
            data = read_data(code=code)
            data['responseFlag'] = 'True'
            logging.info(data)
        else:
            data = {}
            data['message'] = 'Appending error, GUI_thread_data.json, GUI_thread_commands.json resetted'
            data['responseFlag'] = 'False'
            logging.info(data)
        e = time.time()
        logging.info(f'"changeScheduling" timing {s-e}')

        return HttpResponse(str(data))
    except:
        logging.error('Error "which" or "when" field missing - changeSchduling request')
        return HttpResponse(str({'message': 'Error "which" or "when" field missing'}))


def summary(request):
    """Provide statistic plots data

    Args:
        request (HTTP request): GET request
        SHEMS/summary?period=day&object=power
    Returns:
        HttpResponse object
    """
    logging.info('summary')

    try:
        s = time.time()
        payload = {}
        payload['start_time'] = request.GET['period']
        payload['appliance'] = request.GET['object']
        logging.info(f'Recevived data: {payload}')

        code = append_commands(command='summary', flag_payload=True, payload=payload)
        if code != None:
            data = read_data(code=code)
            data['responseFlag'] = 'True'
            logging.info(data)
        else:
            data = {}
            data['message'] = 'Appending error, GUI_thread_data.json, GUI_thread_commands.json resetted'
            data['responseFlag'] = 'False'
            logging.info(data)
        e = time.time()
        logging.info(f'"summary" timing {s-e}')
        
        return HttpResponse(str(data))
    except:
        logging.error('Error "object" or "period" field missing - summary request')
        return HttpResponse(str({'message': 'Error "period" or "object" field missing'}))


def oldParameters(request):
    """ List of actual home parameters

    Args:
        request (HTTP request): GET request
    Returns:
        HttpResponse object
    """
    logging.info('oldParameters')

    s = time.time()
    code = append_commands(command='oldParameters', flag_payload=False)
    if code != None:
        data = read_data(code=code)
        data['responseFlag'] = 'True'
        logging.info(data)
    else:
        data = {}
        data['message'] = 'Appending error, GUI_thread_data.json, GUI_thread_commands.json resetted'
        data['responseFlag'] = 'False'
        logging.info(data)
    e = time.time()
    logging.info(f'"oldParameters" timing {s-e}')
    
    return HttpResponse(str(data))


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
    logging.info('settings')

    s = time.time()
    data = json.loads(request.body)
    logging.info(f'Received data: {data}')

    if data['action'] == 'changeSetpoints':
        try:
            payload = {}
            payload['new_values'] = data['new_values']

            code = append_commands(command='changeSetpoints', flag_payload=True, payload=payload)
            if code != None:
                data = read_data(code=code)
                data['responseFlag'] = 'True'
                logging.info(data)
            else:
                data = {}
                data['message'] = 'Appending error, GUI_thread_data.json, GUI_thread_commands.json resetted'
                data['responseFlag'] = 'False'
                logging.info(data)
            e = time.time()
            logging.info(f'"settings" timing {s-e}')

            return HttpResponse(str(data))
        except:
            logging.error('Error "new_values" field missing - changeSetpoints request')
            return HttpResponse(str({'message': 'Error "action" or "new_value" field missing'}))

    elif data['action'] == 'addAppliances':
        try:
            payload = {}
            payload = data['applianceData']
            """
            {applianceData: {
                name: name_object,
                power_cons: # potenza istantanea
                running_length: # minutes...
            }}
                num_cycles:
                c1 = 1 
                c2 = 2
            }} 
            """
            code = append_commands(command='addAppliances', flag_payload=True, payload=payload)
            if code != None:
                data = read_data(code=code)
                data['responseFlag'] = 'True'
                logging.info(data)
            else:
                data = {}
                data['message'] = 'Appending error, GUI_thread_data.json, GUI_thread_commands.json resetted'
                data['responseFlag'] = 'False'
                logging.info(data)
            e = time.time()
            logging.info(f'"settings" timing {s-e}')

            return HttpResponse(str(data))
        except:
            logging.error('Error "applianceData" field missing - addAppliances request')
            return HttpResponse(str({'message': 'Error "applianceData" field missing'}))

    elif data['action'] == 'deleteAppliances':
        try:
            payload = {}
            payload = data['applianceData']
            
            data = append_commands(command='deleteAppliances', flag_payload=True, payload=payload)
            if code != None:
                data = read_data(code=code)
                data['responseFlag'] = 'True'
                logging.info(data)
            else:
                data = {}
                data['message'] = 'Appending error, GUI_thread_data.json, GUI_thread_commands.json resetted'
                data['responseFlag'] = 'False'
                logging.info(data)
            e = time.time()
            logging.info(f'"settings" timing {s-e}')

            return HttpResponse(str(data))
        except:
            logging.error('Error "applianceData" field missing - deleteAppliances request')
            return HttpResponse(str({'message': 'Error "applianceData" field missing'}))
    else:
        return HttpResponse(str({'message': 'Error "action" field missing or wrong'}))


def communityPlots(request):
    """Statistical information about prosumer community

    Args:
        request (HTTP request): GET request
    Returns:
        HttpResponse object
    """
    logging.info('communityPlots')

    try:
        s = time.time()
        payload = {}
        payload['when'] = request.GET['period']
        payload['which'] = request.GET['object']

        code = append_commands(command='communityPlots', flag_payload=True, payload=payload)
        if code != None:
            data = read_data(code=code)
            data['responseFlag'] = 'True'
            logging.info(data)
        else:
            data = {}
            data['responseFlag'] = 'False'
            data['message'] = 'Appending error, GUI_thread_data.json, GUI_thread_commands.json resetted'
            logging.info(data)
        e = time.time()
        logging.info(f'"communityPlots" timing {s-e}')
        return HttpResponse(str(data))
    except:
        logging.error('"period" or "object" field missing - communityPlots request')
        return HttpResponse(str({'message': 'Error "period" or "object" field missing'}))


def communityProsumers(request):
    """Statistical information about prosumer community

    Args:
        request (HTTP request): GET request
    Returns:
        HttpResponse object
    """
    logging.info('communityProsumers')

    s = time.time()
    code = append_commands(command='communityProsumers', flag_payload=True)
    if code != None:
        data = read_data(code=code)
        data['responseFlag'] = 'True'
        logging.info(data)
    else:
        data = {}
        data['responseFlag'] = 'False'
        data['message'] = 'Appending error, GUI_thread_data.json, GUI_thread_commands.json resetted'
        logging.info(data)
    e = time.time()
    logging.info(f'"communityProsumer" timing {s-e}')
    
    return HttpResponse(str(data))


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
    logging.info('registration')

    try:
        s = time.time()
        data = json.loads(request.body)
        logging.info(f'Receiveed data: {data}')

        payload = {}
        payload['family_name'] = data['family_name']
        payload['EV'] = data['EV']
        payload['setpoints'] = data['setpoints']
        payload['applianceData'] = data['applianceData']
        payload['home_batteries'] = data['home_batteries']
        code = append_commands(command='registration', flag_payload=True, payload=payload)
        if code != None:
            data = read_data(code=code)
            data['responseFlag'] = 'True'
            logging.info(data)
        else:
            data = {}
            data['responseFlag'] = 'False'
            data['message'] = 'Appending error, GUI_thread_data.json, GUI_thread_commands.json resetted'
            logging.info(data)
        e = time.time()
        logging.info(f'"registration" timing {s-e}')

        return HttpResponse(str(data))
    except:
        logging.error('Error new home field missing - registration request')
        return HttpResponse(str({'message': 'Error new home field missing'}))