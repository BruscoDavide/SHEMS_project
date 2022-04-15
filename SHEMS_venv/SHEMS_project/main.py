import json
import logging
from select import devpoll
from tokenize import Decnumber
from matplotlib.pyplot import xlabel
import requests
import datetime
import numpy as np

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
        # Energy optimization model
        self.databaseClient = databaseClient()
        new_instance = Instance()
        self.shems = SHEMS(new_instance)
        
        # Sensors subscribers MQTT
        self.waterWithdrawn_topic = cfg['waterWithdrawn_topic']
        self.carStation_topic = cfg['carStation_topic']
        self.smartMeter_topic = cfg['smartmeter_topic']
        self.deviceID = np.random.randint(1000000000)
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

    def basicScheduling_thread_callback(self):
        """First day scheduling, done at 8:00 a.m. 
        """    
        self.weatherAPI()

        # self.instance = self.instance.getdataserv
        # self.sehms.set_instace(instance.ge)
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
            data = response.json()['list'] # una lista
            for i in range(8): #24/3, data recovering: temperature every 3 hours
                temp.append(round(data[i]['main']['temp']-273, 1))

            new_temp = np.zeros(95)
            # solar radiation su varaibles esempio: res_hour_gebn dalle 8 del mattino per 40 samples con un picco di massimo 10 , faccio una campana
            # al massimo la facciamo figa dopo... 
            # rendere questa parte in funzione del time_granularity 
            for i in range(7): # 0-6, data every 1 hour
                new_temp[i*12]=temp[i]
                new_temp[i*12+1] = round(temp[i]-(temp[i]-temp[i+1])/12, 1)
                new_temp[i*12+2] = round(temp[i]-2*(temp[i]-temp[i+1])/12, 1)
                new_temp[i*12+3] = round(temp[i]-3*(temp[i]-temp[i+1])/12, 1)
                new_temp[i*12+4] = round(temp[i]-4*(temp[i]-temp[i+1])/12, 1)
                new_temp[i*12+5] = round(temp[i]-5*(temp[i]-temp[i+1])/12, 1)
                new_temp[i*12+6] = round(temp[i]-6*(temp[i]-temp[i+1])/12, 1)
                new_temp[i*12+7] = round(temp[i]-7*(temp[i]-temp[i+1])/12, 1)
                new_temp[i*12+8] = round(temp[i]-8*(temp[i]-temp[i+1])/12, 1)
                new_temp[i*12+9] = round(temp[i]-9*(temp[i]-temp[i+1])/12, 1)
                new_temp[i*12+10] = round(temp[i]-10*(temp[i]-temp[i+1])/12, 1)
                new_temp[i*12+11] = round(temp[i]-11*(temp[i]-temp[i+1])/12, 1)
            new_temp[84] = temp[7]
            if new_temp[83]<new_temp[84]: # crescente
                new_temp[85] = new_temp[84] + round((temp[6]-temp[7])/12, 1)
                new_temp[86] = new_temp[84] + 2*round((temp[6]-temp[7])/12, 1)
                new_temp[87] = new_temp[84] + 3*round((temp[6]-temp[7])/12, 1)
                new_temp[88] = new_temp[84] + 4*round((temp[6]-temp[7])/12, 1)
                new_temp[89] = new_temp[84] + 5*round((temp[6]-temp[7])/12, 1)
                new_temp[90] = new_temp[84] + 6*round((temp[6]-temp[7])/12, 1)
                new_temp[91] = new_temp[84] + 7*round((temp[6]-temp[7])/12, 1)
                new_temp[92] = new_temp[84] + 8*round((temp[6]-temp[7])/12, 1)
                new_temp[93] = new_temp[84] + 9*round((temp[6]-temp[7])/12, 1)
                new_temp[94] = new_temp[84] + 10*round((temp[6]-temp[7])/12, 1)
                new_temp[95] = new_temp[84] + 11*round((temp[6]-temp[7])/12, 1)
            else: # decrescente
                new_temp[85] = new_temp[84] - round((temp[6]-temp[7])/12, 1)
                new_temp[86] = new_temp[84] - 2*round((temp[6]-temp[7])/12, 1)
                new_temp[87] = new_temp[84] - 3*round((temp[6]-temp[7])/12, 1)
                new_temp[88] = new_temp[84] - 4*round((temp[6]-temp[7])/12, 1)
                new_temp[89] = new_temp[84] - 5*round((temp[6]-temp[7])/12, 1)
                new_temp[90] = new_temp[84] - 6*round((temp[6]-temp[7])/12, 1)
                new_temp[91] = new_temp[84] - 7*round((temp[6]-temp[7])/12, 1)
                new_temp[92] = new_temp[84] - 8*round((temp[6]-temp[7])/12, 1)
                new_temp[93] = new_temp[84] - 9*round((temp[6]-temp[7])/12, 1)
                new_temp[94] = new_temp[84] - 10*round((temp[6]-temp[7])/12, 1)
                new_temp[95] = new_temp[84] - 11*round((temp[6]-temp[7])/12, 1)
            
            data = self.databaseClient.read_documents(collection_name='home_configuration', document={'_id':1})
            data['Tout']=new_temp
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
            # TODO: ricevo un valori di flusso lo confronto con il vaore settato se minore amen se manggiore modifco e chiamo il modello
            # il valore che ricevo lo genero tra e 0.03 , faccio un publisher, se il codice del modello è -1 richiedo troppa acqua dia ll'utente fottiti
            data = self.databaseClient.read_documents(collection_name='home_configuration', document={'_id':})
            data['Tout']=new_temp
            self.databaseClient.update_documents(collection_name='home_configuration', document={'_id':1}, object=data)
        elif msg.topic == self.carStation_topic:
            if msg.payload == 0 or msg.payload == 1:
                #new_data = msg.payload
                self.shems.set_car_arrival() #se arriva un 1
            else: 
                logging.info('Error in the carStation publisher')
        elif msg.topic == self.smartMeter_topic:
            # miserve un publoisher
            data = self.client.read_documents(collection_name='home_configuration', document={'_id':6})
            data['values']=msg.payload
            self.databaseClient.update_documents('home_configuration', {'_id':6}, data)
            # rifare lo scheduling solita storia... qui dentro ora faccio il primo scheduling della giornata (lo eleimino da in giro)
            # prima di iniziare la giornata mi salvo tutti i dati utili vecchi, da quellle variabili li (attributi di shems) 
            # NONNNNNNNNNNNNNNNNNNNNNNOOOOOOOOOOOaggiorniamo il server con lo storico dei dati ad ogni scheduling
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
            # TODO:check timestamp (più tardi)
            
            if i['command']=='home': # on at this moment

                # quando mi chiama home, io controllo quei vettori vedo cosa c'è attivo, guardo cosa c'è di attivo, temp casa, consumo acqua temp acqua ...
                # non mi serve il database leggo dagli attributi di shems
                # sono vettori di grandezza di 96, tranne ud è una matrice: 96*n_appliances
                # 15*timegranularity/60 = quante ore dalle otto di mattina lo confronto con il time stamp attuale 
                # brutto bastardo fammi vedere anche il livello delle batterie: self.shems.Cess / Cpev 0-Cess_max/Cpev_max
                data = self.databaseClient.read_documents(collection_name='data_collected', document={'_id':'home'})
                # TODO: write online appliances in the way shoed in the database
                self.append_data(code=timestamp, data=data)    
            elif i['command']=='scheduling':
                # vado sempre da quei vettori vado dalla matrice è leggo lo scheduling
                # 15*timegranularity/60 = quante ore dalle otto di mattina lo confronto con il time stamp attuale
                # in più storico della giornata delle attività fatte

                data = self.databaseClient.read_documents(collection_name='data_collected', document={'_id':'actual_scheduling'})
                self.append_data(code=timestamp, data=data)
            elif i['command']=='changeScheduling':
                payload = i['payload'] 
                #payload['start_time'] == now o data hh:mm 
                payload['command']=1

                self.shems.set_working_mode(payload)
                cod = self.shems.solve()
                if cod == 2:
                    self.append_data(code=timestamp, data={'response':'Changing schedluinig success, new scheduling'})
                elif cod == -1:
                    logging.info('Changing scheduling failed, no new scheduling')
                    self.append_data(code=timestamp, data={'response':'Changing schedluinig failed, no new scheduling'})
            elif i['command']=='summary':
                # Ad ogni nuovo timestamp aggiungo un valore in coda (append)
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
                        for j in range(4):
                            # ste mi fa una variabile della giornata, attenzione ho anche i dati del futuro, per ho vettori da 96 recuper dallo tiestmap adesso capisco quale valore mi serve
                            """
                               act_time = act_datetime[1].split(':')
        if act_time[0] == '00' or int(act_time[0]) < 8:
            act_mins = 16*60 #hours passed from 8 to midnight
            act_mins += int(act_time[0])
            act_mins += int(act_time[1])
        else:
            act_mins = (int(act_time[0]) - 8)*60
            act_mins += int(act_time[1])
        start_point = math.ceil(act_mins/self.instance.time_granularity ) -1
                            """
                            s += data[-(i+j+1)][data[-(i+j+1)].keys()[0]]['power'] #!!! non so se sarà power
                        values.append(s/4)
                        xlabel.append(data[-i+j+1].keys()[0])
                        if s/4 > max: max = s/4
                        if s/4 < min: min = s/4
                        m += s/4
                    requiredData['data'] = values # values
                    requiredData['label'] = xlabel# xlabel
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
                        for j in range(24*4):
                            s += data[-(i+j+1)][data[-(i+j+1)].keys()[0]][payload['power']]
                        values.append(s/(24*4))
                        xlabel.append(data[-i+j+1].keys()[0])
                        if s/(24*4) > max: max = s/(24*4)
                        if s/(24*4) < min: min = s/(24*4)
                        m += s/(24*4)
                    requiredData['data'] = values # values
                    requiredData['label'] = xlabel# xlabel
                    requiredData['mean'] = m/(7)
                    requiredData['min'] = min
                    requiredData['max'] = max
                   
                elif payload['when'] == 'month':
                    # 4*24*7*4 
                    s = 0
                    min = 999999
                    max = -999999
                    for i in range(4*24*7*4):
                        if data[-(i+j+1)][data[-(i+j+1)].keys()[0]][payload['power']] > max: max = data[-(i+j+1)][data[-(i+j+1)].keys()[0]][payload['power']]
                        if data[-(i+j+1)][data[-(i+j+1)].keys()[0]][payload['power']] < min: min = data[-(i+j+1)][data[-(i+j+1)].keys()[0]][payload['power']]
                        s +=  data[-(i+j+1)][data[-(i+j+1)].keys()[0]][payload['power']]
                    requiredData['min'] = min
                    requiredData['max'] = max
                    requiredData['mean'] = s/(4*24*7*4)
                elif payload['when'] == 'year':
                    # 4*24*7*4*12
                    s = 0
                    min = 999999
                    max = -999999
                    for i in range(4*24*7*4*12):
                        if data[-(i+j+1)][data[-(i+j+1)].keys()[0]][payload['power']] > max: max = data[-(i+j+1)][data[-(i+j+1)].keys()[0]][payload['power']]
                        if data[-(i+j+1)][data[-(i+j+1)].keys()[0]][payload['power']] < min: min = data[-(i+j+1)][data[-(i+j+1)].keys()[0]][payload['power']]
                        s +=  data[-(i+j+1)][data[-(i+j+1)].keys()[0]][payload['power']]
                    requiredData['min'] = min
                    requiredData['max'] = max
                    requiredData['mean'] = s/(4*24*7*4*12)

                self.append_data(code=timestamp, data=requiredData)
                # TODO: fare in modo che i dati più vecchi di un certo periodo vengano compressi per risparmiare spazio (più tardi)
                
            elif i['command']=='changeSetpoints':   # ----> {Tin_max/Tin_min:int;Tewh_max/Tewh_min:int;time_dep:datetime object}
                payload = i['payload']
                if payload['applaince'] == '': # quello delle batterie!!!!
                    data = self.databaseClient.read_documents(collection_name='home_configuration', document={'_id':3})
                    data[payload['appliance']]=payload['new_value']
                    self.databaseClient.update_documents(collection_name='home_configuration', document={'_id':3}, data=data)
                else:
                    data = self.databaseClient.read_documents(collection_name='home_configuration', document={'_id':0})
                    data[payload['appliance']]=payload['new_value']
                    self.databaseClient.update_documents(collection_name='home_configuration', document={'_id':0}, data=data)
                # aggiungere da id_3: cess thresh_low/high
                payload['command'] = 0
                payload['start_time'] = []
                del payload['new_value']

                self.shems.set_working_mode(payload)
                cod = self.shems.solve()
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

                self.shems.set_working_mode(payload)
                cod = self.shems.solve()
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
                        
                        self.shems.set_working_mode(payload)
                        cod = self.shems.solve()
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
                    values = []
                    xlabel = []
                    min = 999999
                    max = -999999
                    m = 0
                    for i in range(24):
                        s = 0                        
                        for j in range(4):
                            s += data[-(i+j+1)][data[-(i+j+1)].keys()[0]][payload['while']]
                        values.append(s/4)
                        xlabel.append(data[-i+j+1].keys()[0])
                        if s/4 > max: max = s/4
                        if s/4 < min: min = s/4
                        m += s/4
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
                        for j in range(24*4):
                            s += data[-(i+j+1)][data[-(i+j+1)].keys()[0]][payload['while']]
                        values.append(s/(24*4))
                        xlabel.append(data[-i+j+1].keys()[0])
                        if s/(24*4) > max: max = s/(24*4)
                        if s/(24*4) < min: min = s/(24*4)
                        m += s/(24*4)
                    requiredData['data'] = values # values
                    requiredData['label'] = xlabel# xlabel
                    requiredData['mean'] = m/(7)
                    requiredData['min'] = min
                    requiredData['max'] = max
                
                elif payload['when'] == 'month':
                    # 4*24*7*4 
                    s = 0
                    min = 999999
                    max = -999999
                    for i in range(4*24*7*4):
                        if data[-(i+j+1)][data[-(i+j+1)].keys()[0]][payload['while']] > max: max = data[-(i+j+1)][data[-(i+j+1)].keys()[0]][payload['while']]
                        if data[-(i+j+1)][data[-(i+j+1)].keys()[0]][ payload['while']] < min: min = data[-(i+j+1)][data[-(i+j+1)].keys()[0]][payload['while']]
                        s +=  data[-(i+j+1)][data[-(i+j+1)].keys()[0]][ payload['while']]
                    requiredData['min'] = min
                    requiredData['max'] = max
                    requiredData['mean'] = s/(4*24*7*4)
                elif payload['when'] == 'year':
                    # 4*24*7*4*12
                    s = 0
                    min = 999999
                    max = -999999
                    for i in range(4*24*7*4*12):
                        if data[-(i+j+1)][data[-(i+j+1)].keys()[0]][ payload['while']] > max: max = data[-(i+j+1)][data[-(i+j+1)].keys()[0]][payload['while']]
                        if data[-(i+j+1)][data[-(i+j+1)].keys()[0]][ payload['while']] < min: min = data[-(i+j+1)][data[-(i+j+1)].keys()[0]][payload['while']]
                        s +=  data[-(i+j+1)][data[-(i+j+1)].keys()[0]][payload['while']]
                    requiredData['min'] = min
                    requiredData['max'] = max
                    requiredData['mean'] = s/(4*24*7*4*12)
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

    SHEMS_thread_basic_scheduling = perpetualTimer(t=60, hFunction=main.basicScheduling_thread_callback) #24*60*60 = one day
    SHEMS_thread_basic_scheduling.start()

    GUIcommands = perpetualTimer(t=0.5, hFunction=main.GUI_thread_callback)
    GUIcommands.start()

    while True:
        pass