import time
import config
import traceback

datetime_format = config.get('log.datetime_format')


def write(log, s):
    curtime = time.strftime(datetime_format, time.localtime())
    with open('logs/{}.log'.format(log), 'a') as f:
        f.write('[{}] {}\n'.format(curtime, s))

def warning(s):
    print('[WARNING]', s)

def error(s, need_exc_info=False):
    print('[ERROR]', s)
    write('error', s)
    if need_exc_info:
        with open('logs/error.log', 'a') as f:
            traceback.print_exc(file=f)
