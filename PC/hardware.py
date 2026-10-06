import threading
import time

#################################################
#
# Wrapper classes for hardware lib
#
#################################################

class Timer:
    PERIODIC = 1
    ONE_SHOT = 2
    def __init__(self,timer):
        self.timer = timer
    def __periodic_timer(self, func, period):
        print("start periodic_timer %d with %d s" %(self.timer,period))
        while True:
            time.sleep(period)
            func(self.timer)
    def init(self, mode, period, callback):
        if mode == self.ONE_SHOT:
            t = threading.Timer(period/1000, callback)
            t.daemon = True
            t.start()
        elif mode == self.PERIODIC:
            t = threading.Thread(target=self.__periodic_timer, args=(callback,period/1000))
            t.daemon = True
            t.start()
