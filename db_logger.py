import csv
import os
import threading
import time

import accounts
import args
import config
import log as _log

MAX_TEXT_LENGTH = 1024
PG_QUERY = 'INSERT INTO vkbot_logmessage(message, kind, "time", message_text) VALUES (%s, %s, NOW(), %s)'

enabled = bool(args.args['database'])
conn = None
emergency = False

db_lock = threading.RLock()

def restoreRecords():
    for line in csv.reader(open(accounts.getFile('db_log.csv'))):
        conn.cursor().execute(PG_QUERY, line)
    conn.commit()
    os.remove(accounts.getFile('db_log.csv'))

def execute(attempt, params):
    import psycopg2
    global conn, enabled, emergency
    if conn is None and not emergency:
        if not config.get('db_logger.host') or not config.get('db_logger.database'):
            print('Incorrect database configuration!')
            enabled = False
            return
        try:
            conn = psycopg2.connect("dbname='{}' user='{}' host='{}' password='{}'".format(config.get('db_logger.database'),
                                                                                           config.get('db_logger.username'),
                                                                                           config.get('db_logger.host'),
                                                                                           config.get('db_logger.password')))
        except psycopg2.OperationalError as e:
            print(e, flush=True)
            _log.write('error', 'PostgreSQL connection error: ' + str(e))
            conn = None
        else:
            if os.path.isfile(accounts.getFile('db_log.csv')):
                try:
                    restoreRecords()
                except psycopg2.Error:
                    if attempt < 5:
                        return execute(attempt + 1, params)
                    else:
                        emergency = True

    if emergency or attempt >= 5:
        emergency = True
        with open(accounts.getFile('db_log.csv'), 'a') as f:
            csv.writer(f).writerow(params)
        return True
    else:
        if conn is None:
            return False
        try:
            conn.cursor().execute(PG_QUERY, params)
            conn.commit()
        except psycopg2.Error as e:
            print(e, flush=True)
            _log.write('error', 'PostgreSQL error: ' + str(e))
            conn = None
            return False
        else:
            return True


def log(message, kind, text_msg=None, *, attempt=0):
    global enabled, conn
    if not enabled:
        return
    if attempt == 0:
        if text_msg is None:
            text_msg = message
        text_msg = text_msg[:MAX_TEXT_LENGTH]
        message = message.replace('\\', '\\\\')

    with db_lock:
        if not execute(attempt, (message, kind, text_msg)):
            time.sleep(3)
            log(message, kind, text_msg, attempt=attempt+1)
