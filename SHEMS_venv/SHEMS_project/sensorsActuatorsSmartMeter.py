import numpy as np
import json
import logging

from utilities.mqttclient import MQTTPublisher, MQTTSubscriber
from utilities.timer import perpetualTimer

class EV_publisher():
    def __init__(self, cfg):
        """EV status simulator

        Args:
            cfg (dict): configuration file
        """
        self.port = cfg['port']
        self.broker = cfg['broker']
        self.clientID = np.random.randint(1000000000)
        self.publisher = MQTTPublisher(self.clientID, self.broker, self.port)
        self.publisher.start()
        self.EV_topic = cfg['carStation_topic']

    def EV_notify(self, status=None):
        """EV arriving or departure

        Args:
            status (int): it can be 0 or 1: 1 means that the EV is at home, 0 means that the user is using the EV
        """
        # TODO: cosa fare con status.. come simulo sta cosa?
        self.publisher.myPublish(self.EV_topic, status)

class HW_publisher():
    def __init__(self, cfg):
        """HW amount simulator

        Args:
            cfg (dict): configuration file
        """
        self.port = cfg['port']
        self.broker = cfg['broker']
        self.clientID = np.random.randint(1000000000)
        self.publisher = MQTTPublisher(self.clientID, self.broker, self.port)
        self.publisher.start()
        self.EV_topic = cfg['waterWithdrawn_topic']

    def HW_notify(self):
        """HW used amount

        Args:
            amount (int): amount of HW used 
        """
        amount = np.random.randint() # TODO: ordine di grandezza dell'acqua consumata
        self.publisher.myPublish(self.EV_topic, amount)

class smartMeter():
    def __init__(self, cfg):
        self.port = cfg['port']
        self.broker = cfg['broker']
        self.clientID = np.random.randint(1000000000)
        self.publisher = MQTTPublisher(self.clientID, self.broker, self.port)
        self.publisher.start()
        self.SM_topic = cfg['SF_topic']

    def RTP_notify(self):
        RTP_list = [] # TODO: fare qualcosa di più interessante
        self.publisher.myPublish(self.SM_topic, RTP_list)

class generalAppliances_subscriber():
    """General appliance simulator

        Args:
            cfg (dict): configuration file
        """
    def __init__(self, cfg):
        self.port = cfg['port']
        self.broker = cfg['broker']
        self.clientID = np.random.randint(1000000000)
        self.subscriber = MQTTSubscriber(self.clientID, self.broker, self.port)
        self.subscriber.start()
        self.subscriber.callbackRegistration(self.subscriber_callback)
        self.generalAppliances_topic = str(self.clientID)+'_topic'
        self.subscriber.mySubscribe(self.generalAppliances_topic)
    
    def subscriber_callback(self, msg):
        pass

if __name__ == '__main__':

    log_name = './logs/sensorsActuatorsSmartMeter.log'
    logging.basicConfig(
        filename=log_name,
        format='%(asctime)s %(levelname)s: %(message)s',
        level=logging.INFO, datefmt="%H:%M:%S",
        filemode='w'
    )

    fp = open('./files/starting_configuration.json', 'r')
    cfg = json.load(fp)
    fp.close()

    EV = EV_publisher(cfg)
    HW = HW_publisher(cfg)
    SM = smartMeter(cfg)
    n = 5
    appliances = []
    for i in range(n):
        appliances.append(generalAppliances_subscriber(cfg))

    # 5 p.m.
    EV_timer = perpetualTimer(t=180, hFunction=EV.EV_notify) 
    EV_timer.start()

    # 7 p.m.
    HW_timer = perpetualTimer(t=90, hFunction=HW.HW_notify)
    HW_timer.start()

    # 8 a.m.
    SM = perpetualTimer(t=60, hFunction=SM.RTP_notify)
    SM.start()

    while True:
        pass