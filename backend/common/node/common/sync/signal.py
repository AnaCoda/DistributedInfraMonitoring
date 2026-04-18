from threading import Event

class HoldSignal:

    def __init__(self):
        self.state = False
        self.evt = Event()

    def barrier(self):
        while not self.state:
            self.evt.wait()

    def hold(self):
        self.state = False
    
    def ready(self):
        self.state = True
        self.evt.set()