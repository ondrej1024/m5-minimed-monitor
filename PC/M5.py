#################################################
#
# Wrapper classes for M5 libs
#
#################################################

import playsound # Needs GST binding (apt install python3-gst-1.0)

class Lcd:
    def setBrightness(val):
        pass

class Touch:
    def getX():
        return 0
    def getY():
        return 0

class Speaker:
    def begin():
        pass
    def setVolume(val):
        pass
    def playWavFile(sndfile):
        playsound.playsound(sndfile)

class Power:
    def isCharging():
        return False

def begin():
    pass

def update():
    pass
