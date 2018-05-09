import asyncio
import logging
import threading
import time

logger = logging.getLogger('tm')


class ThreadManager:  # not thread-safe, should be used only from main thread
    def __init__(self):
        self.timelines = {}
        self.loop = asyncio.new_event_loop()
        self.loop_thread = threading.Thread(target=self.loop.run_forever, daemon=True)
        self.loop_thread.start()

    def run(self, key, timeline):
        if self.isBusy(key):
            self.terminate(key)
        self.timelines[key] = timeline
        timeline.future = asyncio.run_coroutine_threadsafe(timeline.run(), self.loop)

    def isBusy(self, key):
        return key in self.timelines and not self.timelines[key].future.done()

    def terminate(self, key):
        if key not in self.timelines:
            return False
        self.timelines[key].terminated = True
        return True

    def gc(self):
        to_del = []
        for i in self.timelines:
            if self.timelines[i].future.done():
                to_del.append(i)
        for i in to_del:
            del self.timelines[i]

    def shutdown(self, timeout):
        started = time.time()
        while time.time() - started < timeout:
            for task in asyncio.Task.all_tasks(self.loop):
                if not task.done():
                    break
            else:
                return True
            time.sleep(5)
        return False

    def get(self, key):
        return self.timelines.get(key)


class Timeline:
    def __init__(self, duration=0):
        self.events = []
        self.attr = {}
        self.duration = duration
        self.endtime = 0
        self.terminated = False
        self.is_alive = True

    def do(self, func, need_attr=False):
        async def _f():
            if need_attr:
                func(self.attr)
            else:
                func()
        self.events.append(_f)
        return self

    def sleep(self, seconds):
        async def _f():
            await asyncio.sleep(seconds)
        self.events.append(_f)
        return self

    def sleepUntil(self, seconds, min_sleep=0):
        async def _f():
            rem = max(self.endtime - time.time() - seconds, min_sleep)
            if rem > 0:
                await asyncio.sleep(rem)
        self.events.append(_f)
        return self

    def doEvery(self, interval, func, end_func, do_at_start=True, need_attr=False):
        if do_at_start:
            self.do(func, need_attr)

        async def _f():
            end = end_func()
            while time.time() + interval < end:
                await asyncio.sleep(interval)
                if self.terminated:
                    return
                if need_attr:
                    func(self.attr)
                else:
                    func()
            await asyncio.sleep(max(0, end - time.time()))

        self.events.append(_f)
        return self

    def doEveryUntil(self, interval, func, seconds=0, do_at_start=True, need_attr=False):
        return self.doEvery(interval, func, lambda: self.endtime - seconds, do_at_start, need_attr)

    def doEveryFor(self, interval, func, seconds, do_at_start=True, need_attr=False):
        return self.doEvery(interval, func, lambda: time.time() + seconds, do_at_start, need_attr)

    async def run(self):
        self.endtime = time.time() + self.duration
        for coro in self.events:
            if self.terminated:
                return
            await coro()
