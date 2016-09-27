import time
import traceback
import db_logger
import sys
import threading
import os
import accounts

err_lock = threading.Lock()
log_lock = threading.Lock()
script_name = None


# s = (console message, db message)
def info(s, color=''):
    if isinstance(s, str):
        s = (s, s)
    s = (s[0].replace('`{', '').replace('}`', ''), s[1])
    with log_lock:
        if color == 'red':
            print('\033[38;5;9m' + s[0] + '\033[0m')
        elif color == 'green':
            print('\033[38;5;10m' + s[0] + '\033[0m')
        elif color == 'yellow':
            print('\033[38;5;11m' + s[0] + '\033[0m')
        elif color:
            print('[{}] {}'.format(color.upper(), s[0]))
        else:
            print(s[0])
        if color:
            s = ('[' + color.upper() + ']' + s[0], s[1])
        db_logger.log(s[1], color, text_msg=s[0])
        sys.stdout.flush()


def warning(s):
    info(s, 'warning')


def error(s, need_exc_info=False, fatal=False):
    info(s, 'fatal' if fatal else 'error')
    if not isinstance(s, str):
        s = s[0]
    with err_lock:
        if fatal:
            s = 'Fatal: ' + s
        write('error', s)
        if need_exc_info:
            with open(logdir + 'error.log', 'a', encoding='utf-8') as f:
                traceback.print_exc(file=f)
                print(file=f)
    if fatal:
        os._exit(1)  # it can be called from any thread


datetime_format = '%d.%m.%Y %H:%M:%S'

logdir = 'accounts/{}/logs/'.format(accounts.current_account)
if not os.path.isdir(logdir):
    os.mkdir(logdir)


def write(log, s):
    curtime = time.strftime(datetime_format, time.localtime())
    # if the name starts with _, it must be a special script log
    if script_name and not log.startswith('_'):
        s = '({}) {}'.format(script_name, s)
    with open(logdir + log + '.log', 'a', encoding='utf-8') as f:
        f.write('[{}] {}\n'.format(curtime, s))
