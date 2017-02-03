import threading
import time

import args
import config
import log as _log

MAX_TEXT_LENGTH = 1024

enabled = bool(args.args['database'])
conn = None

db_lock = threading.RLock()

def log(message, kind, text_msg=None):
    global enabled, conn
    if not enabled:
        return
    if text_msg is None:
        text_msg = message
    text_msg = text_msg[:MAX_TEXT_LENGTH]
    message = message.replace('\\', '\\\\')

    with db_lock:
        import psycopg2
        if conn is None:
            if not config.get('db_logger.host') or not config.get('db_logger.database'):
                print('Incorrect database configuration!')
                enabled = False
                return
            conn = psycopg2.connect("dbname='{}' user='{}' host='{}' password='{}'".format(config.get('db_logger.database'),
                                    config.get('db_logger.username'), config.get('db_logger.host'), config.get('db_logger.password')))
        try:
            conn.cursor().execute('INSERT INTO vkbot_logmessage(message, kind, "time", message_text) VALUES (%s, %s, NOW(), %s)',
                                  (message, kind, text_msg))
            conn.commit()
        except psycopg2.Error as e:
            print(e, flush=True)
            _log.write('error', 'PostgreSQL error: ' + str(e))
            conn = None
            time.sleep(5)
            log(message, kind, text_msg)
