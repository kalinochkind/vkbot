import config
import threading
import args

enabled = bool(args.args['database'])
connected = False
conn = None
cur = None

db_lock = threading.Lock()


def log(message, kind, text_msg=None):
    if enabled:
        with db_lock:
            import mysql.connector
            global conn, cur, connected
            if not connected:
                conn = mysql.connector.connect(host=config.get('db_logger.host'), user=config.get('db_logger.username'), password=config.get('db_logger.password'),
                                               database=config.get('db_logger.database'))
                cur = conn.cursor()
                connected = True
            if text_msg is None:
                text_msg = message
            cur.execute('INSERT INTO vkbot_logmessage VALUES (NULL, %s, %s, NOW(), %s)', (message, kind, text_msg))
            conn.commit()
