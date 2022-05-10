from datetime import datetime
from .MyMQTT import MyMQTT
import pandas as pd
import json
import time
from utilities.timer import perpetualTimer
from mongoDB.database_client import databaseClient

class Prosumer:
    def __init__(self, name):
        self.name = name
        self.rtp_i = 0 #eur/kw
        self.market_rtp = 0 #eur/kw
        self.energy_i = 0 #kW available for buying(+) or selling(-) for instant i
        self.offers = {}
        self.buyers = {}
        self.transaction_record = []
        self.mean_RTP = 0
        self.buyer = False
        self.waiting_buying_response = False
        self.waiting_bying_offer = False
        self.waiting_selling_confirm = False
        self.number_sendings = 0

        self.prosumerSubscriber = MyMQTT(name, 'broker.hivemq.com', 1883,  self)
        self.prosumerPublisher = MyMQTT(name + "_pub", 'broker.hivemq.com', 1883)
        
        self.time_instant_counter = 0

        self.databaseClient = databaseClient()
#%% MQTT: START/STOP/SUBSCRIBE
    def publisher_start(self):
        self.prosumerPublisher.start()

    def subscriber_start(self):
        self.prosumerSubscriber.start()

    def publisher_stop(self):
        self.prosumerPublisher.stop()

    def subscriber_stop(self):
        self.prosumerSubscriber.stop()
    ###################################

    def subscribe(self, topic):
        self.prosumerSubscriber.mySubscribe(topic)
#%% NOTIFY AND MESSAGE ANALYSIS
    def notify(self, topic, msg): #callback for when a message is received
        #Receive all the offers from the prosumers and save in the local record
        # - if the prosumer is new, insert it
        # - if already in, update it's offer
        try:
            msg = json.loads(msg)
            msg = json.loads(msg)
########################################################################################
# "offers" is the topic where all the sellers load their surpluses with the price
########################################################################################
            if topic == "offers" and msg["name"] != self.name:
                new_offer = {"energy": msg["energy"], "price": msg["price"]}
                if msg["energy"] == 0:
                    #if the user tells it's energy is finished, just delete it so avoid to store useless offers
                    del self.offers[msg["name"]]
                self.offers[msg["name"]] = new_offer
                
###################################################################################################
# the "name" instead is the topic of direct communication between prosumers for the energy exchange
###################################################################################################

# 1) I'm a BUYER and I sent a energy request, now waiting someone to answer me
            elif topic == self.name and self.waiting_buying_response == True:
                #process the energy request
                self.analyzeresponse(msg)
                
# 2) I'm a SELLER and I published something on the network, now waiting someone to offer me something
            elif topic == self.name and self.waiting_buying_offer == True:
                if self.waiting_selling_confirm == False:
                    response = self.analyzerequest(msg)
                    self.prosumerPublisher.myPublish(msg["name"], json.dumps(response))
                    if response["code"] == 1:
                        self.waiting_selling_confirm = True
                        
                elif self.waiting_selling_confirm == True:
                    self.energy_i += msg["energy"]
                    selling_record_tmp = {"name": msg["name"], "energy": -msg["energy"], "price": msg["price"]}
                    self.transaction_record.append(selling_record_tmp)

                    selling_record_tmp['timestamp'] = datetime.now()

                    data = self.databaseClient.read_documents(collection_name='data_collected', document={'_id':'history'})
                    data['prosumers'].append(selling_record_tmp)
                    self.databaseClient.update_documents(collection_name='data_collected', document={'_id':'history'}, data=data)
                    
        except:
            print("invalid message format")
        
    def set_instant_params(self, rtp, energy):
        if energy < 0:
            self.publishing_surplus(abs(energy), rtp)
        elif energy > 0:
            code = -1
            while code != 0: #iterate till there is no a response
                code = self.choosingseller(energy, rtp)
                if code == 1:
                    rtp += 0.1*rtp #increase price by 10%
                    if rtp >= self.market_rtp: 
                        #if the price increases that much and still no offers, then buy from market
                        transaction_record = {"name":"market", "energy":energy, "price":rtp}
                        self.transaction_record.append(transaction_record)
                        return 
                    
        self.rtp_i = rtp
        self.energy_i = energy

    def publishing_surplus(self, surplus_power, price):
        message = {"name": self.name, "energy": surplus_power, "price": price}
        self.prosumerPublisher.myPublish("offers", json.dumps(message))
        self.waiting_buying_offer = True

    def choosingseller(self, required_energy, required_price):
        """
        self.bestoffers is like:
        {
         'alejo': {'energy': 17, 'price': 0.01}, 
         'dave': {'energy': 19, 'price': 0.02}, 
         'ste': {'energy': 10, 'price': 0.005}
         }
        and the corresponding df is:
                    alejo   dave     ste
            energy  17.00  19.00  10.000
            price    0.01   0.02   0.005

        transposing it is easier for the filtering, after that we transpose it again and the we sort it
        """
        return_code = 0
        if self.offers != {}:
            best_sellers = pd.DataFrame(self.offers).transpose() 
            best_sellers = best_sellers[(best_sellers["energy"] >= required_energy) & (best_sellers["price"] <= required_price)]
            best_sellers = best_sellers.transpose()
            best_sellers = best_sellers.sort_values(by = ["price"], axis = 1)
            if list(best_sellers.columns) != []:
                self.number_sendings = len(list(best_sellers.columns))
                for names in list(best_sellers.columns):
                    message = {"name": self.name, "energy": required_energy, "price": required_price}
                    self.prosumerPublisher.myPublish(names, json.dumps(message))
                
                self.waiting_buying_response = True
            elif list(best_sellers.columns) == []:
                #set the code, in order to make the main know if the price has to be modified
                return_code = 1
        else:
            #TODO: energia da comprare dal market
            pass
        return return_code
    
    def analyzerequest(self, message):
        response = {"name": self.name, "code": 0, "energy":0, "price":0}
        if message["energy"] > abs(self.energy_i) or message["price"] < self.rtp_i :
            response["code"] = 0
        elif message["energy"] < abs(self.energy_i) and message["price"] >= self.rtp_i:
            response["code"] = 1
            response["energy"] = message["energy"]
            response["price"] = message['price']
            
        return response

    def analyzeresponse(self, msg):
        #after sending a buying offer, we wait for the response. Once it arrives, we need to process it
        code = msg["code"]
        if code == 0 and self.waiting_buying_response == True:
            #prosumer is a buyer and the seller rejected the offer
            self.number_sendings -= 1
            if self.number_sendings == 0:
                #buy from the market
                transaction_record = {"name" : "market", "energy" : self.energy_i, "price" : self.market_rtp}
                self.transaction_record.append(transaction_record)
                self.waiting_buying_response = False
                
        elif code == 1 and self.waiting_buying_response == True:
            #seller accepted offer
            self.waiting_buying_response = False
            #add transaction to the record
            transaction_record = {"name" : msg["name"], "energy" : self.energy_i, "price" : self.market_rtp}
            self.transaction_record.append(transaction_record)
            #send back response to the seller to finalize the transaction
            finalization_dictionary = msg
            finalization_dictionary["name"] = self.name
            self.prosumerPublisher.myPublish(msg["name"], json.dumps(finalization_dictionary))            
        else:
            print("error in response analysis")

    def thread_callback(self):
        data = self.databaseClient.read_documents(collection_name='data_collected', document={'_id':'history'}) #TODO: insert correct query, need Pg e RTP
        Pg_i = data['Pg_market']
        data = self.databaseClient.read_documents(collection_name='home_configuration', document={'_id':6})
        rtp_i = data["RTP"]['values'][self.time_instant_counter]/2
        self.set_instant_params(rtp_i, Pg_i[self.time_instant_counter])
        self.time_instant_counter += 1