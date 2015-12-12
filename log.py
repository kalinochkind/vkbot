import time
import config

datetime_format = config.get('log.datetime_format')


def write(log, s):
    f = open('logs/{}.log'.format(log), 'a')
    curtime = time.strftime(datetime_format, time.localtime())
    f.write('[{}] {}\n'.format(curtime, s))
    f.close()