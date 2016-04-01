import socket
import threading
import log

class MessageServer:

    port = 55555

    def __init__(self):
        self.handlers = {}

    def addHandler(self, type, proc):
        self.handlers[type] = proc

    def _listen(self):
        sock = socket.socket()
        sock.bind(('127.0.0.1', self.port))
        sock.listen(16)
        while True:
            conn, addr = sock.accept()
            data = conn.recv(65536).decode('utf-8')  # message format: type|text
            if not data:
                continue
            if '|' in data:
                data = data.split('|', maxsplit=1)
            else:
                data = [data, None]
            if data[0] not in self.handlers:
                continue
            try:
                res = self.handlers[data[0]](data[1])
                conn.send(res.encode('utf-8'))
            except Exception:
                log.error('MessageServer error', True)
                conn.send(b'error')

    def listen(self):
        t = threading.Thread(target=self._listen)
        t.daemon = True
        t.start()
