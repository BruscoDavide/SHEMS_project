import numpy as np
from MyMQTT import MyMQTT
import pandas as pd
import json
import time

class Prosumer:
    def __init__(self, name):
        self.name = name
        self.energy = np.array([]) #kw available for buying(+) or selling(-)
        self.price = np.array([])  #eur/kw
        self.rtp = np.array([])
        self.offers = {}
        self.buyers = {}
        self.mean_RTP = 0
        self.buyer = False
        self.waiting_buying_response = False
        self.waiting_selling_response = False
        self.number_sendings = 0

        self.prosumerSubscriber = MyMQTT(name, 'mqtt.eclipseprojects.io', 1883,  self)
        self.prosumerPublisher = MyMQTT(name + "_pub", 'mqtt.eclipseprojects.io', 1883)

    #TODO: vedere se si possono far partire tutti insieme
    ##################################
    def publisher_start(self):
        self.prosumerPublisher.start()

    def subscriber_start(self):
        self.prosumerSubscriber.start()
    ###################################

    #TODO: vedere se si possono stoppare tutti insieme
    ###################################
    def publisher_stop(self):
        self.prosumerPublisher.stop()

    def subscriber_stop(self):
        self.prosumerSubscriber.stop()
    ###################################

    def subscribe(self, topic):
        self.prosumerSubscriber.mySubscribe(topic)

    def notify(self, topic, msg): #callback for when a message is received
        #Receive all the offers from the prosumers and save in the local record
        # - if the prosumer is new, insert it
        # - if already in, update it's offer
        print("inside notify")
        try:
            print("inside notify")
            #if topic == "offers" and msg["name"] != self.name:
            if topic == "offers":
                msg = json.loads(msg)
                msg = json.loads(msg)
                print(msg)
                print("inside if")
                print(msg["energy"])
                new_offer = {"energy": msg["energy"], "price": msg["price"]}
                print(new_offer)
                if msg["energy"] == 0:
                    #if the user tells it's energy is finished, just delete it so avoid to store useless offers
                    del self.offers[msg["name"]]
                self.offers[msg["name"]] = new_offer

            elif topic == self.name:
                #process the energy request
                self.analyzeresponse(msg)
                pass
        except:
            print("invalid message format")

    def get_energy(self):
    ########### here needed the getter from the database ####################
    #########################################################################
        pass
    
    def get_rtp(self):
        ######################### get RTP from database ######################
        ######################################################################
        self.rtp = np.array([0.14,0.12,0.14,0.1,0.085,0.09,0.11,0.12,0.105,0.105,0.1, 0.095,0.09,0.065,0.09,0.06,0.06,0.06,0.12,0.115,0.11,0.025,0.045,0.05,0.06,0.07,0.06,0.065,0.065,0.09,0.13,0.06, 0.065,0.065,0.14,0.145,0.27,0.13,0.02,0.09,0.19,0.19,0.24,0.15,0.09,0.09,0.13,0.13,0.11,0.135,0.11,0.125,0.105,0.09,0.08,0.09,0.08,0.115,0.12,0.115,0.105,0.145,0.095,0.09,0.07,0.075,0.07,0.09,0.09,0.08,0.08,0.09,0.09,0.08,0.07,0.08,0.07,0.075,0.07,0.075,0.08,0.09,0.09,0.08,0.09,0.105,0.09,0.09,0.09,0.09,0.1,0.1,0.1,0.15,0.09,0.09])
        self.mean_RTP =  np.mean(self.rtp)

    def publishing_surplus(self, surplus_power, price):
        message = {"name": self.name, "energy": surplus_power, "price": price}
        self.prosumerPublisher.myPublish("offers", json.dumps(message))
        self.waiting_buying_response = True

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

        best_sellers = pd.DataFrame(self.offers).transpose() 
        best_sellers = best_sellers[(best_sellers["energy"] >= required_energy) & (best_sellers["price"] <= required_price)]
        best_sellers = best_sellers.transpose()
        best_sellers = best_sellers.sort_values(by = ["price"], axis = 1)
        if list(best_sellers.columns) != []:
            self.number_sendings = len(list(best_sellers.columns))
            for names in list(best_sellers.columns):
                message = {"name": self.name, "energy": required_energy, "price": required_price}
                self.prosumerPublisher.myPublish(names, json.dumps(message))
        elif list(best_sellers.columns) == []:
            #set the code, in order to make the main know if the price has to be modified
            return_code = 1
        self.waiting_buying_response = True

        return return_code

    def analyzeresponse(self, msg):
        #after sending a buying offer, we wait for the response. Once it arrives, we need to process it
        code = msg["code"]
        if code == 0 and self.waiting_buying_response == True:
            #prosumer is a buyer and the seller rejected the offer
            self.number_sendings -= 1
            if self.number_sendings == 0:
                #analyze the action to be inserted here to modify the price
                pass
        elif code == 1 and self.waiting_buying_response == True:
            #seller accepted offer
            self.waiting_buying_response = False
            
            #TODO: record the transaction => energy and price, maybe a call to the server

        else:
            print("error in response analysis")
    
    def deposit(self, amount):
        self.energy -= amount
        print('Your energy left = %d' %self.energy)
        
    def withdraw(self, amount):
        #amount = int(input('Enter the amount to withdraw: '))
        if (amount > self.energy):
            print('Insufficient balance')
        else:
            self.energy += amount
        print('Your remaining energy = %d' %self.energy)

    def get_list(self):
        print("offers: ", self.offers)

if __name__ == "__main__":
    prosumer = Prosumer("ste")
    prosumer.publisher_start()
    prosumer.subscriber_start()
    prosumer.subscribe("offers")

    try:
        while True:
            prosumer.publishing_surplus(4.3, 0.05)
            prosumer.get_list()
    except KeyboardInterrupt:
        print("ending")