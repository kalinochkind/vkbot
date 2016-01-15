import threading
import time


class thread_manager:  # not thread-safe, should be used only from main thread
    def __init__(self):
        self.threads = {}

    def run(self, key, proc):
        t = threading.Thread(target=proc)
        self.threads[key] = t
        t.start()

    def isBusy(self, key):
        return key in self.threads and self.threads[key].is_alive()

    def gc(self):
        to_del = []
        for i in self.threads:
            if not self.threads[i].is_alive():
                to_del.append(i)
        for i in to_del:
            del self.threads[i]


class timeline:

    def __init__(self, duration=0):
        self.events = []
        self.duration = duration
        self.endtime = 0

    def do(self, func):
        self.events.append(func)
        return self

    def sleep(self, seconds):
        return self.do(lambda: time.sleep(seconds))

    def sleep_until(self, seconds=0):
        def _f():
            rem = self.endtime - time.time() - seconds
            if rem > 0:
                time.sleep(rem)
        return self.do(_f)

    def do_every(self, interval, func, end_func, do_at_start=True):
        if do_at_start:
            self.do(func)
        def _f():
            end = end_func()
            while time.time() + interval < end:
                time.sleep(interval)
                func()
            time.sleep(max(0, end - time.time()))
        return self.do(_f)

    def do_every_until(self, interval, func, seconds=0, do_at_start=True):
        return self.do_every(interval, func, lambda:self.endtime - seconds, do_at_start)

    def do_every_for(self, interval, func, seconds, do_at_start=True):
        return self.do_every(interval, func, lambda:time.time() + seconds, do_at_start)

    def __call__(self):
        self.endtime = time.time() + self.duration
        for func in self.events:
            func()
