import json
import math
import logging
import requests
import datetime
import numpy as np

from utilities.timer import perpetualTimer
from utilities.mqttclient import MQTTSubscriber, MQTTPublisher
from mongoDB.database_client import databaseClient
from optimizationModel.Simulator.instance import Instance
from optimizationModel.LP_solver.SHEMSModel import SHEMS
from prosumerCommunity.prosumerMarket import Prosumer
from pushNotification_server.websocket import SHEMSwebsocket

class SHEMS_main():
    def __init__(self, cfg):
        """SHEMS system object. It includes the instance of the energy optimization toll, 
        the instance of the MQTT subscriber and publisher and the instance of the push notificator

        Args:
            cfg (dict): configuration file
        """
        try:
            #self.__reset()

            self.time_granularity = cfg['time_granularity']
            self.commands_path = cfg['commands_path']
            self.data_path = cfg['data_path']

            # Energy optimization model
            self.databaseClient = databaseClient()
            self.instance = Instance()
            self.instance.get_data_serv()
            self.shems = SHEMS(self.instance)
            
            # Sensors subscriber MQTT
            self.waterWithdrawn_topic = cfg['waterWithdrawn_topic']
            self.carStation_topic = cfg['carStation_topic']
            self.smartMeter_topic = cfg['smartMeter_topic']
            self.deviceID = str(np.random.randint(1000000000))
            self.broker = cfg['mqtt_broker']
            self.port = cfg['mqtt_port']
            self.sensors_subscriber = MQTTSubscriber(self.deviceID, self.broker, self.port)
            self.sensors_subscriber.start()
            self.sensors_subscriber.callbackRegistration(self.__sensorsSubscriber_callback)
            self.sensors_subscriber.mySubscribe(self.waterWithdrawn_topic)
            self.sensors_subscriber.mySubscribe(self.carStation_topic)
            self.sensors_subscriber.mySubscribe(self.smartMeter_topic)

            # Weather forecast API
            self.city = cfg['home_city']
            self.country_code = cfg['country_code']
            self.BASE_URL2 = cfg['BASE_URL2']
            self.API_KEY = cfg['API_KEY']
            limit = 1
            url = f"http://api.openweathermap.org/geo/1.0/direct?q={self.city},{self.country_code}&limit={limit}&appid={self.API_KEY}"
            response = requests.get(url)
            if response.status_code == 200:
                self.lat = int(response.json()[0]['lat'])
                self.lon = int(response.json()[0]['lon'])
            else:
                logging.error(f'Error weather API: {response.status_code}')

            # Push notification
            self.pushnotification_server = SHEMSwebsocket(cfg)
            # TODO:contronllo del messaggio, piccola encriptazione del messaggio (in più)

            logging.info('Environment generation done')
        except:
            logging.warning('Environment generation failed')

    def __basicScheduling_thread_callback(self):
        """First day scheduling, done at 8:00 a.m. 
        """ 
        self.__weatherAPI()
        
        obj = self.databaseClient.read_documents(collection_name='home_configuration', document={'_id':0})
        obj['home_setpoints']['Tin_out'] = self.shems.Tin_out[-1]
        obj['home setpoints']['Tewh_out'] = self.shems.Tewh_out[-1]
        self.databaseClient.update_documents(collection_name='home_configuration', document={'_id':0}, object=obj)

        self.instance.get_data_serv()
        self.shems.get_new_instance(self.instance)
        
        cod = self.shems.solve_definitive()
        if cod == 2:
            try:
                data = self.databaseClient.read_documents(collection_name='data_collected', document={'_id':'history'})
                for j in range(60/self.time_granularity*24):
                    data['Phouse_consume'].append(self.shems.Phouse_consume[j])
                code = self.databaseClient.update_documents(collection_name='data_collected', document={'_id':'history'}, object=data)
                if code == 1: logging.info('Data updated')
                else: logging.error('Database failed')
                
                self.pushnotification_server.upgradeNotification({'message':'First scheduling of the day had success'})
                logging.info('First scheduling of the day had success')
            except:
                logging.error('Local websocket server or database error')
        elif cod == -1:
            self.pushnotification_server.upgradeNotification({'message':'First scheduling of the day failed'})
            logging.info('First scheduling of the day failed')
    
    def __weatherAPI(self):
        """Open weather map call to retrive temperature forecast for the day. Stores the results in the database
        """
        url = f'{self.BASE_URL2}lat={self.lat}&lon={self.lon}&appid={self.API_KEY}'
        response = requests.get(url)
        # Data interpolation, from API data every 3 hours to model requirement granularity data (self.time_granularity)
        temp = []
        if response.status_code == 200:  # checking the status code of the request
            data = response.json()['list']
            for i in range(8): #24/3, data recovering: temperature every 3 hours
                temp.append(round(data[i]['main']['temp']-273, 1))

            new_temp = np.zeros(int(60/self.time_granularity*24))
            step = int(3*60/self.time_granularity)
            for i in range(7):  # 0-6, data every 1 hour
                for j in range(step):  # 0-11
                    if j == 0:
                        new_temp[i*step+j] = temp[i]
                    else:
                        new_temp[i*step+j] = round(temp[i] -j*(temp[i]-temp[i+1])/step, 1)
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
                    new_solarRadiation.append(np.normal(loc=center, scale=std))
                elif i <= 18*(60/self.time_granularity):
                    center = center - 9/(4*60/self.time_granularity)
                    if center < 1: center = 1
                    new_solarRadiation.append(np.normal(loc=center, scale=std))
                else:
                    new_solarRadiation.append(0)

            data = self.databaseClient.read_documents(collection_name='home_configuration', document={'_id':2})
            data['home_setpoints']['Tout'] = new_temp
            code = self.databaseClient.update_documents(collection_name='home_configuration', document={'_id':2}, object=data)
            if code == 1: logging.info('Data updated')
            else: logging.error('Database failed')

            data = self.databaseClient.read_documents(collection_name='home_configuration', document={'_id':5})
            data['energy']['RES_hour_geen'] = new_solarRadiation
            self.databaseClient.update_documents(collection_name='home_configuration', document={'_id':5}, object=data)
            if code == 1: logging.info('Data updated')
            else: logging.error('Database failed')

            logging.info('Weather API call done')
        else:
            logging.error(f'Error weather API: {response.status_code} or database failed')  

    def __sensorsSubscriber_callback(self, msg):
        """Subscriber for car station and hot water usage

        Args:
            msg (MQTT msg): 
        """
        if msg.topic == self.waterWithdrawn_topic:
            new_data = msg.payload
            data = self.databaseClient.read_documents(collection_name='home_configuration', document={'_id':1})
            Wd = data['outside_measure']['Wd']

            time = str(datetime.datetime.now())
            hh = int(time.split(' ')[1].split(':')[0])
            mm = int(time.split(' ')[1].split(':')[1])
            if (hh - 8) > 0:
                step = int(60/self.time_granularity*(hh - 8) + math.floor(mm/self.time_granularity)) 
            else:
                step = int(60/self.time_granularity*(24 - (8 - hh)) + math.floor(mm/self.time_granularity))

            if new_data > Wd[step]:
                Wd[step] = new_data
                data = self.databaseClient.read_documents(collection_name='home_configuration', document={'_id':1})
                data['outside_measure']['Wd'] = Wd
                code = self.databaseClient.update_documents(collection_name='home_configuration', document={'_id':1}, object=Wd)
                if code == 1: logging.info('Data updated')
                else: logging.error('Database failed')

            self.instance.get_data_serv()
            self.shems.get_new_instance(self.instance)

            cod = self.shems.solve_definitive()
            if cod == 2:
                try:
                    self.historyData_saving(step)
                    self.pushnotification_server.upgradeNotification({'message':'New schedling performed, hot water used'})
                    logging.info('New schedling performed, hot water used')
                except:
                    logging.error('Local websocket server error')
            elif cod == -1:
                self.pushnotification_server.upgradeNotification({'message':'New scheduling failed. Too much hot water used'})
                logging.warning('New scheduling failed. Too much hot water used')

        elif msg.topic == self.carStation_topic:
            if msg.payload == 1:
                self.shems.set_car_arrival()
                self.pushnotification_server.upgradeNotification({'message':'Electric vehicle in the garage'})
            else: 
                logging.error('Error in the carStation publisher')

        elif msg.topic == self.smartMeter_topic:
            data = self.databaseClient.read_documents(collection_name='home_configuration', document={'_id':6})
            data['RTP']['values']=msg.payload
            code = self.databaseClient.update_documents('home_configuration', {'_id':6}, data)
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
            for c in commands:
                timestamp = c['timestamp']
                time = str(timestamp)
                hh = int(time.split(' ')[1].split(':')[0])
                mm = int(time.split(' ')[1].split(':')[1])
                if (hh - 8) > 0:
                    step = int(60/self.time_granularity*(hh - 8) + math.floor(mm/self.time_granularity)) 
                else:
                    step = int(60/self.time_granularity*(24 - (8 - hh)) + math.floor(mm/self.time_granularity))

                if c['command'] == 'home': # on at this moment
                    try:
                        data = {}
                        data['listDevices'] = []
                        data['single_values'] = {}
                        for j in range(self.shems.instance.N_sched_appliances): # columns
                            if self.shems.ud_out[step][j] == 1:
                                info = self.databaseClient.read_documents(collection_name='home_configuration', document={'_id':4})
                                ob = {}
                                ob['name'] = info['appliances']['sched_appliances']['name'][j]
            
                                for i in range(60/self.time_granularity*24-1): # rows 
                                    if i != 0 and self.shems.ud_out[i][j] == 1 and self.shems.ud_out[i-1][j] == 0:
                                        start = i
                                        ob['starting_time'] = start
                                    elif self.shems.ud_out[i][j] == 1 and self.shems.ud_out[i+1][j] == 0:
                                        end = i
                                        ob['ending_time'] = end
                                data['listDevices'].append(ob)

                        data['single_values']['ESS_battery'] = self.shems.Cess[step]
                        data['single_values']['EV_battery'] = self.shems.Cpev[step]   
                        data['single_values']['consumption'] = self.shems.Phouse_consume[step]      

                        self.__append_data(code=timestamp, data=data)
                        
                        logging.info('"Home" GET request performed')
                    except:
                        logging.error('"Home" GET request failed')

                    self.__clear_file(self.commands_path)

                elif c['command'] == 'scheduling':
                    try:
                        data = {}
                        data['scheduling'] = {}
                        for j in range(self.shems.instance.N_sched_appliances): # columns
                            info = self.databaseClient.read_documents(collection_name='home_configuration', document={'_id':4})
                            name = info['appliances']['sched_appliances']['name'][j]
                            data['scheduling'][name] = {}
                            for i in range(int(60/self.time_granularity*24-1)): # rows 
                                if i != 0 and self.shems.ud_out[i][j] == 1 and self.shems.ud_out[i-1][j] == 0:
                                    start = i
                                    data['scheduling'][name]['start']  = start
                                    try:
                                        data['scheduling'][name]['data'].append(1)
                                    except:
                                        data['scheduling'][name]['data'] = []
                                        data['scheduling'][name]['data'].append(1)
                                elif self.shems.ud_out[i][j] == 1 and self.shems.ud_out[i+1][j] == 0:
                                    end = i
                                    data['scheduling'][name]['end'] = end
                                    done = 0
                                    if end <= step:
                                        done = 1
                                    data['scheduling'][name]['done'] = done
                                try:
                                    data['scheduling'][name]['label'].append((step-i*(self.time_granularity*24)))
                                except:
                                    data['scheduling'][name]['label'] = []
                                    data['scheduling'][name]['label'].append((step-i*(self.time_granularity*24)))
                            data['scheduling'][name]['consumption'] = info['appliances']['sched_appliances']['power_cons'][j]/(60/self.time_granularity)*info['appliances']['sched_appliances']['running_len'][j]
                        
                        name = 'EWH'
                        data['scheduling'][name] = {}
                        for i in range(int(60/self.time_granularity*24-1)): 
                            if i != 0 and self.shems.Tewh_out[i] == 1 and self.shems.Tewh_out[i-1] == 0:
                                start = i
                                data['scheduling'][name]['start']  = start
                                data['data'].append(1)
                            elif self.shems.Tewh_out[i] == 1 and self.shems.Tewh_out[i+1] == 0:
                                end = i
                                data['scheduling'][name]['end'] = end
                                done = 0
                                if end <= step:
                                    done = 1
                                data['scheduling'][name]['done'] = done
                            try:
                                data['scheduling'][name]['label'].append((step-i*(self.time_granularity*24)))
                            except:
                                data['scheduling'][name]['label'] = []
                                data['scheduling'][name]['label'].append((step-i*(self.time_granularity*24)))
                            try:
                                data['scheduling'][name]['consumption'] += self.shems.Pewh_out[i]/(60/self.time_granularity)
                            except:
                                data['scheduling'][name]['consumption'] = 0
                                data['scheduling'][name]['consumption'] += self.shems.Pewh_out[i]/(60/self.time_granularity)

                        self.__append_data(code=timestamp, data=data)
                        
                        logging.info('"Scheduling" GET request performed')
                    except:
                        logging.error('"Shceduling" GET request failed')

                    self.__clear_file(self.commands_path)
                
                elif c['command'] == 'listDevice':
                    try:
                        info = self.databaseClient.read_documents(collection_name='home_configuration', document={'_id':4})
                        data = {}
                        data['listDevice'] = info['appliances']['sched_appliances']['name']

                        self.__append_data(code=timestamp, data=data)

                        logging.info('"listDevice" GET request performed')
                    except:
                        logging.error('"listDevice" GET request failed')
                    self.__clear_file(self.commands_path)

                elif c['command'] == 'changeScheduling':
                    try:
                        payload = c['payload'] 
                        payload['command'] = 1
                    
                        self.instance.get_data_serv()
                        self.shems.get_new_instance(self.instance)

                        self.shems.set_working_mode(payload)
                        cod = self.shems.solve_definitive()

                        if cod == 2:
                            self.__historyData_saving(step)

                            self.__append_data(code=timestamp, data={'response':'Changing scheduling performed, new scheduling'})
                            logging.info('Changing scheduling performed')
                        elif cod == -1:
                            self.__append_data(code=timestamp, data={'response':'Changing schedluinig failed, no new scheduling'})
                            logging.info('Changing scheduling failed, no new scheduling')

                        logging.info('"changeSchduling" POST request performed')
                    except:
                        logging.error('"changeSchduling" POST request failed')

                    self.__clear_file(self.commands_path)

                elif c['command'] == 'summary':
                    try:
                        payload = c['payload']
                        data = self.databaseClient.read_documents(collection_name='data_collected', document={'_id':'history'})
                        requiredData = {}
                        
                        if payload['which'] == 'consumption':
                            if payload['when'] == 'day':
                                values = []
                                xlabel = []
                                min = 999999
                                max = -999999
                                m = 0
                                for i in range(24):
                                    s = 0                        
                                    for j in range(60/self.time_granularity):
                                        s += data['Phouse_consume'][(step-j)*i]
                                    values.append(s/(60/self.time_granularity))
                                    xlabel.append((step-i)*self.time_granularity/60)
                                    if s/(60/self.time_granularity) > max: max = s/(60/self.time_granularity)
                                    if s/(60/self.time_granularity) < min: min = s/(60/self.time_granularity)
                                    m += s/(60/self.time_granularity)
                                requiredData['data'] = values # values
                                requiredData['label'] = xlabel # xlabel
                                requiredData['mean'] = m/24
                                requiredData['min'] = min
                                requiredData['max'] = max

                            elif payload['when'] == 'week':
                                values = []
                                xlabel = []
                                min = 999999
                                max = -999999
                                m = 0
                                for i in range (7):
                                    s = 0
                                    for j in range(24*60/self.time_granularity):
                                        s += data['Phouse_consume'][(step-j)*i]
                                    values.append(s/(24*(60/self.time_granularity)))
                                    xlabel.append((step-i*(self.time_granularity*24)))
                                    if s/(24*(60/self.time_granularity)) > max: max = s/(24*(60/self.time_granularity))
                                    if s/(24*(60/self.time_granularity)) < min: min = s/(24*(60/self.time_granularity))
                                    m += s/(24*(60/self.time_granularity))
                                requiredData['data'] = values # values
                                requiredData['label'] = xlabel# xlabel
                                requiredData['mean'] = m/(7)
                                requiredData['min'] = min
                                requiredData['max'] = max
                            
                            elif payload['when'] == 'month':
                                min = 999999
                                max = -999999
                                m = 0
                                for i in range (7*4):
                                    s = 0
                                    for j in range(24*60/self.time_granularity):
                                        s += data['Phouse_consume'][(step-j)*i]
                                    if s/(24*(60/self.time_granularity)) > max: max = s/(24*(60/self.time_granularity))
                                    if s/(24*(60/self.time_granularity)) < min: min = s/(24*(60/self.time_granularity))
                                    m += s/(24*(60/self.time_granularity))
                                requiredData['mean'] = m/(7)
                                requiredData['min'] = min
                                requiredData['max'] = max

                            elif payload['when'] == 'year':
                                min = 999999
                                max = -999999
                                m = 0
                                for i in range (7*4*12):
                                    s = 0
                                    for j in range(24*60/self.time_granularity):
                                        s += data['Phouse_consume'][(step-j)*i]
                                    if s/(24*(60/self.time_granularity)) > max: max = s/(24*(60/self.time_granularity))
                                    if s/(24*(60/self.time_granularity)) < min: min = s/(24*(60/self.time_granularity))
                                    m += s/(24*(60/self.time_granularity))
                                requiredData['mean'] = m/(7)
                                requiredData['min'] = min
                                requiredData['max'] = max

                        elif payload['which'] == 'EV_battery':
                            values = []
                            xlabel = []
                            min = 999999
                            max = -999999
                            m = 0
                            for i in range(24):
                                s = 0
                                for j in range(60/self.time_granularity):
                                    s += self.shems.Cpev[j*i]
                                values.append(s/(60/self.time_granularity))
                                xlabel.append((step-i)*self.time_granularity/60)
                                if s/(60/self.time_granularity) > max: max = s/(60/self.time_granularity)
                                if s/(60/self.time_granularity) < min: min = s/(60/self.time_granularity)
                                m += s/(60/self.time_granularity)
                            requiredData['data'] = values # values
                            requiredData['label'] = xlabel # xlabel
                            requiredData['mean'] = m/24
                            requiredData['min'] = min
                            requiredData['max'] = max

                        elif payload['which'] == 'ESS_battery':
                            values = []
                            xlabel = []
                            min = 999999
                            max = -999999
                            m = 0
                            for i in range(24):
                                s = 0
                                for j in range(60/self.time_granularity):
                                    s += self.shems.Cess[j*i]
                                values.append(s/(60/self.time_granularity))
                                xlabel.append((step-i)*self.time_granularity/60)
                                if s/(60/self.time_granularity) > max: max = s/(60/self.time_granularity)
                                if s/(60/self.time_granularity) < min: min = s/(60/self.time_granularity)
                                m += s/(60/self.time_granularity)
                            requiredData['data'] = values # values
                            requiredData['label'] = xlabel # xlabel
                            requiredData['mean'] = m/24
                            requiredData['min'] = min
                            requiredData['max'] = max

                        # TODO: fare in modo che i dati più vecchi di un certo periodo vengano compressi per risparmiare spazio (più tardi)
                        self.append_data(code=timestamp, data=requiredData)

                        logging.info('"summary" GET request performed')
                    except:
                        logging.error('"summary" GET request failed')
                    self.__clear_file(self.commands_path)

                elif c['command'] == 'oldParameters':
                    try:
                        info = self.databaseClient.read_documents(collection_name='home_configuration', document={'_id':0})
                        data = {}
                        data['oldParameters']['Tin_max'] = info['home_setpoints']['Tin_max']
                        data['oldParameters']['Tin_min']  = info['home_setpoints']['Tin_min']
                        data['oldParameters']['Tewh_max'] = info['home_setpoints']['Tewh_max']
                        data['oldParameters']['Tewh_min'] = info['home_setpoints']['Tewh_min']

                        info = self.databaseClient.read_documents(collection_name='home_configuration', document={'_id':3})
                        data['oldParameters']['Cess_thresh_low'] = info['batteries']['Cess_thresh_low']
                        data['oldParameters']['Cess_thresh_high'] = info['batteries']['Cess_thresh_high']
                        data['oldParameters']['Cpev_thresh_low'] = info['batteries']['Cpev_thresh_low']
                        data['oldParameters']['Cpev_thresh_high'] = info['batteries']['Cpev_thresh_high']

                        info = self.databaseClient.read_documents(collection_name='home_configuration', document={'_id':7})
                        data['oldParameters']['Time_deperature'] = info['batteries']['time_dep']

                        self.__append_data(code=timestamp, data=data)

                        logging.info('"oldParameter" GET request performed')
                    except:
                        logging.error('"oldParameter" GET request failed')

                    self.__clear_file(self.commands_path)

                elif c['command'] == 'changeSetpoints':
                    code = 1
                    payload = c['payload']

                    data = self.databaseClient.read_documents(collection_name='home_configuration', document={'_id':0})
                    data['home_setpoints']['Tin_max'] = payload['oldParameters']['Tin_max']
                    data['home_setpoints']['Tin_min'] = payload['oldParameters']['Tin_min']
                    data['home_setpoints']['Tewh_max'] = payload['oldParameters']['Tewh_max']
                    data['home_setpoints']['Tewh_min'] = payload['oldParameters']['Tewh_min']
                    code = code*self.databaseClient.update_documents(collection_name='home_configuration', document={'_id':0}, data = data)

                    data = self.databaseClient.read_documents(collection_name='home_configuration', document={'_id':3})
                    data['batteries']['Cess_thresh_low'] = payload['oldParameters']['Cess_thresh_low']
                    data['batteries']['Cess_thresh_high'] = payload['oldParameters']['Cess_thresh_high'] 
                    data['batteries']['Cpev_thresh_low'] = payload['oldParameters']['Cpev_thresh_low']
                    data['batteries']['Cpev_thresh_high'] = payload['oldParameters']['Cpev_thresh_high']
                    code = code*self.databaseClient.update_documents(collection_name='home_configuration', document={'_id':3}, data = data)

                    data = self.databaseClient.read_documents(collection_name='home_configuration', document={'_id':7})
                    data['time']['time_dep'] = payload['oldParameters']['time_dep']
                    code = code*self.databaseClient.update_documents(collection_name='home_configuration', document={'_id':7}, data = data)
                    
                    if code == 1:
                        self.__append_data(code=timestamp, data={'response':'Updating setpoints success'})
                        logging.info('Updating setpoints success')
                    else:
                        self.__append_data(code=timestamp, data={'response':' user Updating setpoints failed'})    
                        logging.error('Updating setpoints failed')

                    payload['command'] = 0
                    payload['start_time'] = []
                    del payload['new_value']
                    
                    self.instance.get_data_serv()
                    self.shems.get_new_instance(self.instance)

                    self.shems.set_working_mode(payload)
                    cod = self.shems.solve_definitive()

                    if cod == 2:
                        self.__append_data(code=timestamp, data={'response':'Updating setpoint performed, new scheduling'})
                        self.__historyData_saving(step)
                        logging.info('New scheduling performed')
                    elif cod == -1:
                        self.__append_data(code=timestamp, data={'response':'New scheduling failed'})
                        logging.error('New scheduling failed')
                    
                    self.__clear_file(self.commands_path)

                elif c['command'] == 'addAppliances':
                    payload = c['payload']
                    
                    data = self.databaseClient.read_documents(collection_name='home_configuration', document={'_id':4})
                    fp = open('./files/appliances_info.json')
                    cfg = json.load(fp)
                    fp.close()

                    if i['name'] != 'washing_machine' or i['name'] != 'dishwasher' or i['name'] != 'vacuum_cleaner':
                        data['appliances']['N_sched_appliances'] += 1
                        data['appliances']['sched_appliances']['name'].append('other')
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
                    code = self.databaseClient.update_documents(collection_name='home_configuration', document={'_id':4}, data=data)
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
                        self.__append_data(code=timestamp, data={'response':'Updating appliances list performed, new scheduling'})
                        logging.info("addAppliances request performed")
                    elif cod == -1:
                        self.__append_data(code=timestamp, data={'response':'Updating appliances list failed, no new scheduling'})
                        logging.error('Updating appliances list failed, no new scheduling')

                    self.__clear_file(self.commands_path)

                elif c['command'] == 'deleteAppliances':
                    payload = c['payload']
                    data = self.databaseClient.read_documents(collection_name='home_configuration', document={'_id':4})

                    data['appliances']['N_sched_appliances'] -= 1
                    for i in data['appliances']['sched_appliances']['name']:
                        if i == payload['applianceData']['name']:
                            data['appliances']['sched_appliances']['name'].pop(i)
                            data['appliances']['sched_appliances']['running_len'].pop(i)
                            data['appliances']['sched_appliances']['num_cycles'].pop(i)
                            data['appliances']['sched_appliances']['power_cons'].pop(i)
                            data['appliances']['sched_appliances']['c1'].pop(i)
                            data['appliances']['sched_appliances']['c2'].pop(i)
                            code = self.databaseClient.update_documents(collection_name='home_configuration', document={'_id':4}, data=data)
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
                                self.__append_data(code=timestamp, data={'response':'Updating appliances list success, new scheduling'})
                                logging.info('"deleteAppliances request performed')
                            elif cod == -1:
                                self.__append_data(code=timestamp, data={'response':'Updating appliances list failed, no new scheduling'})
                                logging.info('Updating appliances list failed')
                        else:
                            logging.warning('Error appliances name wrong, not found')

                    self.__clear_file(self.commands_path)

                elif c['command'] == 'communityPlots':
                    try:
                        payload = c['payload']
                        data = self.databaseClient.read_documents(collection_name='data_collected', document={'_id':'hisotry'})
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
                                    s += data[payload['which']][(step-j)*i]

                                values.append(s/(60/self.time_granularity))
                                xlabel.append((step-i)*self.time_granularity/60)
                                if s/(60/self.time_granularity) > max: max = s/(60/self.time_granularity)
                                if s/(60/self.time_granularity) < min: min = s/(60/self.time_granularity)
                                m += s/(60/self.time_granularity)
                            requiredData['data'] = values # values
                            requiredData['label'] = xlabel # xlabel
                            requiredData['mean'] = m/24
                            requiredData['min'] = min
                            requiredData['max'] = max

                        elif payload['when'] == 'week':
                            values = []
                            xlabel = []
                            min = 999999
                            max = -999999
                            m = 0
                            for i in range (7):
                                s = 0
                                for j in range(24*self.time_granularity):
                                    s += data[payload['which']][(step-j)*i]

                                values.append(s/(24*(60/self.time_granularity)))
                                xlabel.append((step-i*(self.time_granularity*24)))
                                if s/(24*(60/self.time_granularity)) > max: max = s/(24*(60/self.time_granularity))
                                if s/(24*(60/self.time_granularity)) < min: min = s/(24*(60/self.time_granularity))
                                m += s/(24*(60/self.time_granularity))
                            requiredData['data'] = values # values
                            requiredData['label'] = xlabel# xlabel
                            requiredData['mean'] = m/(7)
                            requiredData['min'] = min
                            requiredData['max'] = max
                        
                        elif payload['when'] == 'month':
                            values = []
                            xlabel = []
                            min = 999999
                            max = -999999
                            m = 0
                            for i in range (7*4):
                                s = 0
                                for j in range(24*(60/self.time_granularity)):
                                    s += data[payload['which']][(step-j)*i]

                                if s/(24*(60/self.time_granularity)) > max: max = s/(24*(60/self.time_granularity))
                                if s/(24*(60/self.time_granularity)) < min: min = s/(24*(60/self.time_granularity))
                                m += s/(24*(60/self.time_granularity))
                            requiredData['data'] = values # values
                            requiredData['label'] = xlabel # xlabel
                            requiredData['mean'] = m/(7)
                            requiredData['min'] = min
                            requiredData['max'] = max

                        elif payload['when'] == 'year':
                            values = []
                            xlabel = []
                            min = 999999
                            max = -999999
                            m = 0
                            for i in range (7*4*12):
                                s = 0
                                for j in range(24*(60/self.time_granularity)):
                                    s += data[payload['which']][(step-j)*i]

                                if s/(24*(60/self.time_granularity)) > max: max = s/(24*(60/self.time_granularity))
                                if s/(24*(60/self.time_granularity)) < min: min = s/(24*(60/self.time_granularity))
                                m += s/(24*(60/self.time_granularity))
                            requiredData['data'] = values # values
                            requiredData['label'] = xlabel # xlabel
                            requiredData['mean'] = m/(7)
                            requiredData['min'] = min
                            requiredData['max'] = max

                        self.__append_data(code=timestamp, data=requiredData)
                        
                        logging.info('"communityPlots" GET request performed')
                    except:
                        logging.error('communityPlots GET request failed')

                    self.__clear_file(self.commands_path)

                elif c['command'] == 'communityProsumers':
                    try:
                        data = self.databaseClient.read_documents(collection_name='data_collected', document={'_id':'hisotry'})
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
                                    tot_price_bought += i['energies'][j]*i['prices'][j]
                                else: # <0 
                                    tot_energy_sold += abs(i['energies'][j])
                                    tot_price_sold += abs(i['energies'][j]*i['prices'][j])
                            ob['mean_price_bought'] = tot_price_bought/len(i['energies'])
                            ob['mean_price_sold'] = tot_price_sold/len(i['energies'])
                            ob['mean_energy_bought'] = tot_energy_bought/len(i['energies'])
                            ob['mean_energy_sold'] = tot_energy_sold/len(i['energies'])
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


                        self.append_data(code=timestamp, data=requiredData)

                        logging.info('"communityProsumers" GET request performed')  
                    except:
                        logging.error('"communityProsumers" GET request failed') 
                    
                    self.clear_file(self.commands_path) 

                elif c['command'] == 'registration':
                    try:
                        code = 1
                        payload = c['payload']
                        data = {}

                        data['name'] = payload['family_name']
                        
                        # Minimum and maximum temperature of the environment and of the WH
                        data = self.databaseClient.read_documents(collection_name='home_configuration', document={'_id':0})
                        data['home_setpoints']['Tin_max'] = payload['setpoints']['Tin_max']
                        data['home_setpoints']['Tin_min'] = payload['setpoints']['Tin_min']
                        data['home_setpoints']['Tewh_max'] = payload['setpoints']['Tewh_max']
                        data['home_setpoints']['Tewh_min'] = payload['setpoints']['Tewh_min']
                        code = code*self.databaseClient.update_documents('home_configuration', {'_id':0}, data)

                        # Departure car time, minimum and maximum threashold charging level (home and EV)
                        data = self.databaseClient.read_documents(collection_name='home_configuration', document={'_id':3})
                        data['batteries']['Cpev_thresh_low'] = payload['EV']['Cpev_thresh_low']
                        data['batteries']['Cpev_thresh_high'] = payload['EV']['Cpev_thresh_high']
                        data['batteries']['Cess_thresh_low'] = payload['home_batteries']['Cess_thresh_low']
                        data['batteries']['Cess_thresh_high'] = payload['home_batteries']['Cess_thresh_high'] 
                        code = code*self.databaseClient.update_documents('home_configuration', {'_id':3}, data)

                        data = self.databaseClient.read_documents(collection_name='home_configuration', document={'_id':7})
                        data['time']['time_dep'] = payload['EV']['Time_departure']

                        # None -> for not having the car
                        code = code*self.databaseClient.update_documents('home_configuration', {'_id':7}, data)

                        # appliances:[modello, lavatrice-lavastovigle-vacuum cliner]
                        fp = open('./files/appliances_info.json')
                        cfg = json.load(fp)
                        fp.close()
                        data = self.databaseClient.read_documents(collection_name='home_configuration', document={'_id':4})

                        for i in payload['applianceData']:
                            if i['name'] != 'washing_machine' or i['name'] != 'dishwasher' or i['name'] != 'vacuum_cleaner':
                                data['appliances']['N_sched_appliances'] += 1
                                data['appliances']['sched_appliances']['name'].append('other')
                                running_len = i['running_len']
                                running_len = int(running_len/self.time_granularity)
                                data['appliances']['sched_appliances']['running_len'].append(running_len)
                                data['appliances']['sched_appliances']['num_cycles'].append(1)
                                data['appliances']['sched_appliances']['power_cons'].append(i['power_cons'])
                                data['appliances']['sched_appliances']['c1'].append(1)
                                data['appliances']['sched_appliances']['c2'].append(2)
                            else:
                                data['appliances']['N_sched_appliances'] += 1
                                data['appliances']['sched_appliances']['name'].append(i['name'])
                                data['appliances']['sched_appliances']['running_len'].append(cfg[i['name']]['running_len'])
                                data['appliances']['sched_appliances']['num_cycles'].append(cfg[i['name']]['num_cycles'])
                                data['appliances']['sched_appliances']['power_cons'].append(cfg[i['name']]['power_cons'])
                                data['appliances']['sched_appliances']['c1'].append(cfg[i['name']]['c1'])
                                data['appliances']['sched_appliances']['c2'].append(cfg[i['name']]['c2'])
                        code = code*self.databaseClient.update_documents('home_configuration', {'_id':4}, data)

                        if code == 1:
                            self.__append_data(code=timestamp, data={'response':'New user registration success'})
                            logging.info('New registration success')
                        else:
                            self.__append_data(code=timestamp, data={'response':'New user registration failed, database error'})    
                            logging.error('New registration failed, database error')
                    except:
                        self.__append_data(code=timestamp, data={'response':'New user registration failed'})
                        logging.error('Error new user registration failed')

                    self.__clear_file(self.commands_path)
        except:
            logging.error('User command reading or execution error')

    def __clear_file(self, path):
        # TODO:azzeramento file comandi, attenzione da gestire se ho più comandi insieme
        try:
            fp = open(path, 'w')
            json.dump({'commands_list':[]},fp)
            fp.close()

            logging.info('GUI_thread_commands.json cleaned')
        except:
            logging.error('GUI_thread_commands.json error')
        """
        fp = open(path)
        file = json.load(fp)
        fp.close
        del file[command]
        fp = open(path, 'w')
        json.dump(file)
        fp.close
        """

    def __append_data(self, code, data):
        """Append data to GUI_thread_data.json
    
        Args:
            code: webserver reception command timestamp: command_list[i]['timestamp'] 
            data (dict): data response
        """
        try:
            fp = open(self.data_path)
            file = json.load(fp)
            fp.close()

            file['responses'][code] = data

            fp = open(self.data_path, 'w')
            json.dump(file,fp)
            fp.close()

            logging.info('GUI_thread_data.json cleaned')
        except:
            logging.info('GUI_thread_data.json error') 

    def __historyData_saving(self, step):
        """Storing daily data

        Args:
            step (int): time reference considering the time granularity
        """
        try:
            # power consumption saving
            data = self.databaseClient.read_documents(collection_name='data_collected', document={'_id':'history'})
            i = 60/self.time_granularity*24-step
            for j in range(i):
                data['Phouse_consume'][-i+j] = self.shems.Phouse_consume[step+j]
            code = self.databaseClient.update_documents(collection_name='data_collected', document={'_id':'history'}, object=data)
            if code == 1: logging.info('Data updated')
            else: logging.error('Database failed')

            # historyDataMarket_saving
            data = self.databaseClient.read_documents(collection_name='data_collected', document={'_id':'history'})
            i = 60/self.time_granularity*24-step
            for j in range(i):
                if self.shems.Pg_market[step+j] > 0:
                    data['energyBought'][-i+j] = self.shems.Pg_market[step+j]
                    data['energySold'][-i+j] = 0
                else:
                    data['energyBought'][-i+j] = 0
                    data['energySold'][-i+j] = self.shems.Pg_market[step+j]
                data['Pg_market'][-i+j] = self.shems.Pg_market[step+j]   
            code = self.databaseClient.update_documents(collection_name='data_collected', document={'_id':'history'}, object=data)
            if code == 1: logging.info('Data updated')
            else: logging.error('Database failed')

            logging.info('Data saving performed')
        except:
            logging.error('Database error during data saving')
    
    def __reset(self):
        """Reset of the system: databse and files
        """
        try:
            self.__clear_file(self.commands_path)
            self.__clear_file(self.data_path)
            
            code = 1
            data = {}
            data['Phouse_consume'] = []
            data['energyBought'] = []
            data['energySold'] = []
            data['Pg_market'] = []
            data['prosumers'] = []
            code = code*self.databaseClient.update_documents(collection_name='data_collected', document={'_id':'history'}, object=data)

            data = {}
            data['appliances']['N_sched_appliances'] = 0
            data['appliances']['sched_appliances']['name'] = []
            data['appliances']['sched_appliances']['running_len'] = []
            data['appliances']['sched_appliances']['power_cons'] = []
            data['appliances']['sched_appliances']['c1'] = []
            data['appliances']['sched_appliances']['c2'] = []
            code = code*self.databaseClient.update_documents(collection_name='home_configuration', document={'_id':4}, object=data)

            if code == 1: logging.info('Data resetted')
            else: logging.error('Database failed')
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
    GUIcommands = perpetualTimer(t=5, hFunction=main.GUI_thread_callback)
    GUIcommands.start()

    #prosumer = Prosumer("shems")
    #prosumer_timer = perpetualTimer(t = 15*60, hFunction=prosumer.thread_callback)
    #prosumer_timer.start()

    while True:
        pass