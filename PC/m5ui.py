#################################################
#
# Wrapper classes for M5UI libs
#
#################################################

from tkinter import *
import lvgl as lv

SCREEN_WIDTH  = 320
SCREEN_HEIGHT = 240
SCREEN_BORDER = 20
ICON_FILE = "res/png/icon_mmm.png"


class M5Page:
   def __init__(self,bg_c,icon=ICON_FILE):
      self.window = Tk()
      self.window.config(width=SCREEN_WIDTH+SCREEN_BORDER,height=SCREEN_HEIGHT+SCREEN_BORDER)
      self.window.configure(bg='black')
      self.window.title("Minimed Mon PC")
      self.window.resizable(False, False)
      if icon != None:
         self.window.iconphoto(False, PhotoImage(file=icon))
      self.scr = Canvas(self.window, width=SCREEN_WIDTH,height=SCREEN_HEIGHT,bg='black',highlightthickness=0)
      #self.scr.pack()
      self.scr.place(relx=0.5, rely=0.5, anchor=CENTER)
   def screen_load(self):
      pass
   def set_screen_bg_color(self, color):
      self.window.configure(bg=color)
      self.scr.configure(bg=color)
   def set_screen_brightness(self, brightness):
      pass
   def update(self):
      self.window.update()

class M5Image:
   def __init__(self, img_file, x, y, rotation, scale_x, scale_y, parent):
      self.img = PhotoImage(file=img_file)
      self.scr = parent.scr
      self.img_h = self.scr.create_image(x,y,anchor=NW,image=self.img)
   def set_flag(self,flag,val):
      if flag == lv.obj.FLAG.HIDDEN:
         if val:
            self.scr.itemconfig(self.img_h, state='hidden')
         else:
            self.scr.itemconfig(self.img_h, state='normal')
   def set_image(self, img_file):
      self.img = PhotoImage(file=img_file)
      self.scr.itemconfig(self.img_h,image=self.img)
   def set_pos(self, x, y):
      pass

class M5Label:
   def __init__(self, text, x, y, text_c, bg_c, bg_opa, font, parent):
      self.scr = parent.scr
      self.x = x
      self.y = y
      self.txt_h = self.scr.create_text(x,y,anchor=NW,text=text,fill="#%06X" % (text_c),font=(font))
   def set_text(self, text):
      self.scr.itemconfig(self.txt_h,text=text)
   def align_to(self, parent, pos, off_x, off_y):
      if pos == lv.ALIGN.CENTER:
         self.scr.coords(self.txt_h,SCREEN_WIDTH/2,SCREEN_HEIGHT/2)
         self.scr.itemconfig(self.txt_h,anchor="center")
      elif pos == lv.ALIGN.TOP_RIGHT:
         self.scr.coords(self.txt_h,SCREEN_WIDTH,off_y)
         self.scr.itemconfig(self.txt_h,anchor="ne")
      elif pos == lv.ALIGN.BOTTOM_MID:
         self.scr.coords(self.txt_h,SCREEN_WIDTH/2,SCREEN_HEIGHT)
         self.scr.itemconfig(self.txt_h,anchor="s")
   def set_pos(self, x, y):
      self.scr.coords(self.txt_h,x,y)
   def get_width(self):
      bounds = self.scr.bbox(self.txt_h)
      return bounds[2] - bounds[0]
   def get_height(self):
      bounds = self.scr.bbox(self.txt_h)
      return bounds[3] - bounds[1]
   def set_flag(self,flag,val):
      if flag == lv.obj.FLAG.HIDDEN:
         if val:
            self.scr.itemconfig(self.txt_h, state='hidden')
         else:
            self.scr.itemconfig(self.txt_h, state='normal')
   def set_bg_color(self, color, opa, flags):
      # TODO
      pass

class M5Msgbox:
   def __init__(self,title, x, y, w, h, parent):
      self.scr = parent.scr
      self.x1 = x
      self.y1 = y
      self.x2 = x+w if w != None else SCREEN_WIDTH-x
      self.y2 = y+h if h != None else y+30
      self.rect_h = self.scr.create_rectangle(x,y,self.x2,self.y2,fill="white",outline="white")
      self.text_h = self.scr.create_text(SCREEN_WIDTH/2,self.y1+20,fill="grey",text=title,font=lv.font_montserrat_16,width=self.x2-self.x1,justify="left")
      #self.title = self.scr.itemconfig(self.text_h,text=title)
   def set_title(self, title):
      self.scr.itemconfig(self.text_h,text=title)
   def delete(self):
      self.scr.delete(self.text_h)
      self.scr.delete(self.rect_h)

def init():
   pass

def deinit():
   pass

