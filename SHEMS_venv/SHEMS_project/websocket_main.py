
import json
from pushNotification_server.websocket import SHEMSwebsocket

fp = open('./files/starting_configuration.json')
cfg = json.load(fp)
fp.close()

try:
    pushnotification_server = SHEMSwebsocket(cfg)
    print('Websocket communication online')
except:
    print('Websocket communication offline')


"""
from twisted.internet import reactor
from autobahn.websocket import WebSocketClientFactory, WebSocketClientProtocol, connectWS


class EchoClientProtocol(WebSocketClientProtocol):

   def sendHello(self):
      self.sendMessage("Hello, world!")

   def onOpen(self):
      self.sendHello()

   def onMessage(self, msg, binary):
      print ("Got echo: " + msg)
      reactor.callLater(1, self.sendHello)


if __name__ == '__main__':

   factory = WebSocketClientFactory("ws://127.0.0.1:52268")
   factory.protocol = EchoClientProtocol
   connectWS(factory)
   reactor.run()
"""