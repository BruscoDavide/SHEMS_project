"use strict";


// Importing the required modules
const WebSocketServer = require('ws');

// Creating a new websocket server
const wss = new WebSocketServer.Server({ host:"0.0.0.0", port: 52268 })
 
// Creating connection using websocket
wss.on("connection", ws => {

    
    var payload = require('./files/starting_configuration.json');
    ws.send(String(payload));
    //clear file ora mi stampa [object Object]

    console.log("new client connected");
    // sending message
    ws.on("message", data => {
        console.log(`Client has sent us: ${data}`)
    });
    // handling what to do when clients disconnects from server
    ws.on("close", () => {
        console.log("the client has connected");
    });
    // handling client connection error
    ws.onerror = function () {
        console.log("Some Error occurred")
    }
});
console.log("The WebSocket server is running on port 52268");