import json
import logging
import numpy as np
from datetime import datetime

from utilities.mqttclient import MQTTPublisher, MQTTSubscriber
from utilities.timer import perpetualTimer

class EV_publisher():
    def __init__(self, cfg):
        """EV status simulator

        Args:
            cfg (dict): configuration file
        """
        try:
            self.port = cfg['mqtt_port']
            self.broker = cfg['mqtt_broker']
            self.clientID = str(np.random.randint(1000000000))
            self.publisher = MQTTPublisher(self.clientID, self.broker, self.port)
            self.publisher.start() 
            self.EV_topic = cfg['carStation_topic']
            self.status = None
        except:
            logging.info('EV_publisher does not created: possible internet connection problem')

    def EV_notify(self):
        """EV arriving or departure

        Args:
            status (int): it can be 0 or 1: 1 means that the EV is at home, 0 means that the user is using the EV
        """
        self.status = np.random.randint(10)
        if self.status > 4: self.status = 1
        else: self.status = 0
        try:
            self.publisher.myPublish(self.EV_topic, self.status)
        except:
            logging.error('EV publisher error')

class HW_publisher():
    def __init__(self, cfg):
        """HW amount simulator

        Args:
            cfg (dict): configuration file
        """
        try:
            self.port = cfg['mqtt_port']
            self.broker = cfg['mqtt_broker']
            self.clientID = str(np.random.randint(1000000000))
            self.publisher = MQTTPublisher(self.clientID, self.broker, self.port)
            self.publisher.start()
            self.EV_topic = cfg['waterWithdrawn_topic']
        except:
            logging.info('HW_publisher does not created: possible internet connection problem')

    def HW_notify(self):
        """HW used amount

        Args:
            amount (int): amount of HW used 
        """
        try:
            amount = np.random.uniform(low=0.01, high=0.03)
            self.publisher.myPublish(self.EV_topic, amount)
        except:
            logging.error('HW publisher error')

class smartMeter():
    def __init__(self, cfg):
        """Smart meter simulator

        Args:
            cfg (dict): configuration file
        """
        try:
            self.port = cfg['mqtt_port']
            self.broker = cfg['mqtt_broker']
            self.clientID = str(np.random.randint(1000000000))
            self.publisher = MQTTPublisher(self.clientID, self.broker, self.port)
            self.publisher.start()
            self.SM_topic = cfg['smartMeter_topic']
            self.time_granularity = cfg['time_granularity']
        except:
            logging.info('Smart meter does not created: possible internet connection problem')

    def RTP_notify(self):
        """
        Peak: 10-13-17-19
        Medium: rest of the day
        Low: night
        """
        try:
            RTP_list = [] 
            for i in range(int(60/self.time_granularity*24)):
                if abs(i*self.time_granularity/60 - 10) < 2:
                    l = 0.17
                    h = 0.25
                elif abs(i*self.time_granularity/60 - 13) < 2:
                    l = 0.17
                    h = 0.25
                elif abs(i*self.time_granularity/60 - 17) < 2:
                    l = 0.17
                    h = 0.25
                elif abs(i*self.time_granularity/60 - 19) < 2:
                    l = 0.17
                    h = 0.25
                elif i*self.time_granularity/60 < 7 and i*self.time_granularity/60 > 22:
                    l = 0.01
                    h = 0.10
                else:
                    l = 0.10
                    h = 0.17
                RTP_list.append(np.random.uniform(low=l, high=h))
            
            self.publisher.myPublish(self.SM_topic, len(RTP_list))
        except:
            logging.error('SM publisher error')
class generalAppliances_subscriber(): 
    def __init__(self, cfg):
        """General appliance simulator

        Args:
            cfg (dict): configuration file
        """
        try:
            self.port = cfg['mqtt_port']
            self.broker = cfg['mqtt_broker']
            self.clientID = str(np.random.randint(1000000000))
            self.subscriber = MQTTSubscriber(self.clientID, self.broker, self.port)
            self.subscriber.start()
            #self.subscriber.callbackRegistration(self.subscriber_callback)
            #self.generalAppliances_topic = str(self.clientID)+'_topic'
            #self.subscriber.mySubscribe(self.generalAppliances_topic)
        except:
            logging.info(f'General appliance does not created: possible internet connection problem')
    
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

    SM_flag = True

    while True:
        now = datetime.now()
        if now.strftime("%H:%M") == "08:00" and SM_flag:
            # 8 a.m.   24*60*60 every day
            SM = perpetualTimer(t=24*60*60, hFunction=SM.RTP_notify)
            SM.start()
            SM_flag = False

        #EV_timer = perpetualTimer(t=, hFunction=EV.EV_notify) 
        #EV_timer.start()

        #HW_timer = perpetualTimer(t=, hFunction=HW.HW_notify)
        #HW_timer.start()          
