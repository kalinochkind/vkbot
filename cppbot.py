from subprocess import Popen, PIPE
import fcntl
import os
import log


def nonBlockRead(output):
    fd = output.fileno()
    fl = fcntl.fcntl(fd, fcntl.F_GETFL)
    fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
    try:
        return output.readline()
    except Exception:
        return b''

class cpp_bot:

    source_files = ['Analyzer.cpp', 'ChatBot.cpp', 'main.cpp', 'ChatBot.h']
    exe_name = 'chat.exe'

    def __init__(self):
        try:
            exe_time = os.path.getmtime(self.exe_name)
            src_time = max(os.path.getmtime(i) for i in self.source_files)
            if src_time > exe_time:
                self.build_exe()
        except FileNotFoundError:
            self.build_exe()
        self.bot = Popen('./' + self.exe_name, stdout=PIPE, stdin=PIPE, stderr=PIPE)

    def interact(self, msg):
        self.bot.stdin.write(msg.replace('\n', '\a').strip().encode() + b'\n')
        self.bot.stdin.flush()
        answer = self.bot.stdout.readline().rstrip().replace(b'\a', b'\n')
        while True:
            info = nonBlockRead(self.bot.stderr)
            if not info:
                break
            info = info.decode().rstrip().split('|', maxsplit=1)
            log.info(info[1], info[0])
        return answer.decode().strip()

    def build_exe(self):
        log.info('Rebuilding ' + self.exe_name)
        if os.system('./build.sh'):
            log.fatal('Unable to build')
        log.info('Build successful')
