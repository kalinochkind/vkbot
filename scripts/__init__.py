import importlib
import json
import logging
import socket

import log
import config


def runScript(name, args, api):
    log.local.script_name = name
    try:
        script = importlib.import_module('scripts.' + name)
        importlib.reload(script)
        script.main(api, args)
    finally:
        del log.local.script_name



def runInMaster(name, args):
    try:
        message = ('runscript|' + json.dumps({'name': name, 'args': args})).encode('utf-8')
        port = config.get('server.port', 'i')
        if port <= 0:
            return False
        sock = socket.socket()
        sock.connect(('127.0.0.1', port))
        sock.send(message)
        sock.settimeout(5)
        res = sock.recv(8)
        sock.close()
        return res == b'ok'
    except Exception as e:
        logging.info(e)
        return False
