import codecs
import importlib
import logging
import os
import sys
import time

import accounts
import captcha
import config
import log
from args import args
from vkapi import VkApi

class MyHandler(logging.Handler):
    def emit(self, record):
        pass

    def handle(self, record):
        msg = record.getMessage()
        lvl = record.levelname
        if any(msg.lower().startswith(i) for i in ('red|', 'green|', 'yellow|')):
            color, msg = msg.split('|', maxsplit=1)
            log.info(msg, color.lower())
            return
        db_msg = getattr(record, 'db', None)
        if db_msg:
            msg = (msg, db_msg)
        if lvl == 'CRITICAL':
            log.error(msg, fatal=True)
        elif lvl == 'ERROR':
            log.error(msg, record.exc_info is not None)
        elif lvl == 'WARNING':
            log.warning(msg)
        elif lvl == 'INFO':
            log.info(msg)

logging.basicConfig(handlers=[MyHandler()], level=logging.INFO)
logging.getLogger('antigate').setLevel(logging.CRITICAL)
logging.getLogger('requests').setLevel(logging.CRITICAL)

os.environ['LC_ALL'] = 'ru_RU.utf-8'
sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())
sys.stdout.encoding = 'UTF-8'
login = config.get('login.login')
password = config.get('login.password')

def availableScripts():
    print('Available scripts:', ', '.join(sorted(i[:-3] for i in os.listdir('scripts') if i.endswith('.py') and not i.startswith('__'))))

if args['script'] is None:
    availableScripts()

if args['script']:
    if not args['script'].replace('_', '').isalpha():
        print('Invalid script')
        availableScripts()
        sys.exit()
    log.script_name = args['script'].lower()
    try:
        main = importlib.import_module('scripts.' + args['script'].lower()).main
    except ImportError:
        print('Invalid script')
        availableScripts()
        sys.exit()
    v = VkApi(login, password, timeout=config.get('vkbot_timing.default_timeout', 'i'), token_file=accounts.getFile('token.txt'),
              log_file=accounts.getFile('inf.log') if args['logging'] else '', captcha_handler=captcha.CaptchaHandler())
    v.initLongpoll()
    main(v, args['args'])
    v.sync()
    sys.exit()

import fcntl

pid_file = accounts.getFile('inf.pid')
lock_file = accounts.getFile('inf.lock')
fp = open(lock_file, 'w')
single = False
for attempt in range(100):
    try:
        fcntl.lockf(fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except IOError:
        time.sleep(5)
    else:
        single = True
        break
if not single:
    sys.exit(1)
with open(pid_file, 'w') as f:
    f.write(str(os.getpid()))

logging.info('Starting vkbot, pid ' + str(os.getpid()))
