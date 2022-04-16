import json
import math
import logging
import requests
import datetime
import numpy as np
from numpy.random import randint, normal

from utilities.timer import perpetualTimer
from utilities.mqttclient import MQTTSubscriber, MQTTPublisher
from mongoDB.database_client import databaseClient
from optimizationModel.Simulator.instance import Instance
from optimizationModel.LP_solver.SHEMSModel import SHEMS

class SHEMS_main():
    def __init__(self, cfg):
        """SHEMS system object. It includes the instance of the energy optimization toll, the instance of the MQTT subscriber and publisher and the instance of the push notificator

        Args:
            cfg (dict): configuration file
        """
        try:
            self.time_granularity = cfg['time_granularity']

            # Energy optimization model
            self.databaseClient = databaseClient()
            new_instance = Instance()
            self.shems = SHEMS(new_instance)
            
            # Sensors subscribers MQTT
            self.waterWithdrawn_topic = cfg['waterWithdrawn_topic']
            self.carStation_topic = cfg['carStation_topic']
            self.smartMeter_topic = cfg['smartmeter_topic']
            self.deviceID = randint(1000000000)
            self.broker = cfg['mqtt_broker']
            self.port = cfg['mqtt_port']
            self.sensors_subscriber = MQTTSubscriber(self.deviceID, self.broker, self.port)
            self.sensors_subscriber.start()
            self.sensors_subscriber.callbackRegistration(self.sensorsSubscriber_callback)
            self.sensors_subscriber.mySubscribe(self.waterWithdrawn_topic)
            self.sensors_subscriber.mySubscribe(self.carStation_topic)
            self.sensors_subscriber.mySubscribe(self.smartMeter_topic)

            # Weather forecast API
            self.city = cfg['home_city']
            self.country_code=cfg['country_code']
            self.BASE_URL1 = cfg['BASE_URL1']
            self.BASE_URL2 = cfg['BASE_URL2']
            self.API_KEY = cfg['API_KEY']
            limit = 1
            url = f"http://api.openweathermap.org/geo/1.0/direct?q={self.city},{self.country_code}&limit={limit}&appid={self.API_KEY}"
            response = requests.get(url)
            if response.status_code == 200:
                self.lat = int(response.json()['lat'])
                self.lon = int(response.json()['lon'])
            else:
                logging.info(f'Error city coordinates recovering: {response.status_code}')

            # Push notification
            self.server_topic = cfg['server_topic'] # LO USO PER ANDARE VERSO IL SERVER
            self.client_topic = cfg['client_topic'] # LO USO PER ANDARE VERSO IL CLIENT FINALE, CIOè LA GUI
            self.serverID_publisher = 'publisher_server'
            self.myserver_publisher = MQTTPublisher(self.serverID_publisher, self.broker, self.port)
            self.myserver_publisher.start()
            self.serverID_subscriber = 'subscriber_server'
            self.myserver_subscriber = MQTTSubscriber(self.serverID_subscriber, self.broker, self.port)
            self.myserver_subscriber.start()
            self.myserver_subscriber.callbackRegistration(self.myserver_subscriber_callback)
            self.myserver_subscriber.mySubscribe(self.server_topic)
            
            self.homeID_publisher = 'publisher_home'
            self.home_publisher = MQTTPublisher(self.homeID_publisher, self.broker, self.port)
            self.home_publisher.start()
        except:
            logging.info('Environment generation failed')

    def basicScheduling_thread_callback(self):
        """First day scheduling, done at 8:00 a.m. 
        """    
        self.weatherAPI()
        
        self.instance = self.instance.get_data_serv() #NON OLO RICONOSCE!!!!!!!!!!
        self.shems.get_new_instance(self.instance)
        
        cod = self.shems.solve_definitive()
        if cod == 2:
            try:
                self.home_publisher.myPublish(self.server_topic, 'First scheduling of the day having success')
            except:
                logging.info('Error of the home during sending push notification message to the server')
        elif cod == -1:
            logging.info('First scheduling of the day failed')
    
    def weatherAPI(self):
        """Open weather map call to retrive temperature forecast for the day. Stores the results in the database
        """
        url = f'{self.BASE_URL2}lat={self.lat}&lon={self.lon}&appid={self.API_KEY}'
        response = requests.get(url)
        
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
                    new_solarRadiation.append(normal(loc=center, scale=std))
                elif i <= 18*(60/self.time_granularity):
                    center = center - 9/(4*60/self.time_granularity)
                    if center < 1: center = 1
                    new_solarRadiation.append(normal(loc=center, scale=std))
                else:
                    new_solarRadiation.append(0)

            data = self.databaseClient.read_documents(collection_name='home_configuration', document={'_id':1})
            data['Tout']=new_temp
            data['RES_hour_geen'] = new_solarRadiation
            self.databaseClient.update_documents(collection_name='home_configuration', document={'_id':1}, object=data)
        else:
            logging.info(f'Weather forecast API response status code: {response.status_code}')    

    def sensorsSubscriber_callback(self, msg):
        """Subscriber fot car station and hot water usage

        Args:
            msg (MQTT msg): 
        """
        if msg.topic == self.waterWithdrawn_topic:
            new_data = msg.payload
            data = self.databaseClient.read_documents(collection_name='home_configuration', document={'_id':2})
            Wd = data['Wd']

            time = str(datetime.datetime.now())
            hh = time.split(' ')[1].split(':')[0]
            mm = time.split(' ')[1].split(':')[1]
            step = 60/self.time_granularity*hh + math.floor(mm/self.time_granularity) 

            if new_data > Wd[step]:
                Wd[step] = new_data
                data = self.databaseClient.read_documents(collection_name='home_configuration', document={'_id':2})
                data['Wd']=Wd
                self.databaseClient.update_documents(collection_name='home_configuration', document={'_id':2}, object=Wd)

            self.instance = self.instance.get_data_serv() #NON OLO RICONOSCE!!!!!!!!!!
            self.shems.get_new_instance(self.instance)
        
            cod = self.shems.solve_definitive()
            if cod == 2:
                try:
                    self.home_publisher.myPublish(self.server_topic, 'New schedling, big amount of hot water used')
                except:
                    logging.info('Error of the home during sending push notification message to the server')
            elif cod == -1:
                logging.info('New scheduling falied, too much hot water required')

            # TODO: il valore che ricevo lo genero tra e 0.03 , faccio un publisher, 

        elif msg.topic == self.carStation_topic:
            if msg.payload == 1:
                self.shems.set_car_arrival()
                self.home_publisher.myPublish(self.server_topic, 'Electric vehicle in the garage')
            else: 
                logging.info('Error in the carStation publisher')
        elif msg.topic == self.smartMeter_topic:

            # TODO: mi serve un publoisher
            
            data = self.databaseClient.read_documents(collection_name='home_configuration', document={'_id':6})
            data['values']=msg.payload
            self.databaseClient.update_documents('home_configuration', {'_id':6}, data)

            self.basicScheduling_thread_callback()
    
            # TODO: salvo i dati degli attributi di shems, ad ogni nuovo scheduling devo aggiornare i dati salvati: posso avere un giorno con più schedule e quindi opiù dati

        else:
            logging.info(f'Error in the topic: {msg.topic}')

    def GUI_thread_callback(self):
        """Command manager. It reads the commands from the web server and provide to them a response
        payload = {'command':0/1/2, appliance:[], start_time:[]}
        0 = change setpoint
        1 = modify shcduling
        2: change delete appliance 
        """
        fp = open('./files/GUI_thread_commands.json', 'r')
        file = json.load(fp)
        fp.close()

        commands = file['commands_list']
        for i in commands:
            timestamp = i['timestamp']
            time = str(timestamp)
            hh = time.split(' ')[1].split(':')[0]
            mm = time.split(' ')[1].split(':')[1]
            step = 60/self.time_granularity*hh + math.floor(mm/self.time_granularity) 

            if i['command']=='home': # on at this moment
                #step

                # TODO: capire quali attributi mi servono e vedere nello step attuale quale applaincec è attivo e batteria
                # sono vettori di grandezza di 96, tranne ud è una matrice: 96*n_appliances, il livello delle batterie: self.shems.Cess / Cpev 0-Cess_max/Cpev_max

                self.append_data(code=timestamp, data=data)

            elif i['command']=='scheduling':

                # TODO: recuepero gli uno dalle variabili di shems
                # in più storico della giornata delle attività fatte

                self.append_data(code=timestamp, data=data)
            elif i['command']=='changeScheduling':
                payload = i['payload'] 
                payload['command']=1
                # payload['start_time'] == now o data hh:mm da dire ad alwjo
                
                self.instance = self.instance.get_data_serv() #NON OLO RICONOSCE!!!!!!!!!!
                self.shems.get_new_instance(self.instance)

                self.shems.set_working_mode(payload)
                cod = self.shems.solve()
                if cod == 2:
                    self.append_data(code=timestamp, data={'response':'Changing schedluinig success, new scheduling'})
                elif cod == -1:
                    logging.info('Changing scheduling failed, no new scheduling')
                    self.append_data(code=timestamp, data={'response':'Changing schedluinig failed, no new scheduling'})
            elif i['command']=='summary':
                payload = i['payload']
                data = self.databaseClient.read_documents(collection_name='data_collected', document={'_id':'history'})
                requiredData = []

                if payload['when'] == 'day':
                    # devo andare indietro di 24*4 valori
                    values = []
                    xlabel = []
                    min = 999999
                    max = -999999
                    m = 0
                    for i in range(24):
                        s = 0                        
                        for j in range(self.time_granularity):
                            s += self.shems.Phouse_consume[(step-j)*i]
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
                    # 24*4*  7
                    values = []
                    xlabel = []
                    min = 999999
                    max = -999999
                    m = 0
                    for i in range (7):
                        s = 0
                        for j in range(24*self.time_granularity):
                            s += self.shems.Phouse_consume[(step-j)*i]
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
                    # 24*4*  7
                    values = []
                    xlabel = []
                    min = 999999
                    max = -999999
                    m = 0
                    for i in range (7*4):
                        s = 0
                        for j in range(24*(60/self.time_granularity)):
                            s += self.shems.Phouse_consume[(step-j)*i]
                        if s/(24*(60/self.time_granularity)) > max: max = s/(24*(60/self.time_granularity))
                        if s/(24*(60/self.time_granularity)) < min: min = s/(24*(60/self.time_granularity))
                        m += s/(24*(60/self.time_granularity))
                    requiredData['data'] = values # values
                    requiredData['label'] = xlabel # xlabel
                    requiredData['mean'] = m/(7)
                    requiredData['min'] = min
                    requiredData['max'] = max
                elif payload['when'] == 'year':
                    # 4*24*7*4*12
                    values = []
                    xlabel = []
                    min = 999999
                    max = -999999
                    m = 0
                    for i in range (7*4*12):
                        s = 0
                        for j in range(24*(60/self.time_granularity)):
                            s += self.shems.Phouse_consume[(step-j)*i]
                        if s/(24*(60/self.time_granularity)) > max: max = s/(24*(60/self.time_granularity))
                        if s/(24*(60/self.time_granularity)) < min: min = s/(24*(60/self.time_granularity))
                        m += s/(24*(60/self.time_granularity))
                    requiredData['data'] = values # values
                    requiredData['label'] = xlabel # xlabel
                    requiredData['mean'] = m/(7)
                    requiredData['min'] = min
                    requiredData['max'] = max

                self.append_data(code=timestamp, data=requiredData)
                # TODO: fare in modo che i dati più vecchi di un certo periodo vengano compressi per risparmiare spazio (più tardi)
                
            elif i['command']=='changeSetpoints':   # ----> {Tin_max/Tin_min:int;Tewh_max/Tewh_min:int;time_dep:datetime object}
                payload = i['payload']
                if payload['applaince'] == '': 
                    # decidere con alejo che nome dare per le batterie setpoints
                    # aggiungere da id_3: cess thresh_low/high
                    data = self.databaseClient.read_documents(collection_name='home_configuration', document={'_id':3})
                    data[payload['appliance']]=payload['new_value']
                    self.databaseClient.update_documents(collection_name='home_configuration', document={'_id':3}, data=data)
                else:
                    data = self.databaseClient.read_documents(collection_name='home_configuration', document={'_id':0})
                    data[payload['appliance']]=payload['new_value']
                    self.databaseClient.update_documents(collection_name='home_configuration', document={'_id':0}, data=data)
                
                payload['command'] = 0
                payload['start_time'] = []
                del payload['new_value']
                
                self.instance = self.instance.get_data_serv() #NON OLO RICONOSCE!!!!!!!!!!
                self.shems.get_new_instance(self.instance)

                self.shems.set_working_mode(payload)
                cod = self.shems.solve_definitive()
                if cod == 2:
                    self.append_data(code=timestamp, data={'response':'Updating setpoint success, new scheduling'})
                elif cod == -1:
                    logging.info('Updating setpoint failed, no new scheduling')
                    self.append_data(code=timestamp, data={'response':'Updating setpoint failed, no new scheduling'})

            elif i['command']=='addAppliances':
                payload = i['payload']
                data = self.databaseClient.read_documents(collection_name='home_configuration', document={'_id':4})
                fp = open('./files/appliances_info.json', 'r')
                cfg = json.load(fp)
                fp.close()
                """
                {
                    {
                        name1: {
                            running_len: ,
                            num_cycles: ,
                            ...
                        }
                        name2: {
                            running_len: ,
                            num_cycles: ,
                            ...
                        }
                    }
                }
                """
                data['N_sched_appliances'] += 1
                data['sched_appliances']['name'].append(payload['which'])
                data['sched_appliances']['running_len'].append(cfg[payload['which']]['running_len'])
                data['sched_appliances']['num_cycles'].append(cfg[payload['which']]['num_cycles'])
                data['sched_appliances']['power_cons'].append(cfg[payload['which']]['power_cons'])
                data['sched_appliances']['c1'].append(cfg[payload['which']]['c1'])
                data['sched_appliances']['c2'].append(cfg[payload['which']]['c2'])
                self.databaseClient.update_documents(collection_name='home_configuration', document={'_id':4}, data=data)
                del payload['applianceData']
                payload['command'] = 2
                payload['appliance'] = []
                payload['start_time'] = []

                self.instance = self.instance.get_data_serv() #NON OLO RICONOSCE!!!!!!!!!!
                self.shems.get_new_instance(self.instance)

                self.shems.set_working_mode(payload)
                cod = self.shems.solve_definitive()
                if cod == 2:
                    self.append_data(code=timestamp, data={'response':'Updating appliances list success, new scheduling'})
                elif cod == -1:
                    logging.info('Updating appliances list failed, no new scheduling')
                    self.append_data(code=timestamp, data={'response':'Updating appliances list failed, no new scheduling'})
            
            elif i['command']=='deleteAppliances':
                payload = i['payload']
                data = self.databaseClient.read_documents(collection_name='home_configuration', document={'_id':4})

                data['N_sched_appliances'] -= 1
                for i in data['sched_appliances']['name']:
                    if i == payload['applianceData']['name']:
                        data['sched_appliances']['name'].pop(i)
                        data['sched_appliances']['running_len'].pop(i)
                        data['sched_appliances']['num_cycles'].pop(i)
                        data['sched_appliances']['power_cons'].pop(i)
                        data['sched_appliances']['c1'].pop(i)
                        data['sched_appliances']['c2'].pop(i)
                        self.databaseClient.update_documents(collection_name='home_configuration', document={'_id':4}, data=data)
                        del payload['applianceData']
                        payload['command'] = 2
                        payload['appliance'] = []
                        payload['start_time'] = []
                        
                        self.instance = self.instance.get_data_serv() #NON OLO RICONOSCE!!!!!!!!!!
                        self.shems.get_new_instance(self.instance)

                        self.shems.set_working_mode(payload)
                        cod = self.shems.solve_definitive()
                        if cod == 2:
                            self.append_data(code=timestamp, data={'response':'Updating appliances list success, new scheduling'})
                        elif cod == -1:
                            logging.info('Updating appliances list failed')
                            self.append_data(code=timestamp, data={'response':'Updating appliances list failed, no new scheduling'})
                    else:
                        logging.info('Error appliances name wrong, not found')

            elif i['command']=='community':
                # tranquillomodifico anche te m aspettiamo un attimo
                payload = i['payload']
                data = self.databaseClient.read_documents(collection_name='prosumer_community', document={'_id':payload['while']})
                requiredData = []
                
                if payload['when'] == 'day':
                    # devo andare indietro di 24*4 valori

                    #TODO: sostituire Phouse_consume con altro
                    values = []
                    xlabel = []
                    min = 999999
                    max = -999999
                    m = 0
                    for i in range(24):
                        s = 0                        
                        for j in range(self.time_granularity):
                            s += self.shems.Phouse_consume[(step-j)*i]
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
                    # 24*4*  7
                    values = []
                    xlabel = []
                    min = 999999
                    max = -999999
                    m = 0
                    for i in range (7):
                        s = 0
                        for j in range(24*self.time_granularity):
                            s += self.shems.Phouse_consume[(step-j)*i]
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
                    # 24*4*  7
                    values = []
                    xlabel = []
                    min = 999999
                    max = -999999
                    m = 0
                    for i in range (7*4):
                        s = 0
                        for j in range(24*(60/self.time_granularity)):
                            s += self.shems.Phouse_consume[(step-j)*i]
                        if s/(24*(60/self.time_granularity)) > max: max = s/(24*(60/self.time_granularity))
                        if s/(24*(60/self.time_granularity)) < min: min = s/(24*(60/self.time_granularity))
                        m += s/(24*(60/self.time_granularity))
                    requiredData['data'] = values # values
                    requiredData['label'] = xlabel # xlabel
                    requiredData['mean'] = m/(7)
                    requiredData['min'] = min
                    requiredData['max'] = max
                elif payload['when'] == 'year':
                    # 4*24*7*4*12
                    values = []
                    xlabel = []
                    min = 999999
                    max = -999999
                    m = 0
                    for i in range (7*4*12):
                        s = 0
                        for j in range(24*(60/self.time_granularity)):
                            s += self.shems.Phouse_consume[(step-j)*i]
                        if s/(24*(60/self.time_granularity)) > max: max = s/(24*(60/self.time_granularity))
                        if s/(24*(60/self.time_granularity)) < min: min = s/(24*(60/self.time_granularity))
                        m += s/(24*(60/self.time_granularity))
                    requiredData['data'] = values # values
                    requiredData['label'] = xlabel # xlabel
                    requiredData['mean'] = m/(7)
                    requiredData['min'] = min
                    requiredData['max'] = max

                self.append_data(code=timestamp, data=requiredData)

            elif i['command']=='registration':
                try:
                    payload = i['payload']
                    # temperatura minima e massima di boiler e ambiente,
                    data = self.databaseClient.read_documents(collection_name='home_configuration', document={'_id':0})
                    keys = payload['setpoints'].keys()
                    for i in keys:
                        data['home_setpoints'][i]=payload['setpoints'][i]
                    self.databaseClient.update_documents('home_configuration', {'_id':0}, data)

                    # ora di partenza della macchina, threshold minima di carica della macchina e massima 
                    data = self.databaseClient.read_documents(collection_name='home_configuration', document={'_id':3})
                    data['batteries']['.......'] = payload['EV']['time'] # metti nomi giudto: questo id_ 7
                    data['batteries']['........'] = payload['EV']['minimum']
                    data['batteries']['........'] = payload['EV']['maximum']
                    self.databaseClient.update_documents('home_configuration', {'_id':3}, data)

                    # appliances:[modello, lavatrice-lavastovigle-vacuum cliner]
                    fp = open('./files/appliances_info.json', 'r')
                    cfg = json.load(fp)
                    fp.close()
                    data = self.databaseClient.read_documents(collection_name='home_configuration', document={'_id':4})
                    data['N_sched_appliances'] += 1
                    data['sched_appliances']['name'].append(payload['which'])
                    data['sched_appliances']['running_len'].append(cfg[payload['which']]['running_len'])
                    data['sched_appliances']['num_cycles'].append(cfg[payload['which']]['num_cycles'])
                    data['sched_appliances']['power_cons'].append(cfg[payload['which']]['power_cons'])
                    data['sched_appliances']['c1'].append(cfg[payload['which']]['c1'])
                    data['sched_appliances']['c2'].append(cfg[payload['which']]['c2'])
                    self.databaseClient.update_documents('home_configuration', {'_id':4}, data)
                    
                    self.append_data(code=timestamp, data={'response':'New user registration success'})
                except:
                    self.append_data(code=timestamp, data={'response':'New user registration failed'})
                    logging.info('Error new user registration failed')

    def append_data(self, code, data):
        """Append data to GUI_thread_data.json
    
        Args:
            code: webserver reception command timestamp: command_list[i]['timestamp'] 
            data (dict): data response
        """
        try:
            fp = open('./filesU/GUI_thread_data.json', 'r')
            file = json.load(fp)
            fp.close()

            file['responses'][code] = data
            fp = open('./files/GUI_thread_data.json', 'w')
            json.dump(file,fp)
            fp.close()
        except:
            logging.info('Error during the reading of the "main.py" command response') 

    def myserver_subscriber_callback(self, msg):
        # TODO:contronllo del messaggio, piccola encriptazione del messaggio (in più)
        try:
            self.myserver_publisher.myPublish(self.client_topic, msg.payload)
        except:
            logging.info('Error of the push notification server')

if __name__ == '__main__':
    
    log_name = './logs/main.log'
    logging.basicConfig(
        filename=log_name,
        format='%(asctime)s %(levelname)s: %(message)s',
        level=logging.INFO, datefmt="%H:%M:%S",
        filemode='w'
    )

    fp = open('./files/starting_configuration.json', 'r')
    cfg = json.load(fp)
    fp.close()

    main = SHEMS_main(cfg)

    GUIcommands = perpetualTimer(t=0.5, hFunction=main.GUI_thread_callback)
    GUIcommands.start()

    while True:
        pass