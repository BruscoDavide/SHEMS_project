# Importing the relevant libraries
from email import message
import logging

import websockets
import asyncio

class websocket_server():
    def __init__(self, port, host):
        self.port = port
        self.host = host
        self.payload = ''

    def action(self, a, payload = None):
        """_summary_

        Args:
            a (_type_): _description_
            payload (_type_, optional): _description_. Defaults to None.
        """
        if a == 'echo':
            start_server = websockets.serve(self.__echo(), self.host, self.port)
            asyncio.get_event_loop().run_until_complete(start_server)
            asyncio.get_event_loop().run_forever()
        elif a == 'send':
            self.payload = payload
            start_server = websockets.serve(self.__send(), self.host, self.port)
            asyncio.get_event_loop().run_until_complete(start_server)
        else:
            logging.info('Action wrong')  

    async def __echo(self, websocket, path):
        logging.info('A client just connected to websocket server')
        try:
            async for message in websocket:
                logging.info(f'Received message from client: {message}')

                # ho ricevuto un messaggio dal client cosa devo fare??????
                
                await websocket.send("Pong: " + message)
        except websockets.exceptions.ConnectionClosed as e:
            logging.info('A client just disconnected from websocket server')

    async def __send(self, websocket, path):
        logging.info('A client just connected to websocket server')
        try:
            await websocket.send(self.payload)
        except websockets.exceptions.ConnectionClosed as e:
            logging.info('A client just disconnected from websocket server')

class websocket_client():
    def __init__(self, port, host):
        self.port = port
        self.host = host
        self.url = f'ws://{self.host}:{self.port}'
        self.payload = ''

    def action(self, a, payload=None):
        """_summary_

        Args:
            a (_type_): _description_
            payload (_type_, optional): _description_. Defaults to None.
        """
        # Start the connection
        if a == 'recv':
            asyncio.get_event_loop().run_until_complete(self.__recv(flag=False, payload=None))   
        elif a == 'send':
            self.payload = payload
            asyncio.get_event_loop().run_until_complete(self.__send(flag=False))  
        else:
            logging.info('Action wrong')  
        
    async def __send(self, flag): # flag serve se si vuole lasciare il client in attesa di un feedback tipo handshake
        # Connect to the server
        async with websockets.connect(self.url) as ws:
            await ws.send(message)
            msg = ''
            while flag:
                msg = await ws.recv()
                if msg != '':
                    logging.info(msg)
                    flag = False

    async def __recv(self, flag, payload): # flag server se si vuole far inviare un message tipo handshke
        async with websockets.connect(self.url) as ws:
            f = True
            msg = ''
            while f:
                msg = await ws.recv()
                if msg != '':
                    logging.info(msg)
                    f = False
                    if flag:
                        await ws.send(payload)


