import paho.mqtt.client as PahoMQTT
import time
import json
from MyMQTT import MyMQTT
        
class Prosumer:
    def __init__(self, energy, price, name):
        self.name = name
        self.energy = energy #kw available for buying(+) or selling(-)
        self.price = price  #eur/kw
        self.rtp = 18
        self.buyer = False
        self.waiting_response = False
        print('Prosumer %s registered' %name)
        
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
                
    def choosingseller(self, listoffers):
        bestprice = self.rtp
        secondprice = self.rtp
        self.bestseller = {}
        self.secondbest = {}
        for names in listoffers:
            if listoffers[names]["energy"] >= self.energy:
                if  listoffers[names]["price"] <= secondprice:
                    if  listoffers[names]["price"] <= bestprice:
                        bestprice = listoffers[names]["price"]
                        self.bestseller = {"name": names, "energy":listoffers[names]["energy"], "price": listoffers[names]["price"]}
                    else:
                        secondprice = listoffers[names]["price"]
                        self.secondbest = {"name": names, "energy":listoffers[names]["energy"], "price": listoffers[names]["price"]}
        print('Seller: %s' %self.bestseller)
        if self.bestseller["price"] <= prosumer.price:
            prosumer.price = self.bestseller["price"]
            message = {"name": prosumer.name, "energy":prosumer.energy, "price":prosumer.price}
        else:
            prosumer.price = (self.bestseller["price"]+prosumer.price)/2
            message = {"name": prosumer.name, "energy":prosumer.energy, "price":prosumer.price}  
        comun.myPublish('PC/'+self.bestseller["name"], json.dumps(message))
        self.waiting_response = True
        #return self.bestseller    

    def analyzeresponse(self, seller):
        code = seller["code"]
        if code == 0:
            if self.buyer:
                #seller rejected offer
                comun.offers.pop(seller["name"])
                #prosumer.choosingseller(comun.offers)
            else:
                #buyer rejected counter offer
                comun.buyers.pop(seller["name"])
            self.waiting_response = False
        elif code == 1:
            #seller accepted offer
            self.waiting_response = False
            if self.buyer:
                prosumer.deposit(seller["energy"])
                print("You just bought %d watts at %d kw/h from %s" %(seller["energy"],seller["price"],seller["name"] ))
            #buyer accepted counter offer
            else:
                self.withdraw(seller["energy"])
                print("You just sold %d watts at %d kw/h to %s" %(seller["energy"],seller["price"],seller["name"] ))         
            self.waiting_response = False
        elif code == 2:
            #contra offer if im a buyer
            if self.buyer:
                if  seller["price"] <= self.secondbest["price"] or seller["price"] <= (prosumer.price*0.95):
                    self.waiting_response = False
                    message = {"code": 1, "name": self.name, "energy":seller["energy"], "price":seller["price"]}
                    comun.myPublish('PC/'+seller["name"], json.dumps(message))
                    self.deposit(seller["energy"])
                    print("You just bought %d watts at %d kw/h from %s" %(seller["energy"],seller["price"],seller["name"] ))
                elif seller["price"] >= (self.secondbest["price"]*1.1) or seller["price"] >= (prosumer.price*1.2):
                    #price increased a lot - reject offer
                    message = {"code": 0, "name": self.name, "energy":seller["energy"], "price":seller["price"]}
                    comun.myPublish('PC/'+seller["name"], json.dumps(message))
                    comun.offers.pop(seller["name"])
                    self.waiting_response = False                    
                else:
                    #invio contro contro oferta - WITH SECOND BEST PRICE
                    message = {"code": 2, "name": self.name, "energy":self.energy, "price":self.secondbest["price"]}
                    comun.myPublish('PC/'+seller["name"], json.dumps(message))
                    self.waiting_response = True
            #contra offer if im a seller
            else:
                if seller["price"] <= self.secondbuyer["price"]:
                    #reject counteroffer
                    message = {"code": 0, "name": self.name, "energy":self.energy, "price":self.secondbest["price"]}
                    comun.myPublish('PC/'+seller["name"], json.dumps(message))
                    comun.buyers.pop(seller["name"])
                else:
                    #accept counteroffer
                    self.withdraw(seller["energy"])
                    prosumer.price = seller["price"]
                    print("You just sold %d watts at %d kw/h to %s" %(seller["energy"],seller["price"],seller["name"] ))
                self.waiting_response = False
                    
        else:
            self.waiting_response = False
            
    def analyzeoffer(self,listbuyers):
        bestprice = self.rtp
        secondprice = self.price
        self.bestbuyer = {}
        self.secondbuyer = {}
        for names in listbuyers:
            if listbuyers[names]["energy"] <= self.energy:
                if  listbuyers[names]["price"] >= secondprice:
                    if  listbuyers[names]["price"] >= bestprice:
                        bestprice = listbuyers[names]["price"]
                        self.bestbuyer = {"name": names, "energy":listbuyers[names]["energy"], "price": listbuyers[names]["price"]}
                    else:
                        secondprice = listbuyers[names]["price"]
                        self.secondbuyer = {"name": names, "energy":listbuyers[names]["energy"], "price": listbuyers[names]["price"]}
        print('Buyer: %s' %self.bestbuyer)
        if self.bestbuyer["price"] >= (prosumer.price*0.95):
            #accept offer
            prosumer.price = self.bestbuyer["price"]
            message = {"code": 1, "name": prosumer.name, "energy":prosumer.energy, "price":prosumer.price}
        
        else:
            prosumer.price = (self.bestseller["price"]+prosumer.price)/2
            message = {"code": 2,"name": prosumer.name, "energy":prosumer.energy, "price":prosumer.price}  
        comun.myPublish('PC/'+self.bestseller["name"], json.dumps(message))
        self.waiting_response = True
    

def waitformsg(counter):
    a = 0
    while (a < counter):
        a += 1
        time.sleep(1)

            
if __name__ == "__main__":
    a = 0 #simulate delta time   
    prosumer =  Prosumer(3, 5, 'Kevin')
    
    comun = MyMQTT("myProsumer")
    comun.start()
    comun.mySubscribe('PC/offers')
    comun.mySubscribe("PC/"+prosumer.name)
    
    while (prosumer.energy > 0) and (a < 10):
        prosumer.buyer = True
        waitformsg(2)
        if not prosumer.waiting_response:
            prosumer.choosingseller(comun.offers)
        a += 1
        
    while (prosumer.energy < 0) and (a < 10):
        a += 1
        message = {"name": prosumer.name, "energy":prosumer.energy, "price":prosumer.price}
        comun.myPublish ('PC/offers',json.dumps(message))
        prosumer.waiting_response = True
        waitformsg(10)
        if not prosumer.waiting_response:
            if comun.buyers:
                prosumer.analyzeoffer(comun.buyers)
    
    print('Prosumer %s has %d energy left' %(prosumer.name,prosumer.energy))
    comun.stop()



    