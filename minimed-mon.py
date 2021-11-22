###############################################################################
#  
#  M5Stack Minimed Monitor
#  
#  Description:
#
#  This is an application for the M5Stack Core2 device. It implements a remote
#  monitor for the Medtronic Minimed 770G/780G insulin pump system to be used  
#  by caregivers of Type-1 Diabetes patients wearing the pump.
#
#  Dependencies:
#
#  At this stage, the M5Stack Minimed Monitor relies on an external instance
#  of the Carelink Python Client to provide the Pump data downloaded from the 
#  Carelink Cloud.
#
#  Carelink Python Client
#  https://github.com/ondrej1024/carelink-python-client
#
#  Author:
#
#    Ondrej Wisniewski (ondrej.wisniewski *at* gmail.com)
#  
#  Changelog:
#
#    28/06/2021 - Initial public release
#    20/11/2021 - Handle DST (quick'n'dirty)
#    21/11/2021 - Handle alarm notifications
#
#  TODO:
#
#  * Configuration via config file on SD card or Wifi AP
#  * Integration of Carelink Client
#  * History graph for recent glucose data
#  * Extensive error handling
#
#  Copyright 2021, Ondrej Wisniewski 
#  
#  
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
# 
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
# 
#  You should have received a copy of the GNU General Public License
#  along with crelay.  If not, see <http://www.gnu.org/licenses/>.
#  
###############################################################################

from m5stack import *
from m5stack_ui import *
from uiflow import *
import wifiCfg
import ntptime
import time
import urequests

VERSION = "0.2"

# Configuration parameters
# TODO: read from file

### Replace below with your personal configuration ###

PROXY_SERVER = "0.0.0.0" # The IP address where the carelink_client_proxy is running
PROXY_PORT   = 8081      # The port where the carelink_client_proxy is listening

NTP_SERVER   = 'pool.ntp.org' # A public NTP server
MY_TIMEZONE  = 1              # Time difference from GMT for your location

WIFI_SSID    = 'MY_SSID' # My Wifi SSID
WIFI_PASS    = 'MY_PASS' # My Wifi password

################# End of configuration ###############

PROXY_URL    = "http://"+PROXY_SERVER+":"+str(PROXY_PORT)+"/carelink/nohistory"
dstDelta    = 0

# Gobal variables
lastUpdateTm = time.localtime(0)
lastAlarmId  = 0
lastAlarmMsg = None
runNtpsync        = False
runTimeupdate     = False
runPumpdataupdate = False

# Init screen
screen = M5Screen()
screen.clean_screen()
screen.set_screen_bg_color(0x000000)
screen.set_screen_brightness(40)

# Create screen 1
scr1 = None

# Load images on screen 1
imageBattery     = M5Img("res/mm_batt_unk.png", x=6, y=0, parent=scr1)
imageReservoir   = M5Img("res/mm_tank_unk.png", x=40, y=0, parent=scr1)
imageSensorConn  = M5Img("res/mm_sensor_connection_ok.png", x=68, y=0, parent=scr1)
imageDrop        = M5Img("res/mm_drop_unk.png", x=105, y=8, parent=scr1)
#imageDrop        = M5Img("res/mm_drop_red.png", x=100, y=0, parent=scr1)
imageShield      = M5Img("res/mm_shield_none.png", x=65, y=33, parent=scr1)

# Init labels on screen 1
labelBglValue    = M5Label('--', x=140, y=90, color=0xffffff, font=FONT_MONT_48, parent=scr1)
labelBglUnit     = M5Label('mg/dL', x=137, y=145, color=0x89abeb, font=FONT_MONT_16, parent=scr1)
labelActInsValue = M5Label('-- U', x=261, y=173, color=0xffffff, font=FONT_MONT_26, parent=scr1)
labelActIns      = M5Label('Act Insulin', x=231, y=200, color=0xffffff, font=FONT_MONT_16, parent=scr1)
labelTime        = M5Label('--:--', x=250, y=0, color=0xffffff, font=FONT_MONT_28, parent=scr1)
labelLastData    = M5Label('--', x=120, y=218, color=0xffffff, font=FONT_MONT_20, parent=scr1)

# Create screen 2
scr2 = screen.get_new_screen()
screen.clean_screen(scr2)
screen.set_screen_bg_color(0x000000,scr2)

# Init labels on screen 2
labelScreen2Title     = M5Label('In target range (last 24h)', x=9, y=0, color=0xffffff, font=FONT_MONT_22, parent=scr2)
labelAboveTarget      = M5Label('Above target 180 mg/dl:', x=9, y=60, color=0xffc418, font=FONT_MONT_18, parent=scr2)
labelInTarget         = M5Label('In target:', x=9, y=90, color=0x45db49, font=FONT_MONT_18, parent=scr2)
labelBelowTarget      = M5Label('Below target 70 mg/dl:', x=9, y=119, color=0xff0000, font=FONT_MONT_18, parent=scr2)
labelAgerageSg        = M5Label('Average SG:', x=9, y=147, color=0xa0a0a0, font=FONT_MONT_18, parent=scr2)
labelAboveTargetValue = M5Label('-- %', x=252, y=60, color=0xffffff, font=FONT_MONT_18, parent=scr2)
labelInTargetValue    = M5Label('-- %', x=252, y=90, color=0xffffff, font=FONT_MONT_18, parent=scr2)
labelBelowTargetValue = M5Label('-- %', x=252, y=119, color=0xffffff, font=FONT_MONT_18, parent=scr2)
labelAverageSgValue   = M5Label('-- mg/dl', x=231, y=147, color=0xffffff, font=FONT_MONT_18, parent=scr2)

# Create screen 3
scr3 = screen.get_new_screen()
screen.clean_screen(scr3)
screen.set_screen_bg_color(0x000000,scr3)

# Init labels on screen 3
# TODO

# Init Wifi connection
# TODO: check for errors
wifiCfg.doConnect(WIFI_SSID, WIFI_PASS)


#################################################
#
# Button handlers
#
#################################################

# Init button A
def buttonA_wasPressed():
  # global params
  screen.load_screen(scr1)
btnA.wasPressed(buttonA_wasPressed)

# Init button B
def buttonB_wasPressed():
  # global params
  screen.load_screen(scr2)
btnB.wasPressed(buttonB_wasPressed)

# Init button C
def buttonC_wasPressed():
  # global params
  screen.load_screen(scr3)
btnC.wasPressed(buttonC_wasPressed)


#################################################
#
# Helper functions
#
#################################################

def align_text(label,pos,y):
    if pos=="left":
        label.set_pos(x=0,y=y)
    elif pos=="center":
        label.set_pos(x=160-int(label.get_width()/2),y=y)
    elif pos=="right":
        label.set_pos(x=320-label.get_width(),y=y)


def time_delta(tm,ntp):
   
   if tm != None and ntp != None:
      delta_min  = ntp.minute() - tm[4]
      if delta_min < 0:
         delta_min += 60
      #print("delta_min: "+str(delta_min))
      delta_hour = ntp.hour() - (tm[3]+MY_TIMEZONE+dstDelta)
      if delta_hour < 0:
         delta_hour += 24
      #print("delta_hour: "+str(delta_hour))
      
      if delta_min == 0 and delta_hour == 0:
         delta_txt = "Now"
      elif delta_min > 15 or delta_hour > 1:
         delta_txt = "No data"
      else:
         delta_txt = str(delta_min)+" min ago"
   else:
      delta_txt = "---"
   return delta_txt


def reservoir_level(lvl):
   if lvl > 150:
      img_lvl = 200  # green
   elif lvl > 80:
      img_lvl = 150  # yellow
   elif lvl > 0:
      img_lvl = 50   # red
   else:
      img_lvl = 0    # empty 
   return img_lvl


def time_to_calib_progress(ttc,sst,cst):
   # TODO: check if screen 1 is active
   centerX = 112
   centerY = 17
   radius  = 16
   thick   = 4
   endposfull = 359
   endpos = int(360*((12-ttc)/12))
   endpos = min(endpos,endposfull)
   endpos = max(endpos,0)
   if ttc == 255 or cst == "UNKNOWN": # unknown
      #print("unknown")
      # full blue circle, question mark
      imageDrop.set_img_src("res/mm_drop_unk.png")
      imageDrop.set_pos(106, 8)
      lcd.arc(centerX, centerY, radius, thick, 0, endposfull,0x00cccc,0x00cccc)
   elif ttc >= 12: 
      # full green circle, white drop
      imageDrop.set_img_src("res/mm_drop_white.png")
      imageDrop.set_pos(105, 8)
      lcd.arc(centerX, centerY, radius, thick, 0, endposfull,0x33cc00,0x33cc00)
   elif ttc > 3:
      # decreasing green circle, white drop
      imageDrop.set_img_src("res/mm_drop_white.png")
      imageDrop.set_pos(105, 8)
      lcd.arc(centerX, centerY, radius, thick, 0, endposfull,0x33cc00,0x33cc00)
      lcd.arc(centerX, centerY, radius, thick, 0, endpos,0x000000,0x000000)
   elif ttc > 0:
      # decreasing red circle, white drop
      imageDrop.set_img_src("res/mm_drop_white.png")
      imageDrop.set_pos(105, 8)
      lcd.arc(centerX, centerY, radius, thick, 0, endposfull,0xff0000,0xff0000)
      lcd.arc(centerX, centerY, radius, thick, 0, endpos,0x000000,0x000000)
   else:
      if sst == "CALIBRATION_REQUIRED":
         # no circle, red drop
         imageDrop.set_img_src("res/mm_drop_red.png")
         imageDrop.set_pos(100, 0)
      else:
         # no circle, white drop
         imageDrop.set_img_src("res/mm_drop_white.png")
         imageDrop.set_pos(105, 8)
      lcd.arc(centerX, centerY, radius, thick, 0, endposfull,0x000000,0x000000)


def handle_alarm(lastAlarm):
   global lastAlarmId
   global lastAlarmMsg
   try:
        if lastAlarmId != lastAlarm["instanceId"]:
            if lastAlarmId != 0:
               # Show alarm message
               msg = lastAlarm["messageId"].split('_')[2:]
               if lastAlarmMsg != None:
                  lastAlarmMsg.delete()
                  lastAlarmMsg = None
               lastAlarmMsg = M5Msgbox(btns_list=None, x=0, y=100, w=None, h=None)
               lastAlarmMsg.set_text(" ".join(msg))
            
               # Play alarm sound
               if lastAlarm["type"] == "ALARM":
                  sndfile = "res/sound_alarm.wav"
               else:
                  sndfile = "res/sound_alert.wav"
               speaker.playWAV(sndfile, rate=22000)
            
            lastAlarmId = lastAlarm["instanceId"]
   except:
      pass
        
        
#################################################
#
# Timer definitions
#
#################################################

@timerSch.event('timer0')
def ttimer0():
   global runNtpsync
   runNtpsync = True

def handle_ntpsync():
   global ntp
   # Periodic timer: sync time via NTP
   ntp = ntptime.client(host=NTP_SERVER, timezone=MY_TIMEZONE+dstDelta)


@timerSch.event('timer1')
def ttimer1():
   global runTimeupdate
   runTimeupdate = True

def handle_timeupdate():
   global lastUpdateTm
   
   # Update display time
   time = ("%02d:%02d") % (ntp.hour(),ntp.minute())
   labelTime.set_text(time)
   align_text(labelTime,"right",0)
   
   labelLastData.set_text(time_delta(lastUpdateTm,ntp))
   align_text(labelLastData,"center",218)


@timerSch.event('timer2')
def ttimer2():
   global runPumpdataupdate
   runPumpdataupdate = True

def handle_pumpdataupdate():
   global lastUpdateTm
   global dstDelta
   
   # Update Minimed data
   # TODO: define timeout
   # msgbox = M5Msgbox(btns_list=None, x=0, y=0, w=None, h=None)
   # msgbox.set_text("1")
   r = urequests.request(method='GET', url=PROXY_URL, headers={})
   #msgbox.delete()
   if r.status_code == 200:
      # TODO: check conduit, medical device in range
      
      # Check for DST
      dstDelta = 1 if r.json()["clientTimeZoneName"].lower().find("summer")>-1 else 0
      
      # Check for alarm notification
      # msgbox.set_text("2")
      handle_alarm(r.json()["lastAlarm"])
      
      # Screen 1
      # msgbox.set_text("3")
      lastUpdateTm = time.localtime(int(r.json()["lastConduitUpdateServerTime"]/1000))
      # msgbox.set_text("4")
      imageBattery.set_img_src("res/mm_batt"+str(r.json()["medicalDeviceBatteryLevelPercent"])+".png")
      # msgbox.set_text("5")
      imageReservoir.set_img_src("res/mm_tank"+str(reservoir_level(r.json()["reservoirRemainingUnits"]))+".png")
      #imageSensorConn.set_img_src()
      # msgbox.set_text("6")
      time_to_calib_progress(r.json()["timeToNextCalibHours"],r.json()["sensorState"],r.json()["calibStatus"])
      # msgbox.set_text("7")
      imageShield.set_img_src("res/mm_shield_"+r.json()["lastSGTrend"].lower()+".png")
      # msgbox.set_text("8")
      lastSG = r.json()["lastSG"]["sg"]
      labelBglValue.set_text(str(lastSG) if lastSG > 0 else "--")
      # msgbox.set_text("9")
      align_text(labelBglValue,"center",90)
      # msgbox.set_text("10")
      labelActInsValue.set_text(str(r.json()["activeInsulin"]["amount"])+" U")
      # msgbox.set_text("11")
      align_text(labelActInsValue,"right",173)
      
      # Screen 2
      # msgbox.set_text("12")
      labelAboveTargetValue.set_text(str(r.json()["aboveHyperLimit"])+" %")
      labelInTargetValue.set_text(str(r.json()["timeInRange"])+" %")
      labelBelowTargetValue.set_text(str(r.json()["belowHypoLimit"])+" %")
      labelAverageSgValue.set_text(str(r.json()["averageSG"])+" mg/dl")
   else:
      # TODO: error handling
      pass
   # msgbox.delete()


@timerSch.event('timer3')
def ttimer3():
   # Periodic timer: check touch event
   handle_touchevent()

def handle_touchevent():
   global lastAlarmMsg
   if touch.status():
      if lastAlarmMsg != None:
         lastAlarmMsg.delete() 
         lastAlarmMsg = None
      screen.set_screen_brightness(100)
      timerSch.run('timer4', TIMER4_PERIOD_S*1000, 0x01)


@timerSch.event('timer4')
def ttimer4():
   # One shot timer: reset screen brightness
   screen.set_screen_brightness(40)


# Init timers

# Timer 0: 1200 sec (periodic) // ntpsync
TIMER0_PERIOD_S = 1200
timerSch.run('timer0', TIMER0_PERIOD_S*1000, 0x00)

# Timer 1: 1 sec (periodic) // timeupdate
TIMER1_PERIOD_S = 1
timerSch.run('timer1', TIMER1_PERIOD_S*1000, 0x00)

# Timer 2: 60 sec (periodic) // pumpdataupdate
TIMER2_PERIOD_S = 60
timerSch.run('timer2', TIMER2_PERIOD_S*1000, 0x00)

# Timer 3: 0.1 sec (periodic) // touchevent
TIMER3_PERIOD_S = 0.1
timerSch.run('timer3', TIMER3_PERIOD_S*1000, 0x00)

# Timer 4: 10 sec (one shot) // reset screen brightness
TIMER4_PERIOD_S = 10


#################################################
#
# Init
#
#################################################

ttimer0()
ttimer1()
ttimer2()


#################################################
#
# Main loop
#
#################################################
while True:
   # Run handlers as requested
   if runNtpsync:
      handle_ntpsync()
      runNtpsync = False
   if runTimeupdate:
      handle_timeupdate()
      runTimeupdate = False
   if runPumpdataupdate:
      handle_pumpdataupdate()
      runPumpdataupdate = False
   
   wait_ms(100)
