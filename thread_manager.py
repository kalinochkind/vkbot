import threading
import time

    
class thread_manager:  # not thread-safe, should be used only from main thread
    def __init__(self):
        self.threads = {}
   
    def run(self, key, proc, delay=0):
        if delay:
            def _delay(proc, delay):
                def _f():
                    time.sleep(delay)
                    proc()
                return _f 
            proc = _delay(proc, delay)
        t = threading.Thread(target=proc)
        self.threads[key] = t
        t.start()
        
    def isBusy(self, key):
        return key in self.threads and self.threads[key].is_alive()