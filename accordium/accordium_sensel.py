
# https://www.ginifab.com/feeds/pms/pms_color_in_image.php

from music3 import *
from osc import *
from gui import *

# Use and object pool
#

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

      # delete this, click method only for testing.
      self.display.onMouseClick(self.sonify_click)
      self.display.onMouseDrag(self.sonify_drag)
      self.display.onKeyType(self.stop_sound)

      # lists to track redicles
      self.available_points = []
      self.committed_points = []

      self.displayed_indicators = []

      # setup OSC
      self.osc_in = OscIn(1337)
      self.osc_in.onInput("/.*", self.handle_message)
      self.osc_in.hideMessages()

      # finish initialization
      self.instrument = instrument

      # the color mapping dictionary is ugly
      # for this reason, we take its declaration out of the constructor
      self.color_mapping = self.get_color_mapping()

      # Now that the mapping dictionary has been created, finish the initialization
      self.initialize_instrument()


   def initialize_instrument(self):
      """
      Start all voices and set their volumes to 0.
      """

      for i in range(16):
         self.instrument.start(i)
         self.instrument.setVolume(0,i)

      for key in self.color_mapping:
         self.display.add(self.color_mapping[key][2])


   def __convertPitchToFrequency__(self, pitch):
      """
      Convert MIDI pitch to frequency in Hertz. We need This
      because the color_mapping dictionary takes pitches, but
      the instrument may use an oscillator for its timbre.
      """

      concertA = 440.0
      return concertA * 2.0 ** ((pitch - 69) / 12.0)


   def sonify_click(self, x, y):
      """
      Allows quick testing with clicks instead of relying on Sensel.
      """

      red, blue, green = self.img.getPixel(x,y)
      pixel = (red, blue, green)

      # use a try catch to omit the white pixels surrounding
      # the color wheel along with the black text labels

      c = self.color_mapping[pixel][2]
      c.setColor(Color.BLACK)
      pitch = self.color_mapping[pixel][1]
      n = Note(pitch, QN)
      Play.midi(n)

      # sleep(2)
      # c.setColor(Color.WHITE)

   def sonify_drag(self, x, y):
      """
      delete this
      """
      red, blue, green = self.img.getPixel(x,y)
      pixel = (red, blue, green)

      c = self.color_mapping[pixel][2]
      c.setColor(Color.BLACK)

      # use a try catch to omit the white pixels surrounding
      # the color wheel along with the black text labels
      pitch = self.color_mapping[pixel][1]
      frequency = self.__convertPitchToFrequency__(pitch)
      self.instrument.setFrequency(frequency, 0)
      self.instrument.setVolume(127, 0)

   def stop_sound(self, str):
       for i in range(16):
           self.instrument.setVolume(0, i)

       for indicator in self.displayed_indicators:
           self.display.remove(indicator)

   def sonify_pixel(self, c, x, y, force):
      """
      Take the RGB value of the touch point, and compare that RGB value
      with the master dictionary to find the appropriate pitch/frequency.
      """

      volume = force
      voice = c

      red, blue, green = self.img.getPixel(x,y)
      pixel = (red, blue, green)

      # use a try catch to omit the white pixels surrounding
      # the color wheel along with the black text labels
      try:
          pitch = self.color_mapping[pixel][1]
          frequency = self.__convertPitchToFrequency__(pitch)

          self.instrument.setFrequency(frequency, voice)
          self.instrument.setVolume(volume, voice)

      except KeyError:
          pass


   def trace_touch(self, c, x, y):
      """

      """
      self.committed_points.append(self.available_points[-1])
      touch_point = self.committed_points[-1]
      self.display.add(touch_point)
      self.display.move(touch_point, x, y)


   def handle_message(self, message):
      """
      Takes the contact index, x/y values, and force value from the OSC message and
      passes them to the handler.

      Force is the pressure applied at each contact point.
      """

      address = message.getAddress()
      arguments = message.getArguments()

      # which contact point?
      contact = arguments[0]

      # ensure valid instrument voice
      if contact >= 0 and contact <= 15:
         # map x and y from sensel position to image position
         x = mapValue(arguments[1], 0, 240, 0, self.img_width)
         y = mapValue(arguments[2], 0, 140, 0, self.img_height)

         # map touch pressure to a valid midi volume
         force = mapValue(arguments[3], 0, 1850, 0, 127)

         self.trace_touch(contact, x, y)
         # if force is low enough, assume no touch.
         if force < 6:
            force = 0
            self.display.remove(self.point_list[contact])

         self.sonify_pixel(contact, x, y, force)

   def get_color_mapping(self):
       """
         # remember these are slightly modified for usability and do not
         # follow natural register increases based on luminosity

         # yellows are an issue. There a several color combos.
         # perhaps we should computer generate the image?
       """
       return {
             (216,14,45)    :   ("red_hue",             A2,  Circle(776, 522, 5, Color.WHITE, True)),
             (227,92,80)    :   ("red_tint",            A3,  Circle(702, 483, 5, Color.WHITE, True)),
             (170,8,34)     :   ("red_tone",            A4,  Circle(645, 451, 5, Color.WHITE, True)),
             (141,4,21)     :   ("red_shade",           A5,  Circle(571, 413, 5, Color.WHITE, True)),
             (228,88,50)    :   ("red_orange_hue",      BF2, Circle(813, 364, 5, Color.WHITE, True)),
             (236,136,98)   :   ("red_orange_tint",     BF3, Circle(732, 365, 5, Color.WHITE, True)),
             (179,69,36)    :   ("red_orange_tone",     BF4, Circle(662, 366, 5, Color.WHITE, True)),
             (149,57,25)    :   ("red_orange_shade",    BF5, Circle(583, 373, 5, Color.WHITE, True)),
             (239,163,52)   :   ("orange_hue",          B2,  Circle(766, 212, 5, Color.WHITE, True)),
             (243,174,80)   :   ("orange_tint",         B3,  Circle(699, 251, 5, Color.WHITE, True)),
             (188,130,39)   :   ("orange_tone",         B4,  Circle(639, 284, 5, Color.WHITE, True)),
             (157,109,28)   :   ("orange_shade",        B5,  Circle(577, 325, 5, Color.WHITE, True)),
             (249,217,52)   :   ("yellow_orange_hue",   C3,  Circle(650, 87,  5, Color.WHITE, True)),
             (250,225,110)  :   ("yellow_orange_tint",  C4,  Circle(612, 161, 5, Color.WHITE, True)),
             (194,173,41)   :   ("yellow_orange_tone",  C5,  Circle(579, 227, 5, Color.WHITE, True)),
             (161,145,31)   :   ("yellow_orange_shade", C6,  Circle(542, 296, 5, Color.WHITE, True)),
             (160,146,31)   :   ("yellow_orange_shade", C6,  Circle(542, 296, 5, Color.WHITE, True)),
             (162,144,31)   :   ("yellow_orange_shade", C6,  Circle(542, 296, 5, Color.WHITE, True)),
             (252,253,59)   :   ("yellow_hue",          DF3, Circle(492, 55,  5, Color.WHITE, True)),
             (252,251,119)  :   ("yellow_tint",         DF4, Circle(494, 136, 5, Color.WHITE, True)),
             (202,199,44)   :   ("yellow_tone",         DF5, Circle(494, 202, 5, Color.WHITE, True)),
             (169,169,37)   :   ("yellow_shade",        DF6, Circle(496, 295, 5, Color.WHITE, True)),
             (150,211,88)   :   ("yellow_green_hue",    D3,  Circle(332, 108, 5, Color.WHITE, True)),
             (182,223,135)  :   ("yellow_green_tint",   D4,  Circle(373, 176, 5, Color.WHITE, True)),
             (117,170,68)   :   ("yellow_green_tone",   D5,  Circle(411, 233, 5, Color.WHITE, True)),
             (96,143,56)    :   ("yellow_green_shade",  D6,  Circle(453, 295, 5, Color.WHITE, True)),
             (45,178,81)    :   ("green_hue",           EF3, Circle(224, 224, 5, Color.WHITE, True)),
             (139,198,139)  :   ("green_tint",          EF4, Circle(292, 261, 5, Color.WHITE, True)),
             (34,145,64)    :   ("green_tone",          EF5, Circle(355, 296, 5, Color.WHITE, True)),
             (28,124,55)    :   ("green_shade",         EF6, Circle(425, 330, 5, Color.WHITE, True)),
             (36,191,136)   :   ("blue_green_hue",      E3,  Circle(196, 384, 5, Color.WHITE, True)),
             (80,200,156)   :   ("blue_green_tint",     E4,  Circle(262, 385, 5, Color.WHITE, True)),
             (28,154,110)   :   ("blue_green_tone",     E5,  Circle(337, 378, 5, Color.WHITE, True)),
             (24,132,93)    :   ("blue_green_shade",    E6,  Circle(408, 377, 5, Color.WHITE, True)),
             (19,85,160)    :   ("blue_hue",            F3,  Circle(235, 543, 5, Color.WHITE, True)),
             (103,120,184)  :   ("blue_tint",           F4,  Circle(297, 500, 5, Color.WHITE, True)),
             (14,66,127)    :   ("blue_tone",           F5,  Circle(363, 463, 5, Color.WHITE, True)),
             (11,54,110)    :   ("blue_shade",          F6,  Circle(426, 423, 5, Color.WHITE, True)),
             (62,55,146)    :   ("blue_violet_hue",     GF3, Circle(345, 650, 5, Color.WHITE, True)),
             (101,90,166)   :   ("blue_violet_tint",    GF4, Circle(391, 580, 5, Color.WHITE, True)),
             (48,37,114)    :   ("blue_violet_tone",    GF5, Circle(422, 518, 5, Color.WHITE, True)),
             (39,26,99)     :   ("blue_violet_shade",   GF6, Circle(458, 453, 5, Color.WHITE, True)),
             (86,40,139)    :   ("violet_hue",          G3,  Circle(504, 691, 5, Color.WHITE, True)),
             (115,81,159)   :   ("violet_tint",         G4,  Circle(501, 607, 5, Color.WHITE, True)),
             (75,30,122)    :   ("violet_tone",         G5,  Circle(502, 540, 5, Color.WHITE, True)),
             (58,14,95)     :   ("violet_shade",        G6,  Circle(502, 464, 5, Color.WHITE, True)),
             (130,31,137)   :   ("red_violet_hue",      AF3, Circle(661, 645, 5, Color.WHITE, True)),
             (152,84,160)   :   ("red_violet_tint",     AF4, Circle(618, 575, 5, Color.WHITE, True)),
             (111,22,119)   :   ("red_violet_tone",     AF5, Circle(586, 519, 5, Color.WHITE, True)),
             (85,7,91)      :   ("red_violet_shade",    AF6, Circle(543, 450, 5, Color.WHITE, True)),
         }



fm = FMSynthesisInstrument(440, 3)
img_src = "color-wheel-hues-tints-tones-shades.png"

accordium = Accordium(fm, img_src) # trace touches at a performance cost and add no beautificaiton to the sound
