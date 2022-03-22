from mqttclient import MQTTSubscriber
import logging

def callback(msg):
    print(msg.topic)
    print(msg.payload)

if __name__ == '__main__':

    log_name = './logs/mqttsubscriber.log'
    logging.basicConfig(
        filename=log_name,
        format='%(asctime)s %(levelname)s: %(message)s',
        level=logging.INFO, datefmt="%H:%M:%S",
        filemode='w'
    )

    mydevice = MQTTSubscriber('0001','broker.hivemq.com',1883)
    mydevice.start()
    mydevice.callbackRegistration(callback)
    mydevice.mySubscribe('SHEMS_test_topic')
    
    while True:
        pass