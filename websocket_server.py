from bottle import default_app, get, template, debug
from bottle.ext.websocket import GeventWebSocketServer
from bottle.ext.websocket import websocket

from param import url_server, port_server

from bottle import get, run, template
from bottle.ext.websocket import GeventWebSocketServer
from bottle.ext.websocket import websocket

@get('/')
def index():
    return template('index')

@get('/websocket', apply=[websocket])
def echo(ws):
    while True:
        msg = ws.receive()
        if msg is not None:
            ws.send(msg)
        else: break

debug(True)
run(host=url_server, port=port_server, server=GeventWebSocketServer)
