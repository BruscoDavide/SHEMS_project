import paho.mqtt.client as PahoMQTT
import json

class MyMQTT: 
    def __init__(self, clientID, broker, port, notifier=None): #the first 3 parameters are in common fot both publisher and subs, the fourth is for subscriber only
        self.broker = broker 
        self.port = port 
        self.notifier = notifier #THIS IS AN OBJECT: if nothing is passed, then it will be an empty object:
                                #this object will contain the action function for the message
        self.clientID = clientID 
        self._topic = "" 
        self._isSubscriber = False #let to false and set to True if we want a subscriber

        # create an instance of paho.mqtt.client 
        self._paho_mqtt = PahoMQTT.Client(clientID, False) 
        # register the callbacks
        self._paho_mqtt.on_connect = self.myOnConnect
        self._paho_mqtt.on_message = self.myOnMessageReceived 

    def myOnConnect (self, paho_mqtt, userdata, flags, rc): 
        print ("Connected to %s with result code: %d" % (self.broker, rc)) 

    def myOnMessageReceived (self, paho_mqtt , userdata, msg): # A new message is received 
        print("new message received")
        print(self.clientID)
        print(msg.payload)
        asd = json.loads(msg.payload)
        asd = str(asd)
        asd = json.loads(asd)
        print(asd)
        print(asd["energy"])
        print(asd["price"])
        self.notifier.notify(msg.topic, msg.payload)
        print("message passed to notify")

    def myPublish (self, topic, msg): #to set the script as a publisher
        print ("publishing '%s' with topic '%s'" % (msg, topic)) 
        # publish a message with a certain topic 
        self._paho_mqtt.publish(topic, json.dumps(msg),0) 

    def mySubscribe (self, topic): # if needed, you can do some computation or error-check before subscribing 
        print ("subscribing to %s" % (topic)) 
        # subscribe for a topic 
        self._paho_mqtt.subscribe(topic, 0) 
        # just to remember that it works also as a subscriber 
        self._isSubscriber = True #initially it was set to zero: now since the user called this function, it want a subscriber, and so it is set to True
        self._topic = topic 

    def start(self): #manage connection to broker 
        self._paho_mqtt.connect(self.broker , self.port) 
        self._paho_mqtt.loop_start() 

    def stop (self): 
        if (self._isSubscriber): # remember to unsuscribe if it is working also as subscriber 
            self._paho_mqtt.unsubscribe(self._topic)  
        self._paho_mqtt.loop_stop() 
        self._paho_mqtt.disconnect()
