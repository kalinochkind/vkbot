from subprocess import Popen, PIPE
import fcntl
import os
import logging
import threading
import config


def nonBlockRead(output):
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
    max_smiles = config.get('cppbot.max_smiles', 'i')

    def __init__(self):
        try:
            exe_time = os.path.getmtime(self.path + self.exe_name)
            src_time = max(os.path.getmtime(self.path + i) for i in self.source_files)
            if src_time > exe_time:
                self.buildExe()
        except FileNotFoundError:
            self.buildExe()
        self.runExe()
        self.bot_lock = threading.Lock()

    def runExe(self):
        self.bot = Popen([self.path + self.exe_name, str(self.max_smiles)], stdout=PIPE, stdin=PIPE, stderr=PIPE)

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
                    info = info.decode().rstrip()
                    if do_log:
                        logging.info(info)
        except BrokenPipeError:
            logging.error('Broken pipe, restarting ' + self.exe_name)
            self.runExe()
            return self.interact(msg, do_log)
        return answer.decode().strip()

    def buildExe(self):
        logging.info('Rebuilding ' + self.exe_name)
        if os.system(self.path + 'build.sh'):
            logging.critical('Unable to build')
        logging.info('Build successful')
