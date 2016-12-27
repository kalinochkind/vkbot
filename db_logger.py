import threading
import time

import accounts
import args
import config

enabled = bool(args.args['database'])
if enabled:
    import MySQLdb
connected = False
conn = None
cur = None

db_lock = threading.RLock()

def _connect():
    global conn, cur, connected
    if not connected:
        conn = MySQLdb.connect(host=config.get('db_logger.host'), user=config.get('db_logger.username'), password=config.get('db_logger.password'),
                               database=config.get('db_logger.database'), charset='utf8mb4')
        cur = conn.cursor()
        connected = True

def log(message, kind, text_msg=None):
    global connected, enabled
    if enabled:
        if not config.get('db_logger.host') or not config.get('db_logger.database'):
            print('Incorrect database configuration!')
            enabled = False
            return
        with db_lock:
            try:
                _connect()
                if text_msg is None:
                    text_msg = message
                cur.execute('INSERT INTO vkbot_logmessage VALUES (NULL, %s, %s, NOW(), %s, %s)', (message, kind, text_msg, accounts.current_account))
                conn.commit()
            except MySQLdb.Error as e:
                print(e, flush=True)
                time.sleep(5)
                connected = False
                log(message, kind, text_msg)
