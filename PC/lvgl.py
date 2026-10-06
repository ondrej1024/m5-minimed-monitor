#################################################
#
# Wrapper classes for LVGL libs
#
#################################################

# Font mappings
font_montserrat_14 = 'Helvetica 10'
font_montserrat_16 = 'Helvetica 12'
font_montserrat_20 = 'Helvetica 12'
font_montserrat_24 = 'Helvetica 18'
font_montserrat_26 = 'Helvetica 18'
font_montserrat_28 = 'Helvetica 20'
font_montserrat_48 = 'Helvetica 44'

class Event:
    ALL     = 0
    PRESSED = 1
    CLICKED = 2

class Align:
    TOP_RIGHT  = 0
    CENTER     = 1
    BOTTOM_MID = 2

class Part:
    MAIN=0

class State:
    DEFAULT = 0

class Flag:
    HIDDEN = 0

class Object:
    FLAG = Flag

EVENT = Event
ALIGN = Align
PART  = Part
STATE = State

obj   = Object

def color_hex(color):
    # TODO
    return color
