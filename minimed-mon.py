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
#    09/01/2023 - Improve alarm handling
#    12/02/2023 - Add configuration screen
#    12/02/2023 - Fix a regression in AP handling from 0.7 release 
#    17/01/2025 - Adapt to new Carelink data format
#    21/01/2025 - Display system status message
#    11/02/2025 - Adapt alarm handling to new data format
#
#  TODO:
#
#  * Integration of Carelink Client
#  * History graph for recent glucose data
#
#  Copyright 2021-2025, Ondrej Wisniewski
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

VERSION = "1.1"

# Constants
NTPCONST = 946681200 # seconds from 01/01/1970 to 01/01/2000

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
lastAlarmId  = None
lastAlarmMsg = None
lastErrorMsg = None
lastStatusMsg = None
lastApMsg    = None
runNtpsync        = False
runTimeupdate     = False
runPumpdataupdate = False

# Fault ID table
faultIdTable = {
   "002": "Pump Error. Delivery Stopped",
   "006": "Pump Battery Out Limit",
   "007": "Delivery Stopped. Check BG",
   "011": "Replace Pump Battery Now",
   "012": "Auto Suspend Limit Reached. Delivery Stopped",
   "024": "Critical Pump Error. Stop Pump Use. Use Other Treatment",
   "025": "Pump Power Error. Record Settings",
   "029": "Pump Restarted. Delivery Stopped",
   "037": "Pump Motor Error. Delivery Stopped",
   "051": "Bolus Stopped",
   "052": "Delivery Limit Exceeded. Check BG",
   "057": "Pump Battery Not Compatible",
   "058": "Insert A New AA Battery",
   "061": "Pump Button Error. Delivery Stopped",
   "062": "New Notification Received From Pump",
   "066": "No Reservoir Detected During Infusion Set Change",
   "069": "Loading Incomplete During Infusion Set Change",
   "073": "Replace Pump Battery Now",
   "077": "Pump Settings Error. Delivery Stopped",
   "084": "Pump Battery Removed. Replace Battery",
   "100": "Bolus Entry Timed Out Before Delivery",
   "103": "BG Check Reminder",
   "104": "Replace Pump Battery Soon",
   "105": "Reservoir Low. Change Reservoir Soon",
   "107": "Missed Meal Bolus Reminder",
   "109": "Set Change Reminder",
   "110": "Silenced Sensor Alert. Check Alarm History",
   "113": "Reservoir Empty. Change Reservoir Now",
   "117": "Active Insulin Cleared",
   "130": "Rewind Required. Delivery Stopped",
   "140": "Delivery Suspended. Connect Infusion Set",
   "775": "Calibrate Now",
   "776": "Calibration Error",
   "777": "Change Sensor",
   "779": "Recharge Transmitter Now",
   "780": "Lost Sensor Signal",
   "784": "SG Rising Rapidly",
   "794": "Sensor Expired. Change Sensor",
   "795": "Lost Sensor Signal. Check Transmitter",
   "796": "No Sensor Signal",
   "797": "Sensor Connected",
   "801": "Do Not Calibrate. Wait Up To 3 Hours",
   "802": "Low Sensor Glucose",
   "803": "Low Sensor Glucose. Check BG",
   "805": "Alert Before Low. Check BG",
   "807": "Basal Delivery Resumed. Check BG",
   "809": "Suspend On Low. Delivery Stopped. Check BG",
   "810": "Suspend Before Low. Delivery Stopped. Check BG",
   "812": "Call Emergency Assistance",
   "814": "Basal Resumed. SG Still Under Low Limit. Check BG",
   "815": "Low Limit Changed. Basal Manually Resumed. Check BG",
   "816": "High Sensor Glucose",
   "817": "Alert Before High. Check BG",
   "819": "Auto Mode Exit. Basal Delivery Started. BG Required",
   "821": "Minimum Delivery Timeout. BG Required",
   "822": "Maximum Delivery Timeout. BG Required",
   "823": "High Sensor Glucose For Over 1 Hour",
   "827": "Urgent Low Sensor Glucose. Check BG",
   "829": "BG Required",
   "832": "Calibration Required",
   "833": "Correction Bolus Recommended",
   "869": "Calibration Reminder",
   "870": "Recharge Transmitter Soon",
}


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
      lastApMsg = M5Msgbox(btns_list=None, x=0, y=100, w=None, h=None, parent=None)
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
   do_ap_msg("Device configuration needed\nConnect to WIFI network\n%s" %(AP_SSID))
   
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

# Wifi settings
labelWifi        = M5Label('WIFI', x=31, y=0, color=0x09f31a, font=FONT_MONT_20, parent=scr3)
labelSsid        = M5Label('SSID', x=52, y=25, color=0xffffff, font=FONT_MONT_14, parent=scr3)
labelMySsid      = M5Label(wifissid, x=143, y=25, color=0xffffff, font=FONT_MONT_14, parent=scr3)

# Time and date settings
labelTimeAndDate = M5Label('Time and Date', x=31, y=47, color=0x09f31a, font=FONT_MONT_20, parent=scr3)
labelNtpServer   = M5Label('NTP server', x=52, y=75, color=0xffffff, font=FONT_MONT_14, parent=scr3)
labelMyNtpServer = M5Label(ntpserver, x=143, y=75, color=0xffffff, font=FONT_MONT_14, parent=scr3)
labelTimeZone    = M5Label('Time zone', x=52, y=97, color=0xffffff, font=FONT_MONT_14, parent=scr3)
labelMyTimeZone  = M5Label(timezone, x=143, y=97, color=0xffffff, font=FONT_MONT_14, parent=scr3)

# Carelink proxy settings
labelCarelinkProxy = M5Label('Carelink Proxy', x=31, y=124, color=0x09f31a, font=FONT_MONT_20, parent=scr3)
labelIpAddress   = M5Label('IP address', x=52, y=151, color=0xffffff, font=FONT_MONT_14, parent=scr3)
labelMyIpAddress = M5Label(proxyaddr, x=143, y=151, color=0xffffff, font=FONT_MONT_14, parent=scr3)
labelPort        = M5Label('Port', x=52, y=173, color=0xffffff, font=FONT_MONT_14, parent=scr3)
labelMyPort      = M5Label(proxyport, x=143, y=173, color=0xffffff, font=FONT_MONT_14, parent=scr3)

# Screen 3 button
btn0 = M5Btn(text='Reset config', x=110, y=200, w=105, h=34, bg_c=0xff0000, text_c=0xffffff, font=FONT_MONT_14, parent=scr3)
def btn0_wasReleased():
   # delete NVRAM parameters
   nvs.esp32.nvs_erase('wifissid')
   nvs.esp32.nvs_erase('wifipass')
   # Restart
   machine.reset()

btn0.released(btn0_wasReleased)


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


def time_to_calib_progress(cfs,ttc,sst,cst):
   # TODO: check if screen 1 is active
   centerX = 112
   centerY = 17
   radius  = 16
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


def getFaultStr(faultId):
   try:
      faultStr = faultIdTable[faultId]
   except KeyError:
      faultStr = "Unknow error"
   print("faultStr = %s" % faultStr)
   return faultStr


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
      if lastAlarmId != lastAlarm["GUID"]:
         # Check if alarm is recent
         if convert_datetimestr_to_epoch(lastAlarm["dateTime"]) > (time.time() - TDELTA_S):
            # Show alarm message
            msg = getFaultStr(lastAlarm["faultId"])
            if lastAlarmMsg != None:
               lastAlarmMsg.delete()
            lastAlarmMsg = M5Msgbox(btns_list=None, x=0, y=100, w=None, h=None, parent=scr1)
            lastAlarmMsg.set_text(msg)
            
            # Play alarm sound
            if lastAlarm["type"] == "ALARM":
               sndfile = "res/sound_alarm.wav"
            else:
               sndfile = "res/sound_alert.wav"
            speaker.playWAV(sndfile, rate=22000)
         lastAlarmId = lastAlarm["GUID"]
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
   global lastStatusMsg
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
   
   if r != None and r.status_code == 200 and r.json() != "":
      try:
         lastUpdateTm = time.localtime(int(r.json()["lastConduitUpdateServerDateTime"]/1000)) #-NTPCONST)
         
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
         labelBglValue.set_text(str(lastSG) if lastSG > 0 else "--")
         align_text(labelBglValue,"center",90)
         
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
   lastErrorMsg = M5Msgbox(btns_list=None, x=0, y=0, w=None, h=None, parent=scr1)
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
      msgbox = M5Msgbox(btns_list=None, x=0, y=0, w=None, h=None, parent=scr1)
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
