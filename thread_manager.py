import threading
import time
import log

class ThreadManager:  # not thread-safe, should be used only from main thread
    def __init__(self):
        self.threads = {}

    def run(self, key, proc, terminate_func=None):
        if self.isBusy(key):
            if self.canTerminate(key):
                self.terminate(key)
            else:
                log.error('Unable to run a new thread with key ' + str(key))
                return
        t = threading.Thread(target=proc)
        t.terminate_func = terminate_func
        self.threads[key] = t
        t.start()

    def isBusy(self, key):
        return key in self.threads and self.threads[key].is_alive()

    def terminate(self, key):
        try:
            self.threads[key].terminate_func()
        except TypeError:
            pass

    def canTerminate(self, key):
        return key in self.threads and self.threads[key].terminate_func is not None

    def gc(self):
        to_del = []
        for i in self.threads:
            if not self.threads[i].is_alive():
                to_del.append(i)
        for i in to_del:
            del self.threads[i]

    def all(self):
        return list(self.threads.values())


class Timeline:

    def __init__(self, duration=0):
        self.events = []
        self.duration = duration
        self.endtime = 0
        self.terminated = False

    def do(self, func):
        self.events.append(func)
        return self

    def sleep(self, seconds):
        return self.do(lambda: time.sleep(seconds))

    def sleepUntil(self, seconds, min_sleep=0):
        def _f():
            rem = max(self.endtime - time.time() - seconds, min_sleep)
            if rem > 0:
                time.sleep(rem)
        return self.do(_f)

    def doEvery(self, interval, func, end_func, do_at_start=True):
        if do_at_start:
            self.do(func)
        def _f():
            end = end_func()
            while time.time() + interval < end:
                time.sleep(interval)
                if self.terminated:
                    return
                func()
            time.sleep(max(0, end - time.time()))
        return self.do(_f)

    def doEveryUntil(self, interval, func, seconds=0, do_at_start=True):
        return self.doEvery(interval, func, lambda:self.endtime - seconds, do_at_start)

    def doEveryFor(self, interval, func, seconds, do_at_start=True):
        return self.doEvery(interval, func, lambda:time.time() + seconds, do_at_start)

    def terminate():
        self.terminated = True

    def __call__(self):
        self.endtime = time.time() + self.duration
        for func in self.events:
            if self.terminated:
                return
            func()
