import threading

class RWLock:
    def __init__(self):
        self._cond = threading.Condition()
        self._lectores = 0

    def acquire_read(self):
        with self._cond:
            self._lectores += 1

    def release_read(self):
        with self._cond:
            self._lectores -= 1
            if self._lectores == 0:
                self._cond.notifyAll()

    def acquire_write(self):
        self._cond.acquire()
        while self._lectores > 0:
            self._cond.wait()

    def release_write(self):
        self._cond.release()

class Jugador:
    def __init__(self, nickname, x=0, y=0):
        self.nickname = nickname
        self.x = x
        self.y = y
        self.estado = 'IDLE'