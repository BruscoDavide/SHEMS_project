import datetime 
import math

act_time = [] 
for i in range(3):
    act_time.append(str(str(datetime.datetime.now()).split(' ')[1].split(':')[i]))
print(act_time)


if act_time[0] == '00' or act_time[0] < 8:
    act_mins = 16*60 #hours passed from 8 to midnight
    act_mins += int(act_time[0])
    act_mins += int(act_time[1])
else:
    act_mins = (int(act_time[0]) - 8)*60
    act_mins += int(act_time[1])
step = math.ceil(act_mins/15) - 1

print(step)