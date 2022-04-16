import numpy as np
import random
import json

from mongoDB.database_client import databaseClient
class Instance():

    def __init__(self):
        ########## CONSTANT VALUES ######
        self.databaseClient = databaseClient()

        #THERMAL CONFORT 
        self.U_val = 0 #U value of the house, needed for the temperature dispersion
        self.Pac_max = 0 #AC max power
        self.Pewh_max = 0 #Water heater max power
        self.Tin_max = 0 #max indoor temp
        self.Tin_min = 0 #min indoor temp
        self.Tewh_max = 0 #max water temp
        self.Tewh_min = 0 #min water temp
        self.Tcw = [] #incoming cold water temperature. List because has different temp during the day
        self.Tout = [] #outside temperatures
        self.Tset_off = 0 #tipical temperature of that kind of house
        self.Tset_off_wat = 0 #tipical temperature of the water in the pipes of that kind of house

        #extra EWH parameters:
        self.SA = 0 #surface area
        self.Wd = [] #water withdrawn
        self.Cp = 0 #CHECK WHAT THIS PARAMETER IS

        #BATTERY ENERGY SOURCES
        self.disch_eff_ESS = 0 #ESS discharging efficiency
        self.disch_eff_PEV = 0 #PEV discharging efficiency
        self.charge_eff_ESS = 0 #ESS charging efficiency
        self.charge_eff_PEV = 0 #PEV charging efficiency

        self.Pess_chmax = 0
        self.Pess_dismax = 0 #max discharging power NOTA: it's a negative number
        self.Ppev_chmax = 0
        self.Ppev_dismax = 0

        self.Cess_max = 0 #max capacity of the battery
        self.Cpev_max = 0 #max capacity of the PEV battery

        self.Cess_thresh_low = 0 #perceptages telling which is the lower bound of the battery 
        self.Cess_thresh_high = 0
        self.Cpev_thresh_low = 0
        self.Cpev_thresh_high = 0

        #APPLIANCES
        self.N_sched_appliances = 0 #this number has to be defined so we can write variables like Nd and all the othersvariables
        #Probably in the instance phase will be created a list with the appliance names and their running length and their consumption
        self.sched_appliances = {"name":[],
                                 "running_len":[],
                                 "num_cycles":[], #for all those appliances where there are more cycles, like for washing machine, where the second cycle is the dryer
                                 "power_cons":[],
                                 "c1":[],
                                 "c2":[]}
        self.daily_mean_EA = []

        #OTHER ENERGY SOURCES
        self.RES_hour_gen = [] #REV hourly production, probably like kW/h
        self.Pdr = 0 #contract with the utility
        
        #PRICES
        self.RTP = [] #list with the price of elec during all the day
        self.RTPess_dis = 0 #price for discharging the battery
        self.RTPpev_dis = 0 #prive for discharging the vehicle

        #TIME 
        self.time_granularity = 15 #expressed in minutes, tells the time range of the measures. In this way there are 96 time slots
        self.time_dep = 0 #departure time of PEV

    def get_data_serv(self):
        data = self.databaseClient.read_documents(collection_name='home_configuration', collection={'_id':0}) 
        
        #THERMAL CONFORT 
        self.U_val = data["U_val"] #U value of the house, needed for the temperature dispersion
        self.Pac_max = data["Pac_max"] #AC max power
        self.Pewh_max = data["Pewh_max"] #Water heater max power
        self.AC_mode = data["AC_mode"] #1 Heating, -1 Chiller
        self.Tin_max = data["Tin_max"] #max indoor temp
        self.Tin_min = data["Tin_min"] #min indoor temp
        self.Tewh_max = data["Tewh_max"] #max water temp
        self.Tewh_min = data["Tewh_min"] #min water temp
        self.Tcw = data["Tcw"] #incoming cold water temperature. List because has different temp during the day
        self.Ten = data["Ten"] #same here, the enviromental temperature can be different during the day
        self.Tout = data["Tout"] #outside temperatures
        self.Tset_off = data["Tset_off"] #tipical temperature of that kind of house
        self.Tset_off_wat = data["Tset_off_wat"] #tipical temperature of the water in the pipes of that kind of house

        data = self.databaseClient.read_documents(collection_name='home_configuration', collection={'_id':2}) 
        
        #extra EWH parameters:
        self.R = data['R']
        self.boiler_vol =  data["boiler_vol"]
        self.boiler_radius = data["boiler_radius"]
        self.Cp = data["Cp"]
        
        self.U = data["U"] #stand-by loss
        self.home_dimensions = data["home_dimensions"]
        self.SA = data["SA"] #surface area
        self.G = data["G"] # = self.U*self.SA
        self.Wd = data["Wd"]  #water withdrawn
        self.rho = data["rho"] #water density
        self.C = data["C"] #CHECK WHAT THIS PARAMETER IS
        self.B = data["B"] #self.Wd*self.rho*self.C
        self.Rprime = data["Rprime"] #1/(self.G+self.B)
        self.tau = data["tau"] #self.Rprime*self.C

        data = self.databaseClient.read_documents(collection_name='home_configuration', collection={'_id':3}) 

        #BATTERY ENERGY SOURCES
        self.disch_eff_ESS = data["disch_eff_ESS"] #ESS discharging efficiency
        self.disch_eff_PEV = data["disch_eff_PEV"] #PEV discharging efficiency
        self.charge_eff_ESS = data["charge_eff_ESS"] #ESS charging efficiency
        self.charge_eff_PEV = data["charge_eff_PEV"] #PEV charging efficiency

        self.Pess_chmax = data["Pess_chmax"] 
        self.Pess_dismax = data["Pess_dismax"] #max discharging power NOTA: it's a negative number
        self.Ppev_chmax = data["Ppev_chmax"]
        self.Ppev_dismax = data["Ppev_dismax"]

        self.Cess_max = data["Cess_max"] #max capacity of the battery
        self.Cpev_max = data["Cpev_max"] #max capacity of the PEV battery

        self.Cess_thresh_low = data["Cess_thresh_low"] #perceptages telling which is the lower bound of the battery 
        self.Cess_thresh_high = data["Cess_thresh_high"]
        self.Cpev_thresh_low = data["Cpev_thresh_low"]
        self.Cpev_thresh_high = data["Cpev_thresh_high"]

        self.Cess_init = data["Cess_init"] #Save the battery status from one day to another
        self.Cpev_init = data["Cpev_init"] #Save the battery status at the arrival time

        data = self.databaseClient.read_documents(collection_name='home_configuration', collection={'_id':4}) 

        #APPLIANCES
        self.N_sched_appliances = data["N_sched_appliances"] #this number has to be defined so we can write variables like Nd and all the othersvariables
        #Probably in the instance phase will be created a list with the appliance names and their running length and their consumption
        self.sched_appliances = data["sched_appliances"] 
        self.daily_mean_EA = data["daily_mean_EA"]

        data = self.databaseClient.read_documents(collection_name='home_configuration', collection={'_id':5}) 

        #OTHER ENERGY SOURCES
        self.RES_hour_gen = data["RES_hour_gen"] #REV hourly production, probably like kW/h
        self.Pdr = data["Pdr"] #contract with the utility
        
        data = self.databaseClient.read_documents(collection_name='home_configuration', collection={'_id':6}) 

        #PRICES
        self.RTP = data["RTP"] #list with the price of elec during all the day
        self.RTP_avg = data["RTP_avg"] #mean elec mean price. Check more what's useful for
        self.RTPess_dis = data["RTPess_dis"]  #price for discharging the battery
        self.RTPpev_dis = data["RTPpev_dis"] #prive for discharging the vehicle
        self.RTPpev_ch = data["RTPpev_ch"]

        data = self.databaseClient.read_documents(collection_name='home_configuration', collection={'_id':7}) 

        #TIME 
        self.time_granularity = data["time_granularity"] #expressed in minutes, tells the time range of the measures. In this way there are 96 time slots
        self.time_dep = data["time_dep"] #departure time of PEV
        self.time_arrival = data["time_arrival"] #arrival time of PEV (only for the first implementation, for next implementation not a constant
                                                    #we'll use the MQTT subs)
        self.tn_end = data["tn_end"] #upper limit for the PEV battery utilization, after that, the vehicle will be only charged