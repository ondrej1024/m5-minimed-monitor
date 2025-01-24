###############################################################################
#  
#  PC Minimed Monitor
#  
#  Description:
#
#  This is a PC version of the "M5Stack Minimed Monitor". It has the same code
#  base as the M5 Stack version plus some wrapper functions for the M5 Stack
#  specific graphics API, replacing it with the TKinter framework.
#
#  Dependencies:
#
#  At this stage, the PC Minimed Monitor relies on an external instance
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
#    30/05/2022 - Initial public release
#    09/01/2023 - Display alarm messages
#    17/01/2025 - Adapt to new Carelink data format
#    21/01/2025 - Display system status message
#
#  TODO:
#
#  * Integration of Carelink Client
#
#  Copyright 2022-2025, Ondrej Wisniewski
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

from tkinter import *
import threading
import time
import datetime
import requests as urequests
import playsound # Needs GST binding (apt install python3-gst-1.0)

# Font mappings
FONT_MONT_14 = 'Helvetica 10'
FONT_MONT_16 = 'Helvetica 12'
FONT_MONT_20 = 'Helvetica 12'
FONT_MONT_26 = 'Helvetica 18'
FONT_MONT_28 = 'Helvetica 20'
FONT_MONT_48 = 'Helvetica 44'

# Window geometry
WINWIDTH  = 320
WINHEIGHT = 240
WINBORDER = 20

# Default configuration parameters
DEFAULT_NTP_SERVER = "pool.ntp.org"
DEFAULT_TIME_ZONE  = "0"
DEFAULT_PROXY_PORT = "8081"

ntpserver = DEFAULT_NTP_SERVER
timezone  = DEFAULT_TIME_ZONE

# API
API_URL   = "carelink/nohistory"
proxyaddr = "0.0.0.0" # Replace with your Carelink Python Client IP address
proxyaddr = "192.168.1.100"
proxyport = 8081

# Gobal variables
dstDelta     = 0
lastUpdateTm = time.localtime(0)
lastAlarmId  = 0
lastAlarmMsg = None
lastErrorMsg = None
lastStatusMsg = None
lastApMsg    = None
runNtpsync        = False
runTimeupdate     = False
runPumpdataupdate = False


#################################################
#
# Wrapper classes for M5 libs
#
#################################################

class M5Screen:
   def __init__(self,icon=None):
      self.window = Tk()
      self.window.config(width=WINWIDTH+WINBORDER,height=WINHEIGHT+WINBORDER)
      self.window.configure(bg='black')
      self.window.title("Minimed Mon PC")
      self.window.resizable(False, False)
      if icon != None:
         self.window.iconphoto(False, PhotoImage(file=icon))
      self.scr = Canvas(self.window, width=WINWIDTH,height=WINHEIGHT,bg='black',highlightthickness=0)
      #self.scr.pack()
      self.scr.place(relx=0.5, rely=0.5, anchor=CENTER)
   def set_screen_bg_color(self, color):
      self.window.configure(bg=color)
      self.scr.configure(bg=color)
   def set_screen_brightness(self, brightness):
      pass

class M5Img:
   def __init__(self, img_file, x, y, parent):
      self.img = PhotoImage(file=img_file)
      self.scr = parent
      self.img_h = self.scr.create_image(x,y,anchor=NW,image=self.img)
   def set_hidden(self,hidden):
      if hidden:
         self.scr.itemconfig(self.img_h, state='hidden')
      else:
         self.scr.itemconfig(self.img_h, state='normal')
   def set_img_src(self, img_file):
      self.img = PhotoImage(file=img_file)
      self.scr.itemconfig(self.img_h,image=self.img)
   def set_pos(self, x, y):
      # TODO
      pass

class M5Label:
   def __init__(self, text, x, y, color, font, parent):
      self.scr = parent
      self.txt_h = self.scr.create_text(x,y,anchor=NW,text=text,fill="#%06X" % (color),font=(font))
   def set_text(self, text):
      self.scr.itemconfig(self.txt_h,text=text)
   def set_pos(self, x, y):
      self.scr.coords(self.txt_h,x,y)
   def get_width(self):
      bounds = self.scr.bbox(self.txt_h)
      return bounds[2] - bounds[0]
   def get_height(self):
      bounds = self.scr.bbox(self.txt_h)
      return bounds[3] - bounds[1]

class M5Msgbox:
   def __init__(self,btns_list, x, y, w, h, parent):
      self.scr = parent
      self.x1 = x
      self.y1 = y
      self.x2 = x+w if w != None else WINWIDTH-x
      self.y2 = y+h if h != None else y+30
      self.rect_h = self.scr.create_rectangle(x,y,self.x2,self.y2,fill="white",outline="white")
      self.text_h = self.scr.create_text(WINWIDTH/2,self.y1+17,fill="grey",text="text",font=FONT_MONT_16,width=self.x2-self.x1,justify="center")
      self.btns_list = btns_list
   def set_text(self, text):
      self.scr.itemconfig(self.text_h,text=text)
   def delete(self):
      self.scr.delete(self.text_h)
      self.scr.delete(self.rect_h)

class timerSch:
   def __init__(self):
      pass
   def __periodic_timer(self, func, period):
      print("start periodic_timer with %d s" %(period))
      while True:
         time.sleep(period)
         func()
   def run(self, func, period, oneshot):
      if oneshot:
         t = threading.Timer(period/1000, func)
         t.daemon = True
         t.start()
      else:
         t = threading.Thread(target=self.__periodic_timer, args=(func,period/1000))
         t.daemon = True
         t.start()
   
   
#################################################
#
# Wrapper classes for Micropython libs
#
#################################################

class lcd:
   def __init__(self,parent):
      self.scr = parent
   def arc(self, x, y, radius, thick, startpos, endpos, color1, color2):
      x1 = x-radius
      y1 = y-radius
      x2 = x+radius
      y2 = y+radius
      start = (360-startpos)+90
      extend = -endpos
      outline = "#%06X" % (color1)
      arc = self.scr.create_arc((x1,y1,x2,y2), start=start, extent=extend, style=ARC, width=thick, outline=outline)

class ntpclient:
   def __init__(self, host, timezone):
      self.host = host
      self.timezone = timezone
      self.datetime = datetime.datetime
   def hour(self):
      return self.datetime.now().hour
   def minute(self):
      return self.datetime.now().minute

class speaker:
   def __init__(self):
      self.playsound = playsound.playsound
   def playWAV(self, sndfile, rate):
      self.playsound(sndfile)
   
def wait_ms(time_ms):
   time.sleep(time_ms/1000)


# Create screen
print("Create screen")
s=M5Screen('res/icon_mmm.png')
scr1 = s.scr

timerSch = timerSch()
lcd = lcd(parent=scr1)
speaker = speaker()

# Load images on screen 1
print("Create images")
imageBattery     = M5Img("res/mm_batt_unk.png", x=6, y=0, parent=scr1)
imageReservoir   = M5Img("res/mm_tank_unk.png", x=40, y=0, parent=scr1)
imageSensorConn  = M5Img("res/mm_sensor_connection_nok.png", x=68, y=0, parent=scr1)
imageDrop        = M5Img("res/mm_drop_unk.png", x=105, y=8, parent=scr1)
imageSage        = M5Img("res/mm_sage_unk.png", x=135, y=0, parent=scr1)
imageShield      = M5Img("res/mm_shield_none.png", x=65, y=33, parent=scr1)
imageBanner      = M5Img("res/mm_banner_delivery_suspend.png", x=40, y=145, parent=scr1)

imageBanner.set_hidden(True)

# Init labels on screen 1
print("Create labels")
labelBglValue    = M5Label('--', x=160, y=95, color=0xffffff, font=FONT_MONT_48, parent=scr1)
labelBglUnit     = M5Label('mg/dL', x=135, y=150, color=0x89abeb, font=FONT_MONT_16, parent=scr1)
labelActInsValue = M5Label('-- U', x=261, y=173, color=0xffffff, font=FONT_MONT_26, parent=scr1)
labelActIns      = M5Label('Act Insulin', x=231, y=200, color=0xffffff, font=FONT_MONT_16, parent=scr1)
labelTime        = M5Label('--:--', x=250, y=0, color=0xffffff, font=FONT_MONT_28, parent=scr1)
labelLastData    = M5Label('--', x=160, y=218, color=0xffffff, font=FONT_MONT_20, parent=scr1)
labelSage        = M5Label('', x=144, y=10, color=0xffffff, font=FONT_MONT_14, parent=scr1)


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


def time_delta(tm,ntp,timezone):
   if tm != None and ntp != None:
      delta_min  = ntp.minute() - tm[4]
      if delta_min < 0:
         delta_min += 60
      #print("delta_min: "+str(delta_min))
      #delta_hour = ntp.hour() - (tm[3]+int(timezone)+dstDelta)
      delta_hour = ntp.hour() - (tm[3]+int(timezone))
      if delta_hour < 0:
         delta_hour += 24
      #print("myHour: %d devHour: %d, dstDelta: %d" % (ntp.hour(),tm[3],dstDelta))
      #print("delta_hour: "+str(delta_hour))
      
      if delta_min == 0 and delta_hour == 0:
         delta_txt = "Now"
      elif delta_min > 15 or delta_hour > 1:
         delta_txt = "No data"
         #deltaMsg = M5Msgbox(btns_list=None, x=0, y=50, w=None, h=None, parent=scr1)
         #deltaMsg.set_text("No data")
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
   elif lvl > 1:
      img_lvl = 50   # red
   else:
      img_lvl = 0    # empty 
   return img_lvl


def time_to_calib_progress(cfs,ttc,sst,cst):
   # TODO: check if screen 1 is active
   centerX = 112
   centerY = 17
   radius  = 14
   thick   = 4
   endposfull = 359
   endpos = int(360*((12-ttc)/12))
   endpos = min(endpos,endposfull)
   endpos = max(endpos,0)
   if (ttc == 255 or cst == "UNKNOWN") and not cfs: # unknown
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


def sensor_age_text(rem_hours):
   if rem_hours == 255:
      text = ""
   elif rem_hours > 9:
      text = str(round(rem_hours/24))
   else:
      text = str(rem_hours)
   return text
   

def sensor_age_icon(rem_hours, sensor_state):
   if sensor_state == "CHANGE_SENSOR":
      icon = "expired"
   elif rem_hours == 255:
      icon = "unk"
   elif rem_hours > 9:
      icon = "green"
   else:
      icon = "red"
   return icon
      
      
def convert_datetimestr_to_epoch(datetimestr):
   # datetime string format is the following:
   # yyyy-mm-ddThh:mm:ss.000-00:00
   try:
      d  = datetimestr.split('.')[0].split('T')[0]
      t  = datetimestr.split('.')[0].split('T')[1]
      year = int(d.split('-')[0])
      mon  = int(d.split('-')[1])
      day  = int(d.split('-')[2])
      hour = int(t.split(':')[0])
      min  = int(t.split(':')[1])
      sec  = int(t.split(':')[2])
      #print("%d-%d-%d %d:%d:%d"%(year,mon,day,hour,min,sec))
      return time.mktime((year,mon,day,hour,min,sec,0,0,dstDelta))
   except:
      return 0


def handle_alarm(lastAlarm):
   TDELTA_S = 15*60 # 15 min in seconds
   global lastAlarmId
   global lastAlarmMsg
   
   # Delete previous alarm message
   if lastAlarmMsg != None:
      lastAlarmMsg.delete() 
      lastAlarmMsg = None

   try:
      # Check for new alarm
      if lastAlarmId != lastAlarm["instanceId"]:
         # Check if alarm is recent
         if convert_datetimestr_to_epoch(lastAlarm["datetime"]) > (time.time() - TDELTA_S):
            # Show alarm message
            msg = lastAlarm["messageId"].split('_')[2:]
            print("%s : %s" % (lastAlarm["datetime"],lastAlarm["messageId"]))
            if lastAlarmMsg != None:
               lastAlarmMsg.delete()
            lastAlarmMsg = M5Msgbox(btns_list=None, x=0, y=100, w=None, h=None, parent=scr1)
            lastAlarmMsg.set_text(" ".join(msg))
            
            # Play alarm sound
            if lastAlarm["kind"] == "ALARM":
               sndfile = "res/sound_alarm.wav"
            else:
               sndfile = "res/sound_alert.wav"
            speaker.playWAV(sndfile, rate=22000)
         lastAlarmId = lastAlarm["instanceId"]
   except:
      pass
        

#################################################
#
# Worker functions
#
#################################################

def ttimer0():
   global runNtpsync
   runNtpsync = True

def handle_ntpsync(ntpserver, timezone):
   # Periodic timer: sync time via NTP
   try:
      ntp = ntpclient(host=ntpserver, timezone=int(timezone)+dstDelta)
   except:
      ntp = None
   return ntp


def ttimer1():
   global runTimeupdate
   runTimeupdate = True

def handle_timeupdate(ntp, timezone):
   try:
      # Update display time
      time = ("%02d:%02d") % (ntp.hour(),ntp.minute())
      labelTime.set_text(time)
      align_text(labelTime,"right",0)
      labelLastData.set_text(time_delta(lastUpdateTm,ntp,timezone))
      align_text(labelLastData,"center",218)
   except:
      pass


def ttimer2():
   global runPumpdataupdate
   runPumpdataupdate = True

def handle_pumpdataupdate(proxyaddr, proxyport):
   global lastErrorMsg
   global lastStatusMsg
   global lastUpdateTm
   global dstDelta
   proxy_url = "http://%s:%s/%s" % (proxyaddr, proxyport, API_URL)

   # Update Minimed data
   
   # Get Minimed data from proxy via API
   # (urequests does not handle timeouts so we do this with an external timer)
   #timerSch.run('timer5', TIMER5_PERIOD_S*1000, 0x01)
   try:
      r = urequests.request(method='GET', url=proxy_url, headers={})
   except OSError:
      r = None
   #timerSch.stop('timer5')
   if lastErrorMsg != None:
      lastErrorMsg.delete()
      lastErrorMsg = None
   
   if r != None and r.status_code == 200 and r.json() != "":
      try:
         lastUpdateTm = time.localtime(int(r.json()["lastConduitUpdateServerDateTime"]/1000))
         
         # Check for DST
         dstDelta = 1 if r.json()["clientTimeZoneName"].lower().find("Summer")>-1 else 0
         
         # Check for alarm notification
         handle_alarm(r.json()["lastAlarm"])
         
         # Check conduit, medical device in range
         haveData = r.json()["conduitInRange"] and r.json()["conduitMedicalDeviceInRange"]

         ##### Screen 1 #####
         
         if haveData:
            imageBattery.set_img_src("res/mm_batt"+str(r.json()["pumpBatteryLevelPercent"])+".png")
            imageReservoir.set_img_src("res/mm_tank"+str(reservoir_level(r.json()["reservoirRemainingUnits"]))+".png")
            imageSage.set_img_src("res/mm_sage_"+sensor_age_icon(r.json()["sensorDurationHours"],r.json()["sensorState"])+".png")
            labelSage.set_text(sensor_age_text(r.json()["sensorDurationHours"]))
         else:
            imageBattery.set_img_src("res/mm_batt_unk.png")
            imageReservoir.set_img_src("res/mm_tank_unk.png")
            imageSage.set_img_src("res/mm_sage_unk.png")
            labelSage.set_text("")
         
         if r.json()["conduitSensorInRange"]:
            imageSensorConn.set_img_src("res/mm_sensor_connection_ok.png")
         else:
            imageSensorConn.set_img_src("res/mm_sensor_connection_nok.png")
         
         time_to_calib_progress(r.json()["calFreeSensor"],r.json()["timeToNextCalibHours"],r.json()["sensorState"],r.json()["calibStatus"])
         
         if not haveData or r.json()["therapyAlgorithmState"]["autoModeShieldState"] == "FEATURE_OFF":
            imageShield.set_hidden(True)
         else:
            imageShield.set_img_src("res/mm_shield_"+r.json()["lastSGTrend"].lower()+".png")
            imageShield.set_hidden(False)
         lastSG = r.json()["lastSG"]["sg"]
         #print("lastSG: "+str(lastSG))
         labelBglValue.set_text(str(lastSG) if lastSG > 0 else "--")
         align_text(labelBglValue,"center",95)
         
         if haveData:
            labelActInsValue.set_text(str(round(r.json()["activeInsulin"]["amount"],1))+" U")
         else:
            labelActInsValue.set_text("-- U")
         align_text(labelActInsValue,"right",173)
      except:
         pass
      
      try:
         systemStatus = r.json()["systemStatusMessage"]
         if systemStatus == "NO_ERROR_MESSAGE":
            raise Exception
         else:
            if lastStatusMsg == None:
               lastStatusMsg = M5Msgbox(btns_list=None, x=0, y=50, w=None, h=None, parent=scr1)
            lastStatusMsg.set_text(systemStatus.replace("_"," "))
            print("systemStatus: %s" % systemStatus)
      except:
         if lastStatusMsg != None:
            lastStatusMsg.delete()
            lastStatusMsg = None

      try:
         pumpBanner = r.json()["pumpBannerState"][0]["type"]
         imageBanner.set_img_src("res/mm_banner_"+pumpBanner.lower()+".png")
         imageBanner.set_hidden(False)
      except:
         imageBanner.set_hidden(True)

#################################################
#
# Init
#
#################################################

align_text(labelBglUnit,"center",150)
align_text(labelActIns,"right",200)

ntp = None
msgbox = None
while ntp == None:
   wait_ms(1000)
   ntp = handle_ntpsync(ntpserver, timezone)
   if ntp == None and msgbox == None:
      msgbox = M5Msgbox(btns_list=None, x=0, y=0, w=None, h=None, parent=scr1)
      msgbox.set_text("Trying to synch time and date ...")
if msgbox != None:
   msgbox.delete()

print("Time and date successfully synched")

# Init timers

# Timer 0: 1200 sec (periodic) // ntpsync
TIMER0_PERIOD_S = 1200
#timerSch.run('timer0', TIMER0_PERIOD_S*1000, 0x00)
timerSch.run(ttimer0, TIMER0_PERIOD_S*1000, 0x00)

# Timer 1: 10 sec (periodic) // timeupdate
TIMER1_PERIOD_S = 10
#timerSch.run('timer1', TIMER1_PERIOD_S*1000, 0x00)
timerSch.run(ttimer1, TIMER1_PERIOD_S*1000, 0x00)

# Timer 2: 60 sec (periodic) // pumpdataupdate
TIMER2_PERIOD_S = 60
#timerSch.run('timer2', TIMER2_PERIOD_S*1000, 0x00)
timerSch.run(ttimer2, TIMER2_PERIOD_S*1000, 0x00)

# Timer 3: 0.2 sec (periodic) // touchevent
TIMER3_PERIOD_S = 0.2
#timerSch.run('timer3', int(TIMER3_PERIOD_S*1000), 0x00)

# Timer 4: 10 sec (one shot) // reset screen brightness
TIMER4_PERIOD_S = 10

# Timer 5: 60 sec (one shot) // urequest watchdog
TIMER5_PERIOD_S = 60

# Run some timer functions immediately to init
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
   if runPumpdataupdate:
      handle_pumpdataupdate(proxyaddr, proxyport)
      runPumpdataupdate = False
   if runNtpsync:
      ntp = handle_ntpsync(ntpserver, timezone)
      runNtpsync = False
   if runTimeupdate:
      handle_timeupdate(ntp, timezone)
      runTimeupdate = False
   
   wait_ms(100)

   try:
      s.window.update()
   except:
      break

print("Exiting")
