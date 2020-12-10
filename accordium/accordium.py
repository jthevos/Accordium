from music3 import *
from osc import *
from gui import *
import re


# Forget about the play button. Too simple. one sentence MAYBE.
# Dx7 is fine.
#
#
# Perfect the image -> accordium
# Add a legend point out where A4 is.
# Perhaps switch to clockwise instead of counterclock
# Secular Piano?



class Accordium():

   """
   This class is the first prototype of a new compositional assistive
   tool. This tool takes a color wheel containing 12 hues (pure color),
   tints (add white), tones (add grey), and shades (add black).

   This tool uses 12 tone equal temperment as the musical basis.

   The musical pitch of a color is controled using a dictionary with
   a three tuple as a key.
   """

   def __init__(self, instrument, image):

      self.img = Icon(image)
      self.img_width = self.img.getWidth()
      self.img_height = self.img.getHeight()


      self.display = Display("Synaesthetic", self.img_width, self.img_height)
      self.display.drawImage(image, 0, 0)
      self.display.showMouseCoordinates()

      # setup OSC
      self.osc_in = OscIn(1337)
      self.osc_in.onInput("/.*", self.handle_osc_message)
      self.osc_in.hideMessages()

      # the color mapping dictionary is ugly
      # for this reason, we take its declaration out of the constructor
      self.color_mapping = self.initialize_color_mapping()

      # Now that the mapping dictionary has been created, finish the initialization
      self.instrument = instrument
      self.initialize_instrument()
      self.initialize_user_feedback_system()

      # testing handlers, to be deleted
      self.display.onMouseClick(self.__sonify_click__)
      self.display.onMouseDrag(self.__sonify_drag__)
      self.display.onKeyType(self.__stop_sound__)


   ##### User Feedback System Functions #####
   def initialize_user_feedback_system(self):
      """
      This feedback system consists of 5 black circles which correspond
      to the 5 available touch points coming from our MultiXY OSC controller.

      It uses 5 timers to control these circles. After a specified time, the
      circles disappear if they are unnused.

      Each tracker has its own timer and hide function.
      """

      self.innactivity_time = 2000   # in milliseconds

      # initialize the timers, they will be started when a touch event occurs
      self.timer1 = Timer(self.innactivity_time, self.hide_tracker_1, [], False)
      self.timer2 = Timer(self.innactivity_time, self.hide_tracker_2, [], False)
      self.timer3 = Timer(self.innactivity_time, self.hide_tracker_3, [], False)
      self.timer4 = Timer(self.innactivity_time, self.hide_tracker_4, [], False)
      self.timer5 = Timer(self.innactivity_time, self.hide_tracker_5, [], False)

      # initialize the visiable trackers
      self.tracker1 = Circle(0, 0, 5, Color.BLACK, True)
      self.tracker2 = Circle(0, 0, 5, Color.BLACK, True)
      self.tracker3 = Circle(0, 0, 5, Color.BLACK, True)
      self.tracker4 = Circle(0, 0, 5, Color.BLACK, True)
      self.tracker5 = Circle(0, 0, 5, Color.BLACK, True)

      # add the trackers to the display
      self.display.add(self.tracker1)
      self.display.add(self.tracker2)
      self.display.add(self.tracker3)
      self.display.add(self.tracker4)
      self.display.add(self.tracker5)

      # hide the trackers until a touch event occurs
      self.tracker1.hide()
      self.tracker2.hide()
      self.tracker3.hide()
      self.tracker4.hide()
      self.tracker5.hide()


   def hide_tracker_1(self):
      self.tracker1.hide()
      self.timer1.stop()
      self.instrument.setVolume(0, 1)  # mute first voice


   def hide_tracker_2(self):
      self.tracker2.hide()
      self.timer2.stop()
      self.instrument.setVolume(0, 2)  # mute second voice


   def hide_tracker_3(self):
      self.tracker3.hide()
      self.timer3.stop()
      self.instrument.setVolume(0, 3)  # mute third voice


   def hide_tracker_4(self):
      self.tracker4.hide()
      self.timer4.stop()
      self.instrument.setVolume(0, 4)  # mute fourth voice


   def hide_tracker_5(self):
      self.tracker5.hide()
      self.timer5.stop()
      self.instrument.setVolume(0, 5)  # mute fifth voice
   ##### End Feedback System Functions #####


   ##### Initialization Functions #####
   def initialize_instrument(self):
      """
      Start five voices and set their volumes to 0.

      Becuase five timers and trackers are running independently,
      we start voices 1,2,3,4,5 (not 0,1,2,3,4) for code readability.
      """

      for i in range(1, 6):
         self.instrument.start(i)
         self.instrument.setVolume(0,i)


   def initialize_color_mapping(self):
      """
      # remember these are slightly modified for usability and do not
      # follow natural register increases based on luminosity

      # yellows are an issue. There a several color combos.
      # perhaps we should computer generate the image?
      """
      return {
           (216,14,45)    :   ("red_hue",             A2),
           (227,92,80)    :   ("red_tint",            A3),
           (170,8,34)     :   ("red_tone",            A4),
           (141,4,21)     :   ("red_shade",           A5),
           (228,88,50)    :   ("red_orange_hue",      BF2),
           (236,136,98)   :   ("red_orange_tint",     BF3),
           (179,69,36)    :   ("red_orange_tone",     BF4),
           (149,57,25)    :   ("red_orange_shade",    BF5),
           (239,163,52)   :   ("orange_hue",          B2),
           (243,174,80)   :   ("orange_tint",         B3),
           (188,130,39)   :   ("orange_tone",         B4),
           (157,109,28)   :   ("orange_shade",        B5),
           (249,217,52)   :   ("yellow_orange_hue",   C3),
           (250,225,110)  :   ("yellow_orange_tint",  C4),
           (194,173,41)   :   ("yellow_orange_tone",  C5),
           (163,146,32)   :   ("yellow_orange_shade", C6),
           (251,253,59)   :   ("yellow_hue",          DF3),
           (252,251,119)  :   ("yellow_tint",         DF4),
           (202,199,44)   :   ("yellow_tone",         DF5),
           (169,169,37)   :   ("yellow_shade",        DF6),
           (150,211,88)   :   ("yellow_green_hue",    D3),
           (182,223,135)  :   ("yellow_green_tint",   D4),
           (117,170,68)   :   ("yellow_green_tone",   D5),
           (96,143,56)    :   ("yellow_green_shade",  D6),
           (45,178,81)    :   ("green_hue",           EF3),
           (139,198,139)  :   ("green_tint",          EF4),
           (34,145,64)    :   ("green_tone",          EF5),
           (28,124,55)    :   ("green_shade",         EF6),
           (36,191,136)   :   ("blue_green_hue",      E3),
           (80,200,156)   :   ("blue_green_tint",     E4),
           (28,154,110)   :   ("blue_green_tone",     E5),
           (24,132,93)    :   ("blue_green_shade",    E6),
           (19,85,160)    :   ("blue_hue",            F3),
           (103,120,184)  :   ("blue_tint",           F4),
           (14,66,127)    :   ("blue_tone",           F5),
           (11,54,110)    :   ("blue_shade",          F6),
           (62,55,146)    :   ("blue_violet_hue",     GF3),
           (101,90,166)   :   ("blue_violet_tint",    GF4),
           (48,37,114)    :   ("blue_violet_tone",    GF5),
           (39,26,99)     :   ("blue_violet_shade",   GF6),
           (86,40,139)    :   ("violet_hue",          G3),
           (115,81,159)   :   ("violet_tint",         G4),
           (75,30,122)    :   ("violet_tone",         G5),
           (58,14,95)     :   ("violet_shade",        G6),
           (130,31,137)   :   ("red_violet_hue",      AF3),
           (152,84,160)   :   ("red_violet_tint",     AF4),
           (111,22,119)   :   ("red_violet_tone",     AF5),
           (85,7,91)      :   ("red_violet_shade",    AF6),
         }
   ##### End Initialization Functions #####


   def sonify_pixel(self, contact, x, y):
      """
      Take the RGB value of the touch point, and compare that RGB value
      with the master dictionary to find the appropriate pitch/frequency.

      Each voice also restarts its feedback timer.
      """

      volume = 55  # set to 55 to avoid harshities.
      voice = contact
      x, y = int(x), int(y)   # cast to int, throw away decimal

      if voice   == 1:
         self.tracker1.show()
         self.tracker1.setPosition(x,y)
         #self.timer1.start()
      elif voice == 2:
         self.tracker2.show()
         self.tracker2.setPosition(x,y)
         #self.timer2.start()
      elif voice == 3:
         self.tracker3.show()
         self.tracker3.setPosition(x,y)
         #self.timer3.start()
      elif voice == 4:
         self.tracker4.show()
         self.tracker4.setPosition(x,y)
         #self.timer4.start()
      elif voice == 5:
         self.tracker5.show()
         self.tracker5.setPosition(x,y)
         #self.timer5.start()


      red, blue, green = self.img.getPixel(x,y)
      pixel = (red, blue, green)

      # use a try catch to omit the white pixels surrounding
      # the color wheel along with the black text labels
      try:
         pitch = self.color_mapping[pixel][1]
         frequency = self.__convertPitchToFrequency__(pitch)

         # if highest possible register, set volume to 65% of default volume
         if pitch >= A5:
            volume = volume * 0.65

         self.instrument.setFrequency(frequency, voice)
         self.instrument.setVolume(volume, voice)

      except KeyError:
         pass
         #print "The touched color", pixel, "is unmapped."


   def handle_osc_message(self, message):
      """
      Takes a maxumim if 5 x,y points from the touchOSC device.
      """

      address = message.getAddress()
      arguments = message.getArguments()

      width = float(self.img_width)     # ensure float for mapping accuracy
      height = float(self.img_height)

      if address == "/accordium/1":
         x = mapValue(arguments[0], 0.0, 1.0, 0.0, width)
         y = mapValue(arguments[1], 0.0, 1.0, 0.0, height)
         c = 1
         self.sonify_pixel(c, x, y)
      elif address == "/accordium/2":
         x = mapValue(arguments[0], 0.0, 1.0, 0.0, width)
         y = mapValue(arguments[1], 0.0, 1.0, 0.0, height)
         c = 2
         self.sonify_pixel(c, x, y)
      elif address == "/accordium/3":
         x = mapValue(arguments[0], 0.0, 1.0, 0.0, width)
         y = mapValue(arguments[1], 0.0, 1.0, 0.0, height)
         c = 3
         self.sonify_pixel(c, x, y)
      elif address == "/accordium/4":
         x = mapValue(arguments[0], 0.0, 1.0, 0.0, width)
         y = mapValue(arguments[1], 0.0, 1.0, 0.0, height)
         c = 4
         self.sonify_pixel(c, x, y)
      elif address == "/accordium/5":
         x = mapValue(arguments[0], 0.0, 1.0, 0.0, width)
         y = mapValue(arguments[1], 0.0, 1.0, 0.0, height)
         c = 5
         self.sonify_pixel(c, x, y)


      # if we are no longer holding our fingers down, hide the tracker
      if not   re.search("1/z$", address) == None and arguments[0] == 0.0:
         self.timer1.start()
      elif not re.search("2/z$", address) == None and arguments[0] == 0.0:
         self.timer2.start()
      elif not re.search("3/z$", address) == None and arguments[0] == 0.0:
         self.timer3.start()
      elif not re.search("4/z$", address) == None and arguments[0] == 0.0:
         self.timer4.start()
      elif not re.search("5/z$", address) == None and arguments[0] == 0.0:
         self.timer5.start()


   ##### UTILITY FUNCTIONS #####
   def __convertPitchToFrequency__(self, pitch):
      """
      Convert MIDI pitch to frequency in Hertz. We need This
      because the color_mapping dictionary takes pitches, but
      the instrument may use an oscillator for its timbre.
      """

      concertA = 440.0
      return concertA * 2.0 ** ((pitch - 69) / 12.0)


   ##### TESTING FUNCTIONS #####
   def __sonify_click__(self, x, y):
      """
      Allows quick testing with clicks instead of relying on iPad.
      """

      red, blue, green = self.img.getPixel(x,y)
      pixel = (red, blue, green)

      pitch = self.color_mapping[pixel][1]
      n = Note(pitch, QN)
      Play.midi(n)


   def __sonify_drag__(self, x, y):
      """
      Allows quick testing with click drags instead of relying on iPad.
      """
      red, blue, green = self.img.getPixel(x,y)
      pixel = (red, blue, green)

      # use a try catch to omit the white pixels surrounding
      # the color wheel along with the black text labels
      try:
         pitch = self.color_mapping[pixel][1]
         frequency = self.__convertPitchToFrequency__(pitch)
         self.instrument.setFrequency(frequency, 0)
         self.instrument.setVolume(127, 0)
      except KeyError:
         pass


   def __stop_sound__(self, str):
      """
      Test function. Forces all sound to stop by pressing "/".
      """
      for i in range(16):
         self.instrument.setVolume(0, i)



if __name__ == "__main__":

   fm = FMSynthesisInstrument(440, 3)
   img_src = "color-wheel-hues-tints-tones-shades.png"

   accordium = Accordium(fm, img_src) # trace touches at a performance cost and add no beautificaiton to the sound
