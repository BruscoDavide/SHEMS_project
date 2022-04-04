import paho.mqtt.client as PahoMQTT
import logging
import json

class MQTTPublisher():
    """
    General MQTT publisher class exploiting PahoMQTT.Client class
    """
    def __init__(self, clientID, broker, port):
        self.broker = broker 
        self.port = port 
        self._clientID = clientID 
        
        # create an instance of paho.mqtt.client 
        self._paho_mqtt = PahoMQTT.Client(self._clientID, False) 
        # register the callbacks
        self._paho_mqtt.on_connect = self.myOnConnect

    def myOnConnect (self, paho_mqtt, userdata, flags, rc): 
        logging.info(f'Connected to {self.broker} with result code {rc}') 

    def start(self):
        self._paho_mqtt.connect(self.broker, self.port) 
        self._paho_mqtt.loop_start() 

    def stop (self): 
        self._paho_mqtt.loop_stop() 
        self._paho_mqtt.disconnect()

    def myPublish (self, topic, msg):
        """Publishing a message under certain topic

        Args:
            topic (string): topic of the message
            msg (python object): message delivered
        """
        logging.info(f'Publishing {msg} with topic {topic}') 
        self._paho_mqtt.publish(topic, json.dumps(msg),0) 

class MQTTSubscriber(): 
    """
    General MQTT subscriber class exploiting PahoMQTT.Client class
    """
    def __init__(self, clientID, broker, port): 
        self.broker = broker 
        self.port = port 
        self._clientID = clientID 
        self._topic = ''
        
        # create an instance of paho.mqtt.client 
        self._paho_mqtt = PahoMQTT.Client(self._clientID, False) 
        # register the callbacks
        self._paho_mqtt.on_connect = self.myOnConnect
        self._paho_mqtt.on_message = self.myOnMessageReceived
        self.__callback = self.__primaryCallback  

    def myOnConnect (self, paho_mqtt, userdata, flags, rc): 
        logging.info(f'Connected to {self.broker} with result code {rc}')

    def myOnMessageReceived (self, paho_mqtt , userdata, msg):
        logging.info(f'New messager receiver with topic {msg.topic}, with payload {msg.payload}, with QoS {msg.qos}')
        self.__callback(msg)

    def __primaryCallback(self):
        pass

    def callbackRegistration(self, callback):
        """Setting the callback to execute when a message under a specific topic is received

        Args:
            callback (function): python function
        """
        self.__callback = callback

    def start(self): #manage connection to broker 
        self._paho_mqtt.connect(self.broker , self.port) 
        self._paho_mqtt.loop_start() 

    def mySubscribe (self, topic):
        """Subscribing under a certain topic in order to receive messages

        Args:
            topic (string): topic of the communication
        """
        self._topic = topic
        logging.info(f'CLient {self._clientID} subscribing to {self._topic} topic')
        self._paho_mqtt.subscribe(topic, 0) 

    def stop (self): 
        self._paho_mqtt.unsubscribe(self._topic)  
        self._paho_mqtt.loop_stop() 
        self._paho_mqtt.disconnect()

     

  

