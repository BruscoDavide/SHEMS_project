from mqttclient import MQTTPublisher
import time
import logging

if __name__ == '__main__':
    
    log_name = './logs/mqttpublisher.log'
    logging.basicConfig(
        filename=log_name,
        format='%(asctime)s %(levelname)s: %(message)s',
        level=logging.INFO, datefmt="%H:%M:%S",
        filemode='w'
    )

    mydevice = MQTTPublisher('0000', 'broker.hivemq.com', 1883)
    mydevice.start()
    while True:
        time.sleep(5)
        mydevice.myPublish('SHEMS_test_topic','SHEMS_test_message')
        print('data published')