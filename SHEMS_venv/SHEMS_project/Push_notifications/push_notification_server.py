import logging
import json

from mqttclient import MQTTSubscriber, MQTTPublisher

#TODO: PULIZIA DEL FILE LOG

def callback(msg):
    #TODO: AGGIUNTA CONTROLLO TESTO O CONTROLLO SICUREZZA
    #logging.info(msg)
    myserver_publisher.myPublish('client_test', 'push_notification')
    #logging.info(f'sending ... client_test {msg.payload}')

if __name__ == '__main__':

    log_name = './logs/push_notification_server.log'
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
    client_topic = d['client_topic']
    broker = d['broker']
    port = d['port']
    deviceID_subscriber = 'myserver_subscriber'
    deviceID_publisher = 'myserver_publisher'
    
    ######################################

    myserver_publisher = MQTTPublisher(deviceID_publisher, broker, port)
    myserver_publisher.start()
    
    myserver_subscriber = MQTTSubscriber(deviceID_subscriber, broker, port)
    myserver_subscriber.start()
    myserver_subscriber.callbackRegistration(callback)
    myserver_subscriber.mySubscribe(topic)

    while True:
        pass