import json
import logging
import requests
import numpy as np

from utilities.timer import perpetualTimer
from utilities.mqttclient import MQTTSubscriber, MQTTPublisher
from mongoDB.database_client import databaseClient
from optimizationModel.Simulator.instance import Instance
from optimizationModel.LP_solver.SHEMSfile import SHEMS

class SHEMS_main():
    def __init__(self, cfg):
        """SHEMS system object. It includes the instance of the energy optimization toll, the instance of the MQTT subscriber and publisher and the instance of the push notificator

        Args:
            cfg (dict): configuration file
        """
        # Energy optimization model
        self.databaseClient = databaseClient()
        new_instance = Instance() # TODO: da aggiungere a instance costruttore data = new_databaseClient.read_myDocuments() 
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

        cod = self.shems.solve()
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
            # TODO: inserire controllo sul valore
            # TODO: scrivo sul database o cosa??
        elif msg.topic == self.carStation_topic:
            if msg.payload == 0 or msg.payload == 1:
                new_data = msg.payload
                # TODO: scrivo sul database o cosa??
            else: 
                logging.info('Error in the carStation publisher')
        elif msg.topic == self.smartMeter_topic:
            data = self.client.read_documents(collection_name='home_configuration', document={'_id':6})
            data['values']=msg.payload
            self.databaseClient.update_documents('home_configuration', {'_id':6}, data)
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
            
            if i['command']=='home':
                data = self.databaseClient.read_documents(collection_name='data_collected', document={'_id':'home'})
                self.append_data(code=timestamp, data=data)    
            elif i['command']=='appliances':
                data = self.databaseClient.read_documents(collection_name='data_collected', document={'_id':'home'})
                self.append_data(code=timestamp, data=data)
            elif i['command']=='scheduling':
                data = self.databaseClient.read_documents(collection_name='data_collected', document={'_id':'actual_scheduling'})
                self.append_data(code=timestamp, data=data)
            elif i['command']=='changeScheduling':
                payload = i['payload'] 
                payload['command']=1

                self.shems.set_working_mode(payload)
                cod = self.shems.solve()
                if cod == 2:
                    self.append_data(code=timestamp, data={'response':'Changing schedluinig success, new scheduling'})
                elif cod == -1:
                    logging.info('Changing scheduling failed, no new scheduling')
                    self.append_data(code=timestamp, data={'response':'Changing schedluinig failed, no new scheduling'})
            elif i['command']=='summary':
                # TODO: check data stored on database
                payload = i['payload']
                requiredData = []
                if payload['when'] == 'day':
                    data = self.databaseClient.read_documents(collection_name='data_collected', document={'_id':'history'})     
                    requiredData.append(data[''][''][payload['which']])
                elif payload['when'] == 'week':
                    data = self.databaseClient.read_documents(collection_name='data_collected', document={'_id':'history'}) 
                    for i in range(7):
                        requiredData.append(data[''][''][payload['which']])
                elif payload['when'] == 'month':
                    data = self.databaseClient.read_documents(collection_name='data_collected', document={'_id':'history'}) 
                    requiredData.append(data['summaries']['month'][payload['which']])
                elif payload['when'] == 'year':
                    data = self.databaseClient.read_documents(collection_name='data_collected', document={'_id':'history'}) 
                    requiredData.append(data['summaries']['year'][payload['which']])

                # TODO: fare in modo che i dati più vecchi di un certo periodo vengano compressi per risparmiare spazio (più tardi)
                # TODO: xlabel glielo passo a posta o se lo ricava lui
                self.append_data(code=timestamp, data=requiredData)
            elif i['command']=='changeSetpoints':   # ----> {Tin_max/Tin_min:int;Tewh_max/Tewh_min:int;time_dep:datetime object}
                payload = i['payload']
                data = self.databaseClient.read_documents(collection_name='home_configuration', document={'_id':0})
                data[payload['appliance']]=payload['new_value']
                self.databaseClient.update_documents('home_configuration', {'_id':0}, data)
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

                # TODO: also change EV setpoints (in più)

            elif i['command']=='addAppliances':
                payload = i['payload']
                data = self.databaseClient.read_documents(collection_name='home_configuration', document={'_id':4})
                
                data['N_sched_appliances'] += 1
                data['sched_appliances']['name'].append(payload['name'])
                data['sched_appliances']['running_len'].append(payload['running_len'])
                data['sched_appliances']['num_cycles'].append(payload['num_cycles'])
                data['sched_appliances']['power_cons'].append(payload['power_cons'])
                data['sched_appliances']['c1'].append(payload['c1'])
                data['sched_appliances']['c2'].append(payload['c2'])
                self.databaseClient.update_documents('home_configuration', {'_id':4}, data)
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
                data = self.client.read_documents(collection_name='home_configuration', document={'_id':4})

                data['N_sched_appliances'] -= 1
                for i in data['sched_appliances']['name']:
                    if i == payload['applianceData']['name']:
                        data['sched_appliances']['name'].pop(i)
                        data['sched_appliances']['running_len'].pop(i)
                        data['sched_appliances']['num_cycles'].pop(i)
                        data['sched_appliances']['power_cons'].pop(i)
                        data['sched_appliances']['c1'].pop(i)
                        data['sched_appliances']['c2'].pop(i)
                        res = self.client.delete_documents(collection_name='home_configuration', document={'_id':4})
                        self.databaseClient.write_document(document = data, collection_name='home_configuration')
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
                payload = i['payload']
                # TODO: check payload format, period and object
                data = self.client.read_documents(collection_name='community', document={}) #!!!!!!!
                self.append_data(command='summary', data=data)
            elif i['command']=='registration':
                payload = i['payload']
                #temperatura minima e massima di boiler e ambiente,
                data = self.databaseClient.read_documents(collection_name='home_configuration', document={'_id':0})
                for i in range(payload['setpoints']['#']):
                    data[payload['setpoints']['appliance'][i]]=payload['setpoints']['new_value'][i]
                self.databaseClient.update_documents('home_configuration', {'_id':0}, data)
                # ora di partenza della macchina, hreasolg minima di carica della macchina]
                data = self.databaseClient.read_documents(collection_name='home_configuration', document={'_id':3})
                data['batteries'][''] = payload['EV']['time']
                data['batteries'][''] = payload['EV']['minimum']
                self.databaseClient.update_documents('home_configuration', {'_id':3}, data)
                # appliances:[modello, lavatrice-lavastovigle-vacuum cliner]
                data = self.databaseClient.read_documents(collection_name='home_configuration', document={'_id':4})
                data['N_sched_appliances'] += 1
                data['sched_appliances']['name'].append(payload['name'])
                data['sched_appliances']['running_len'].append(payload['running_len'])
                data['sched_appliances']['num_cycles'].append(payload['num_cycles'])
                data['sched_appliances']['power_cons'].append(payload['power_cons'])
                data['sched_appliances']['c1'].append(payload['c1'])
                data['sched_appliances']['c2'].append(payload['c2'])
                self.databaseClient.update_documents('home_configuration', {'_id':4}, data)

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