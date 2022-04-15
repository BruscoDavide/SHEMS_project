import json
import time as t
import numpy as np

from LP_solver.SHEMS_smart_batt_functions_callable import SHEMS
from Simulator.instance import Instance

if __name__ == "__main__":
    solver_inst = Instance()
    solver_inst.get_data_no_serv()
    shems = SHEMS(solver_inst)
    
    trial_flag = 1

    start = t.time()
    #CALLABLE DEFINITIVE TRIALS
    if trial_flag == 0:
        obj = shems.solve_definitive() #working
        shems.set_working_mode(payload= {"command":7} )
        obj = shems.solve_definitive()

    #CAR ARRIVAL TESTES
    elif trial_flag == 1:
        obj = shems.solve_definitive() #working
        shems.set_car_arrival()
        shems.set_car_leave()
    stop = t.time()
    solving_time = stop - start
    print(obj)
    print(solving_time)