
import sounddevice as sd

class Player:
    def __init__(self):
        pass

    def play(self, array, sr, viewBox=None):
         sd.play(array, sr)
         status = sd.wait()

player = Player()
