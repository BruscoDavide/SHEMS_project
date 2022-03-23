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
mydb = client['SHEMS_test']
mycol = mydb['mongoapp_todo']
myquery = {'name': 'davide'}
mydoc = mycol.find()
print(list(mydoc))