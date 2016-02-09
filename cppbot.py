from subprocess import Popen, PIPE
import fcntl
import os


def nonBlockRead(output):
    fd = output.fileno()
    fl = fcntl.fcntl(fd, fcntl.F_GETFL)
    fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
    try:
        return output.read()
    except Exception:
        return b''

class cpp_bot:
    def __init__(self, filename):
        self.bot = Popen([filename], stdout=PIPE, stdin=PIPE, stderr=PIPE)

    def interact(self, msg):
        self.bot.stdin.write(msg.replace('\n', '\a').strip().encode() + b'\n')
        self.bot.stdin.flush()
        answer = self.bot.stdout.readline().rstrip().replace(b'\a', b'\n')
        info = nonBlockRead(self.bot.stderr)
        print(info.decode(), end='')
        return answer.decode().strip()
