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
#    31/03/2025 - Fix regression bug in DST handling
#    01/09/2026 - Porting to UIFlow2
#
#
#  Copyright 2021-2026, Ondrej Wisniewski
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


import os, sys, io
import M5
from M5 import *
import m5ui
import lvgl as lv

from hardware import Timer
import esp
import machine
import time
import ntptime
import network
import socket
import requests2


#################################################
#
# Constants
#
#################################################

VERSION = "2.0.beta"

# Default configuration parameters
DEFAULT_NTP_SERVER = "pool.ntp.org"
DEFAULT_TIME_ZONE  = 1
DEFAULT_PROXY_PORT = 8081

# Access point parameters
API_URL     = "carelink/nohistory"
AP_SSID     = "M5_MINIMED_MON"
AP_ADDR     = "192.168.4.1"

TIMER0_PERIOD_S = 1200
TIMER1_PERIOD_S = 10
TIMER2_PERIOD_S = 60
TIMER3_PERIOD_S = 10


#################################################
#
# Global variables
#
#################################################

# Pages
page0 = None
page1 = None
page2 = None
page3 = None

# Images
imageBattery = None
imageReservoir = None
imageSensorConn = None
imageDrop = None
imageSage = None
imageShield = None
imageBanner = None

# Labels
labelBglValue = None
labelBglUnit = None
labelActInsValue = None
labelActIns = None
labelTime = None
labelLastData = None

# Timers
timer0 = None
timer1 = None
timer2 = None
timer3 = None

# Other
dstDelta      = 0
lastUpdateTm  = 0
lastAlarmId   = None
lastAlarmMsg  = None
lastErrorMsg  = None
lastStatusMsg = None
lastApMsg     = None
runNtpsync        = False
runTimeupdate     = False
runPumpdataupdate = False


# Fault ID mapping
faultIdMapping = {
   "002": "002",
   "003": "002",
   "004": "002",
   "013": "002",
   "014": "002",
   "015": "002",
   "016": "002",
   "017": "002",
   "018": "002",
   "019": "002",
   "020": "002",
   "022": "002",
   "023": "002",
   "026": "002",
   "027": "002",
   "028": "002",
   "030": "002",
   "031": "002",
   "033": "002",
   "034": "002",
   "044": "002",
   "045": "002",
   "046": "002",
   "049": "002",
   "053": "002",
   "054": "002",
   "060": "002",
   "063": "002",
   "064": "002",
   "065": "002",
   "067": "002",
   "068": "002",
   "074": "002",
   "075": "002",
   "076": "002",
   "079": "002",
   "080": "002",
   "081": "002",
   "082": "002",
   "117": "117",
   "817": "817",
   "805": "805",
   "819": "819",
   "820": "819",
   "012": "012",
   "807": "807",
   "808": "807",
   "814": "814",
   "103": "103",
   "829": "829",
   "830": "829",
   "831": "829",
   "100": "100",
   "051": "051",
   "775": "775",
   "776": "776",
   "869": "869",
   "832": "832",
   "812": "812",
   "777": "777",
   "778": "777",
   "789": "777",
   "833": "833",
   "024": "024",
   "035": "024",
   "040": "024",
   "047": "024",
   "048": "024",
   "050": "024",
   "055": "024",
   "131": "024",
   "052": "052",
   "007": "007",
   "008": "007",
   "140": "140",
   "801": "801",
   "816": "816",
   "823": "823",
   "824": "823",
   "058": "058",
   "069": "069",
   "780": "780",
   "781": "780",
   "795": "795",
   "815": "815",
   "802": "802",
   "803": "803",
   "822": "822",
   "821": "821",
   "107": "107",
   "066": "066",
   "796": "796",
   "057": "057",
   "006": "006",
   "084": "084",
   "061": "061",
   "037": "037",
   "038": "037",
   "039": "037",
   "041": "037",
   "042": "037",
   "043": "037",
   "025": "025",
   "029": "029",
   "077": "077",
   "779": "779",
   "870": "870",
   "011": "011",
   "073": "011",
   "104": "104",
   "113": "113",
   "105": "105",
   "106": "105",
   "130": "130",
   "797": "797",
   "798": "797",
   "794": "794",
   "109": "109",
   "784": "784",
   "110": "110",
   "810": "810",
   "811": "810",
   "809": "809",
   "062": "062",
   "070": "062",
   "071": "062",
   "072": "062",
   "108": "062",
   "114": "062",
   "786": "062",
   "787": "062",
   "788": "062",
   "799": "062",
   "806": "062",
   "825": "062",
   "828": "062",
   "827": "827",
}

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
      lastApMsg = m5ui.M5Msgbox(title=msg, x=0, y=100, w=320, h=50, parent=page0)
      #lastApMsg.set_text(msg)
      sndfile = "/flash/res/audio/sound_alert.wav"
      Speaker.playWavFile(sndfile)


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

   # Write config data to EEPROM
   nvs = esp32.NVS("mmmon")

   nvs.set_str('wifissid',  wifissid.strip())
   time.sleep_ms(100)

   nvs.set_str('wifipass',  wifipass.strip())
   time.sleep_ms(100)

   nvs.set_str('ntpserver', ntpserver.strip())
   time.sleep_ms(100)

   try:
      nvs.set_i8('timezone', int(timezone))
   except:
      print("invalid time zone, saving default")
      nvs.set_i8('timezone', DEFAULT_TIME_ZONE)
   time.sleep_ms(100)

   nvs.set_str('proxyaddr', proxyaddr.strip())
   time.sleep_ms(100)

   try:
      nvs.set_u16('proxyport', int(proxyport))
   except:
      print("invalid proxy port, saving default")
      nvs.set_u16(DEFAULT_PROXY_PORT)
   time.sleep_ms(100)

   nvs.commit()
   print("New configuration parameters stored in EEPROM\n")
   print("wifissid: %s, wifipass: %s, proxyaddr: %s, proxyport: %s, ntpserver: %s, timezone: %s\n" % (wifissid,wifipass,proxyaddr,proxyport,ntpserver,timezone))
   do_ap_msg("New configuration parameters stored in EEPROM\nResetting device ...")

   # Reset device
   time.sleep_ms(8000)
   machine.reset()


#################################################
#
# Access configuration parameters
#
#################################################

def read_config():
   # Try to read config from EEPROM
   nvs = esp32.NVS("mmmon")
   try:
      wifissid  = nvs.get_str('wifissid')
      wifipass  = nvs.get_str('wifipass')
      ntpserver = nvs.get_str('ntpserver')
      tz_int  = nvs.get_i8('timezone')
      if tz_int < 0:
         timezone = "GMT%d" % tz_int
      else:
         timezone = "GMT+%d" % tz_int
      proxyaddr = nvs.get_str('proxyaddr')
      proxyport = str(nvs.get_u16('proxyport'))
   except OSError:
      print("Needed configuration parameters not found in EEPROM\n")
      # Start access point for configuration
      do_access_point(DEFAULT_NTP_SERVER,DEFAULT_TIME_ZONE,DEFAULT_PROXY_PORT)

   return (wifissid,wifipass,proxyaddr,proxyport,ntpserver,timezone)


#################################################
#
# WIFI connection handling
#
#################################################

def wlan_connect(wifissid, wifipass):
   # Try to connect to WIFI network
   print("connecting Wifi")
   wlan = network.WLAN(network.STA_IF)
   wlan.active(True)
   wlan.connect(wifissid, wifipass)
   ctimeout=0
   while not wlan.isconnected():
      time.sleep_ms(1000)
      ctimeout += 1
      if ctimeout > 5:
         break
   if not wlan.isconnected():
      wlan.active(False)
      print("Failed to connect to WIFI network %s\n" % (wifissid))
      # Start access point for configuration
      do_access_point(DEFAULT_NTP_SERVER,DEFAULT_TIME_ZONE,DEFAULT_PROXY_PORT)
   else:
     print("Wifi connected (IP %s, GW %s)" % (wlan.ifconfig()[0], wlan.ifconfig()[2]))


#################################################
#
# Helper functions
#
#################################################

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

def time_delta():
   global lastUpdateTm
   global dstDelta
   
   if lastUpdateTm > 0:
      dt_min = (time.time() - lastUpdateTm)//60
      if dt_min == 0:
         dt_txt = "Now"
      elif dt_min > 15:
         dt_txt = "No data"
      else:
         dt_txt = str(dt_min)+" min ago"
   else:
      dt_txt = "---"
   return dt_txt


#################################################
#
# Alarm handling functions
#
#################################################

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
      faultStr = faultIdTable[faultIdMapping[faultId]]
   except KeyError:
      faultStr = "Unknow error code %s" % faultId
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
      print("check for recent alarm")
      # Check for new alarm
      if lastAlarmId != lastAlarm["GUID"]:
         # Check if alarm is recent
         if convert_datetimestr_to_epoch(lastAlarm["dateTime"]) > (time.time() - TDELTA_S):
            # Show alarm message
            msg = getFaultStr(lastAlarm["faultId"])
            if lastAlarmMsg != None:
               lastAlarmMsg.delete()
            lastAlarmMsg = m5ui.M5Msgbox(title=msg, x=0, y=100, w=320, h=40, parent=page1)
            #lastAlarmMsg.set_text(msg)

            # Play alarm sound
            if lastAlarm["type"] == "ALARM":
               sndfile = "/flash/res/audio/sound_alarm.wav"
            else:
               sndfile = "/flash/res/audio/sound_alert.wav"
            Speaker.playWavFile(sndfile)
         lastAlarmId = lastAlarm["GUID"]
   except:
      pass


#################################################
#
# Time update handler
#
#################################################

def handle_ntpsync(ntpserver):
   # Sync local time via NTP
   print("sync local time")
   ntptime.host = ntpserver
   ntptime.settime()

def handle_timeupdate():
   global labelTime
   global labelLastData
   global dstDelta

   try:
      # Update time on screen
      print("update time on screen")
      now = time.time() + dstDelta*3600
      timestr = ("%02d:%02d") % (time.localtime(now)[3:5])
      labelTime.set_text(timestr)
      labelTime.align_to(page1, lv.ALIGN.TOP_RIGHT, 0, 0)
      labelLastData.set_text(time_delta())
      labelLastData.align_to(page1, lv.ALIGN.BOTTOM_MID, 0, 0)
      #align_text(labelLastData,"center",218)
   except:
      pass
    

#################################################
#
# Pump data update handler
#
#################################################

def handle_pumpdataupdate(proxyaddr, proxyport):
   global page1, page1, page2, imageBattery, imageReservoir, imageSensorConn, imageDrop, imageSage, imageShield, imageBanner, labelBglValue, labelBglUnit, labelActInsValue, labelActIns, labelTime, labelLastData, labelSage, timer0, timer1, timer2, timer3
   global lastErrorMsg
   global lastStatusMsg
   global lastUpdateTm
   global dstDelta
   proxy_url = "http://%s:%s/%s" % (proxyaddr, proxyport, API_URL)

   # Update Minimed data
   print("update Minimed data")
   
   # Get Minimed data from proxy via API
   try:
      r = requests2.get(proxy_url, headers={'Content-Type': 'application/json'}, timeout=20)
      jdata = r.json()
      print("status code: %d" % (r.status_code))
   except:
      r = None
   
   if r != None and r.status_code == 200 and jdata != "":
      try:
         lastUpdateTm = int(jdata["lastConduitUpdateServerDateTime"]//1000)
         # Check for DST
         dstDelta = 1 if jdata["clientTimeZoneName"].lower().find("summer")>-1 else 0
         print("dstDelta: %d" % dstDelta)
         
         # Check for alarm notification
         handle_alarm(jdata["lastAlarm"])
         
         # Check conduit, medical device in range
         haveData = jdata["conduitInRange"] and jdata["conduitMedicalDeviceInRange"]

         ##### Screen 1 #####
         
         if haveData:
            imageBattery.set_image("/flash/res/img/mm_batt"+str(jdata["pumpBatteryLevelPercent"])+".png")
            imageReservoir.set_image("/flash/res/img/mm_tank"+str(reservoir_level(jdata["reservoirRemainingUnits"]))+".png")
            imageSage.set_image("/flash/res/img/mm_sage_"+sensor_age_icon(jdata["sensorDurationHours"],jdata["sensorState"])+".png")
            labelSage.set_text(sensor_age_text(jdata["sensorDurationHours"]))
         else:
            imageBattery.set_image("/flash/res/img/mm_batt_unk.png")
            imageReservoir.set_image("/flash/res/img/mm_tank_unk.png")
            imageSage.set_image("/flash/res/img/mm_sage_unk.png")
            labelSage.set_text("")
         
         if jdata["conduitSensorInRange"]:
            imageSensorConn.set_image("/flash/res/img/mm_sensor_connection_ok.png")
         else:
            imageSensorConn.set_image("/flash/res/img/mm_sensor_connection_nok.png")
         
         #time_to_calib_progress(jdata["calFreeSensor"],jdata["timeToNextCalibHours"],jdata["sensorState"],jdata["calibStatus"])

         if not haveData or jdata["therapyAlgorithmState"]["autoModeShieldState"] == "FEATURE_OFF":
            imageShield.set_flag(lv.obj.FLAG.HIDDEN, True)
         else:
            imageShield.set_image("/flash/res/img/mm_shield_"+jdata["lastSGTrend"].lower()+".png")
            imageShield.set_flag(lv.obj.FLAG.HIDDEN, False)
         lastSG = jdata["lastSG"]["sg"]
         labelBglValue.set_text(str(lastSG) if lastSG > 0 else "--")
         labelBglValue.align_to(page1, lv.ALIGN.CENTER, 0, 0)
         #align_text(labelBglValue,"center",90)
         
         if haveData:
            labelActInsValue.set_text(str(round(jdata["activeInsulin"]["amount"],1))+" U")
         else:
            labelActInsValue.set_text("-- U")
         labelActInsValue.align_to(page1, lv.ALIGN.TOP_RIGHT, 0, 173)
         #align_text(labelActInsValue,"right",173)
      except:
         pass
      
      try:
         systemStatus = jdata["systemStatusMessage"]
         if systemStatus == "NO_ERROR_MESSAGE" or systemStatus == None:
            raise Exception
         else:
            if lastStatusMsg == None:
               status_txt = systemStatus.replace("_"," ")
               lastStatusMsg = m5ui.M5Msgbox(title = status_txt, x=0, y=50, w=320, h=40, parent=page1)
            #lastStatusMsg.set_text(systemStatus.replace("_"," "))
      except:
         if lastStatusMsg != None:
            lastStatusMsg.delete()
            lastStatusMsg = None

      try:
         pumpBanner = jdata["pumpBannerState"][0]["type"]
         imageBanner.set_image("/flash/res/img/mm_banner_"+pumpBanner.lower()+".png")
         imageBanner.set_flag(lv.obj.FLAG.HIDDEN, False)
      except:
         imageBanner.set_flag(lv.obj.FLAG.HIDDEN, True)

      ##### Screen 2 #####
      try:
         labelAboveTargetValue.set_text(str(jdata["aboveHyperLimit"])+" %")
         labelInTargetValue.set_text(str(jdata["timeInRange"])+" %")
         labelBelowTargetValue.set_text(str(jdata["belowHypoLimit"])+" %")
         labelAverageSgValue.set_text(str(jdata["averageSG"])+" mg/dl")
      except:
         pass


#################################################
#
# Button event handlers
#
#################################################

def btnA_wasPressed_event(state):
   global page1
   page1.screen_load()

def btnB_wasPressed_event(state):
   global page1
   page2.screen_load()

def btnC_wasPressed_event(state):
   global page2
   page3.screen_load()

def btn0_event_handler(event_struct):
   event = event_struct.code
   print("btn0 event: %d" % event)
   if event == lv.EVENT.RELEASED:
      # delete NVRAM parameters
      print("delete NVRAM parameters")
      nvs = esp32.NVS("mmmon")
      nvs.erase_key('wifissid')
      nvs.erase_key('wifipass')
      nvs.commit()
      # Restart
      print("restarting ...")
      machine.reset()


#################################################
#
# Page event handlers
#
#################################################

def page_event_handler(event_struct):
   event = event_struct.code
   print("page event: %d" % event)
   if event == lv.EVENT.PRESSED:
      M5.Lcd.setBrightness(100)
      timer3.init(mode=Timer.ONE_SHOT, period=TIMER3_PERIOD_S*1000, callback=timer3_cb)
   return


#################################################
#
# Timer event handlers
#
#################################################

def timer0_cb(t):
   global runNtpsync
   runNtpsync = True
   print("timer0")

def timer1_cb(t):
   global runTimeupdate
   runTimeupdate = True
   print("timer1")

def timer2_cb(t):
   global runPumpdataupdate
   runPumpdataupdate = True
   print("timer2")

def timer3_cb(t):
   M5.Lcd.setBrightness(50)
   print("timer3")


#################################################
#
# Initialization
#
#################################################

def setup():
   global page0, page1, page2, page3, imageBattery, imageReservoir, imageSensorConn, imageDrop, imageSage, imageShield, imageBanner, labelBglValue, labelBglUnit, labelActInsValue, labelActIns, labelTime, labelLastData, labelSage, labelAboveTargetValue, labelInTargetValue, labelBelowTargetValue, labelAverageSgValue, timer0, timer1, timer2, timer3

   global ntpserver
   global proxyaddr
   global proxyport

   M5.begin()
   m5ui.init()

   # Create and load initial page
   page0 = m5ui.M5Page(bg_c=0x000000)
   page0.screen_load()
  
   # Read config from EEPROM
   wifissid,wifipass,proxyaddr,proxyport,ntpserver,timezone = read_config()
   print("wifissid: %s, wifipass: %s, proxyaddr: %s, proxyport: %s, ntpserver: %s, timezone: %s\n" % (wifissid,wifipass,proxyaddr,proxyport,ntpserver,timezone))

   # Wifi connection
   wlan_connect(wifissid, wifipass)

   # Create pages
   page1 = m5ui.M5Page(bg_c=0x000000)
   page2 = m5ui.M5Page(bg_c=0x000000)
   page3 = m5ui.M5Page(bg_c=0x000000)
   M5.Lcd.setBrightness(50)

   # Images on page 1
   imageBattery     = m5ui.M5Image("/flash/res/img/mm_batt_unk.png", x=6, y=0, rotation=0, scale_x=1, scale_y=1, parent=page1)
   imageReservoir   = m5ui.M5Image("/flash/res/img/mm_tank_unk.png", x=40, y=0, rotation=0, scale_x=1, scale_y=1, parent=page1)
   imageSensorConn  = m5ui.M5Image("/flash/res/img/mm_sensor_connection_nok.png", x=68, y=0, rotation=0, scale_x=1, scale_y=1, parent=page1)
   imageDrop        = m5ui.M5Image("/flash/res/img/mm_drop_unk.png", x=105, y=8, rotation=0, scale_x=1, scale_y=1, parent=page1)
   imageSage        = m5ui.M5Image("/flash/res/img/mm_sage_unk.png", x=135, y=0, rotation=0, scale_x=1, scale_y=1, parent=page1)
   imageShield      = m5ui.M5Image("/flash/res/img/mm_shield_none.png", x=65, y=33, rotation=0, scale_x=1, scale_y=1, parent=page1)
   imageBanner      = m5ui.M5Image("/flash/res/img/mm_banner_delivery_suspend.png", x=40, y=145, rotation=0, scale_x=1, scale_y=1, parent=page1)

   # Labels on page 1
   labelBglValue    = m5ui.M5Label("--", x=140, y=90, text_c=0xffffff, bg_c=0xffffff, bg_opa=0, font=lv.font_montserrat_48, parent=page1)
   labelBglUnit     = m5ui.M5Label("mg/dL", x=133, y=145, text_c=0xffffff, bg_c=0x89abeb, bg_opa=0, font=lv.font_montserrat_16, parent=page1)
   labelActInsValue = m5ui.M5Label("-- U", x=274, y=163, text_c=0xffffff, bg_c=0xffffff, bg_opa=0, font=lv.font_montserrat_24, parent=page1)
   labelActIns      = m5ui.M5Label("Act Insulin", x=232, y=200, text_c=0xffffff, bg_c=0xffffff, bg_opa=0, font=lv.font_montserrat_16, parent=page1)
   labelTime        = m5ui.M5Label("--:--", x=276, y=0, text_c=0xffffff, bg_c=0xffffff, bg_opa=0, font=lv.font_montserrat_24, parent=page1)
   labelLastData    = m5ui.M5Label("--", x=150, y=211, text_c=0xffffff, bg_c=0xffffff, bg_opa=0, font=lv.font_montserrat_24, parent=page1)
   labelSage        = m5ui.M5Label('', x=144, y=8, text_c=0xffffff, bg_c=0xffffff, bg_opa=0, font=lv.font_montserrat_14, parent=page1)

   # Labels on page 2
   labelScreen2Title     = m5ui.M5Label('In target range (last 24h)', x=9, y=0, text_c=0xffffff, font=lv.font_montserrat_24, parent=page2)
   labelAboveTarget      = m5ui.M5Label('Above target 180 mg/dl:', x=9, y=60, text_c=0xffc418, font=lv.font_montserrat_18, parent=page2)
   labelInTarget         = m5ui.M5Label('In target:', x=9, y=90, text_c=0x45db49, font=lv.font_montserrat_18, parent=page2)
   labelBelowTarget      = m5ui.M5Label('Below target 70 mg/dl:', x=9, y=119, text_c=0xff0000, font=lv.font_montserrat_18, parent=page2)
   labelAgerageSg        = m5ui.M5Label('Average SG:', x=9, y=147, text_c=0xa0a0a0, font=lv.font_montserrat_18, parent=page2)
   labelAboveTargetValue = m5ui.M5Label('-- %', x=252, y=60, text_c=0xffffff, font=lv.font_montserrat_18, parent=page2)
   labelInTargetValue    = m5ui.M5Label('-- %', x=252, y=90, text_c=0xffffff, font=lv.font_montserrat_18, parent=page2)
   labelBelowTargetValue = m5ui.M5Label('-- %', x=252, y=119, text_c=0xffffff, font=lv.font_montserrat_18, parent=page2)
   labelAverageSgValue   = m5ui.M5Label('-- mg/dl', x=231, y=147, text_c=0xffffff, font=lv.font_montserrat_18, parent=page2)

   # Labels on page 3

   # Wifi settings
   labelWifi        = m5ui.M5Label('WIFI', x=31, y=0, text_c=0x09f31a, font=lv.font_montserrat_18, parent=page3)
   labelSsid        = m5ui.M5Label('SSID', x=52, y=25, text_c=0xffffff, font=lv.font_montserrat_14, parent=page3)
   labelMySsid      = m5ui.M5Label(wifissid, x=143, y=25, text_c=0xffffff, font=lv.font_montserrat_14, parent=page3)

   # Time and date settings
   labelTimeAndDate = m5ui.M5Label('Time and Date', x=31, y=47, text_c=0x09f31a, font=lv.font_montserrat_18, parent=page3)
   labelNtpServer   = m5ui.M5Label('NTP server', x=52, y=75, text_c=0xffffff, font=lv.font_montserrat_14, parent=page3)
   labelMyNtpServer = m5ui.M5Label(ntpserver, x=143, y=75, text_c=0xffffff, font=lv.font_montserrat_14, parent=page3)
   labelTimeZone    = m5ui.M5Label('Time zone', x=52, y=97, text_c=0xffffff, font=lv.font_montserrat_14, parent=page3)
   labelMyTimeZone  = m5ui.M5Label(timezone, x=143, y=97, text_c=0xffffff, font=lv.font_montserrat_14, parent=page3)

   # Carelink proxy settings
   labelCarelinkProxy = m5ui.M5Label('Carelink Proxy', x=31, y=124, text_c=0x09f31a, font=lv.font_montserrat_18, parent=page3)
   labelIpAddress   = m5ui.M5Label('IP address', x=52, y=151, text_c=0xffffff, font=lv.font_montserrat_14, parent=page3)
   labelMyIpAddress = m5ui.M5Label(proxyaddr, x=143, y=151, text_c=0xffffff, font=lv.font_montserrat_14, parent=page3)
   labelPort        = m5ui.M5Label('Port', x=52, y=173, text_c=0xffffff, font=lv.font_montserrat_14, parent=page3)
   labelMyPort      = m5ui.M5Label(proxyport, x=143, y=173, text_c=0xffffff, font=lv.font_montserrat_14, parent=page3)

   # Button on page 3
   btn0 = m5ui.M5Button(text='Reset config', x=110, y=200, bg_c=0xff0000, text_c=0xffffff, font=lv.font_montserrat_14, parent=page3)
   btn0.add_event_cb(btn0_event_handler, lv.EVENT.RELEASED, None)

   # Init button event handlers
   BtnA.setCallback(type=BtnA.CB_TYPE.WAS_PRESSED, cb=btnA_wasPressed_event)
   BtnB.setCallback(type=BtnB.CB_TYPE.WAS_PRESSED, cb=btnB_wasPressed_event)
   BtnC.setCallback(type=BtnC.CB_TYPE.WAS_PRESSED, cb=btnC_wasPressed_event)

   # Init timers

   # Periodic timer: sync time via NTP
   timer0 = Timer(0)
   timer0.init(mode=Timer.PERIODIC, period=TIMER0_PERIOD_S*1000, callback=timer0_cb)

   # Periodic timer: update time on screen
   timer1 = Timer(1)
   timer1.init(mode=Timer.PERIODIC, period=TIMER1_PERIOD_S*1000, callback=timer1_cb)

   # Periodic timer: update pump data on screen
   timer2 = Timer(2)
   timer2.init(mode=Timer.PERIODIC, period=TIMER2_PERIOD_S*1000, callback=timer2_cb)

   # Oneshot timer: reset screen brightness
   timer3 = Timer(3)

   # Init touch event detection for all pages
   page1.add_event_cb(page_event_handler, lv.EVENT.PRESSED, None)
   page2.add_event_cb(page_event_handler, lv.EVENT.PRESSED, None)
   page3.add_event_cb(page_event_handler, lv.EVENT.PRESSED, None)

   # Init time and date
   time.timezone(timezone)
   handle_ntpsync(ntpserver)
   handle_timeupdate()

   # Get first data from pump
   handle_pumpdataupdate(proxyaddr, proxyport)

   # Load page 1
   page1.screen_load()


#################################################
#
# Main loop
#
#################################################

def loop():
   global proxyaddr
   global proxyport
   global ntpserver
   global runNtpsync
   global runTimeupdate
   global runPumpdataupdate

   M5.update()

   # Run handlers as requested
   if runPumpdataupdate:
      handle_pumpdataupdate(proxyaddr, proxyport)
      runPumpdataupdate = False
   if runNtpsync:
      handle_ntpsync(ntpserver)
      runNtpsync = False
   if runTimeupdate:
      handle_timeupdate()
      runTimeupdate = False
  

#################################################
#
# Program entrypoint
#
#################################################

if __name__ == '__main__':
   try:
      setup()
      while True:
         loop()
   except (Exception, KeyboardInterrupt) as e:
      try:
         m5ui.deinit()
         from utility import print_error_msg
         print_error_msg(e)
      except ImportError:
         print("please update to latest firmware")
