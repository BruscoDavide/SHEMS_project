import json
import logging
import requests
import numpy as np

from Utilities.timer import perpetualTimer
from Utilities.mqttclient import MQTTSubscriber
from MongoDB.database_client import databaseClient
from Optimization_model.Simulator.instance import Instance
from Optimization_model.LP_solver.SHEMSfile import SHEMS

class SHEMS_main():
    def __init__(self, cfg):
        self.databaseClient = databaseClient()
        new_instance = Instance() # TODO: da aggiungere a instance costruttore data = new_databaseClient.read_myDocuments() 
        self.shems = SHEMS(new_instance)
        
        self.waterWithdrawn_topic = cfg['waterWithdrawn_topic']
        self.carStation_topic = cfg['carStation_topic']
        self.deviceID = np.random.randint(1000000000)
        self.broker = cfg['mqtt_broker']
        self.port = cfg['mqtt_port']
        sensors_subscriber = MQTTSubscriber(self.deviceID, self.broker, self.port)
        sensors_subscriber.start()
        sensors_subscriber.callbackRegistration(self.sensors_subscriver_callback)
        sensors_subscriber.mySubscribe(self.waterWithdrawn_topic)
        sensors_subscriber.mySubscribe(self.carStation_topic)

        self.city = cfg['home_city']
        self.BASE_URL1 = cfg['BASE_URL1']
        self.BASE_URL2 = cfg['BASE_URL2']
        self.API_KEY = cfg['API_KEY']

    def SHEMS_thread_basic_scheduling_callback(self):
        """First day scheduling 
        """    
        self.weatherAPI()

        cod = self.shems.solve()
        if cod == 2:
            logging.info('First day schedluinig success')
        elif cod == -1:
            logging.info('First day scheduling failed')
        # TODO: inserire feedback utente        

    def SHEMS_thread_callback(self):
        """USer operation on: setting parameters/appliances and change scheduling
        """
        fp = open('SHEMS_thread_file.json', 'r')
        file = json.load(fp)
        fp.close()
        timestamp = file['timestamp']
        # TODO: controllo timestamp sia corretto
        payload = file['payload']
        if payload['command'] == 0:
            self.databaseClient.update_myDocuments('home_configuration', {'home_configuration_id':0}, payload)
            self.shems.set_working_mode(payload)
            cod = self.shems.solve()
            if cod == 2:
                logging.info('First day schedluinig success')
            elif cod == -1:
                logging.info('First day scheduling failed')
            # TODO: inserire feedback utente
        elif payload['command'] == 1:
            self.shems.set_working_mode(payload)
            cod = self.shems.solve()
            if cod == 2:
                logging.info('First day schedluinig success')
            elif cod == -1:
                logging.info('First day scheduling failed')
            # TODO: inserire feedback utente
    
        elif payload['command'] == 2:
            self.databaseClient.update_myDocuments('home_configuration', {'home_configuration_id':0}, payload) #payload = {:}
            #self.databaseClient.delete_myDocuments('home_configuration', {'home_configuration_id':0}, payload)
            self.databaseClient.write_document('home_configuration', {'home_configuration_id':0}, payload)
            # TODO: capire se nuovo o elimino appliances
            self.shems.set_working_mode(payload)
            scod = self.shems.solve()
            if cod == 2:
                logging.info('First day schedluinig success')
            elif cod == -1:
                logging.info('First day scheduling failed')
            # TODO: inserire feedback utente
        else:
            raise logging.info('Command code error')  

    def sensors_subscriver_callback(self, msg):
        if msg.topic == self.waterWithdrawn_topic:
            new_data = msg.payload['waterFlux']
            # TODO: inserire controllo sul valore
            # TODO: scrivo sul database o cosa??
        elif msg.topic == self.arStation_topic:
            if msg.payload['carStation'] == 0 or msg.payload['carStation'] == 1:
                new_data = msg.payload['carStation']
                # TODO: scrivo sul database o cosa??
            else: 
                raise logging.info('Error in the carStation publisher')

    def weatherAPI(self):
        #country_code="380"
        #limit = 1
        #url = f"http://api.openweathermap.org/geo/1.0/direct?q={self.city},{country_code}&limit={limit}&appid={self.api_key}"
        #response = requests.get(url)
        #if response.status_code == 200:
            #recupero delle coordinate

        lat = 45.0677551 # Torino
        lon = 7.6824892
        url = self.BASE_URL2 + "&appid=" + self.API_KEY
        response = requests.get(url)
        temp = []
        if response.status_code == 200:  # checking the status code of the request
            data = response.json()['list'] # una lista
            
            for i in range(8): #24/3, data recovering: temperature every 3 hours
                temp.append(round(data[i]['main']['temp']-273, 1))
            new_temp = np.zeros(24)
            
            for i in range(7): # 0-6, data every 1 hour
                new_temp[i*3]=temp[i]
                new_temp[i*3+1] = round(temp[i]-(temp[i]-temp[i+1])/3, 1)
                new_temp[i*3+2] = round(temp[i]-2*(temp[i]-temp[i+1])/3, 1)
            new_temp[21] = temp[7]
            if new_temp[20]<new_temp[21]: # crescente
                new_temp[22] = new_temp[21] + round((temp[7]-temp[6])/3, 1)
                new_temp[23] = new_temp[21] + 2*round((temp[7]-temp[6])/3, 1)
            else: # decrescente
                new_temp[22] = new_temp[21] - round((temp[7]-temp[6])/3, 1)
                new_temp[23] = new_temp[21] - 2*round((temp[7]-temp[6])/3, 1)

            temp = new_temp
            new_temp = np.zeros(96)
            for i in range(23): # 0-6, data every 15 minutes
                new_temp[i*4]=temp[i]
                new_temp[i*4+1] = round(temp[i]-(temp[i]-temp[i+1])/4, 1)
                new_temp[i*4+2] = round(temp[i]-2*(temp[i]-temp[i+1])/4, 1)
                new_temp[i*4+3] = round(temp[i]-3*(temp[i]-temp[i+1])/4, 1)
            new_temp[92] = temp[23]
            if new_temp[91]<new_temp[92]: # crescente
                new_temp[93] = new_temp[92] + round((temp[23]-temp[22])/4, 1)
                new_temp[94] = new_temp[92] + 2*round((temp[23]-temp[22])/4, 1)
                new_temp[95] = new_temp[92] + 3*round((temp[23]-temp[22])/4, 1)
            else: # decrescente
                new_temp[93] = new_temp[92] - round((temp[23]-temp[22])/4, 1)
                new_temp[94] = new_temp[92] - 2*round((temp[23]-temp[22])/4, 1)
                new_temp[95] = new_temp[92] - 2*round((temp[23]-temp[22])/4, 1)

            # TODO: update del database con le temperature e update dei dati vari climatici

        else:
            logging.info(f'Weather forecast API response status code: {response.status_code}')
    




def reading_json_callback2():
    fp = open('test2.json', 'r')
    file = json.load(fp)
    fp.close()
    # i perform something... 
    print(file)
    #open file, write on it


def reading_json_callback3():
    fp = open('test3.json', 'r')
    file = json.load(fp)
    fp.close()
    print(file)   

if __name__ == '__main__':
    
    log_name = './logs/main.log'
    logging.basicConfig(
        filename=log_name,
        format='%(asctime)s %(levelname)s: %(message)s',
        level=logging.INFO, datefmt="%H:%M:%S",
        filemode='w'
    )

    fp = open('starting_configuration.json', 'r')
    cfg = json.load(fp)
    fp.close()

    main = SHEMS_main(cfg)

    t = 60  #24*60*60
    SHEMS_thread_basic_scheduling = perpetualTimer(t, main.SHEMS_thread_basic_scheduling_callback(main.shems))
    SHEMS_thread_basic_scheduling.start()

    t = 1
    SHEMS_thread = perpetualTimer(t, main.SHEMS_thread_callback(main.shems))
    SHEMS_thread.start()






    # sia local gui che web server scrivono li: ho 3 task da gestire suoi

    GUI = perpetualTimer(t=0.5, reading_json_callback2)
    GUI.start()

    test = perpetualTimer(t, main.reading_json_callback3)
    test.start()

    while True:
        pass