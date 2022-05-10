import logging

from websocket_server import WebsocketServer

class SHEMSwebsocket():
    def __init__(self, cfg):
        self.client =  {"id": "SHEMS"}
        self.server = WebsocketServer(port = cfg['websocket_port'])
        self.server.set_fn_new_client(self.__sendNotification)
        self.server.set_fn_client_left(self.__clientLeft)
        self.server.set_fn_message_received(self.__messageReceived)
        self.server.run_forever()
        self.payload = {}

    def __sendNotification(self):
        self.server.send_message_to_all(self.payload)

    def __clientLeft(self):
        logging.warning('Websocket client disconnected')

    def __messageReceived(self, message):
        if len(message) > 200:
            message = message[:200]+'..'
        logging.info('Message received by the client')

    def upgradeNotification(self, payload):
        try:
            self.paylaod = payload
            self.__sendNotification()
            logging.info('Notification sent')
        except:
            logging.error('Sending notification failed')

