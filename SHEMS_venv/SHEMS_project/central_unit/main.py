import json
import math
import logging
import requests
import datetime
import numpy as np
from zmq import EVENT_CLOSE_FAILED

from utilities.timer import perpetualTimer
from utilities.mqttclient import MQTTSubscriber
from mongoDB.database_client import databaseClient
from optimizationModel.Simulator.instance import Instance
from optimizationModel.LP_solver.SHEMSModel import SHEMS
from prosumerCommunity.prosumerMarket import Prosumer

class SHEMS_main(): 
    def __init__(self, cfg):
        """SHEMS system object. It includes the instance of the energy optimization toll, 
        the instance of the MQTT subscriber and publisher and the instance of the push notificator

        Args:
            cfg (dict): configuration file
        """
        logging.info('__init__')
        try:
            self.coin = 't'
            self.c = 0

            self.time_granularity = cfg['time_granularity']
            self.commands_path = cfg['commands_path']
            self.data_path = cfg['data_path']
            self.push_path = cfg['push_path']

            self.databaseClient = databaseClient()
            self.__reset()
            # Energy optimization model
            self.instance = Instance()
            self.model = False

            # Sensors subscriber MQTT
            self.waterWithdrawn_topic = cfg['waterWithdrawn_topic']
            self.carStation_topic = cfg['carStation_topic']
            self.smartMeter_topic = cfg['smartMeter_topic']
            self.deviceID = str(np.random.randint(1000000000))
            self.broker = cfg['mqtt_broker']
            self.port = cfg['mqtt_port']
            try:
                self.sensors_subscriber = MQTTSubscriber(self.deviceID, self.broker, self.port)
                self.sensors_subscriber.start()
                self.sensors_subscriber.callbackRegistration(self.__sensorsSubscriber_callback)
                self.sensors_subscriber.mySubscribe(self.waterWithdrawn_topic)
                self.sensors_subscriber.mySubscribe(self.carStation_topic)
                self.sensors_subscriber.mySubscribe(self.smartMeter_topic)
            except:
                logging.warning('Possible internet connection problem')

            # Weather forecast API
            self.city = cfg['home_city']
            self.country_code = cfg['country_code']
            self.BASE_URL2 = cfg['BASE_URL2']
            self.API_KEY = cfg['API_KEY']
            limit = 1
            try:
                url = f"http://api.openweathermap.org/geo/1.0/direct?q={self.city},{self.country_code}&limit={limit}&appid={self.API_KEY}"
                response = requests.get(url)
                if response.status_code == 200:
                    self.lat = int(response.json()[0]['lat'])
                    self.lon = int(response.json()[0]['lon'])
                else:
                    logging.error(f'Error weather API: {response.status_code}')
            except:
                logging.warning('Possible internet connection problem')

            logging.info('Environment generation done, SHEMS model not active')
        except:
            logging.warning('Environment generation failed')

    def __basicScheduling_thread_callback(self):
        """First day scheduling, done at 8:00 a.m. 
        """
        logging.info('__basicScheduling_thread_callback')
        self.__weatherAPI()

        if self.model:
            code = 1
            obj = self.databaseClient.read_documents(collection_name='home_configuration', document={'_id': 0})
            obj['home_setpoints']['Tin_out'] = self.shems.Tin_out[-1]
            obj['home_setpoints']['Tewh_out'] = self.shems.Tewh_out[-1]
            code = code*self.databaseClient.update_documents(collection_name='home_configuration', document={'_id': 0}, object=obj)

            obj = self.databaseClient.read_documents(collection_name='home_configuration', document={'_id': 3})
            obj['batteries']['Cess_init'] = self.shems.Cess[-1]
            obj['batteries']['Cpev_init'] = self.shems.Cpev[-1]
            code = code*self.databaseClient.update_documents(collection_name='home_configuration', document={'_id': 3}, object=obj)

            self.instance.get_data_serv()
            self.shems.get_new_instance(self.instance)

            cod = self.shems.solve_definitive()
            if cod == 2:
                try:
                    self.__historyData_saving()

                    payload = {'message': 'First scheduling of the day had success'}
                    fp = open(self.push_path)
                    pushes = json.load(fp)
                    fp.close()
                    pushes['pushes'].append(payload)
                    fp = open(self.push_path, 'w')
                    json.dump(pushes, fp)
                    fp.close()

                    logging.info('First scheduling of the day had success')
                except:
                    logging.error('Local websocket server or database error')
            elif cod == -1:

                payload = {'message': 'First scheduling of the day failed, please contact the customer care'}
                fp = open(self.push_path)
                pushes = json.load(fp)
                fp.close()
                payload = {'message': 'SHEMS model not active, please contact the customer care'}
                pushes['pushes'].append(payload)
                fp = open(self.push_path, 'w')
                json.dump(pushes, fp)
                fp.close()

                logging.info('First scheduling of the day failed')

        else:
            logging.warning('SHEMS model not active')
            payload = {'message': 'SHEMS model not active: new scheduling failed, please contact the customer care'}
            fp = open(self.push_path)
            pushes = json.load(fp)
            fp.close()
            pushes['pushes'].append(payload)
            fp = open(self.push_path, 'w')
            json.dump(pushes, fp)
            fp.close()


    def __weatherAPI(self):
        """Open weather map call to retrive temperature forecast for the day. Stores the results in the database
        """
        logging.info('__weatherAPI')
        url = f'{self.BASE_URL2}lat={self.lat}&lon={self.lon}&appid={self.API_KEY}'
        response = requests.get(url)
        # Data interpolation, from API data every 3 hours to model requirement granularity data (self.time_granularity)
        temp = []
        if response.status_code == 200:  # checking the status code of the request
            data = response.json()['list']
            for i in range(8):  # 24/3, data recovering: temperature every 3 hours
                temp.append(round(data[i]['main']['temp']-273, 1))

            new_temp = np.zeros(int(60/self.time_granularity*24))
            step = int(3*60/self.time_granularity)
            for i in range(7):  # 0-6, data every 1 hour
                for j in range(step):  # 0-11
                    if j == 0: new_temp[i*step+j] = temp[i]
                    else: new_temp[i*step + j] = round(temp[i] - j*(temp[i]-temp[i+1])/step, 1)
            new_temp[int(60/self.time_granularity*24)-step] = temp[7]
            if new_temp[int(60/self.time_granularity*24)-step-1] < new_temp[int(60/self.time_granularity*24)-step]:  # increase
                for i in range(step):  # 0-11
                    if i == 0:
                        new_temp[int(60/self.time_granularity*24)-step+i] = new_temp[int(60/self.time_granularity)*24-step] + round((temp[6]-temp[7])/step, 1)
                    elif i != 11:
                        new_temp[int(60/self.time_granularity*24)-step+i] = new_temp[int(60/self.time_granularity*24)-step] + (j+1)*round((temp[6]-temp[7])/step, 1)
                    else:
                        new_temp[int(60/self.time_granularity*24)-step+i] = new_temp[int(60/self.time_granularity*24)-step] + (j)*round((temp[6]-temp[7])/step, 1)
            else:  # decrease
                for i in range(step):  # 0-11
                    if i == 0:
                        new_temp[int(60/self.time_granularity*24)-step+i] = new_temp[int(60/self.time_granularity*24)-step] - round((temp[6]-temp[7])/step, 1)
                    elif i != 11:
                        new_temp[int(60/self.time_granularity*24)-step+i] = new_temp[int(60/self.time_granularity*24)-step] - (j+1)*round((temp[6]-temp[7])/step, 1)
                    else:
                        new_temp[int(60/self.time_granularity*24)-step+i] = new_temp[int(60/self.time_granularity*24)-step] - (j)*round((temp[6]-temp[7])/step, 1)

            """ Solar radiation model:
            from 8 to 15; center = from 1 to 10
            from 14 to 18; center =  from 10 to 1
            from 18 t0 7; center = 0
            """
            new_solarRadiation = []
            center = 1
            std = 0.1
            for i in range(int(60/self.time_granularity*24)):
                if i <= 14*(60/self.time_granularity):
                    center = center + 9/(6*60/self.time_granularity)
                    if center > 10: center = 10
                    new_solarRadiation.append(np.random.normal(loc=center, scale=std))
                elif i <= 18*(60/self.time_granularity):
                    center = center - 9/(4*60/self.time_granularity)
                    if center < 1: center = 1
                    new_solarRadiation.append(np.random.normal(loc=center, scale=std))
                else:
                    new_solarRadiation.append(0)

            data = self.databaseClient.read_documents(collection_name='home_configuration', document={'_id': 1})
            data['outside_measure']['Tout'] = new_temp
            code = self.databaseClient.update_documents(collection_name='home_configuration', document={'_id': 1}, object=data)
            if code == 1: logging.info('Data updated')
            else: logging.error('Database failed')

            data = self.databaseClient.read_documents(collection_name='home_configuration', document={'_id': 5})
            data['energy']['RES_hour_geen'] = new_solarRadiation
            code = self.databaseClient.update_documents(collection_name='home_configuration', document={'_id': 5}, object=data)
            if code == 1: logging.info('Data updated')
            else: logging.error('Database failed')

            logging.info('Weather API call done')
        else:
            logging.error(f'Error weather API: {response.status_code} or database failed')
            payload = {'message': 'Error weather API, possible internet connection failed'}
            fp = open(self.push_path)
            pushes = json.load(fp)
            fp.close()
            pushes['pushes'].append(payload)
            fp = open(self.push_path, 'w')
            json.dump(pushes, fp)
            fp.close()

    def __sensorsSubscriber_callback(self, msg):
        """Subscriber for car station and hot water usage

        Args:
            msg (MQTT msg): 
        """
        logging.info('__sensorsSubscriber_callback')
        if msg.topic == self.waterWithdrawn_topic:
            new_data = msg.payload
            data = self.databaseClient.read_documents(collection_name='home_configuration', document={'_id': 1})
            Wd = data['outside_measure']['Wd']

            time = str(datetime.datetime.now())
            hh = int(time.split(' ')[1].split(':')[0])
            mm = int(time.split(' ')[1].split(':')[1])
            if (hh - 8) > 0: step = int(60/self.time_granularity*(hh - 8) + math.floor(mm/self.time_granularity))
            else: step = int(60/self.time_granularity*(24 - (8 - hh)) + math.floor(mm/self.time_granularity))

            if new_data > Wd[step]:
                Wd[step] = new_data
                data = self.databaseClient.read_documents(collection_name='home_configuration', document={'_id': 1})
                data['outside_measure']['Wd'] = Wd
                code = self.databaseClient.update_documents(collection_name='home_configuration', document={'_id': 1}, object=Wd)
                if code == 1:
                    logging.info('Data updated')
                else:
                    logging.error('Database failed')

            self.instance.get_data_serv()
            self.shems.get_new_instance(self.instance)

            cod = self.shems.solve_definitive()
            if cod == 2:
                try:
                    self.__historyData_saving(step)

                    payload = {'message': 'New schedling performed, hot water used'}
                    fp = open(self.push_path)
                    pushes = json.load(fp)
                    fp.close()
                    pushes['pushes'].append(payload)
                    fp = open(self.push_path, 'w')
                    json.dump(pushes, fp)
                    fp.close()

                    logging.info('New schedling performed, hot water used')
                except:
                    logging.error('Local websocket server error')
            elif cod == -1:
                payload = {'message': 'New scheduling failed. Too much hot water used'}
                fp = open(self.push_path)
                pushes = json.load(fp)
                fp.close()
                pushes['pushes'].append(payload)
                fp = open(self.push_path, 'w')
                json.dump(pushes, fp)
                fp.close()
                logging.warning('New scheduling failed. Too much hot water used')

        elif msg.topic == self.carStation_topic:
            if msg.payload == 1:
                self.shems.set_car_arrival()
                payload = {'message': 'Electric vehicle in the garage'}
                fp = open(self.push_path)
                pushes = json.load(fp)
                fp.close()
                pushes['pushes'].append(payload)
                fp = open(self.push_path, 'w')
                json.dump(pushes, fp)
                fp.close()

            else:
                logging.error('Error in the carStation publisher')

        elif msg.topic == self.smartMeter_topic:
            logging.info('Smart Meter')
            b_rtp = msg.payload
            rtp = str(b_rtp).split('[')[1]
            rtp = rtp.split(']')[0]
            rtps = []
            for i in range(int(60/self.time_granularity*24)):
                rtps.append(float(rtp.split(',')[i]))
            logging.info(rtps)
            
            data = self.databaseClient.read_documents(collection_name='home_configuration', document={'_id': 6})
            data['RTP']['values'] = rtps
            code = self.databaseClient.update_documents('home_configuration', {'_id': 6}, data)
            if code == 1: logging.info('Data updated')
            else: logging.error('Database failed')

            self.__basicScheduling_thread_callback()

        else:
            logging.error(f'Error in the MQTT topic: {msg.topic}')

    def GUI_thread_callback(self):
        """Command manager. It reads the commands from the web server and provide to them a response
        payload = {'command':0/1/2, appliance:[], start_time:[]}
        0 = change setpoint
        1 = modify shcduling
        2: change delete appliance 
        """
        try:
            fp = open(self.commands_path)
            file = json.load(fp)
            fp.close()

            commands = file['commands_list']

            if len(commands) == 0:
                if self.coin == 'c':
                    self.__reset()
                    self.coin = 't'
                else:
                    self.coin == 'c'
            else:
                for c in commands:
                    timestamp = c['timestamp']
                    time = str(timestamp)
                    hh = int(time.split(' ')[1].split(':')[0])
                    mm = int(time.split(' ')[1].split(':')[1])
                    if (hh - 8) > 0: step = int(60/self.time_granularity*(hh - 8) + math.floor(mm/self.time_granularity))
                    else: step = int(60/self.time_granularity*(24 - (8 - hh)) + math.floor(mm/self.time_granularity))
                    logging.info(f'Timestamp = {timestamp}, Step = {step}, command_list = {commands}')

                    if c['command'] == 'home' and self.model:  # on at this moment
                        logging.info('GUI_thread_callback-home')
                        try:
                            data = {}
                            data['listDevices'] = []
                            data['single_values'] = {}
                            for j in range(self.shems.instance.N_sched_appliances):  # columns
                                if self.shems.ud_out[step][j] == 1:
                                    info = self.databaseClient.read_documents(collection_name='home_configuration', document={'_id': 4})
                                    ob = {}
                                    ob['name'] = info['appliances']['sched_appliances']['name'][j]

                                    for i in range(int(60/self.time_granularity*24)-1):  # rows
                                        if i != 0 and self.shems.ud_out[i][j] == 1 and self.shems.ud_out[i-1][j] == 0:
                                            min = i*self.time_granularity
                                            if min % 60 == 0:
                                                hou = i*self.time_granularity/60
                                                min = 0
                                            else:
                                                hou = (min - min%60)/60
                                                min = min - 60*hou
                                            if hou + 8 > 23: hou = (hou+8)-23
                                            else: hou = hou + 8
                                            ob['starting_time'] = str(hou)+':'+str(min) 
                                        
                                        elif self.shems.ud_out[i][j] == 1 and self.shems.ud_out[i+1][j] == 0:
                                            min = i*self.time_granularity
                                            if min % 60 == 0:
                                                hou = int(i*self.time_granularity/60)
                                                min = 0
                                            else:
                                                hou = (min - min%60)/60
                                                min = min - 60*hou
                                            if hou + 8 > 23: hou = (hou+8)-23
                                            else: hou = hou + 8
                                            ob['ending_time'] = str(hou)+':'+str(min) 
                                        else:
                                            pass
                                    data['listDevices'].append(ob)

                            data['single_values']['ESS_battery'] = self.shems.Cess[step]
                            data['single_values']['EV_battery'] = self.shems.Cpev[step]
                            data['single_values']['consumption'] = self.shems.Phouse_consume[step]

                            self.__append_data(code=timestamp, data=data)

                            logging.info('"Home" GET request performed')
                        except:
                            logging.error('"Home" GET request failed')

                    elif c['command'] == 'scheduling' and self.model:
                        logging.info('GUI_thread_callback-scheduling')
                        try:
                            data = {}
                            data['scheduling'] = []
                            for j in range(self.shems.instance.N_sched_appliances):  # columns
                                ob = {}
                                ob['data'] = []
                                info = self.databaseClient.read_documents(collection_name='home_configuration', document={'_id': 4})
                                ob['name'] = info['appliances']['sched_appliances']['name'][j]
                                for i in range(int(60/self.time_granularity*24-1)):  # rows
                                    if i != 0 and self.shems.ud_out[i][j] == 1 and self.shems.ud_out[i-1][j] == 0:
                                        min = i*self.time_granularity
                                        if min % 60 == 0:
                                            hou = int(i*self.time_granularity/60)
                                            min = 0
                                        else:
                                            hou = int((min - min%60)/60)
                                            min = min - 60*hou
                                        if hou + 8 > 23: hou = (hou+8)-23
                                        else: hou = hou + 8
                                        ob['start'] = str(hou)+':'+str(min)
                                        ob['data'].append(1)
                                    elif self.shems.ud_out[i][j] == 1 and self.shems.ud_out[i+1][j] == 0:
                                        end = i
                                        min = i*self.time_granularity
                                        if min % 60 == 0:
                                            hou = int(i*self.time_granularity/60)
                                            min = 0
                                        else:
                                            hou = int((min - min%60)/60)
                                            min = min - 60*hou
                                        if hou + 8 > 23: hou = (hou+8)-23
                                        else: hou = hou + 8
                                        ob['end'] = str(hou)+':'+str(min) 
                                        ob['data'].append(1)
                                        
                                        done = 0
                                        if end <= step:
                                            done = 1
                                        ob['done'] = done

                                    elif self.shems.Tewh_out[i] == 1:
                                        ob['data'].append(1)
                                    else:
                                        ob['data'].append(0)

                                    try:
                                        min = i*self.time_granularity
                                        if min % 60 == 0:
                                            hou = int(i*self.time_granularity/60)
                                            if hou + 8 > 23: hou = (hou+8)-23
                                            else: hou = hou + 8
                                            ob['label'].append(str(hou))
                                        else:
                                            hou1 = int((min - min%60)/60)
                                            if hou1 + 8 > 23: hou = (hou1+8)-23
                                            else: hou = hou1 + 8
                                            ob['label'].append(str(hou)+":"+str(min-hou1*60))
                                    except:
                                        ob['label'] = []
                                        
                                        min = i*self.time_granularity
                                        if min % 60 == 0:
                                            hou = int(i*self.time_granularity/60)
                                            if hou + 8 > 23: hou = (hou+8)-23
                                            else: hou = hou + 8
                                            ob['label'].append(str(hou))
                                        else:
                                            hou1 = int((min - min%60)/60)
                                            if hou + 8 > 23: hou = (hou1+8)-23
                                            else: hou = hou1 + 8
                                            ob['label'].append(str(hou)+":"+str(min-hou1*60))

                                ob['consumption'] = info['appliances']['sched_appliances']['power_cons'][j]/(60/self.time_granularity)*info['appliances']['sched_appliances']['running_len'][j]
                                data['scheduling'].append(ob)
                            
                            logging.info(data)

                            name = 'EWH'
                            ob = {}
                            ob['name']=name
                            ob['data'] = []
                            for i in range(int(60/self.time_granularity*24-1)):
                                if i != 0 and self.shems.Tewh_out[i] == 1 and self.shems.Tewh_out[i-1] == 0:
                                    min = i*self.time_granularity
                                    if min % 60 == 0:
                                        hou = int(i*self.time_granularity/60)
                                        min = 0
                                    else:
                                        hou = (min - min%60)/60
                                        min = min - 60*hou
                                    if hou + 8 > 23: hou = (hou+8)-23
                                    else: hou = hou + 8
                                    ob['start'] = str(hou)+':'+str(min) 
                                    ob['data'].append(1)
                                elif self.shems.Tewh_out[i] == 1 and self.shems.Tewh_out[i+1] == 0:
                                    end = 1
                                    min = i*self.time_granularity
                                    if min % 60 == 0:
                                        hou = int(i*self.time_granularity/60)
                                        min = 0
                                    else:
                                        hou = (min - min%60)/60
                                        min = min - 60*hou
                                    if hou + 8 > 23: hou = (hou+8)-23
                                    else: hou = hou + 8
                                    ob['end'] = str(hou)+':'+str(min) 
                                    ob['data'].append(1)
                                    done = 0
                                    if end <= step:
                                        done = 1
                                    ob['done'] = done
                                elif self.shems.Tewh_out[i] == 1:
                                    ob['data'].append(1)
                                else:
                                    ob['data'].append(0)

                                try:
                                    min = i*self.time_granularity
                                    if min % 60 == 0:
                                        hou = int(i*self.time_granularity/60)
                                        ob['label'].append(str(hou))
                                    else:
                                        hou = (min - min%60)/60
                                        ob['label'].append(str(hou)+":"+str(min-hou*60))
                                except:
                                    ob['label'] = []
                                    min = i*self.time_granularity
                                    if min % 60 == 0:
                                        hou = int(i*self.time_granularity/60)
                                        if hou + 8 > 23: hou = (hou+8)-23
                                        else: hou = hou + 8
                                        ob['label'].append(str(hou))
                                    else:
                                        hou = (min - min%60)/60
                                        if hou + 8 > 23: hou = (hou1+8)-23
                                        else: hou = hou1 + 8
                                        ob['label'].append(str(hou)+":"+str(min-hou1*60))

                                try:
                                    ob['consumption'] += self.shems.Pewh_out[i]/(60/self.time_granularity)
                                except:
                                    ob['consumption'] = 0
                                    ob['consumption'] += self.shems.Pewh_out[i]/(60/self.time_granularity)
                            
                            data['scheduling'].append(ob)

                            self.__append_data(code=timestamp, data=data)

                            logging.info('"Scheduling" GET request performed')
                        except:
                            logging.error('"Shceduling" GET request failed')

                    elif c['command'] == 'listDevice':
                        logging.info('GUI_thread_callback-listDevice')
                        try:
                            info = self.databaseClient.read_documents(collection_name='home_configuration', document={'_id': 4})
                            data = {}
                            data['listDevices'] = info['appliances']['sched_appliances']['name']

                            self.__append_data(code=timestamp, data=data)

                            logging.info('"listDevice" GET request performed')
                        except:
                            logging.error('"listDevice" GET request failed')

                    elif c['command'] == 'changeScheduling' and self.model:
                        logging.info('GUI_thread_callback-changeScheduling')
                        try:
                            payload = c['payload']
                            payload['command'] = 1

                            self.instance.get_data_serv()
                            self.shems.get_new_instance(self.instance)

                            self.shems.set_working_mode(payload)
                            cod = self.shems.solve_definitive()

                            if cod == 2:
                                self.__historyData_saving(step)

                                self.__append_data(code=timestamp, data={'response': 'Changing scheduling performed, new scheduling'})
                                logging.info('Changing scheduling performed')
                            elif cod == -1:
                                self.__append_data(code=timestamp, data={'response': 'Changing schedluinig failed, no new scheduling'})
                                logging.info('Changing scheduling failed, no new scheduling')

                            logging.info('"changeSchduling" POST request performed')
                        except:
                            logging.error('"changeSchduling" POST request failed')

                    elif c['command'] == 'summary':
                        logging.info('GUI_thread_callback-summary')
                        try:
                            payload = c['payload']
                            data = self.databaseClient.read_documents(collection_name='data_collected', document={'_id': 'history'})
                            logging.info(data['Phouse_consume'])
                            requiredData = {}

                            if payload['appliance'] == 'consumption':
                                if payload['start_time'] == 'day':
                                    try:
                                        values = []
                                        xlabel = []
                                        min = 999999
                                        max = -999999
                                        m = 0
                                        for i in range(24): #0-23
                                            s = 0
                                            for j in range(int(60/self.time_granularity)): #0-3
                                                s += data['Phouse_consume'][j*i]

                                            values.append(s/(60/self.time_granularity))
                                            xlabel = [8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,0,1,2,3,4,5,6,7]  # this labels consider the day starting from 8
                                            if s/(60/self.time_granularity) > max: max = s/(60/self.time_granularity)
                                            if s/(60/self.time_granularity) < min: min = s/(60/self.time_granularity)
                                            m += s/(60/self.time_granularity)
                                        requiredData['data'] = values  # values
                                        requiredData['label'] = xlabel  # xlabel
                                        requiredData['mean'] = m/24
                                        requiredData['min'] = min
                                        requiredData['max'] = max
                                    except:
                                        logging.info('Not enough data to solve the request')

                                elif payload['start_time'] == 'week':
                                    try:
                                        values = []
                                        xlabel = []
                                        min = 999999
                                        max = -999999
                                        m = 0
                                        for i in range(7):
                                            s = 0
                                            for j in range(int(24*60/self.time_granularity)): 
                                                s += data['Phouse_consume'][j*i]
                                            values.append(s/(24*(60/self.time_granularity)))
                                            xlabel.append(i*self.time_granularity*24) # this labels consider the day starting from 8
                                            if s/(24*(60/self.time_granularity)) > max: max = s /(24*(60/self.time_granularity))
                                            if s/(24*(60/self.time_granularity)) < min: min = s / (24*(60/self.time_granularity))
                                            m += s/(24*(60/self.time_granularity))
                                        requiredData['data'] = values  # values
                                        requiredData['label'] = xlabel  # xlabel
                                        requiredData['mean'] = m/7
                                        requiredData['min'] = min
                                        requiredData['max'] = max
                                    except:
                                        logging.info('Not enough data to solve the request')

                                elif payload['start_time'] == 'month':
                                    try:
                                        min = 999999
                                        max = -999999
                                        m = 0
                                        for i in range(7*4):
                                            s = 0
                                            for j in range(int(24*60/self.time_granularity)):
                                                s += data['Phouse_consume'][j*i]
                                            if s/(24*(60/self.time_granularity)) > max: max = s / (24*(60/self.time_granularity))
                                            if s/(24*(60/self.time_granularity)) < min: min = s / (24*(60/self.time_granularity))
                                            m += s/(24*(60/self.time_granularity))
                                        requiredData['mean'] = m/7
                                        requiredData['min'] = min
                                        requiredData['max'] = max
                                    except:
                                        logging.info('Not enough data to solve the request')

                                elif payload['start_time'] == 'year':
                                    try:
                                        min = 999999
                                        max = -999999
                                        m = 0
                                        for i in range(7*4*12):
                                            s = 0
                                            for j in range(int(24*60/self.time_granularity)):
                                                s += data['Phouse_consume'][j*i]
                                            if s/(24*(60/self.time_granularity)) > max: max = s /(24*(60/self.time_granularity))
                                            if s/(24*(60/self.time_granularity)) < min: min = s / (24*(60/self.time_granularity))
                                            m += s/(24*(60/self.time_granularity))
                                        requiredData['mean'] = m/7
                                        requiredData['min'] = min
                                        requiredData['max'] = max
                                    except:
                                        logging.info('Not enough data to solve the request')

                            elif payload['appliance'] == 'EV_battery':
                                try:
                                    values = []
                                    xlabel = []
                                    min = 999999
                                    max = -999999
                                    m = 0
                                    for i in range(24):
                                        s = 0
                                        for j in range(int(60/self.time_granularity)):
                                            s += self.shems.Cpev[j*i]
                                        values.append(s/(60/self.time_granularity))
                                        xlabel = [8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,0,1,2,3,4,5,6,7] # this labels consider the day starting from 8
                                        if s/(60/self.time_granularity) > max: max = s/(60/self.time_granularity)
                                        if s/(60/self.time_granularity) < min: min = s/(60/self.time_granularity)
                                        m += s/(60/self.time_granularity)
                                    requiredData['data'] = values  # values
                                    requiredData['label'] = xlabel  # xlabel
                                    requiredData['mean'] = m/24
                                    requiredData['min'] = min
                                    requiredData['max'] = max
                                except:
                                        logging.info('Not enough data to solve the request')

                            elif payload['appliance'] == 'ESS_battery':
                                try:
                                    values = []
                                    xlabel = []
                                    min = 999999
                                    max = -999999
                                    m = 0
                                    for i in range(24):
                                        s = 0
                                        for j in range(int(60/self.time_granularity)):
                                            s += self.shems.Cess[j*i]
                                        values.append(s/(60/self.time_granularity))
                                        xlabel = [8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,0,1,2,3,4,5,6,7]  # this labels consider the day starting from 8
                                        if s/(60/self.time_granularity) > max: max = s/(60/self.time_granularity)
                                        if s/(60/self.time_granularity) < min: min = s/(60/self.time_granularity)
                                        m += s/(60/self.time_granularity)
                                    requiredData['data'] = values  # values
                                    requiredData['label'] = xlabel  # xlabel
                                    requiredData['mean'] = m/24
                                    requiredData['min'] = min
                                    requiredData['max'] = max

                                except:
                                        logging.info('Not enough data to solve the request')
                            if self.instance.car_ownership == 1: requiredData['EV_flag'] = 'True'
                            else: requiredData['EV_flag'] = 'False'
                            self.__append_data(code=timestamp, data=requiredData)

                            logging.info('"summary" GET request performed')
                        except:
                            logging.error('"summary" GET request failed')

                    elif c['command'] == 'oldParameters':
                        logging.info('GUI_thread_callback-oldParameters')
                        try:
                            info = self.databaseClient.read_documents(collection_name='home_configuration', document={'_id': 0})
                            data = {}
                            data['new_values'] = {}
                            data['new_values'] = {}
                            data['new_values']['Tin_max'] = info['home_setpoints']['Tin_max']
                            data['new_values']['Tin_min'] = info['home_setpoints']['Tin_min']
                            data['new_values']['Tewh_max'] = info['home_setpoints']['Tewh_max']
                            data['new_values']['Tewh_min'] = info['home_setpoints']['Tewh_min']
                            data['new_values']['family_name'] = info['family_name']
                            info = self.databaseClient.read_documents(collection_name='home_configuration', document={'_id': 3})
                            data['new_values']['Cess_thresh_low'] = info['batteries']['Cess_thresh_low']
                            data['new_values']['Cess_thresh_high'] = info['batteries']['Cess_thresh_high']
                            data['new_values']['Cpev_thresh_low'] = info['batteries']['Cpev_thresh_low']
                            data['new_values']['Cpev_thresh_high'] = info['batteries']['Cpev_thresh_high']
                            info = self.databaseClient.read_documents(collection_name='home_configuration', document={'_id': 7})
                            data['new_values']['Time_deperature'] = info['time']['time_dep']

                            if self.instance.car_ownership == 1: data['new_values']['EV_flag'] = 'True'
                            else: data['new_values']['EV_flag'] = 'False'
                            self.__append_data(code=timestamp, data=data)

                            logging.info(
                                '"oldParameters" GET request performed')
                        except:
                            logging.error('"oldParameters" GET request failed')

                    elif c['command'] == 'changeSetpoints' and self.model:
                        logging.info('GUI_thread_callback-changeSetpoins')
                        code = 1
                        payload = c['payload']

                        data = self.databaseClient.read_documents(collection_name='home_configuration', document={'_id': 0})
                        data['home_setpoints']['Tin_max'] = float(payload['oldParameters']['Tin_max'])
                        data['home_setpoints']['Tin_min'] = float(payload['oldParameters']['Tin_min'])
                        data['home_setpoints']['Tewh_max'] = float(payload['oldParameters']['Tewh_max'])
                        data['home_setpoints']['Tewh_min'] = float(payload['oldParameters']['Tewh_min'])
                        code = code*self.databaseClient.update_documents(collection_name='home_configuration', document={'_id': 0}, data=data)

                        data = self.databaseClient.read_documents(collection_name='batteries', document={'_id': 3})
                        data['batteries']['Cess_thresh_low'] = float(payload['oldParameters']['Cess_thresh_low'])/100
                        data['batteries']['Cess_thresh_high'] = float(payload['oldParameters']['Cess_thresh_high'])/100
                        data['batteries']['Cpev_thresh_low'] = float(payload['oldParameters']['Cpev_thresh_low'])/100
                        data['batteries']['Cpev_thresh_high'] = float(payload['oldParameters']['Cpev_thresh_high'])/100
                        code = code*self.databaseClient.update_documents(collection_name='batteries', document={'_id': 3}, data=data)

                        data = self.databaseClient.read_documents(collection_name='time', document={'_id': 7})
                        data['time']['time_dep'] = payload['oldParameters']['time_dep']
                        code = code*self.databaseClient.update_documents(collection_name='time', document={'_id': 7}, data=data)

                        if code == 1:
                            self.__append_data(code=timestamp, data={'response': 'Updating setpoints success'})
                            logging.info('Updating setpoints success')
                        else:
                            self.__append_data(code=timestamp, data={'response': ' user Updating setpoints failed'})
                            logging.error('Updating setpoints failed')

                        payload['command'] = 0
                        payload['start_time'] = []
                        del payload['new_value']

                        self.instance.get_data_serv()
                        self.shems.get_new_instance(self.instance)

                        self.shems.set_working_mode(payload)
                        cod = self.shems.solve_definitive()

                        if cod == 2:
                            self.__append_data(code=timestamp, data={'response': 'Updating setpoint performed, new scheduling'})
                            self.__historyData_saving(step)
                            logging.info('New scheduling performed')
                        elif cod == -1:
                            self.__append_data(code=timestamp, data={'response': 'New scheduling failed'})
                            logging.error('New scheduling failed')

                    elif c['command'] == 'addAppliances' and self.model:
                        logging.info('GUI_thread_callback-addAppliances')
                        payload = c['payload']

                        data = self.databaseClient.read_documents(collection_name='home_configuration', document={'_id': 4})
                        fp = open('./files/appliances_info.json')
                        cfg = json.load(fp)
                        fp.close()

                        if payload['applianceData']['name'] != 'washing_machine' or payload['applianceData']['name'] != 'dishwasher' or payload['applianceData']['name'] != 'vacuum_cleaner':
                            data['appliances']['N_sched_appliances'] += 1
                            data['appliances']['sched_appliances']['name'].append(payload['applianceData']['name'])
                            running_len = payload['applianceData']['running_len']
                            running_len = int(running_len/self.time_granularity)
                            data['appliances']['sched_appliances']['running_len'].append(running_len)
                            data['appliances']['sched_appliances']['num_cycles'].append(1)
                            data['appliances']['sched_appliances']['power_cons'].append(payload['applianceData']['power_cons'])
                            data['appliances']['sched_appliances']['c1'].append(1)
                            data['appliances']['sched_appliances']['c2'].append(2)
                        else:
                            data['appliances']['N_sched_appliances'] += 1
                            data['appliances']['sched_appliances']['name'].append(payload['applianceData']['name'])
                            data['appliances']['sched_appliances']['running_len'].append(cfg[payload['applianceData']['name']]['running_len'])
                            data['appliances']['sched_appliances']['num_cycles'].append(cfg[payload['applianceData']['name']]['num_cycles'])
                            data['appliances']['sched_appliances']['power_cons'].append(cfg[payload['applianceData']['name']]['power_cons'])
                            data['appliances']['sched_appliances']['c1'].append(cfg[payload['applianceData']]['c1'])
                            data['appliances']['sched_appliances']['c2'].append(cfg[payload['applianceData']]['c2'])
                        code = self.databaseClient.update_documents(collection_name='home_configuration', document={'_id': 4}, data=data)
                        if code == 1: logging.info('Data updated')
                        else: logging.error('Database failed')

                        del payload['applianceData']
                        payload['command'] = 2
                        payload['appliance'] = []
                        payload['start_time'] = []

                        self.instance.get_data_serv()
                        self.shems.get_new_instance(self.instance)

                        self.shems.set_working_mode(payload)
                        cod = self.shems.solve_definitive()
                        if cod == 2:
                            self.__historyData_saving(step)
                            self.__append_data(code=timestamp, data={ 'response': 'Updating appliances list performed, new scheduling'})
                            logging.info("addAppliances request performed")
                        elif cod == -1:
                            self.__append_data(code=timestamp, data={'response': 'Updating appliances list failed, no new scheduling'})
                            logging.error('Updating appliances list failed, no new scheduling')

                    elif c['command'] == 'deleteAppliances' and self.model:
                        logging.info('GUI_thread_callback-deleteAppliances')
                        payload = c['payload']
                        data = self.databaseClient.read_documents(collection_name='home_configuration', document={'_id': 4})

                        data['appliances']['N_sched_appliances'] -= 1
                        for i in data['appliances']['sched_appliances']['name']:
                            if i == payload['applianceData']['name']:
                                data['appliances']['sched_appliances']['name'].pop(i)
                                data['appliances']['sched_appliances']['running_len'].pop(i)
                                data['appliances']['sched_appliances']['num_cycles'].pop(i)
                                data['appliances']['sched_appliances']['power_cons'].pop(i)
                                data['appliances']['sched_appliances']['c1'].pop(i)
                                data['appliances']['sched_appliances']['c2'].pop(i)
                                code = self.databaseClient.update_documents(collection_name='home_configuration', document={'_id': 4}, data=data)
                                if code == 1: logging.info('Data updated')
                                else: logging.error('Database failed')

                                del payload['applianceData']
                                payload['command'] = 2
                                payload['appliance'] = []
                                payload['start_time'] = []

                                self.instance.get_data_serv()
                                self.shems.get_new_instance(self.instance)

                                self.shems.set_working_mode(payload)
                                cod = self.shems.solve_definitive()
                                if cod == 2:
                                    self.__historyData_saving(step)
                                    self.__append_data(code=timestamp, data={'response': 'Updating appliances list success, new scheduling'})
                                    logging.info('"deleteAppliances request performed')
                                elif cod == -1:
                                    self.__append_data(code=timestamp, data={'response': 'Updating appliances list failed, no new scheduling'})
                                    logging.info('Updating appliances list failed')
                            else:
                                logging.warning('Error appliances name wrong, not found')

                    elif c['command'] == 'communityPlots':
                        logging.info('GUI_thread_callback-communityPlots')
                        try:
                            payload = c['payload']
                            data = self.databaseClient.read_documents(collection_name='data_collected', document={'_id': 'hisotry'})
                            requiredData = []

                            if payload['when'] == 'day':
                                values = []
                                xlabel = []
                                min = 999999
                                max = -999999
                                m = 0
                                for i in range(24):
                                    s = 0
                                    for j in range(self.time_granularity):
                                        s += data[payload['which']][j*i]

                                    values.append(s/(60/self.time_granularity))
                                    xlabel.append(i*self.time_granularity/60) # this labels consider the day starting from 8
                                    if s/(60/self.time_granularity) > max: max = s/(60/self.time_granularity)
                                    if s/(60/self.time_granularity) < min: min = s/(60/self.time_granularity)
                                    m += s/(60/self.time_granularity)
                                requiredData['data'] = values  # values
                                requiredData['label'] = xlabel  # xlabel
                                requiredData['mean'] = m/24
                                requiredData['min'] = min
                                requiredData['max'] = max

                            elif payload['when'] == 'week':
                                values = []
                                xlabel = []
                                min = 999999
                                max = -999999
                                m = 0
                                for i in range(7):
                                    s = 0
                                    for j in range(24*self.time_granularity):
                                        s += data[payload['which']][j*i]

                                    values.append(s/(24*(60/self.time_granularity)))
                                    xlabel.append(i*(self.time_granularity*24)) # this labels consider the day starting from 8
                                    if s/(24*(60/self.time_granularity)) > max: max = s/(24*(60/self.time_granularity))
                                    if s/(24*(60/self.time_granularity)) < min: min = s/(24*(60/self.time_granularity))
                                    m += s/(24*(60/self.time_granularity))
                                requiredData['data'] = values  # values
                                requiredData['label'] = xlabel  # xlabel
                                requiredData['mean'] = m/7
                                requiredData['min'] = min
                                requiredData['max'] = max

                            elif payload['when'] == 'month':
                                values = []
                                xlabel = []
                                min = 999999
                                max = -999999
                                m = 0
                                for i in range(7*4):
                                    s = 0
                                    for j in range(int(24*(60/self.time_granularity))):
                                        s += data[payload['which']][j*i]

                                    if s/(24*(60/self.time_granularity)) > max: max = s/(24*(60/self.time_granularity))
                                    if s/(24*(60/self.time_granularity)) < min: min = s/(24*(60/self.time_granularity))
                                    m += s/(24*(60/self.time_granularity))
                                requiredData['mean'] = m/7
                                requiredData['min'] = min
                                requiredData['max'] = max

                            elif payload['when'] == 'year':
                                values = []
                                xlabel = []
                                min = 999999
                                max = -999999
                                m = 0
                                for i in range(7*4*12):
                                    s = 0
                                    for j in range(int(24*(60/self.time_granularity))):
                                        s += data[payload['which']][j*i]

                                    if s/(24*(60/self.time_granularity)) > max: max = s/(24*(60/self.time_granularity))
                                    if s/(24*(60/self.time_granularity)) < min: min = s/(24*(60/self.time_granularity))
                                    m += s/(24*(60/self.time_granularity))
                                requiredData['mean'] = m/7
                                requiredData['min'] = min
                                requiredData['max'] = max

                            self.__append_data(code=timestamp, data=requiredData)

                            logging.info('"communityPlots" GET request performed')
                        except:
                            logging.error('communityPlots GET request failed')

                    elif c['command'] == 'communityProsumers':
                        logging.info('GUI_thread_callback-communityProsumer')
                        try:
                            data = self.databaseClient.read_documents(collection_name='data_collected', document={'_id': 'hisotry'})
                            requiredData = []
                            tot_energy_sold = 0
                            tot_energy_bought = 0
                            tot_price_sold = 0
                            tot_price_bought = 0
                            for i in data['prosumers']:
                                ob = {}
                                ob['name'] = i['name']
                                ob['interactions'] += 1
                                for j in range(len(i['energies'])):
                                    if i['energies'][j] > 0:
                                        tot_energy_bought += i['energies'][j]
                                        tot_price_bought += i['energies'][j] * i['prices'][j]
                                    else:  # <0
                                        tot_energy_sold += abs(i['energies'][j])
                                        tot_price_sold += abs(i['energies'][j]*i['prices'][j])
                                ob['mean_price_bought'] = tot_price_bought / len(i['energies'])
                                ob['mean_price_sold'] = tot_price_sold / len(i['energies'])
                                ob['mean_energy_bought'] = tot_energy_bought / len(i['energies'])
                                ob['mean_energy_sold'] = tot_energy_sold / len(i['energies'])
                                ob['tot_price_bought'] = tot_price_bought
                                ob['tot_price_sold'] = tot_price_sold
                                ob['tot_energy_bought'] = tot_energy_bought
                                ob['tot_energy_sold'] = tot_energy_sold
                                # now data about the home owner
                                ob['my_tot_energy_sold'] += tot_energy_sold
                                ob['my_tot_energy_bought'] += tot_energy_bought
                                ob['my_tot_price_sold'] += tot_price_sold
                                ob['my_tot_price_bought'] += tot_price_bought
                                requiredData.append(ob)

                            self.__append_data(code=timestamp, data=requiredData)

                            logging.info('"communityProsumers" GET request performed')
                        except:
                            logging.error('"communityProsumers" GET request failed')

                    elif c['command'] == 'registration':
                        logging.info('GUI_thread_callback-registration')
                        try:
                            code = 1
                            payload = c['payload']
                            data = {}

                            data['name'] = payload['family_name']['family_name']

                            # Minimum and maximum temperature of the environment and of the WH
                            data = self.databaseClient.read_documents(collection_name='home_configuration', document={'_id': 0})
                            data['home_setpoints']['Tin_max'] = int(payload['setpoints']['Tin_max'])
                            data['home_setpoints']['Tin_min'] = int(payload['setpoints']['Tin_min'])
                            data['home_setpoints']['Tewh_max'] = int(payload['setpoints']['Tewh_max'])
                            data['home_setpoints']['Tewh_min'] = int(payload['setpoints']['Tewh_min'])   

                            data['family_name'] = payload['family_name']['family_name']

                            code = code * self.databaseClient.update_documents('home_configuration', {'_id': 0}, data)
    
                            # Departure car time, minimum and maximum threashold charging level (home and EV)
                            data = self.databaseClient.read_documents(
                                collection_name='home_configuration', document={'_id': 3})
                            try:
                                data['batteries']['Cpev_thresh_low'] = int(payload['EV']['Cpev_thresh_low']/100)
                                data['batteries']['Cpev_thresh_high'] = int(payload['EV']['Cpev_thresh_high']/100)
                                data['batteries']['car_ownership'] = 1
                                self.instance.car_ownership = 1
                            except:
                                self.instance.car_ownership = 0
                                data['batteries']['car_ownership'] = 0
                            data['batteries']['Cess_thresh_low'] = int(payload['home_batteries']['Cess_thresh_low'])/100
                            data['batteries']['Cess_thresh_high'] = int(payload['home_batteries']['Cess_thresh_high'])/100
                            code = code * self.databaseClient.update_documents('home_configuration', {'_id': 3}, data)
                            data = self.databaseClient.read_documents(collection_name='home_configuration', document={'_id': 7})
                            try:
                                data['time']['time_dep'] = payload['EV']['Time_departure']
                            except:
                                pass
                                # None -> for not having the car
                            code = code * self.databaseClient.update_documents('home_configuration', {'_id': 7}, data)
                            
                            # appliances:[modello, lavatrice-lavastovigle-vacuum cliner]
                            fp = open('./files/appliances_info.json')
                            cfg = json.load(fp)
                            fp.close()
                            data = self.databaseClient.read_documents(collection_name='home_configuration', document={'_id': 4})
                            for i in payload['applianceData']:
                                if i['name'] == 'none':
                                    pass
                                elif i['name'] != 'washing_machine' and i['name'] != 'dishwasher' and i['name'] != 'vacuum_cleaner':
                                    data['appliances']['N_sched_appliances'] += 1
                                    data['appliances']['sched_appliances']['name'].append(i['name'])
                                    running_len = int(i['running_len'])
                                    running_len = int(running_len/self.time_granularity)
                                    data['appliances']['sched_appliances']['running_len'].append(running_len)
                                    data['appliances']['sched_appliances']['num_cycles'].append(1)
                                    data['appliances']['sched_appliances']['power_cons'].append(i['consumption'])
                                    data['appliances']['sched_appliances']['c1'].append(1)
                                    data['appliances']['sched_appliances']['c2'].append(2)
                                else:
                                    data['appliances']['N_sched_appliances'] += 1
                                    data['appliances']['sched_appliances']['name'].append(i['name'])
                                    data['appliances']['sched_appliances']['running_len'].append(int(cfg[i['name']]['running_len']))
                                    data['appliances']['sched_appliances']['num_cycles'].append(int(cfg[i['name']]['num_cycles']))
                                    data['appliances']['sched_appliances']['power_cons'].append(float(cfg[i['name']]['power_cons']))
                                    data['appliances']['sched_appliances']['c1'].append(cfg[i['name']]['c1'])
                                    data['appliances']['sched_appliances']['c2'].append(cfg[i['name']]['c2'])

                            code = code * self.databaseClient.update_documents('home_configuration', {'_id': 4}, data)
                            if code == 1:
                                self.__append_data(code=timestamp, data={'response': 'New user registration success'})
                                logging.info('New registration success')

                                # first modelling computation after registration
                                cd = None
                                try:
                                    self.instance.get_data_serv()
                                    self.shems = SHEMS(self.instance)
                                    cod = self.shems.solve_definitive()
                                    if cod == 2:
                                        self.model = True
                                        self.__historyData_saving()
                                except:
                                    logging.error(f'New user registration failed, mathematical model error, code = {cd}')

                            else:
                                self.__append_data(code=timestamp, data={'response': 'New user registration failed, database error'})
                                logging.error('New user registration failed, database error')
                        except:
                            self.__append_data(code=timestamp, data={'response': 'New user registration failed'})
                            logging.error('New user registration failed')

                        if self.model == False:
                            logging.warning('SHEMS model not active')
                            fp = open(self.push_path)
                            pushes = json.load(fp)
                            fp.close()
                            payload = {'message': 'SHEMS model not active, please contact the customer care'}
                            pushes['pushes'].append(payload)
                            fp = open(self.push_path, 'w')
                            json.dump(pushes, fp)
                            fp.close()
                    else:
                        break

                    self.__clear_file(path=self.commands_path, timestamp=timestamp)

        except:
            logging.error('User command reading or execution error')

    def __clear_file(self, path, timestamp=None):
        logging.info('__clear_file')
        try:
            fp = open(path)
            file = json.load(fp)
            fp.close

            if timestamp != None:
                if path == self.commands_path:
                    for c in range(len(file['commands_list'])):
                        if file['commands_list'][c]['timestamp'] == timestamp:
                            file['commands_list'].pop(c)
                    logging.info('GUI_thread_commands.json cleaned')
            else:
                if path == self.commands_path:
                    file = {"commands_list": []}
                    logging.info('GUI_thread_commands.json cleaned')
                elif path == self.data_path:
                    file = {"responses": {}}
                    logging.info('GUI_thread_data.json cleaned')

            with open(path, 'w') as outfile:
                json.dump(file, outfile)
      
        except:
            logging.error('GUI_thread_commands or GUI_thread_data .json error')
            self.c += 1
            if self.c > 3:
                self.c = 0
                self.__clear_file(path, None)
                
                logging.warning('Cleaning files error: repeat the operation')
                fp = open(self.push_path)
                pushes = json.load(fp)
                fp.close()
                payload = {'message': 'Cleaning files error: repeat the operation'}
                pushes['pushes'].append(payload)
                fp = open(self.push_path, 'w')
                json.dump(pushes, fp)
                fp.close()

    def __append_data(self, code, data):
        """Append data to GUI_thread_data.json

        Args:
            code: webserver reception command timestamp: command_list[i]['timestamp'] 
            data (dict): data response
        """
        logging.info('__append_data')
        try:
            fp = open(self.data_path)
            file = json.load(fp)
            fp.close()

            file['responses'][code] = data

            fp = open(self.data_path, 'w')
            json.dump(file, fp)
            fp.close()

            logging.info('GUI_thread_data.json modify')
        except:
            logging.info('GUI_thread_data.json error')

    def __historyData_saving(self, step=None):
        """Storing daily data

        Args:
            step (int): time reference considering the time granularity
        """
        logging.info('__historyData_saving')
        try:
            if step != None:
                data = self.databaseClient.read_documents(collection_name='data_collected', document={'_id': 'history'})
                i = int(60/self.time_granularity*24)-step
                for j in range(i):
                    # power consumption saving
                    data['Phouse_consume'][-i+j] = self.shems.Phouse_consume[step+j]
                    # historyDataMarket_saving
                    if self.shems.Pg_market[step+j] > 0:
                        data['energyBought'][-i+j] = self.shems.Pg_market[step+j]
                        data['energySold'][-i+j] = 0
                    else:
                        data['energyBought'][-i+j] = 0
                        data['energySold'][-i+j] = self.shems.Pg_market[step+j]
                    data['Pg_market'][-i+j] = self.shems.Pg_market[step+j]
                
                code = self.databaseClient.update_documents(collection_name='data_collected', document={'_id': 'history'}, object=data)
                if code == 1: logging.info('Data updated')
                else: logging.error('Database failed')

                logging.info('Data saving performed')
            else:
                data = self.databaseClient.read_documents(collection_name='data_collected', document={'_id': 'history'})
                for j in range(int(60/self.time_granularity*24)):
                    # power consumption saving
                    data['Phouse_consume'].append(self.shems.Phouse_consume[j])
                    # historyDataMarket_saving
                    if self.shems.Pg_market[j] > 0:
                        data['energyBought'].append(self.shems.Pg_market[j])
                        data['energySold'].append(0)
                    else:
                        data['energyBought'].append(0)
                        data['energySold'].append(self.shems.Pg_market[j])
                    data['Pg_market'].append(self.shems.Pg_market[j])

                code = self.databaseClient.update_documents(collection_name='data_collected', document={'_id': 'history'}, object=data)
                if code == 1: logging.info('Data updated')
                else: logging.error('Database failed')
                
                logging.info('Data saving performed')
        except:
            logging.error('Database error during data saving')

    def __reset(self):
        """Reset of the system: databse and files
        """
        logging.info('__reset')
        try:
            self.__clear_file(self.commands_path, None)
            self.__clear_file(self.data_path, None)
            code = 1
            
            data = {}
            data['Phouse_consume'] = []
            data['energyBought'] = []
            data['energySold'] = []
            data['Pg_market'] = []
            data['prosumers'] = []
            code = code*self.databaseClient.update_documents(
                collection_name='data_collected', document={'_id': 'history'}, object=data)
            
            data = {}
            data['appliances'] = {}
            data['appliances']['N_sched_appliances'] = 0
            data['appliances']['sched_appliances'] = {}
            data['appliances']['sched_appliances']['name'] = []
            data['appliances']['sched_appliances']['running_len'] = []
            data['appliances']['sched_appliances']['power_cons'] = []
            data['appliances']['sched_appliances']['num_cycles'] = []
            data['appliances']['sched_appliances']['c1'] = []
            data['appliances']['sched_appliances']['c2'] = []
            code = code*self.databaseClient.update_documents(
                collection_name='home_configuration', document={'_id': 4}, object=data)
            if code == 1:
                logging.info('Data resetted')
            else:
                logging.error('Database failed')
        except:
            logging.error('Reset of the system failed')

if __name__ == '__main__':
    log_name = './logs/main.log'
    logging.basicConfig(
        filename=log_name,
        format='%(asctime)s %(levelname)s: %(message)s',
        level=logging.INFO, datefmt="%H:%M:%S",
        filemode='w'
    )

    fp = open('./files/starting_configuration.json')
    cfg = json.load(fp)
    fp.close()

    main = SHEMS_main(cfg)
    GUIcommands = perpetualTimer(t=3, hFunction=main.GUI_thread_callback)
    GUIcommands.start()

    #prosumer = Prosumer("shems")
    #prosumer_timer = perpetualTimer(t = 15*60, hFunction=prosumer.thread_callback)
    # prosumer_timer.start()

    while True:
        pass
