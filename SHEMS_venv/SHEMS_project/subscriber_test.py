from cmd import IDENTCHARS
from xmlrpc.client import ProtocolError
from matplotlib.pyplot import broken_barh
from more_itertools import callback_iter
from utilities.mqttclient import MQTTSubscriber

def callback(msg):
    print(msg.paylaod)
    print('\n')

ID = 'test'
broker = 'broker.hivemq.com'
port = 1883

client = MQTTSubscriber(ID, broker, port)
client.callbackRegistration(callback)
client.mySubscribe('carStation_topic')
client.mySubscribe('smartMeter_topic')
client.mySubscribe('waterWithdrawn_topic')
client.start()

while True:
    pass