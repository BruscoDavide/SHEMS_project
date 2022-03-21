"""
eliminabile o come esempio
"""

import pymongo as pm
import pprint
import json
from datetime import datetime
import numpy as np
import matplotlib
matplotlib.rcParams['text.usetex'] = True
import matplotlib.pyplot as plt
import math

#Connect ion to the MongoDB
client = pm.MongoClient ('localhost')
mydb = client['SHEMS_database']
mycol = mydb['first_configuration']
myquery = {'first_configuration'}
mydoc = mycol.find()
print(list(mydoc))