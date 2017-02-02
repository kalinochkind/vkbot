import threading
import time

import accounts
import args
import config
import log as _log

MAX_TEXT_LENGTH = 1024

enabled = bool(args.args['database'])
engine = None
connected = False
conn = None
cur = None

db_lock = threading.RLock()

def _connect():
    global conn, cur, connected, enabled
    if engine == 'mysql':
        import MySQLdb
    elif engine == 'postgresql':
        import psycopg2
    if not connected:
        if engine == 'mysql':
            conn = MySQLdb.connect(host=config.get('db_logger.host'), user=config.get('db_logger.username'),
                                   password=config.get('db_logger.password'), database=config.get('db_logger.database'), charset='utf8mb4')
        else:
            conn = psycopg2.connect("dbname='{}' user='{}' host='{}' password='{}'".format(config.get('db_logger.database'),
                                    config.get('db_logger.username'), config.get('db_logger.host'), config.get('db_logger.password')))
        cur = conn.cursor()
        connected = True

def log(message, kind, text_msg=None):
    global connected, enabled, engine
    if enabled:
        engine = config.get('db_logger.engine')
    if enabled:
        if not config.get('db_logger.host') or not config.get('db_logger.database'):
            print('Incorrect database configuration!')
            enabled = False
            return
        if text_msg is None:
            text_msg = message
        text_msg = text_msg[:MAX_TEXT_LENGTH]
        with db_lock:
            if engine == 'mysql':
                import MySQLdb
                try:
                    _connect()
                    cur.execute('INSERT INTO vkbot_logmessage VALUES (NULL, %s, %s, NOW(), %s, %s)',
                                (message, kind, text_msg, accounts.current_account))
                    conn.commit()
                except MySQLdb.Error as e:
                    print(e, flush=True)
                    _log.write('error', 'MySQL error: ' + str(e))
                    time.sleep(5)
                    connected = False
                    log(message, kind, text_msg)
            elif engine == 'postgresql':
                import psycopg2
                try:
                    message = message.replace('\\', '\\\\')
                    _connect()
                    cur.execute('INSERT INTO vkbot_logmessage(message, kind, "time", message_text) VALUES (%s, %s, NOW(), %s)', (message, kind, text_msg))
                    conn.commit()
                except psycopg2.Error as e:
                    print(e, flush=True)
                    _log.write('error', 'PostgreSQL error: ' + str(e))
                    time.sleep(5)
                    connected = False
                    log(message, kind, text_msg)
            else:
                print('Unknown database engine')
                enabled = False
                return
