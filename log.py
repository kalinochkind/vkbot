import time


def write(log, s):
    f = open('logs/{}.log'.format(log), 'a')
    curtime = time.strftime("%d.%m.%Y %H:%M:%S", time.localtime())
    f.write('[{}] {}\n'.format(curtime, s))
    f.close()