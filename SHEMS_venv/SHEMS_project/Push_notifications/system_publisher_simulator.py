import time
import json
import logging

from mqttclient import MQTTPublisher

if __name__ == '__main__':
    
    log_name = './logs/system_publisher_simulator.log'
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

    topic = d['topic']
    broker = d['broker']
    port = d['port']
    deviceID = 'system_publisher_simulator'

    mydevice = MQTTPublisher(deviceID, broker, port)
    mydevice.start()
    
    i = 1
    while True:
        time.sleep(5)
        msg = 'test'+str(i)
        mydevice.myPublish(topic, msg)
        #logging.info(f'sending ... {topic} {msg}')
        i+=1