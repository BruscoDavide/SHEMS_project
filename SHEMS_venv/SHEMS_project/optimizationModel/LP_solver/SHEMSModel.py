from cProfile import label
import gurobipy as gp
from gurobipy import GRB
import numpy as np
import time
import datetime 
import math
import matplotlib.pyplot as plt
import copy

class SHEMS():

    def __init__(self, instance):
        self.instance = instance

        self.total_power_cons = 0 #sum of the total power consumed over the day, multiplied by the RTP(i)
        self.Tin_out = np.zeros(int(1440/self.instance.time_granularity)) #internal scheduled temperature of the house
        self.Pac_out = np.zeros(int(1440/self.instance.time_granularity)) #required temperature for keeping the internal temperature in the desider range
        self.Tewh_out = np.zeros(int(1440/self.instance.time_granularity)) #schedule for the electic water heater given the water usage
        self.Pewh_out = np.zeros(int(1440/self.instance.time_granularity)) #power used for keeping the EWH in the desired range
        self.ud_out = np.zeros((int(1440/self.instance.time_granularity), self.instance.N_sched_appliances)) #activation indicators of the home appliacens
        self.Pg_out = np.zeros(int(1440/self.instance.time_granularity)) #total power consumed/produced by the house: retrieved as the sum of EA + CA + SA + RES_power

        self.Pess = np.zeros(int(1440/self.instance.time_granularity)) #power that the ESS can return in output
        self.Cess = np.zeros(int(1440/self.instance.time_granularity)) #capacity that the battery can supply
        self.Ppev = np.zeros(int(1440/self.instance.time_granularity)) #power that the PEV can return in output
        self.Cpev = np.zeros(int(1440/self.instance.time_granularity)) #capacity that the battery of the electic vehicle can supply
        self.Pg_market = np.zeros(int(1440/self.instance.time_granularity)) #power exchange with the grid: positive is needed power, negative is selling power

        self.Pess_chable = np.zeros(int(1440/self.instance.time_granularity)) #how much power can be insert in the battery
        self.Pess_disable = np.zeros(int(1440/self.instance.time_granularity)) #how much power can be discharged from the battery
        self.Ppev_chable = np.zeros(int(1440/self.instance.time_granularity)) #how much power can be insert in the electric vehicle
        self.Ppev_disable = np.zeros(int(1440/self.instance.time_granularity)) #how much power can be discharged from the electric vehicle

        self.Pess_ch  = np.zeros(int(1440/self.instance.time_granularity)) #quantity of power that was charged/discharged from the battery
        self.Ppev_ch = np.zeros(int(1440/self.instance.time_granularity)) #quantity of power that was charged/discharged from the electric vehicle

        self.Phouse_consume = np.zeros(int(1440/self.instance.time_granularity)) #total power required from the house 
        self.Pselling = np.zeros(int(1440/self.instance.time_granularity)) #net energy that can be sold 

        self.delta_t = 0 
        self.start_point = 0 #used for calls different from the first morning iteration. It tells the slot of time we're in

        self.first_iteration = 1 #when the class is instantiated, it means that it's the first time it's runned, so it will do all the scheduling
        self.appliances_set = 0 #activated after the first schedule
        self.changed_set_points = 0 #telling the system that there is needed a new scheduling because confort constraints changed
        self.new_or_deleted_appliance = {"flag":0, "backup":{}} #used to insert or delete new appliances
        self.modify_appliance = {"flag":0, "appliance":[], "start_time":[]} #used to change the time of execution of an appliance

        self.vehicle_at_home = 0 #used for informing the system that the car is at home and it can be considered in the charging/discharging cycles

    def get_new_instance(self, instance):
        self.instance = instance
        #when data are changed, the new data have to be retrieved from the server, or they will have to be read from the file

    def set_working_mode(self, payload):
        """
        LEGEND:
        0 - changed set points
        1 - modify appliance
        2 - change/delete appliance 
        3 - [water withdraw] ancora da vedere
        4 - car at home
        """
        if payload["command"] == 0:
            self.instance = self.get_new_instance()
            self.changed_set_points = 1
        elif payload["command"] == 1:
            self.modify_appliance["flag"] = 1
            self.modify_appliance["appliance"] = payload["appliance"]
            self.modify_appliance["start_time"] = payload["start_time"]
        elif payload["command"] == 2:
            self.new_or_deleted_appliance["flag"] = 0
            self.new_or_deleted_appliance["backup"] = self.instance #NOTA: here there can be the pointer problem
            self.instance = self.get_new_instance()
        elif payload["command"] == 3:
            pass


        else: #trial toy case
            self.modify_appliance["flag"] = 1
            self.modify_appliance["appliance"].append("washing_machine")
            self.modify_appliance["start_time"].append("01:00")

    def set_car_arrival(self):
        self.vehicle_at_home = 1
        act_datetime = datetime.datetime.now()
        act_datetime = str(act_datetime)
        act_datetime = act_datetime.split()
        act_time = act_datetime[1].split(':')
        if act_time[0] == '00' or int(act_time[0]) < 8:
            act_mins = 16*60 #hours passed from 8 to midnight
            act_mins += int(act_time[0])
            act_mins += int(act_time[1])
        else:
            act_mins = (int(act_time[0]) - 8)*60
            act_mins += int(act_time[1])
        start_point = math.ceil(act_mins/self.instance.time_granularity ) -1
        self.Cpev[start_point -1] = np.random.uniform(0, self.instance.Cpev_thresh_high*self.instance.Cpev_max/2)
        self.Ppev[start_point -1] = self.Cpev[start_point - 1]*self.instance.charge_eff_PEV
        self.Cpev[start_point] = self.Cpev[start_point -1]
        self.Ppev[start_point] = self.Cpev[start_point]*self.instance.charge_eff_PEV
        self.battery_schedule(start_point)
        
    def set_car_leave(self):
        pass

################# WORK IN PROGRESS on the new version of the model #####################################
    #NOTA: now the model seems working pretty fine
    #      1) it does the scheduling for all the day
    #           -> TODO: add the penalty function on the appliances with the table as Tao suggested in the past
    #              NOTA: the penalty function can not be compatible with the flexible model where new appliances can be added or deleted
    #           -> does a first scheduling using a standard schedule of what an average house uses among the day
    #      2) it does the scheduling only for the AC/HW
    #           -> AC planning done using the weather forecast
    #           -> HW planning done at first time using a predefined schedule, then adapted during the day
    #           -> TODO: check the goodness of the models:
    #                   - AC fixed, correct Building formula introduced with xps insulation 
    #                   - HW to be fixed, uses too much energy 
    #      3) it takes in input modifications from the user side 
    #           -> starts now the appliance
    #           -> take custom requests with specific starting times -> RECALL TO TELL ALEJO TO INSERT THE CONTROLS
    #
    def solve_definitive(self, time_limit = None, gap = None, verbose = False):
        """
            The function is composed always by the same building blocks, but it changes the way it is composed, depending on the flags that are passed
            There can be different scenarios:
            1) the new day has started, so do the full cheduling for all the day, no matter if the water usage changes. Once the scheduling is done, set the 
               self.first_iteration_done = 1 =======> the first_iteration flag is perfect for the first run
            2) the set_points of the water or of the AC are changed, so only need to reschedule those appliances
            3) the water is withdrawn from the tank, so the model needs to be rescheduled
            3) the users wants to move an appliance in a defined moment

        Args:
            first_iteration (_type_): _description_
            time_limit (_type_, optional): _description_. Defaults to None.
            gap (_type_, optional): _description_. Defaults to None.
            verbose (bool, optional): Tells to Gurobi if to print all the model or not. Defaults to False.

        Returns:
            _type_: _description_
        """
        #before starting solving, check the time to understand on how many time slots we have to iterate
        flags_runnining_appliances = np.zeros(self.instance.N_sched_appliances)
        if self.first_iteration == 0:
            act_datetime = datetime.datetime.now()
            act_datetime = str(act_datetime)
            act_datetime = act_datetime.split()
            act_time = act_datetime[1].split(':')
            if act_time[0] == '00' or int(act_time[0]) < 8:
                act_mins = 16*60 #hours passed from 8 to midnight
                act_mins += int(act_time[0])
                act_mins += int(act_time[1])
            else:
                act_mins = (int(act_time[0]) - 8)*60
                act_mins += int(act_time[1])
            start_point = math.ceil(act_mins/self.instance.time_granularity ) 
            self.start_point = start_point 
            remaining_minutes = 1440 - act_mins
            tmp = math.floor(remaining_minutes/self.instance.time_granularity)

            ################################################
            #new part regarding the appliance insertion or deletion
            #create a cycle iterating on all the old appliances and check if they are in the new appliance list:
            # - those that are still there, hold self.ud_out to check if they are completed or if they are running at the moment
            # - those that are deleted, are got out of self.ud_out
            # - those that are new, will have a dedicated new column
            if self.new_or_deleted_appliance["flag"] == 1:
                ud_tmp = np.zeros((int(1440/self.instance.time_granularity), self.instance.N_sched_appliances))
                for appl in self.new_or_deleted_appliance["backup"]["name"]:
                    if appl in self.instance.sched_appliances["name"]:
                        ud_tmp[:, np.where(self.instance.sched_appliances["name"] == appl)[0][0] ] = self.ud_out[:, np.where(self.new_or_deleted_appliance["backup"]["name"] == appl)[0][0] ]
            
                self.ud_out = ud_tmp
            ################################################

            #check for schedules that are completed or that are done at the moment
            for t in range(self.instance.N_sched_appliances):
                if self.ud_out[start_point-1][t] == 1:
                    flags_runnining_appliances[t] = 1 #appliances still running, so they have to be taken in account in the future energy balance
                if np.sum(self.ud_out[0:start_point-1,t]) >= self.instance.sched_appliances["running_len"][t]:
                    flags_runnining_appliances[t] = 2 #done, no more in the model

        elif self.first_iteration == 1: #FIRST RUN OF THE DAY, RUN THE FULL MODEL
            start_point = 0
            remaining_minutes = 1440
        
        ###### SCHED APPLIANCES VARS ######
        #If all the appliances were already set and the user doesn't ask to modify an appliance, the this part can be skipped from the model
        flag_all_sched_done = 0 
        #if self.appliances_set == 1 and self.modify_appliance["flag"] == 0: 
        if self.appliances_set == 1 and self.new_or_deleted_appliance["flag"] == 1: 
            #NOTA: il a full rescheduling is needed because some appliances were took outside or addes, we have to check if eventual appliances are
            #running or already are already finished, so no reschedule needing
            #We use the flag vector and check how many indexes are nonzero, we sum them and we know how many appliances not to schedule
            #If all the schedulable appliances had a run, the no need for rescheduling
            if len(flags_runnining_appliances[np.nonzero(flags_runnining_appliances)]) == self.instance.N_sched_appliances:
                #np.nonzero returns the indeces of where the number is different from zero
                #x[np.nonzero(x)] returns the values of the values that are non zero
                #len(x[...]) returns the length of the nonzero value vector
                #If this vector il long as the number of schedulable appliances, then all are done
                flag_all_sched_done = 1

        problem_name = "SHEMS_scheduling"
        model = gp.Model(problem_name)
        ######################################################################################################
        ############################### VARIABLE DEFINITION: #################################################
        ######################################################################################################
        T_in, dT, beta, Pac, T_ewh, Pewh, Q, ud, aux, Pg = self.set_gurobi_variables(model, remaining_minutes, flag_all_sched_done, flags_runnining_appliances)
        ######################################################################################################
        ################## OBJ FUNCTION DEFINITION ###########################################################
        ######################################################################################################
        obj = 0
        obj += gp.quicksum(Pg[i]*self.instance.RTP[start_point -1 + i]*self.instance.time_granularity for i in range(int(remaining_minutes/self.instance.time_granularity)))
        model.setObjective(obj, GRB.MINIMIZE)
        ######################################################################################################
        ################## CONSTRAINTS #######################################################################
        ######################################################################################################
        indexes = self.set_gurobi_constraints(model, T_in, dT, beta, Pac, T_ewh, Pewh, Q, ud, aux, Pg, remaining_minutes, start_point, flag_all_sched_done, flags_runnining_appliances)

        model.update()
        model.params.NonConvex = 2
        if gap:
            model.setParam('MIPgap', gap)
        if time_limit:
            model.setParam(GRB.Param.TimeLimit, time_limit)
        if verbose:
            model.setParam('OutputFlag', 1)
        else:
            model.setParam('OutputFlag', 0)

        start = time.time()
        model.optimize()
        end = time.time()
        comp_time = end - start

        #model.write("./logs/model.lp")
        print(model.status)
        '''
        https://www.gurobi.com/documentation/9.1/refman/optimization_status_codes.html
        for status legend
        '''
        if model.status == GRB.Status.OPTIMAL:
            #objective function extraction
            self.total_power_cons = round(model.getObjective().getValue(),4)
            #self.ud_out = np.zeros((int(remaining_minutes/self.instance.time_granularity), self.instance.N_sched_appliances))
            #all variable extraction:
            for i in range(int(remaining_minutes/self.instance.time_granularity)):
                self.Tin_out[start_point+i] = model.getVarByName(f"Tin[{i}]").X
                self.Pac_out[start_point+i] = model.getVarByName(f"Pac[{i}]").X
                self.Tewh_out[start_point+i] = model.getVarByName(f"Tewh[{i}]").X
                self.Pewh_out[start_point+i] = model.getVarByName(f"Pewh[{i}]").X
                self.Pg_out[start_point+i] = model.getVarByName(f"Pg[{i}]").X
                if self.first_iteration == 1:
                    for j in range(self.instance.N_sched_appliances):
                        #this can be a source of bug, check if you can leave it like this or to put "start_point + i"
                        self.ud_out[i][j] = model.getVarByName(f"ud[{i},{j}]").X
                elif self.appliances_set == 1 or self.modify_appliance["flag"] == 1:
                    pass
                else: #self.first_iteration == 0:
                    for index in indexes:
                        asd = index[1]
                        self.ud_out[start_point+i][index[0]] = model.getVarByName(f"ud[{i},{asd}]").X
                        #print(model.getVarByName(f"ud[{i},{asd}]").X)

                #variables for telling the user how much is he consuming or has in surplus
                for t in range(self.instance.N_sched_appliances):
                    appliance_consumption_tmp = self.ud_out[start_point+i][t]*self.instance.sched_appliances["power_cons"][t]
                self.Phouse_consume[start_point+i] = self.Pac_out[start_point+i] + self.Pewh_out[start_point+i] + appliance_consumption_tmp + self.instance.daily_mean_EA[start_point+i]
                self.Pselling[start_point+i] = self.Phouse_consume[start_point+i] - self.instance.RES_hour_gen[start_point+i]
                    #print("\n")
            if self.first_iteration == 1:        
                self.first_iteration = 0
                self.appliances_set = 1        
           
            #self.get_plots()
            self.battery_schedule(start_point)
            return 2
        else:
            return -1

    def set_gurobi_variables(self, model, remaining_minutes, flag_all_sched_done, flags_runnining_appliances):
        ###### AC VARS ######
        T_in = model.addVars(
            int(remaining_minutes/self.instance.time_granularity),
            lb = self.instance.Tin_min, 
            ub = self.instance.Tin_max,
            vtype = GRB.CONTINUOUS, #for now set it continuous, but then check if can be integer
            name = "Tin"
        )

        dT = model.addVars(
            int(remaining_minutes/self.instance.time_granularity),
            lb = 0, #same here, assign them randomly, but more or less taking in account the real life devices limitations
            ub = 15,
            vtype = GRB.CONTINUOUS,
            name = "dT"
        )

        beta = model.addVars(
            int(remaining_minutes/self.instance.time_granularity),
            lb = -1, #same here, assign them randomly, but more or less taking in account the real life devices limitations
            ub = 1,
            vtype = GRB.INTEGER,
            name = "B"
        )

        Pac = model.addVars(
            int(remaining_minutes/self.instance.time_granularity),
            lb = 0, #same here, assign them randomly, but more or less taking in account the real life devices limitations
            ub = self.instance.Pac_max,
            vtype = GRB.CONTINUOUS,
            name = "Pac"
        )
        ###### EWH VARS #####
        T_ewh = model.addVars(
            int(remaining_minutes/self.instance.time_granularity),
            lb = (9/5*self.instance.Tewh_min + 32), #to avoid make the water freezing
            ub = (9/5*self.instance.Tewh_max + 32), #to avoid high water vapour and high pressure
            vtype = GRB.CONTINUOUS,
            name = "Tewh"
        )

        Pewh = model.addVars(
            int(remaining_minutes/self.instance.time_granularity),
            lb = 0, #same here, assign them randomly, but more or less taking in account the real life devices limitations
            ub = self.instance.Pewh_max,
            vtype = GRB.CONTINUOUS,
            name = "Pewh"
        )

        Q = model.addVars(
            int(remaining_minutes/self.instance.time_granularity),
            lb = 0, #same here, assign them randomly, but more or less taking in account the real life devices limitations
            ub = (0.947)*6*self.instance.Pewh_max, #0.947 is the conversion factor from BTU/h to BTU/s
            vtype = GRB.CONTINUOUS,
            name = "Q"
        )

        if self.appliances_set == 1 and self.modify_appliance["flag"] == 0 and self.new_or_deleted_appliance["flag"] == 0:
            ud = None #no need to be set, so put them as None
            aux = None
        elif self.appliances_set == 0 or (self.appliances_set == 1 and self.new_or_deleted_appliance["flag"] == 1): #appliances still not set, or new electodomestics, so need to schedule everything
            if flag_all_sched_done == 0:
                ud = model.addVars( #ud will have a shape like ud[x,y] where x is the time granularity and y is the number of appliances
                    int(remaining_minutes/self.instance.time_granularity), self.instance.N_sched_appliances - len(flags_runnining_appliances[np.nonzero(flags_runnining_appliances)]),
                    lb = 0,
                    ub = 1,
                    vtype = GRB.INTEGER,
                    name = "ud"
                    )

                aux = model.addVars(#here we have to use the auxiliary variables otherwise we can't set the abs value
                    int(remaining_minutes/self.instance.time_granularity)*2, self.instance.N_sched_appliances - len(flags_runnining_appliances[np.nonzero(flags_runnining_appliances)]),
                    lb = -1,
                    ub = 1,
                    vtype = GRB.INTEGER,
                    name = "aux"
                    )
            else:
                ud = None
                aux = None
        elif self.modify_appliance["flag"] == 1: #we'll modify self.ud_out, no need to insert it again in the model
            ud = None
            aux = None

        Pg = model.addVars(
            int(remaining_minutes/self.instance.time_granularity),
            lb = -10000,
            ub = self.instance.Pdr,
            vtype = GRB.CONTINUOUS,
            name = "Pg"
        )

        return T_in, dT, beta, Pac, T_ewh, Pewh, Q, ud, aux, Pg

    def set_gurobi_constraints(self, model, T_in, dT, beta, Pac, T_ewh, Pewh, Q, ud, aux, Pg, remaining_minutes, start_point, flag_all_sched_done, flags_runnining_appliances):
        self.set_comfort_constraints(model, T_in, dT, beta, Pac, T_ewh, Pewh, Q, remaining_minutes, start_point)
        indexes = self.set_CA_constraints(model, ud, aux, remaining_minutes, flag_all_sched_done, flags_runnining_appliances)
        self.set_total_power_constraints(model, ud, Pac, Pewh, Pg, remaining_minutes, flags_runnining_appliances, start_point)
        return indexes

    def set_comfort_constraints(self, model, T_in, dT, beta, Pac, T_ewh, Pewh, Q, remaining_minutes, start_point):
        ######################### AC VARIABLES #############################
        wall_height = 3
        wall_thinckness = 0.2
        home_wall_area = (self.instance.home_dimensions["north"] + self.instance.home_dimensions["south"] + self.instance.home_dimensions["east"] + self.instance.home_dimensions["west"])*wall_height
        home_volume =  (self.instance.home_dimensions["north"] + self.instance.home_dimensions["south"] + self.instance.home_dimensions["east"] + self.instance.home_dimensions["west"])*wall_height*wall_thinckness
        home_internal_volume = self.instance.home_dimensions["north"]*self.instance.home_dimensions["east"]*3
        ######################### HOT WATER VARIABLES ######################
        #Before defining the WH variables, we have to define some conversions because the model works in british units
        # BTU = kW *3414
        # meters = foots*0.3048
        # m3 = gallons/264.172
        # C = (F-32)*5/9
        # Q = 3,4121*10^3 * 3414 * kW
        # R = (9/5 * C * + 32)*(m3 * 0.003785)^2*3600/(kW*3414)
        # SA = (m/0.3048)^2 
        # libbres = 8.34*gallons
        """ 
        PARAMETER EXPLANATION:
        R = 15 #F * ft^2 * hour / BTU it's like the opposite of the U value
        Rseconds = R*3600 # F * ft^2 * s / BTU
        boiler_vol = [litri]/1000 => [m^3]
        boiler_radius = [m]
        boiler_height = boiler_vol/(3.14*boiler_radius**2) [m]
        SA = 2*3.14*boiler_radius*boiler_height + 2*(2*3.14*boiler_radius)  [m^2] => lateral cilinder area + base cilinder area
        SA = [m^2]/(0.3048)^2 => [ft^2]
        boiler_vol = [m^3]*(264.172) => [gallons]
        Cp = [BTU/(lbs * F)]
        G = SA/R [BTU/(F*hour)] NOTA: if R is defined in seconds, then also the G will have as unit BTU/(F*seconds)
        C = boiler_vol*8.34*Cp [libbres] NOTA: the 8.34 is for the gallons to lbs conversion since the boiler_vol is in gallons 
        """

        R = self.instance.R*3600 #F * ft^2 * sec / BTU
        boiler_vol = self.instance.boiler_vol/1000 # m^3
        boiler_height = boiler_vol/(3.14*self.instance.boiler_radius**2) #m^2
        SA = 2*3.14*self.instance.boiler_radius*boiler_height + 2*(2*3.14*self.instance.boiler_radius) # m^2 => lateral cilinder area + base cilinder area
        SA = SA/(0.3048)**2 #ft^2
        boiler_vol = boiler_vol*264.172 #gallons
        Cp = self.instance.Cp #BTU/(lbs * F)
        G = SA/R #BTU/(F*s) 
        C = boiler_vol*8.34*Cp 
        

        ####### AC CONSTRAINTS ########
        for i in range(int(remaining_minutes/self.instance.time_granularity)):
            ########### INDOOR TEMP RELATION ##########
            if i != 0:
                #NEW MODEL:
                # Tin(t) = Tin(t-1) * U*home_wall_area*(Tout(t) - Tin(t-1))/(material_density*vol_home*Cs_air) * (deltaT_min*60)
                # [C] = [C] * [W/(K*m2)]*[m2]*[K]/( [Kg/m3]*[m3] * [J/(Kg*K)] )*sec 
                #
                model.addConstr(
                    T_in[i] == T_in[i-1] + self.instance.U_val*home_wall_area*(self.instance.Tout[start_point + i] - T_in[i-1])*self.instance.time_granularity*60/(2.5*home_volume*1300) + beta[i]*dT[i]
                )
            elif i == 0 and self.first_iteration == 1:
                model.addConstr(
                    T_in[i] == self.instance.Tset_off + self.instance.U_val*home_wall_area*(self.instance.Tout[start_point + i] - self.instance.Tset_off)*self.instance.time_granularity*60/(2.5*home_volume*1300) + beta[i]*dT[i]
                
                )
                
            elif i == 0 and self.first_iteration == 0:
                model.addConstr(
                    T_in[i] == self.Tin_out[start_point - 1] + self.instance.U_val*home_wall_area*(self.instance.Tout[start_point + i] - self.instance.Tset_off)*self.instance.time_granularity*60/(2.5*home_volume*1300) + beta[i]*dT[i]
                )
            model.addConstr(
                    beta[i]*(self.instance.Tout[start_point + i] - self.instance.Tset_off) <= 0
                )
            model.addConstr(
                    dT[i] == Pac[i]*self.instance.time_granularity*60/(1.005*home_internal_volume*0.718) #Pac*time*60/(air_density*Vol_home*Cs)
                )
            
        ####### HOT WATER RELATION ################
            B = 8.34*self.instance.Wd[i]*Cp
            Rprime = 1/(G + B)
            exp = np.exp(-self.instance.time_granularity*60*(1/(Rprime*C)))

            model.addConstr(
                Q[i] == (0.947)*6*Pewh[i] #0.947 is the conversion of the kW to btu/s
            )

            if exp != 0:
                if i != 0:
                    model.addConstr(
                        T_ewh[i] == T_ewh[i-1]*exp + (B*Rprime*(9/5*self.instance.Tcw[i] + 32) + Q[i]*Rprime)*(1 - exp) 
                    )
                elif i == 0:
                    model.addConstr(
                        T_ewh[i] == (9/5*48 + 32)*exp + (B*Rprime*(9/5*self.instance.Tcw[i] + 32) + Q[i]*Rprime)*(1 - exp)
                    )
            elif exp == 0:
                if i != 0:
                    model.addConstr(
                        T_ewh[i] == T_ewh[i-1] + (B*Rprime*(9/5*self.instance.Tcw[i] + 32) + Q[i]*Rprime) 
                    )
                elif i == 0:
                    model.addConstr(
                        T_ewh[i] == (9/5*48 + 32) + (B*Rprime*(9/5*self.instance.Tcw[i] + 32) + Q[i]*Rprime)
                    )

    def set_CA_constraints(self, model, ud, aux, remaining_minutes, flag_all_sched_done, flags_runnining_appliances):
        indexes = []
        if self.appliances_set == 1 and self.modify_appliance["flag"] == 0 and self.new_or_deleted_appliance["flag"] == 0:
            pass
        elif self.appliances_set == 1 and self.modify_appliance["flag"] == 1:
            counter = 0
            for to_change in self.modify_appliance["appliance"]: #take every appliance that user wants to change
                for z in range(self.instance.N_sched_appliances): #search among all the possible appliances     
                    if to_change == self.instance.sched_appliances["name"][z]: #check if you met the appliance of interest
                        if self.modify_appliance["start_time"] == "now":
                            self.ud_out[(self.start_point -1):,z] = 0 #deleting the old schedule
                            self.ud_out[(self.start_point - 1):(self.start_point - 1 + self.instance.sched_appliances["running_len"][z]),z] = 1 #setting the new schedule
                        elif self.modify_appliance["start_time"] != "now":
                            #Here there are two different controls to be done:
                            #1) check if the time is not wrong
                            #2) check if there are enough time slots
                            # NOTA: all of this would be better to be done on alejandros part
                            plan_time = self.modify_appliance["start_time"][counter].split(':')
                            if plan_time[0] == '00' or int(plan_time[0]) < 8:
                                plan_mins = 16*60 #hours passed from 8 to midnight
                                plan_mins += int(plan_time[0])
                                plan_mins += int(plan_time[1])
                            else:
                                plan_mins = (int(plan_time[0]) - 8)*60
                                plan_mins += int(plan_time[1])
                            plan_point = math.ceil(plan_mins/self.instance.time_granularity ) 
                            self.ud_out[(self.start_point -1):,z] = 0 #deleting the old schedule
                            self.ud_out[(plan_point - 1):(plan_point - 1 + self.instance.sched_appliances["running_len"][z]),z] = 1 #setting the new schedule
                counter += 1
        elif self.appliances_set == 0 or (self.appliances_set == 1 and self.new_or_deleted_appliance["flag"] == 1): 
            #enters here in two conditions:
            #1) if it's early in the morning and the daily schedule has to be done
            #2) if something new was added or something was took off, so all the schedule has to be done again.
            #   In this case, all the schedules that were already done or that are in action, are not touched, the others that are new
            #   or that still weren't performed, are rescheduled for a more optimal spreading on the day

            if flag_all_sched_done == 0:
                indexes = np.where(flags_runnining_appliances == 0)
                indexes = indexes[0]
                indexes = list(indexes)
                for t in range(len(indexes)): #questa schifezza e' per sapere quale appliance corrisponde alle ud del vettore ricalcolato
                    tmp1 = (indexes[t],t)
                    indexes[t] = tmp1

                for j in range(self.instance.N_sched_appliances - len(flags_runnining_appliances[np.nonzero(flags_runnining_appliances)])):
                    for i in range(1, int(remaining_minutes/self.instance.time_granularity)):
                        model.addConstr(aux[i,j] == ud[i,j]-ud[i-1,j])
                        model.addConstr(aux[int(remaining_minutes/self.instance.time_granularity)+i,j] == gp.abs_(aux[i,j]))

                #after the auxiliary variable definition, we have to define the c1/c2 constraints
                for index in indexes:
                    model.addConstr(
                        gp.quicksum(ud[i,index[1]] for i in range(int(remaining_minutes/self.instance.time_granularity)) ) == self.instance.sched_appliances["running_len"][index[0]] #check how to define the running length. I guess it is in timeslots
                    )
                    model.addConstr(
                        gp.quicksum(aux[int(remaining_minutes/self.instance.time_granularity)+i,index[1]] for i in range(int(remaining_minutes/self.instance.time_granularity)) ) >= self.instance.sched_appliances["c1"][index[0]])
                    model.addConstr(
                        gp.quicksum(aux[int(remaining_minutes/self.instance.time_granularity)+i,index[1]] for i in range(int(remaining_minutes/self.instance.time_granularity))  ) <= self.instance.sched_appliances["c2"][index[0]]
                    )
            
            return indexes

    def set_total_power_constraints(self, model, ud, Pac, Pewh, Pg, remaining_minutes, flags_runnining_appliances, start_point):
        ####### TOTAL ENERGY CONS ##########
        if self.appliances_set == 1 or self.modify_appliance["flag"] == 1: #both cases, the appliances are fixed
            #NOTA: cosi' la schedule si puo' modificare solo facendo partire l'appliance ORA. Per il futuro dare la scelta all'utente di scegliere i time slots che preferisce
            for i in range(int(remaining_minutes/self.instance.time_granularity)):
                tmp = 0
                for j in range(self.instance.N_sched_appliances): #take the updated schedule and add the time slot consumption
                    tmp += self.ud_out[start_point -1 + i][j]*self.instance.sched_appliances["power_cons"][j]
                timeslot_compsumption = self.instance.daily_mean_EA[start_point - 1 + i] + tmp
                model.addConstr(
                    Pg[i] == timeslot_compsumption + Pac[i] + Pewh[i] - self.instance.RES_hour_gen[start_point + i]
                    )
        else: #here for when we do all the scheduling/rescheduling
            for i in range(int(remaining_minutes/self.instance.time_granularity)):
                if len(flags_runnining_appliances[np.nonzero(flags_runnining_appliances)]) == 0: #if nothing is still finished, neither in progress
                    model.addConstr(
                        Pg[i] == self.instance.daily_mean_EA[start_point -1 + i] + Pac[i] + Pewh[i] + gp.quicksum(self.instance.sched_appliances["power_cons"][j]*ud[i,j] for j in range(self.instance.N_sched_appliances - len(flags_runnining_appliances[np.nonzero(flags_runnining_appliances)]))) - self.instance.RES_hour_gen[start_point -1 + i]
                        )
                elif len(flags_runnining_appliances[np.nonzero(flags_runnining_appliances)]) != 0: #if something is finished or it's in process
                    tmp = 0
                    for j in range(self.instance.N_sched_appliances):
                        #here we have to take in account all the energy consumption present at the moment of the acquisition
                        if flags_runnining_appliances[j] == 1: #if the appliance is running at the moment, consider it's current working energy requirement
                            tmp += self.ud_out[start_point -1 + i][j]*self.instance.sched_appliances["power_cons"][j]
                            #timeslot_compsumption = self.instance.daily_mean_EA[start_point + i] + self.ud_out[i][j]*self.instance.sched_appliances["power_cons"][j]
                        elif flags_runnining_appliances[j] == 2: #if ended, don't consider it's contribution
                            #timeslot_compsumption = self.instance.daily_mean_EA[start_point + i]
                            tmp += 0
                    timeslot_compsumption = self.instance.daily_mean_EA[start_point + i] + tmp
                    model.addConstr(
                        Pg[i] == timeslot_compsumption + Pac[i] + Pewh[i] - self.instance.RES_hour_gen[start_point + i]
                        )

    def get_plots(self):
        plt.figure()
        plt.plot(self.Tin_out, label = "Tin")
        plt.plot(self.instance.Tout, label = "Tout")
        plt.legend()
        plt.show()

        fig, ax1 = plt.subplots()
        ax1.set_xlabel("time of day")
        ax1.set_ylabel("kW")
        ax1.plot(self.Pac_out, label = "Pac", color = 'b')
        ax1.plot(self.instance.RES_hour_gen, label = "RES", color = 'g')
        ax2 = ax1.twinx()
        ax2.set_label("Euros")
        ax2.plot(self.instance.RTP, label = "RTP", color = 'y')
        fig.legend()
        plt.show()

        fig, ax1 = plt.subplots()
        ax1.set_xlabel("time of day")
        ax1.set_ylabel("kW")
        ax1.plot(self.Pewh_out, label = 'Pewh', color = 'b')
        #ax1.plot(self.instance.RES_hour_gen, label = "RES", color = 'g')
        ax2 = ax1.twinx()
        ax2.set_label("Euros")
        ax2.plot(self.instance.RTP, label = "RTP", color = 'y')
        fig.legend()
        plt.show()

        fig, ax1 = plt.subplots()
        ax1.set_xlabel("time of day")
        ax1.set_ylabel("kW")
        ax1.plot(self.Pewh_out, label = 'Pewh', color = 'b')
        #ax1.plot(self.instance.RES_hour_gen, label = "RES", color = 'g')
        ax2 = ax1.twinx()
        ax2.set_label("F")
        ax2.plot(self.Tewh_out, label = "Tehw", color = 'y')
        fig.legend()
        plt.show()

        fig, ax1 = plt.subplots()
        ax1.set_xlabel("time of day")
        ax1.set_ylabel("kW")
        ax1.plot(self.Pewh_out, label = 'Pewh', color = 'b')
        #ax1.plot(self.instance.RES_hour_gen, label = "RES", color = 'g')
        ax2 = ax1.twinx()
        ax2.set_label("gallons/sec")
        ax2.plot(self.instance.Wd, label = "gallons/sec", color = 'y')
        fig.legend()
        plt.show()

        fig, ax1 = plt.subplots()
        ax1.set_xlabel("time of day")
        ax1.set_ylabel("F")
        ax1.plot(self.Tewh_out, label = 'Tewh', color = 'b')
        #ax1.plot(self.instance.RES_hour_gen, label = "RES", color = 'g')
        ax2 = ax1.twinx()
        ax2.set_label("gallons/sec")
        ax2.plot(self.instance.Wd, label = "gallons/sec", color = 'y')
        fig.legend()
        plt.show()

        fig, ax1 = plt.subplots()
        ax1.set_xlabel("time of day")
        ax1.set_ylabel("kW")
        ax1.plot(self.Pg_out, label = 'Total power per deltaT', color = 'b')
        ax1.plot(self.instance.RES_hour_gen, label = "RES", color = 'g')
        ax2 = ax1.twinx()
        ax2.set_label("Euros")
        ax2.plot(self.instance.RTP, label = "RTP", color = 'y')
        fig.legend()
        plt.show()

        plt.plot(self.Pg_market, marker = 'o', color = 'r', label = "market")
        plt.plot(self.Pg_out, marker = 'x', color = 'b', label = 'Smart Meter')
        #plt.plot(self.instance.RES_hour_gen, marker = 'v', color = 'g', label = "RES")
        plt.plot(self.Pess_ch, marker = '+', color = 'black', label = "ESS ch +/-")
        plt.plot(self.Ppev_ch, marker = '+', label = "PEV ch +/-")
        plt.plot(self.Ppev, marker = '.', color = 'y', label = "Ppev")
        plt.plot(self.Pess, marker = ".", label = 'Pess')
        #plt.plot(self.Cess)
        plt.legend()
        plt.show()

    def get_results(self):
        return self.total_power_cons, self.Tin_out, self.Pac_out, self.Pg_out, self.ud_out, self.start_point
        #return self.total_power_cons, self.Tin_out, self.Pac_out, self.Tewh_out, self.Pewh_out, self.Pg_out, self.Cess, self.Pess, self.Pess_ch, self.Ppev, self.Ppev_ch, self.Cpev

    def charge_ESS(self, power,i):        
        charging_power = power
        energy_to_sell = 0
        if charging_power > self.instance.Pess_chmax: #if the power is bigger that the charging limit, cut the exceeding part and sell it
            energy_to_sell = charging_power - self.instance.Pess_chmax  
            charging_power = self.instance.Pess_chmax                                                                                     
        self.Pess_ch[i] = charging_power
        self.Cess[i] = self.Cess[i-1] + charging_power/(self.delta_t)    #the battery with "power" input for an hour whould have reached powerKWh, but the time is 15 minutes
                                                                #so to understand the capacity, we need to divide by 4
        if self.Cess[i] > self.instance.Cess_thresh_high*self.instance.Cess_max:
            self.Cess[i] = self.instance.Cess_thresh_high*self.instance.Cess_max
            self.Pess_ch[i] = self.Pess_chable[i]*self.delta_t
            energy_to_sell = power - self.Pess_chable[i]*self.delta_t
        self.Pess[i] = self.Cess[i]*self.instance.charge_eff_ESS #/self.delta_t   #the charge is in kWh. That capacity has still to be divided by 4 to understand how
                                                                                #much energy we can have in 15 minutes

        return energy_to_sell

    def charge_PEV(self, power, i): 
        charging_power = power
        energy_to_sell = 0
        if charging_power > self.instance.Ppev_chmax: #if the power is bigger that the charging limit, cut the exceeding part and sell it
            energy_to_sell = charging_power - self.instance.Ppev_chmax  
            charging_power = self.instance.Ppev_chmax                                                                                     
        self.Ppev_ch[i] = charging_power
        self.Cpev[i] = self.Cpev[i-1] + charging_power/(self.delta_t)    #the battery with "power" input for an hour whould have reached powerKWh, but the time is 15 minutes
                                                                #so to understand the capacity, we need to divide by 4
        if self.Cpev[i] > self.instance.Cpev_thresh_high*self.instance.Cpev_max:
            self.Cpev[i] = self.instance.Cpev_thresh_high*self.instance.Cpev_max
            self.Ppev_ch[i] = self.Ppev_chable[i]*self.delta_t
            energy_to_sell = power - self.Ppev_chable[i]*self.delta_t
        self.Ppev[i] = self.Cpev[i]*self.instance.charge_eff_PEV #/self.delta_t   #the charge is in kWh. That capacity has still to be divided by 4 to understand how
                                                                                #much energy we can have in 15 minutes

        return energy_to_sell

    def discharge_ESS(self, P1, i):    
        if P1 < abs(self.instance.Pess_dismax):                                                                  
            self.Pess_ch[i] = -P1
            self.Cess[i] = self.Cess[i-1] - P1/(self.delta_t)   #the battery with "power" input for an hour whould have reached powerKWh, but the time is 15 minutes
                                                                #so to understand the capacity, we need to divide by 4
            if self.Cess[i] < self.instance.Cess_thresh_low*self.instance.Cess_max: #if absorbing too much energy, skip
                self.Cess[i] = self.Cess[i-1]
                self.Pess_ch[i] = 0
                self.Pg_market[i] = P1
            self.Pess[i] = self.Cess[i]*self.instance.charge_eff_ESS#/self.delta_t   #the charge is in kWh. That capacity has still to be divided by 4 to understand how
                                                                                       #much energy we can have in 15 minutes
        elif P1 > abs(self.instance.Pess_dismax):
            #The requested energy is too much and the battery can't output it, so must split it between acquiring from market and battery discharge
            self.Pess_ch[i] = self.instance.Pess_dismax
            self.Pg_market[i] = P1 + self.instance.Pess_dismax #reacall: Pess_dismax is a negative value
            self.Cess[i] = self.Cess[i-1] - abs(self.instance.Pess_dismax)/(self.delta_t)
            if self.Cess[i] < self.instance.Cess_thresh_low*self.instance.Cess_max: #if absorbing too much energy, skip
                self.Cess[i] = self.Cess[i-1]
                self.Pess_ch[i] = 0
                self.Pg_market[i] = P1
            self.Pess[i] = self.Cess[i]*self.instance.charge_eff_ESS


    def discharge_PEV(self, P1, i):
        if self.Cpev[i - 1] < self.instance.Cpev_thresh_low*self.instance.Cpev_max:
            self.Pg_market[i] = P1 
        elif P1 < abs(self.instance.Ppev_dismax):                                                                            
            self.Ppev_ch[i] = -P1
            self.Cpev[i] = self.Cpev[i-1] - P1/(self.delta_t)   #the battery with "power" input for an hour whould have reached powerKWh, but the time is 15 minutes
                                                                #so to understand the capacity, we need to divide by 4
            if self.Cpev[i] < self.instance.Cpev_thresh_low*self.instance.Cpev_max: #if absorbing too much energy, skip
                self.Cpev[i] = self.Cpev[i-1]
                self.Ppev_ch[i] = 0
                self.Pg_market[i] = P1
            self.Ppev[i] = self.Cpev[i]*self.instance.charge_eff_PEV   #the charge is in kWh. That capacity has still to be divided by 4 to understand how
                                                                                    #much energy we can have in 15 minutes
        elif P1 > abs(self.instance.Ppev_dismax): 
            #The requested energy is too much and the battery can't output it, so must split it between acquiring from market and battery discharge
            self.Ppev_ch[i] = self.instance.Ppev_dismax
            self.Pg_market[i] = P1 + self.instance.Ppev_dismax #reacall: Pess_dismax is a negative value
            self.Cpev[i] = self.Cpev[i-1] - abs(self.instance.Ppev_dismax)/(self.delta_t)
            if self.Cpev[i] < self.instance.Cpev_thresh_low*self.instance.Cpev_max: #if absorbing too much energy, skip
                self.Cpev[i] = self.Cpev[i-1]
                self.Ppev_ch[i] = 0
                self.Pg_market[i] = P1
            self.Ppev[i] = self.Cpev[i]*self.instance.charge_eff_PEV


    def battery_schedule(self, start_point = 0):
        remaining_minutes = 1440 - start_point*15
        if self.instance.ess_ownership == 1 and self.vehicle_at_home == 1:
            n = self.charging_cycles_comp(start_point)
        else:
            n = None
        self.Cess[start_point+1:] = 0 #then the system needs a function that gets the power levels
        self.Pess[start_point+1:] = 0 #to check the total level of the battery during the day
        self.Pess_ch[start_point+1:] = 0 #to check the delta charge/discharge over the day
        #########################################
        Cess_day_before = 0 #NEED FUNCTION
        ########################################

        self.Cpev[start_point+1:] = 0
        self.Ppev[start_point+1:] = 0 #to check the total level of the battery during the day
        self.Ppev_ch[start_point+1:] = 0 #to check the delta charge/discharge over the day
        #########################################
        Cpev_day_before = 0 #NEED FUNCTION
        ########################################

        self.Pess_chable[start_point+1:] = 0 
        self.Pess_disable[start_point+1:] = 0
        self.Ppev_chable[start_point+1:] = 0
        self.Ppev_disable[start_point+1:] = 0

        self.Pg_market[start_point+1:] = 0

        self.delta_t = 60/self.instance.time_granularity #in the first case it is delta_t = 0.25h
        if self.instance.ess_ownership == 0 and self.instance.pev_ownership == 0:
            for i in range(int(remaining_minutes/self.instance.time_granularity)):
                self.Pg_market[start_point + i] = self.Pg_out[start_point + i]
                

        elif self.instance.ess_ownership == 1 or self.instance.pev_ownership == 1:
            for i in range(int(remaining_minutes/self.instance.time_granularity)):
                #STEP 1: COMPUTE THE AVAILABLE ENERGY TO BE CHARGED AND DISCHARGED
                #
                if self.instance.ess_ownership == 1:
                    if i == 0 and start_point == 0:
                        """
                        NOTA: the capacity is expressed in kWh, but in our case the time_granularity is in minutes, 15 minutes slots.
                        So when doing the computations we need to pay attention how we compute the Chable.
                        We do the subtraction between upper limit and actual capacity and we obtain something which is kWh. To transform it in power we need to divide it
                        by the time duration so we remain with Watts. The time granularity is in minutes, so we have to transform it in minutes => kWh = 60kWmin, kWmin = kWh/60
                        Our time slot has a length of 15 minutes, so we have to multiply by 15, so the final capacity becomes expressed in function of the time slots => kW15min = kWh*15/60 = kWh/4
                        This is only the capacity, so now we can derive the Watts => P = C/time_slot
                        Now the measures are compatible and we obtain the amount of power that we can load into the battery in that time slot.
                        Remember then to divide by the charging inefficiency to obtain the real power needed to inject.
                        """
                        self.Pess_chable[start_point + i] = ( (self.instance.Cess_thresh_high*self.instance.Cess_max - Cess_day_before) / self.instance.charge_eff_ESS ) #/ self.delta_t # avail_Capacity/60*15 [kWmin * min]
                        if Cess_day_before <= 0:
                            self.Pess_disable[start_point + i] = 0
                        else:
                            tmp = (Cess_day_before - self.instance.Cess_thresh_low*self.instance.Cess_max)
                            if tmp < 0: #if the energy available is lower than the lower bound, than the battery can't be discharged
                                self.Pess_disable[start_point + i] = 0
                            else:
                                self.Pess_disable[start_point + i] = ( (Cess_day_before - self.instance.Cess_thresh_low*self.instance.Cess_max) * self.instance.disch_eff_ESS ) / self.delta_t
                    else: 
                        self.Pess_chable[start_point + i] = ( (self.instance.Cess_thresh_high*self.instance.Cess_max - self.Cess[start_point + i-1]) / self.instance.charge_eff_ESS ) #/ self.delta_t
                        if self.Cess[start_point + i-1] <= 0:
                            self.Pess_disable[start_point + i] = 0
                        else:
                            tmp = (self.Cess[start_point + i -1] - self.instance.Cess_thresh_low*self.instance.Cess_max) 
                            if tmp < 0: #if the energy available is lower than the lower bound, than the battery can't be discharged
                                self.Pess_disable[start_point + i] = 0 
                            else:
                                self.Pess_disable[start_point + i] = ( (self.Cess[start_point + i -1] - self.instance.Cess_thresh_low*self.instance.Cess_max) * self.instance.disch_eff_ESS ) #/ self.delta_t
                
                else:
                    #do nothing since all the charges are already set to 0 or they were resetted previously
                    pass
                
                #STEP 2: CHARGE/DISCHARGE THE BATTERIES
                #
                #
                # 2a: VEHICLE NOT AT HOME 
                if self.vehicle_at_home == 0 and self.instance.ess_ownership == 1: 
                    P1 = self.Pg_out[start_point + i]
                    if P1 < 0: #energy surplus 
                        #charge the battery with the extra power
                        extra_power = self.charge_ESS(abs(P1), start_point + i)

                        ##############################
                        # SELL THE ENERGY ON THE MARKET
                        ##############################
                        self.Pg_market[start_point + i] = -extra_power #energy given, so it's negative

                    elif P1 > 0: #energy required for the home
                        #provide the energy from the battery or from the utility
                        if self.instance.RTP[start_point + i] < self.instance.RTPess_dis: #electricity is convenient to be bought
                            ###########################################
                            #NOTA: here pay attention, if i = 0 we have to insert the last data of the day before
                            ##########################################
                            self.Pess[start_point + i] = self.Pess[start_point + i-1]
                            self.Cess[start_point + i] = self.Cess[start_point + i-1]
                            self.Pg_market[start_point + i] = P1 #record the energy bougth from the energy market
                            #if the price is low enough, buy some energy also for the battery:
                            if self.instance.RTP[start_point + i] < 0.09 and self.Pess_chable[start_point + i] != 0:
                                self.Pg_market[start_point + i] += self.Pess_chable[start_point + i]
                                self.charge_ESS(self.Pess_chable[start_point + i], start_point + i)
                            
                        elif self.instance.RTP[start_point + i] > self.instance.RTPess_dis: #electricity market is not that cheap, try with the ESS
                            if self.Pess_disable[start_point + i] > P1: #check if ESS has enough energy
                                self.discharge_ESS(P1,start_point + i)
                            else: #if not enough energy, just buy it
                                self.Pess[start_point + i] = self.Pess[start_point + i-1]
                                self.Cess[start_point + i] = self.Cess[start_point + i-1]
                                self.Pg_market[start_point + i] = P1 #record the energy bougth from the energy market

                #
                #
                # 2b: VEHICLE AT HOME
                elif self.instance.car_ownership == 1 and self.vehicle_at_home == 1: 
                    if i == 0 and start_point == 0:
                        self.Ppev_chable[start_point + i] = ( (self.instance.Cpev_thresh_high*self.instance.Cpev_max - Cpev_day_before) / self.instance.charge_eff_PEV ) #/ self.delta_t # avail_Capacity/60*15 [kWmin * min]
                        if Cpev_day_before <= 0:
                            self.Ppev_disable[start_point + i] = 0
                        else:
                            tmp = (Cpev_day_before - self.instance.Cpev_thresh_low*self.instance.Cpev_max)
                            if tmp < 0: #if the energy available is lower than the lower bound, than the battery can't be discharged
                                self.Ppev_disable[start_point + i] = 0
                            else:
                                self.Ppev_disable[start_point + i] = ( (Cpev_day_before - self.instance.Cpev_thresh_low*self.instance.Cpev_max) * self.instance.disch_eff_PEV ) / self.delta_t
                    else: 
                        self.Ppev_chable[start_point + i] = ( (self.instance.Cpev_thresh_high*self.instance.Cpev_max - self.Cpev[start_point + i-1]) / self.instance.charge_eff_PEV ) #/ self.delta_t
                        if self.Cpev[start_point + i-1] <= 0:
                            self.Ppev_disable[start_point + i] = 0
                        else:
                            tmp = (self.Cpev[start_point + i -1] - self.instance.Cpev_thresh_low*self.instance.Cpev_max) 
                            if tmp < 0: #if the energy available is lower than the lower bound, than the battery can't be discharged
                                self.Ppev_disable[start_point + i] = 0 
                            else:
                                self.Ppev_disable[start_point + i] = ( (self.Cpev[start_point + i -1] - self.instance.Cpev_thresh_low*self.instance.Cpev_max) * self.instance.disch_eff_PEV ) #/ self.delta_t
                    #
                    #
                    # 2b-1: VEHICLE AT HOME AND CAN BE USED
                    if start_point + i <= n: 
                        P1 = self.Pg_out[start_point + i]
                        if P1 > 0: #it means that the renewable is not enough, ask someone
                            if self.instance.RTP[start_point + i] < self.instance.RTPess_dis and self.instance.RTP[start_point + i] < self.instance.RTPpev_dis: #electricity is convenient to be bought
                            ###########################################
                            #NOTA: here pay attention, if i = 0 we have to insert the last data of the day before
                            ##########################################
                                self.Pess[start_point + i] = self.Pess[start_point + i-1]
                                self.Cess[start_point + i] = self.Cess[start_point + i-1]
                                self.Ppev[start_point + i] = self.Ppev[start_point + i-1]
                                self.Cpev[start_point + i] = self.Cpev[start_point + i-1]
                                self.Pg_market[start_point + i] = P1 #record the energy bougth from the energy market

                            elif self.instance.RTP[start_point + i] < self.instance.RTPess_dis and self.instance.RTP[start_point + i] > self.instance.RTPpev_dis: #electricity market is not that cheap, try with the ESS or PEV
                                if self.Ppev_disable[start_point + i] > P1:
                                    self.discharge_PEV(P1, start_point + i)
                                    self.Pess[start_point + i] = self.Pess[start_point + i-1]
                                    self.Cess[start_point + i] = self.Cess[start_point + i-1]
                                elif self.Ppev_disable[start_point + i] < P1: #if no enough energy, be conservative and buy from the market
                                    self.Ppev[start_point + i] = self.Ppev[start_point + i-1]
                                    self.Cpev[start_point + i] = self.Cpev[start_point + i-1]
                                    self.Pess[start_point + i] = self.Pess[start_point + i-1]
                                    self.Cess[start_point + i] = self.Cess[start_point + i-1]
                                    self.Pg_market[start_point + i] = P1

                            elif self.instance.RTP[start_point + i] > self.instance.RTPess_dis and self.instance.RTP[start_point + i] < self.instance.RTPpev_dis:
                                if self.Pess_disable[start_point + i] > P1:
                                    self.discharge_ESS(P1,start_point + i)
                                    self.Ppev[start_point + i] = self.Ppev[start_point + i-1]
                                    self.Cpev[start_point + i] = self.Cpev[start_point + i-1]
                                elif self.Pess_disable[start_point + i] < P1:
                                    ###########################################
                                    #NOTA: here pay attention, if i = 0 we have to insert the last data of the day before
                                    ##########################################
                                    self.Pess[start_point + i] = self.Pess[start_point + i-1]
                                    self.Cess[start_point + i] = self.Cess[start_point + i-1]
                                    self.Ppev[start_point + i] = self.Ppev[start_point + i-1]
                                    self.Cpev[start_point + i] = self.Cpev[start_point + i-1]

                                    self.Pg_market[start_point + i] = P1
                            elif self.instance.RTP[start_point + i] > self.instance.RTPess_dis and self.instance.RTP[start_point + i] > self.instance.RTPpev_dis:
                                #if RTP is higher than both discharging prices, we evaluate which device has more power to be discharged
                                #if ESS has more power, discharge that on
                                if self.Pess_disable[start_point + i] > self.Ppev_disable[start_point + i] and P1 < self.Pess_disable[start_point + i]:
                                    self.discharge_ESS(P1,start_point + i)
                                    self.Ppev[start_point + i] = self.Ppev[start_point + i-1]
                                    self.Cpev[start_point + i] = self.Cpev[start_point + i-1]
                                #if PEV has more power, discharge that
                                elif self.Ppev_disable[start_point + i] > self.Pess_disable[start_point + i] and P1 < self.Ppev_disable[start_point + i]:
                                    self.discharge_PEV(P1,start_point + i)
                                    self.Pess[start_point + i] = self.Pess[start_point + i-1]
                                    self.Cess[start_point + i] = self.Cess[start_point + i-1]
                                #if P1 is bigger than the single batteries capacities, but it is smaller than their total capacity
                                elif P1 > self.Pess_disable[start_point + i] and P1 > self.Ppev_disable[start_point + i] and P1 < self.Pess_disable[start_point + i] + self.Ppev_disable[start_point + i]:
                                    #different strategies can be applied:
                                    #1) if both batteries can be discharged, split the quantity
                                    #2) if previous cannot be applied, then take what you can form one and the remaining part from the other one
                                    if self.Pess_disable[start_point + i] > P1/2 and self.Ppev_disable[start_point + i] > P1/2:
                                        self.discharge_ESS(P1/2, start_point + i)
                                        self.discharge_PEV(P1/2, start_point + i)
                                    elif self.Pess_disable[start_point + i] > P1/2 and self.Ppev_disable[start_point + i] < P1/2: #PEV is the one with less power
                                        self.discharge_ESS(P1 - self.Ppev_disable[start_point + i], start_point + i)
                                        self.discharge_PEV(self.Ppev_disable[start_point + i], start_point + i)
                                    elif self.Pess_disable[start_point + i] < P1/2 and self.Ppev_disable[start_point + i] > P1/2: #ESS is the one with less power
                                        self.discharge_ESS(self.Pess_disable[start_point + i], start_point + i)
                                        self.discharge_PEV(P1 - self.Pess_disable[start_point + i], start_point + i)

                                #if P1 is bigger than the combination of both ESS and PEV, use what you can and then buy it from the market
                                elif P1 > self.Pess_disable[start_point + i] + self.Ppev_disable[start_point + i]:
                                    self.discharge_ESS(self.Pess_disable[start_point + i], start_point + i)
                                    self.discharge_PEV(self.Ppev_disable[start_point + i], start_point + i)
                                    self.Pg_market[start_point + i] = P1 - ( self.Pess_disable[start_point + i] + self.Ppev_disable[start_point + i] ) 
                                else:
                                    print("something went wrong with the RTPs in iteration ", start_point + i)


                        elif P1 < 0: #energy surplus, load the battery
                            avail_power = abs(P1) #power available for the battery charge
                            extra_power = self.charge_PEV(avail_power, start_point + i)
                            self.Pess[start_point + i] = self.Pess[start_point + i-1]
                            self.Cess[start_point + i] = self.Cess[start_point + i-1]
                            if extra_power > 0:
                                extra_power = self.charge_ESS(extra_power, start_point + i)
                                if extra_power > 0:
                                    self.Pg_market[start_point + i] = -extra_power
                        else:
                            print("something went wrong in section VEHICLE AT HOME, I<n")
                    #
                    #
                    # 2b-2: VEHICLE AT HOME AND CANNOT BE USED, ONLY CHARGE
                    elif start_point + i > n and start_point + i < self.instance.time_dep: #VEHICLE CAN'T BE USED ANYMORE FOR DISCHARGING
                        P1 = self.Pg_out[start_point + i]
                        if P1 < 0: #energy surplus 
                            avail_power = abs(P1)
                            extra_power = self.charge_PEV(avail_power, start_point + i)
                            self.Pess[start_point + i] = self.Pess[start_point + i-1]
                            self.Cess[start_point + i] = self.Cess[start_point + i-1]
                            #then charge the battery with the remaining power
                            if extra_power > 0:
                                extra_power = self.charge_ESS(extra_power, start_point + i)
                                ################################
                                # sell the remaining part of energy
                                ################################
                                if extra_power > 0:
                                    self.Pg_market[start_point + i] = -extra_power

                        elif P1 > 0: #energy required for the home
                            #PROVIDE THE ENERGY TO THE HOME 
                            if self.instance.RTP[start_point + i] < self.instance.RTPess_dis: #electricity is convenient to be bought
                                ###########################################
                                #NOTA: here pay attention, if i = 0 we have to insert the last data of the day before
                                ##########################################
                                self.Pess[start_point + i] = self.Pess[start_point + i-1]
                                self.Cess[start_point + i] = self.Cess[start_point + i-1]
                                self.Ppev[start_point + i] = self.Ppev[start_point + i-1]
                                self.Cpev[start_point + i] = self.Cpev[start_point + i-1]
                                self.Pg_market[start_point + i] = P1 #record the energy bougth from the energy market

                                #check if you can charge the car in this slot 
                                if self.instance.RTP[start_point + i] < np.mean(self.instance.RTP[start_point:self.instance.time_dep + 1]):
                                    #buy electricity also for the car
                                    self.Pg_market[start_point + i] += min(self.Ppev_chable[start_point + i], self.instance.Pdr - self.Pg_market[start_point + i], self.instance.Ppev_chmax) 
                                                                        #if available, buy all the Ppev_chable, otherwise buy only what's possible
                                    self.charge_PEV( min(self.Ppev_chable[start_point + i], self.instance.Pdr - self.Pg_market[start_point + i], self.instance.Ppev_chmax) , start_point + i)

                            elif self.instance.RTP[start_point + i] > self.instance.RTPess_dis: #electricity market is not that cheap, try with the ESS or PEV
                                if self.Pess_disable[start_point + i] > P1: #check if ESS has enough energy
                                    self.discharge_ESS(P1, start_point + i)
                                    self.Ppev[start_point + i] = self.Pess[start_point + i-1]
                                    self.Cpev[start_point + i] = self.Cpev[start_point + i-1]
                                elif self.Pess_disable[start_point + i] < P1:
                                    self.Pess[start_point + i] = self.Pess[start_point + i-1]
                                    self.Cess[start_point + i] = self.Cess[start_point + i-1]
                                    self.Ppev[start_point + i] = self.Ppev[start_point + i-1]
                                    self.Cpev[start_point + i] = self.Cpev[start_point + i-1]
                                    self.Pg_market[start_point + i] = P1

                                #check if you can charge the car in this slot    
                                if self.instance.RTP[start_point + i] < np.mean(self.instance.RTP[start_point:self.instance.time_dep + 1]):
                                    #buy electricity also for the car
                                    self.Pg_market[start_point + i] += min(self.Ppev_chable[start_point + i], self.instance.Pdr - self.Pg_market[start_point + i], self.instance.Ppev_chmax) 
                                                                        #if available, buy all the Ppev_chable, otherwise buy only what's possible
                                    self.charge_PEV( min(self.Ppev_chable[start_point + i], self.instance.Pdr - self.Pg_market[start_point + i], self.instance.Ppev_chmax) , start_point + i)
                    
                    elif start_point + i >= self.instance.time_dep:
                        self.Pess[start_point + i] = self.Pess[start_point + i-1]
                        self.Cess[start_point + i] = self.Cess[start_point + i-1]
                        if self.vehicle_at_home == 1:
                            self.vehicle_at_home = 0

    #Fucntion working: TODO eventually add a warning for all the situations where the user come home too late and the battery can't be fully charged
    def charging_cycles_comp(self, start_point):
        RTPpev_ch = np.mean(self.instance.RTP[start_point:self.instance.time_dep + 1]) #mean electricity price during the time car is connected to home
                                                                                        #this parameter is used to filter the charging time slots of the car
        RTP = np.array(self.instance.RTP)
        charge_time_slots = np.where(RTP[start_point:self.instance.time_dep] < RTPpev_ch)[0]
        #NOTA: this returns a list of indices that assumes self.instance.time_arrival as the first element of the list, so all the indexing needs to be as: 
        #self.instance.time_arrival + charge_time_slots[i]

        Ppev = copy.copy(self.Ppev)
        Cpev = copy.copy(self.Cpev)
        Ppev[start_point:] = 0
        Cpev[start_point:] = 0
        #from Pdr we subtract the total energy used for the other things and we remain with the net
        Ptemp = [self.instance.Pdr]*int(1440/self.instance.time_granularity)
        Ptemp = np.array(Ptemp)
        Ptemp = Ptemp - self.Pg_out
        for i in range(len(charge_time_slots),0,-1):
            if i == len(charge_time_slots): #at first iteration set the capacity to max
                Cpev[start_point + charge_time_slots[i - 1]] = self.instance.Cpev_thresh_high*self.instance.Cpev_max
                continue
            #for each iteration:
            #1) compute the power that can be charged on that time slot: we choose between the minimun qt that can be charged. If there's enough Pd energy that can fit in the battery, use it all
            #otherwise, if the battery is almost full and can fit only a part of the energy, fit only that
            Ppev[start_point + charge_time_slots[i - 1]] = min(Ptemp[start_point + charge_time_slots[i - 1] -1], self.instance.Ppev_chmax/self.instance.charge_eff_PEV)
            #2) subtract that power from the actual capacity to know the state of the battery at the instant t-1
            #NOTA: all the time slots between the two PEV charging designed slots have to be set to the same battery capacity
            Cpev[start_point + charge_time_slots[i-1]] = Cpev[start_point + charge_time_slots[i]] - Ppev[start_point + charge_time_slots[i-1]]/self.delta_t
            if Cpev[start_point + charge_time_slots[i-1]] > 0 and Cpev[start_point + charge_time_slots[i-1]] < self.instance.Cpev_thresh_low*self.instance.Cpev_max:
                n = start_point + charge_time_slots[i-1] #n is the time slot where the car stop working as power source and starts charging
                break
            Cpev[start_point + charge_time_slots[i-2] + 1 : start_point + charge_time_slots[i-1]] = Cpev[start_point + charge_time_slots[i-1]]
        
        return n




