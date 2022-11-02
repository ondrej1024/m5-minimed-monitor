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
#    03/04/2022 - Add AP mode for configuration
#    01/02/2022 - Improve error handling
#    23/02/2022 - Handle pump banner, shield state, device in range
#    27/03/2022 - Add sensor age icon
#    02/11/2022 - Fix DST handling
#
#  TODO:
#
#  * Integration of Carelink Client
#  * History graph for recent glucose data
#
#  Copyright 2021-2022, Ondrej Wisniewski 
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
import ntptime
import time
import urequests
import nvs
import network
import socket
import machine

VERSION = "0.6"


# Default configuration parameters
DEFAULT_NTP_SERVER = "pool.ntp.org"
DEFAULT_TIME_ZONE  = "1"
DEFAULT_PROXY_PORT = "8081"

# Access point parameters
API_URL     = "carelink/nohistory"
AP_SSID     = "M5_MINIMED_MON"
AP_ADDR     = "192.168.4.1"

# Gobal variables
dstDelta     = 0
lastUpdateTm = time.localtime(0)
lastAlarmId  = 0
lastAlarmMsg = None
lastErrorMsg = None
lastApMsg    = None
runNtpsync        = False
runTimeupdate     = False
runPumpdataupdate = False


#################################################
#
# WIFI Access Point functions
#
#################################################

def web_page_config(ntpserver,timezone,proxyport):
   html =  '<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01//EN" "http://www.w3.org/TR/html4/strict.dtd"> \n \
            <html><head><title>M5 Minimed Mon</title></head> \n \
            <body><table style="text-align: left; width: 400px; background-color: #2196F3; font-family: Helvetica,Arial,sans-serif; font-weight: bold; color: white;" border="0" cellpadding="2" cellspacing="2"> \n \
            <tbody><tr><td> \n \
            <span style="vertical-align: top; font-size: 48px;">M5 Minimed Mon</span><br> \n \
            <span style="font-size: 20px; color: rgb(204, 255, 255);">Configuration</span> \n \
            </td></tr></tbody></table><br> \n \
            <form action="/m5config"> \n \
            <table style="text-align: left; width: 400px; background-color: white; font-family: Helvetica,Arial,sans-serif; font-weight: bold; font-size: 14px;" border="0" cellpadding="2" cellspacing="3"><tbody> \n \
            <tr style="font-size: 18px; background-color: lightgrey"> \n \
            <td style="width: 200px;">Wifi parameters</td> \n \
            <tr style="vertical-align: top; background-color: rgb(230, 230, 255);"> \n \
            <td style="width: 300px;">SSID<br><input type="text" id="fwifissid" name="fwifissid"></td> \n \
            <tr style="vertical-align: top; background-color: rgb(230, 230, 255);"> \n \
            <td style="width: 300px;">Password<br><input type="text" id="fwifipass" name="fwifipass"></td> \n \
            </tbody></table><br> \n \
            <table style="text-align: left; width: 400px; background-color: white; font-family: Helvetica,Arial,sans-serif; font-weight: bold; font-size: 14px;" border="0" cellpadding="2" cellspacing="3"><tbody> \n \
            <tr style="font-size: 18px; background-color: lightgrey"> \n \
            <td style="width: 200px;">Time and date</td> \n \
            <tr style="vertical-align: top; background-color: rgb(230, 230, 255);"> \n \
            <td style="width: 300px;">NTP server address<br><input type="text" id="fntpserver" name="fntpserver" value=%s></td> \n \
            <tr style="vertical-align: top; background-color: rgb(230, 230, 255);"> \n \
            <td style="width: 300px;">Time Zone (h)<br><input type="text" id="ftimezone" name="ftimezone" value=%s></td> \n \
            </tbody></table><br> \n \
            <table style="text-align: left; width: 400px; background-color: white; font-family: Helvetica,Arial,sans-serif; font-weight: bold; font-size: 14px;" border="0" cellpadding="2" cellspacing="3"><tbody> \n \
            <tr style="font-size: 18px; background-color: lightgrey"> \n \
            <td style="width: 200px;">Carelink proxy</td> \n \
            <tr style="vertical-align: top; background-color: rgb(230, 230, 255);"> \n \
            <td style="width: 300px;">IP address<br><input type="text" id="fproxyaddr" name="fproxyaddr"></td> \n \
            <tr style="vertical-align: top; background-color: rgb(230, 230, 255);"> \n \
            <td style="width: 300px;">Port<br><input type="text" id="fproxyport" name="fproxyport" value=%s></td> \n \
            </tbody></table><br> \n \
            <input type="submit" value="Save"> \n \
            </form></body></html>' % (ntpserver,timezone,proxyport)
   return html


def web_page_success():
   html =  '<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01//EN" "http://www.w3.org/TR/html4/strict.dtd"> \n \
            <html><head><title>M5 Minimed Mon</title></head> \n \
            <body><table style="text-align: left; width: 400px; background-color: #2196F3; font-family: Helvetica,Arial,sans-serif; font-weight: bold; color: white;" border="0" cellpadding="2" cellspacing="2"> \n \
            <tbody><tr><td> \n \
            <span style="vertical-align: top; font-size: 48px;">M5 Minimed Mon</span><br> \n \
            <span style="font-size: 20px; color: rgb(204, 255, 255);">Configuration</span> \n \
            </td></tr></tbody></table><br> \n \
            <table style="text-align: left; width: 400px; background-color: rgb(230, 230, 255); font-family: Helvetica,Arial,sans-serif; font-weight: bold; font-size: 14px;" border="0" cellpadding="2" cellspacing="3"><tbody> \n \
            <tr><td style="color: green; font-size: 18px;">Parameters updated successfully</td> \n \
            <tr><td style="color: grey">Restarting device with new configuration ...</td> \n \
            </tbody></table></body></html>'
   return html


def get_url_param(url,param):
   try:
      value = url.split("?")[1].split(param+"=")[1].split("&")[0]
   except IndexError:
      value = None
   return value


def do_ap_msg(msg):
   global lastApMsg
   if lastApMsg != None:
      lastApMsg.delete()
      lastApMsg = None
   if msg:
      lastApMsg = M5Msgbox(btns_list=None, x=0, y=100, w=None, h=None)
      lastApMsg.set_text(msg)
      sndfile = "res/sound_alert.wav"
      speaker.playWAV(sndfile, rate=22000)


def do_access_point(ntpserver,timezone,proxyport):
   # Start access point
   ap = network.WLAN(network.AP_IF)
   ap.active(True)
   ap.config(essid=AP_SSID)
   ap.config(authmode=3, password='123456789')
   ap.config(max_clients=1) 
   do_ap_msg("Device configuration needed\nConnect to WIFI network %s" %(AP_SSID))
   
   # Wait for client to connect
   while ap.isconnected() == False:
       pass
   do_ap_msg("WIFI connection established\nLoad address %s in web browser" % (AP_ADDR))
   
   # Get WIFI credentials via Web GUI
   s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
   s.bind((AP_ADDR, 80))
   s.listen(5)
   
   while True:
      # Get request
      conn,addr = s.accept()
      request = str(conn.recv(1024))
      rmethod  = request.split()[0]
      rurl     = request.split()[1]
      rheaders = request.split()[2]
      print("request: %s\n" % (request))
      #print("rmethod: %s\n" % (rmethod))
      print("rurl: %s\n" % (rurl))
      
      # Send response headers
      conn.send('HTTP/1.1 200 OK\n')
      conn.send('Content-Type: text/html\n')
      conn.send('Connection: close\n\n')

      if rurl.find("/m5config") != -1:
         # Get input parameters from request
         wifissid  = get_url_param(rurl, "fwifissid")
         wifipass  = get_url_param(rurl, "fwifipass")
         ntpserver = get_url_param(rurl, "fntpserver")
         timezone  = get_url_param(rurl, "ftimezone")
         proxyaddr = get_url_param(rurl, "fproxyaddr")
         proxyport = get_url_param(rurl, "fproxyport")
         if wifissid  != None and wifissid  != "" and \
            wifipass  != None and wifipass  != "" and \
            ntpserver != None and ntpserver != "" and \
            timezone  != None and timezone  != "" and \
            proxyaddr != None and proxyaddr != "" and \
            proxyport != None and proxyport != "":
            
            print("New configuration parameters received\n")
            # Send reboot page
            conn.sendall(web_page_success())
            conn.close()
            break

      # Send setup page
      conn.sendall(web_page_config(ntpserver,timezone,proxyport))
      conn.close()
            
   # Write WIFI credentials to EEPROM
   nvs.write_str('wifissid',  wifissid) 
   wait_ms(100)
   nvs.write_str('wifipass',  wifipass)
   wait_ms(100)
   nvs.write_str('ntpserver', ntpserver)
   wait_ms(100)
   nvs.write_str('timezone',  timezone)
   wait_ms(100)
   nvs.write_str('proxyaddr', proxyaddr)
   wait_ms(100)
   nvs.write_str('proxyport', proxyport)
   wait_ms(100)
   print("New configuration parameters stored in EEPROM\n")
   print("wifissid: %s, wifipass: %s, proxyaddr: %s, proxyport: %s, ntpserver: %s, timezone: %s\n" % (wifissid,wifipass,proxyaddr,proxyport,ntpserver,timezone))
   do_ap_msg("New configuration parameters stored in EEPROM\nResetting device ...")

   # Reset device
   wait_ms(8000)
   machine.reset()


#################################################
#
# Access configuration parameters
#
#################################################

def read_config():
   # Try to read config from EEPROM
   wifissid  = nvs.read_str('wifissid')
   wifipass  = nvs.read_str('wifipass')
   ntpserver = nvs.read_str('ntpserver')
   timezone  = nvs.read_str('timezone')
   proxyaddr = nvs.read_str('proxyaddr')
   proxyport = nvs.read_str('proxyport')

   # Set default values
   if proxyport == None:
      proxyport = DEFAULT_PROXY_PORT
   if ntpserver == None:
      ntpserver = DEFAULT_NTP_SERVER
   if timezone == None:
      timezone  = DEFAULT_TIME_ZONE

   # To delete a key/value pair use the following command
   # nvs.esp32.nvs_erase(<key>)

   if wifissid == None or wifipass == None or proxyaddr == None:
      print("Needed configuration parameters not found in EEPROM\n")
      # Start access point for configuration
      do_access_point(ntpserver,timezone,proxyport)

   return (wifissid,wifipass,proxyaddr,proxyport,ntpserver,timezone)


#################################################
#
# Connect to network
#
#################################################

def wlan_connect(wifissid, wifipass, ntpserver, timezone, proxyport):
   # Try to connect to WIFI network
   wlan = network.WLAN(network.STA_IF)
   wlan.active(True)
   wlan.connect(wifissid, wifipass)
   ctimeout=0
   while not wlan.isconnected():
      wait_ms(1000)
      ctimeout += 1
      if ctimeout > 5:
         break
   if not wlan.isconnected():
      wlan.active(False)
      print("Failed to connect to WIFI network %s\n" % (wifissid))
      # Start access point for configuration
      do_access_point(ntpserver,timezone,proxyport)


# Startup message
lcd.clear()
lcd.font(lcd.FONT_DejaVu24)
lcd.setTextColor(lcd.WHITE)
lcd.println("Minimed Mon, ver %s" % (VERSION))
print("Minimed Mon, ver %s" % (VERSION))
wait_ms(3000)

# Init screen
screen = M5Screen()
screen.clean_screen()
screen.set_screen_bg_color(0x000000)
screen.set_screen_brightness(40)

# Read config from EEPROM
wifissid,wifipass,proxyaddr,proxyport,ntpserver,timezone = read_config()
print("wifissid: %s, wifipass: %s, proxyaddr: %s, proxyport: %s, ntpserver: %s, timezone: %s\n" % (wifissid,wifipass,proxyaddr,proxyport,ntpserver,timezone))

# Connect to network
wlan_connect(wifissid, wifipass, ntpserver, timezone, proxyport)

# Create screen 1
scr1 = None

# Load images on screen 1
imageBattery     = M5Img("res/mm_batt_unk.png", x=6, y=0, parent=scr1)
imageReservoir   = M5Img("res/mm_tank_unk.png", x=40, y=0, parent=scr1)
imageSensorConn  = M5Img("res/mm_sensor_connection_nok.png", x=68, y=0, parent=scr1)
imageDrop        = M5Img("res/mm_drop_unk.png", x=105, y=8, parent=scr1)
imageSage        = M5Img("res/mm_sage_unk.png", x=135, y=0, parent=scr1)
imageShield      = M5Img("res/mm_shield_none.png", x=65, y=33, parent=scr1)
imageBanner      = M5Img("res/mm_banner_delivery_suspend.png", x=40, y=145, parent=scr1)

# Init labels on screen 1
labelBglValue    = M5Label('--', x=140, y=90, color=0xffffff, font=FONT_MONT_48, parent=scr1)
labelBglUnit     = M5Label('mg/dL', x=137, y=145, color=0x89abeb, font=FONT_MONT_16, parent=scr1)
labelActInsValue = M5Label('-- U', x=261, y=173, color=0xffffff, font=FONT_MONT_26, parent=scr1)
labelActIns      = M5Label('Act Insulin', x=231, y=200, color=0xffffff, font=FONT_MONT_16, parent=scr1)
labelTime        = M5Label('--:--', x=250, y=0, color=0xffffff, font=FONT_MONT_28, parent=scr1)
labelLastData    = M5Label('--', x=120, y=218, color=0xffffff, font=FONT_MONT_20, parent=scr1)
labelSage        = M5Label('', x=144, y=8, color=0xffffff, font=FONT_MONT_14, parent=scr1)

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


def time_delta(tm,ntp,timezone):
   
   if tm != None and ntp != None:
      delta_min  = ntp.minute() - tm[4]
      if delta_min < 0:
         delta_min += 60
      #print("delta_min: "+str(delta_min))
      delta_hour = ntp.hour() - (tm[3]+int(timezone)+dstDelta)
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
   elif lvl > 1:
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
            lastAlarmMsg = M5Msgbox(btns_list=None, x=0, y=100, w=None, h=None)
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
# Timer definitions
#
#################################################

@timerSch.event('timer0')
def ttimer0():
   global runNtpsync
   runNtpsync = True

def handle_ntpsync(ntpserver, timezone):
   # Periodic timer: sync time via NTP
   try:
      ntp = ntptime.client(host=ntpserver, timezone=int(timezone)+dstDelta)
      #print("time: %02d:%02d (tz:%d, dd:%d)" % (ntp.hour(),ntp.minute(),int(timezone),dstDelta))
   except:
      ntp = None
   return ntp


@timerSch.event('timer1')
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


@timerSch.event('timer2')
def ttimer2():
   global runPumpdataupdate
   runPumpdataupdate = True

def handle_pumpdataupdate(proxyaddr, proxyport):
   global lastErrorMsg
   global lastUpdateTm
   global dstDelta
   proxy_url = "http://%s:%s/%s" % (proxyaddr, proxyport, API_URL)

   # Update Minimed data
   
   # Get Minimed data from proxy via API
   # (urequests does not handle timeouts so we do this with an external timer)
   timerSch.run('timer5', TIMER5_PERIOD_S*1000, 0x01)
   try:
      r = urequests.request(method='GET', url=proxy_url, headers={})
   except OSError:
      r = None
   timerSch.stop('timer5')
   if lastErrorMsg != None:
      lastErrorMsg.delete()
      lastErrorMsg = None
   
   if r != None and r.status_code == 200:
      try:
         lastUpdateTm = time.localtime(int(r.json()["lastConduitUpdateServerTime"]/1000))
         
         # Check for DST
         dstDelta = 1 if r.json()["clientTimeZoneName"].lower().find("summer")>-1 else 0
         
         # Check for alarm notification
         handle_alarm(r.json()["lastAlarm"])
         
         # Check conduit, medical device in range
         haveData = r.json()["conduitInRange"] and r.json()["conduitMedicalDeviceInRange"]

         ##### Screen 1 #####
         
         if haveData:
            imageBattery.set_img_src("res/mm_batt"+str(r.json()["medicalDeviceBatteryLevelPercent"])+".png")
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
         
         time_to_calib_progress(r.json()["timeToNextCalibHours"],r.json()["sensorState"],r.json()["calibStatus"])
         
         if not haveData or r.json()["therapyAlgorithmState"]["autoModeShieldState"] == "FEATURE_OFF":
            imageShield.set_hidden(True)
         else:
            imageShield.set_img_src("res/mm_shield_"+r.json()["lastSGTrend"].lower()+".png")
            imageShield.set_hidden(False)
         lastSG = r.json()["lastSG"]["sg"]
         labelBglValue.set_text(str(lastSG) if lastSG > 0 else "--")
         align_text(labelBglValue,"center",90)
         
         if haveData:
            labelActInsValue.set_text(str(r.json()["activeInsulin"]["amount"])+" U")
         else:
            labelActInsValue.set_text("-- U")
         align_text(labelActInsValue,"right",173)
      except:
         pass
      
      try:
         pumpBanner = r.json()["pumpBannerState"][0]["type"]
         imageBanner.set_img_src("res/mm_banner_"+pumpBanner.lower()+".png")
         imageBanner.set_hidden(False)
      except:
         imageBanner.set_hidden(True)
         
      ##### Screen 2 #####
      try:
         labelAboveTargetValue.set_text(str(r.json()["aboveHyperLimit"])+" %")
         labelInTargetValue.set_text(str(r.json()["timeInRange"])+" %")
         labelBelowTargetValue.set_text(str(r.json()["belowHypoLimit"])+" %")
         labelAverageSgValue.set_text(str(r.json()["averageSG"])+" mg/dl")
      except:
         pass
   

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


@timerSch.event('timer5')
def ttimer5():
   # One shot timer: urequests watchdog
   # Just issue a warning nessage
   global lastErrorMsg
   if lastErrorMsg != None:
      lastErrorMsg.delete()
      lastErrorMsg = None
   lastErrorMsg = M5Msgbox(btns_list=None, x=0, y=0, w=None, h=None)
   lastErrorMsg.set_text("ERROR: urequests is stuck, reset device")


#################################################
#
# Init
#
#################################################

ntp = None
msgbox = None
while ntp == None:
   wait_ms(1000)
   ntp = handle_ntpsync(ntpserver, timezone)
   if ntp == None and msgbox == None:
      msgbox = M5Msgbox(btns_list=None, x=0, y=0, w=None, h=None)
      msgbox.set_text("Trying to synch time and date ...")
if msgbox != None:
   msgbox.delete()

print("Time and date successfully synched")

# Init timers

# Timer 0: 1200 sec (periodic) // ntpsync
TIMER0_PERIOD_S = 1200
timerSch.run('timer0', TIMER0_PERIOD_S*1000, 0x00)

# Timer 1: 10 sec (periodic) // timeupdate
TIMER1_PERIOD_S = 10
timerSch.run('timer1', TIMER1_PERIOD_S*1000, 0x00)

# Timer 2: 60 sec (periodic) // pumpdataupdate
TIMER2_PERIOD_S = 60
timerSch.run('timer2', TIMER2_PERIOD_S*1000, 0x00)

# Timer 3: 0.2 sec (periodic) // touchevent
TIMER3_PERIOD_S = 0.2
timerSch.run('timer3', int(TIMER3_PERIOD_S*1000), 0x00)

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
   
   wait_ms(1000)
