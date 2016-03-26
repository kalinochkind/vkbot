import config
import threading
import args

enabled = bool(args.args['database'])
connected = False

db_lock = threading.Lock()


def log(message, kind):
    if enabled:
        with db_lock:
            import mysql.connector
            global conn, cur, connected
            if not connected:
                conn = mysql.connector.connect(host=config.get('db_logger.host'), user=config.get('db_logger.username'), password=config.get('db_logger.password'), database=config.get('db_logger.database'))
                cur = conn.cursor()
                connected = True
            cur.execute('INSERT INTO vkbot_logmessage VALUES (NULL, %s, %s, NOW())', (message, kind))
            conn.commit()
