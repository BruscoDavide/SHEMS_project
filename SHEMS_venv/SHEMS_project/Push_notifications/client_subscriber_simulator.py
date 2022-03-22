import logging
import json

from mqttclient import MQTTSubscriber

def callback(msg):
    #logging.info(msg.topic)
    #logging.info(msg.payload)
    logging.info('\n')

if __name__ == '__main__':

    log_name = './logs/client_subscriber_simulator.log'
    logging.basicConfig(
        filename=log_name,
        format='%(asctime)s %(levelname)s: %(message)s',
        level=logging.INFO, datefmt="%H:%M:%S",
        filemode='w'
    )

    with open('settings.json') as json_data:
        d = json.load(json_data)
        json_data.close()
        logging.info(f'settings.json: {d}')

    topic = d['client_topic']
    broker = d['broker']
    port = d['port']
    deviceID = 'client_subscriber_simulator'

    mydevice = MQTTSubscriber(deviceID, broker, port)
    mydevice.start()
    mydevice.callbackRegistration(callback)
    mydevice.mySubscribe(topic)
    
    while True:
        pass
