import html
import logging
import os
import threading
import time
from subprocess import Popen, PIPE

logger = logging.getLogger('cppbot')
bot_logger = logging.getLogger('chatlog')

def nonBlockRead(output):
    import fcntl
    fd = output.fileno()
    fl = fcntl.fcntl(fd, fcntl.F_GETFL)
    fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
    try:
        return output.readline()
    except Exception:
        return b''

class CppBot:
    source_files = ['Analyzer.cpp', 'ChatBot.cpp', 'main.cpp', 'ChatBot.h', 'build.sh']
    exe_name = 'chat.exe'
    path = 'chat/'
    data_path = 'data/'
    data_files = ['bot.txt', 'blacklist.txt', 'fixedstem.txt', 'names.txt', 'noans.txt', 'smiles.txt']

    def __init__(self, name, max_smiles, dump_filename):
        try:
            exe_time = os.path.getmtime(self.path + self.exe_name)
            src_time = max(os.path.getmtime(self.path + i) for i in self.source_files)
            if src_time > exe_time:
                self.buildExe()
        except FileNotFoundError:
            self.buildExe()
        self.name = name
        self.max_smiles = max_smiles
        self.start_time = time.time()
        self.bot = None
        self.runExe()
        self.bot_lock = threading.Lock()
        self.dump_filename = dump_filename
        self.load()

    def runExe(self):
        self.bot = Popen([self.path + self.exe_name, str(self.max_smiles), str(self.name)], stdout=PIPE, stdin=PIPE, stderr=PIPE)

    def interact(self, msg, do_log=True):
        try:
            with self.bot_lock:
                self.bot.stdin.write(msg.replace('\n', '\a').strip().encode() + b'\n')
                self.bot.stdin.flush()
                answer = self.bot.stdout.readline().rstrip().replace(b'\a', b'\n')
                while True:
                    info = nonBlockRead(self.bot.stderr)
                    if not info:
                        break
                    info = info.decode().rstrip().replace('\x07', ' ')
                    if do_log:
                        bot_logger.info(info, extra={'db': html.escape(info)})
        except BrokenPipeError:
            logger.warning('Broken pipe, restarting ' + self.exe_name)
            self.runExe()
            return self.interact(msg, do_log)
        return answer.decode().strip()

    def buildExe(self):
        logger.info('Rebuilding ' + self.exe_name)
        if os.system(self.path + 'build.sh'):
            logger.critical('Unable to build')
        logger.info('Build successful')

    def reload(self):
        self.start_time = time.time()
        self.interact('reld')
        logger.info('Reloaded!')

    def dataTime(self):
        return max(os.path.getmtime(self.data_path + i) for i in self.data_files)

    def reloadIfChanged(self):
        data_time = self.dataTime()
        if data_time > self.start_time and time.time() > data_time + 5:
            self.reload()

    def dump(self):
        if not self.dump_filename:
            return
        data = self.interact('dump')
        data = str(int(self.start_time)) + '\n' + data
        with open(self.dump_filename, 'w') as f:
            f.write(data)

    def load(self):
        if not self.dump_filename:
            return
        if not os.path.isfile(self.dump_filename):
            logging.info('Chat dump does not exist')
            return
        data = open(self.dump_filename).read().splitlines()
        if len(data) < 2:
            return
        modtime = int(data[0])
        if modtime < self.dataTime():
            logging.info('Chat database has been modified')
        else:
            self.interact('load ' + data[1])
        os.remove(self.dump_filename)

    @staticmethod
    def escape(message):
        message = message.replace('\u0401', '\u0415').replace('\u0451', '\u0435')  # yo
        message = message.replace('\u0490', '\u0413').replace('\u0491', '\u0433')  # g
        message = message.replace('\u0404', '\u042d').replace('\u0454', '\u044d')  # e
        message = message.replace('\u0406', '\u0418').replace('\u0456', '\u0438')  # i
        message = message.replace('\u0407', '\u0418').replace('\u0457', '\u0438')  # i
        message = message.replace("`", "'")
        message = message.replace('{', '\u200b{\u200b').replace('}', '\u200b}\u200b')  # zero width spaces
        return message
