import logging
import json

from websocket_server import WebsocketServer
from utilities.mqttclient import MQTTPublisher, MQTTSubscriber
class SHEMSwebsocket():
    def __init__(self, cfg):
        self.server = WebsocketServer(port = cfg['websocket_port'])
        self.server.set_fn_new_client(self.__sendNotification)
        #self.server.set_fn_client_left(self.__clientLeft)
        #self.server.set_fn_message_received(self.__messageReceived())
        self.server.run_forever()

    def __sendNotification(self):
        fp = open('./files/push_notification.json')
        payload = json.load(fp)
        fp.close()
        
        try:
            self.server.send_message_to_all(payload)
            print('yes')
        except:
            print('nooo')

        payload = []
        fp = open('./files/push_notification.json', 'w')
        json.dump(payload, fp)
        fp.close()

    def __clientLeft(self):
        logging.warning('Websocket client disconnected')

    def __messageReceived(self, message):
        if len(message) > 200:
            message = message[:200]+'..'
        logging.info('Message received by the client')
