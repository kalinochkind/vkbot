import mysql.connector
import config

enabled = True

conn = mysql.connector.connect(host=config.get('db_logger.host'), user=config.get('db_logger.username'), password=config.get('db_logger.password'), database=config.get('db_logger.database'))
cur = conn.cursor()

def log(message, kind):
    if enabled:
        cur.execute('INSERT INTO vkbot_logmessage VALUES (NULL, %s, %s, NOW())', (message, kind))
        conn.commit()
