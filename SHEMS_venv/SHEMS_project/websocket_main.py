import json

from pushNotification_server.websocket import SHEMSwebsocket

fp = open('./files/starting_configuration.json')
cfg = json.load(fp)
fp.close()
pushnotification_server = SHEMSwebsocket(cfg)