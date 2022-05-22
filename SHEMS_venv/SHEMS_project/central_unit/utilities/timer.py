from threading import Timer

class perpetualTimer():
    def __init__(self,t,hFunction):
        """Recursiove perpetual timer

        Args:
            t (int): time interval between 2 callbakcs [s]
            hFunction (function): callback function
        """
        self.t=t
        self.hFunction = hFunction
        self.thread = Timer(self.t,self.handle_function)

    def handle_function(self):
        self.hFunction()
        self.thread = Timer(self.t, self.handle_function)
        self.thread.start()

    def start(self):
        self.thread.start()

    def cancel(self):
        self.thread.cancel()