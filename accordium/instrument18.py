from musicAudioSamplePoly8 import *
from math import *
from java.io import *
from gui import *
from time import sleep

import random
import math

# global scoped list of active samples for JEM purposes
__ActiveAudioSamples__ = []

__ActiveAudioInstruments__  = []

from com.jsyn import JSyn

class Synthesizer():
   """
   This implementation of synthesizer follows the Singleton design pattern. Only one
   instance of Synthesizer may exist. Any new ones create will point to this instance.
   https://en.wikipedia.org/wiki/Singleton_pattern
   """
    
   instance = None     # ensure one instance by keeping instance outside of the init
   synthRunning = False
   
   def __init__(self):
      if not Synthesizer.instance:
         Synthesizer.instance = JSyn.createSynthesizer()
      
   def getSynthesizer(self):
      return  Synthesizer.instance
   
   def startSynth(self):
      """
      Starts the synthesizer with the appropriate parameters.
      """      
      if not Synthesizer.synthRunning:
         temporarySynth  =   JSyn.createSynthesizer()
         framerate       = temporarySynth.getFrameRate()

         audioDeviceManager  = temporarySynth.getAudioDeviceManager()                  # create an audioDeviceManager to access import and output devices
         inputPortID         = audioDeviceManager.getDefaultInputDeviceID()            # use default audio input
         inputChannels       = audioDeviceManager.getMaxInputChannels( inputPortID )   # get the max number of channels for default input device
         outputPortID        = audioDeviceManager.getDefaultOutputDeviceID()           # use default audio output
         outputChannels      = audioDeviceManager.getMaxOutputChannels( outputPortID ) # get the max number of channels for default output device

         del temporarySynth

         Synthesizer.instance.start( framerate, inputPortID, inputChannels, outputPortID, outputChannels )
         Synthesizer.synthRunning = True
   
   def stopSynth(self):
      """
      Both stop and delete this synth.
      """
      if Synthesizer.synthRunning:
         Synthesizer.instance.stop()
         del Synthesizer.instance
         Synthesizer.instance = None
         Synthesizer.synthRunning = False
         
   def getFrameRate(self):
      return self.instance.getFrameRate()


from com.jsyn.unitgen import Multiply
class SynthUnit(Multiply):
   """
   This class encapsulates a pass-through object for injection into the polyphonic
   pipeline created by the Instrument class.
   """
   def __init__(self, synth, delay=0.0002):
      
      self.lastUnit = self

      from com.jsyn.unitgen import LinearRamp
      # create linear ramp and connect them to inputB (amplitude aka volume)
      self.volumeRamp =  LinearRamp()                 # create linear ramp
      self.volumeRamp.output.connect( self.inputB )   # connect to player's amplitude
      self.volumeRamp.input.setup( 0.0, 0.5, 1.0 )    # set minimum, current, and maximum settings for control
      self.volumeRamp.time.set( delay )               # and how many seconds to take for smoothing amplitude changes

      synth.add( self.volumeRamp )                    # add the ramp to the synth

   def setVolume(self, amplitude, delay=0.0002):
      """
      Sets the volume for this specific voice via amplitude. 
      """
      print "amplitude synthUnit =", amplitude
      self.volumeRamp.input.set( amplitude )
      self.volumeRamp.time.set( delay )
   
   def addUnit(self, unit, synth):
      """
      This method takes a unit and adds it to the sound pipeline.
      """

      synth.add(unit)
      self.lastUnit.output.connect( unit.input )   # make the connection
      self.lastUnit = unit                         # update last unit


from com.jsyn.unitgen import FilterLowPass
class LowPassFilter(FilterLowPass):
   def __init__(self, threshold):
      """
      Creates a low pass filter where threshold is the desired frequency cutoff.
      All frequencies BELOW the threshold will pass through. 
      """
      self.frequency.set( threshold )
      

from com.jsyn.unitgen import FilterHighPass
class HighPassFilter(FilterHighPass):
   def __init__(self, threshold):
      """
      Creates a high pass filter where threshold is the desired frequency cutoff.
      All frequencies ABOVE the threshold will pass through.
      """
      self.frequency.set( threshold )


class AudioInstrument():
   """
   Encapsulates the construction of the audio pipeline shared between all instruments. It is the top most
   class in the instrument hierarchy. This class is voice player agnostic. Subclasses specificy which voice
   player should be instantiated by this super class.
   Volume, panning, starting, stopping, and pausing are handled by this class.
   """

   def __init__(self, channels, voices, volume, voiceClass, *voiceClassArgs):
      # Handle imports
      # import shared jSyn classes here, so as to not polute the global namespace
      # subclasses will import jSyn classes specific to their own needs
      from com.jsyn.unitgen import LineOut, Pan

      # define the class level variables that are independent from the polyphonic voices
      self.channels  = channels
      self.maxVoices = voices

      # create the singleton synthsizer
      self.synthesizer = Synthesizer()
      self.synth = Synthesizer().getSynthesizer()

      # ensure mono or stereo audio
      if not (self.channels == 1 or self.channels == 2):
         raise TypeError( "Can only play mono or stereo samples." )

      # initialize the parallel voice pipelines as empty lists
      self.voices             = []   # holds the voiceClass objects supplied by the contructor
                                     # these players are the beginning of the parallel pipeline shared by all instruments
      self.voicesPitches      = []   # holds the corresponding player's set pitch as an integer between 0 and 127
      self.voicesFrequencies  = []   # holds the corresponding player's set frequency as a float
      self.panLefts           = []   # holds panLeft objects to work in tandem with panRights
      self.panRights          = []   # holds panRight objects to work in tandem with panLefts
      self.pannings           = []   # holds panning settings as an integer between 0 and 127 for corresponding players
      self.volumes            = []   # holds volume settings as an integer between 0 and 127 for corresponding players
      self.paused             = []   # holds boolean paused flags for corresponding players
      self.muted              = []   # holds boolean muted flags for corresponding players
      self.playing            = []   # holds boolean playing flags for corresponding players
      self.lineOuts           = []   # holds lineOut objects from which all sound output is produced
                                     # LineOut is the last component in the parallel pipeline
                                     # It mixes output to computer's audio (DAC) card

      self.pitchSounding      = {}  # holds associations between a pitch currently sounding and corresponding voice (one pitch per voice)
                                    # NOTE: Here we are simulating a MIDI synthesizer, which is polyphonic, i.e., allows several pitches to sound simultaneously on a given channel.
                                    # We accomplish this by utilizing the various voices defined by the pipeline above and associating each sounding pitch with a single voice.
                                    # Different pitches are associated with different voices.  We can reserve or allocate a voice to sound a specific pitch, and we can release that
                                    # voice (presumably after the pitch has stopped sounding).  This allows us to easily play polyphonic Scores via Play.audio().

      # # define locally used variables
      defaultPitch     = A4               # set the default pitch to A4 - voices will modify this on their own
      defaultFrequency = 440.0            # set default frequency to 440.0 - voices will modify this on their own

      # interate to produce the appropriate number of parallel voice pipelines
      for voice in range( self.maxVoices ):
         print "before"
         player = voiceClass( self.synth, *voiceClassArgs )          # instantiate single player
         print "after"
         self.voices.append( player )   # add it to list of players

         # initialze voice pitch and frequency lists with their defaults
         self.voicesPitches.append( defaultPitch )
         self.voicesFrequencies.append( defaultFrequency )

         # create panning control (we simulate this using two pan controls, one for the left channel and
         # another for the right channel) - to pan we adjust their respective pan
         self.panLefts.append( Pan() )
         self.panRights.append( Pan() )

         # now, that panning is set up, initialize it to center
         self.pannings.append( 63 )                      # ranges from 0 (left) to 127 (right) - 63 is center
         self.setPanning( self.pannings[voice], voice )  # and initialize
                                                         # NOTE: The two pan controls have only one of their outputs (as their names indicate)
                                                         # connected to LineOut.  This way, we can set their pan value as we would normally, and not worry
                                                         # about clipping (i.e., doubling the output amplitude).  Also, this works for both mono and
                                                         # stereo samples.
         
         # SYNTH UNIT ONLY HAS ONE OUTPUT - WE NEVER NEED STEREO HERE
         
         # # Now that we have our panning objects, we can correctly connect them based on how many channels we have
         # if self.channels == 1:    # mono audio input?
         #    self.voices[voice].lastUnit.output.connect( 0, self.panLefts[voice].input, 0 )   # connect single channel to pan control
         #    self.voices[voice].lastUnit.output.connect( 0, self.panRights[voice].input, 0 )
         #
         # elif self.channels == 2:  # stereo audio input?
         #    self.voices[voice].lastUnit.output.connect( 0, self.panLefts[voice].input, 0 )   # connect both channels to pan control
         #    # <!>
         #    #self.voices[voice].lastUnit.output.connect( 1, self.panRights[voice].input, 0 )
         #    self.voices[voice].lastUnit.output.connect( 0, self.panRights[voice].input, 0 )
         #
         # else:
         #    raise TypeError( "Can only handle mono or stereo input." )              # overkill error checking to cover possible future features

         self.voices[voice].lastUnit.output.connect( 0, self.panLefts[voice].input, 0 )
         self.voices[voice].lastUnit.output.connect( 0, self.panRights[voice].input, 0 )
         
         # set volume for this voice (0 - 127)
         self.volumes.append( volume )                                             # create volume setting for this player
         print "instrument level volume = ", volume
         self.setVolume( volume, voice )

         # now we are ready for the LineOuts
         self.lineOuts.append( LineOut() )

         # connect inputs of the LineOuts to the outputs of the panners
         self.panLefts[voice].output.connect( 0, self.lineOuts[voice].input, 0 )
         self.panRights[voice].output.connect( 1, self.lineOuts[voice].input, 1 )

         # initialize the three boolean flag lists
         self.playing.append( True )   # we ARE playing
         self.muted.append( False )    # we are NOT muted
         self.paused.append( False )   # we are NOT paused

         # add everything to the synth
         self.synth.add( self.voices[voice] )
         self.synth.add( self.panLefts[voice] )
         self.synth.add( self.panRights[voice] )
         self.synth.add( self.lineOuts[voice] )

      # This concludes the set up of the parallel voice pipelines. The subclasses can now govern their own specific implementations of certain functionality


   def pause(self, voice=0):
      """
      Pause playing corresponding sample.
      """

      if voice < 0 or voice >= self.maxVoices:

         print "Voice (" + str(voice) + ") should range from 0 to " + str(self.maxVoices) + "."

      else:

         if self.paused[voice]:
            print "This voice is already paused!"
         else:
            self.lineOuts[voice].stop()   # pause playing
            self.paused[voice] = True     # remember sample is paused


   def resume(self, voice=0):
      """
      Resume playing the corresponding sample from the paused position.
      """

      if voice < 0 or voice >= self.maxVoices:

         print "Voice (" + str(voice) + ") should range from 0 to " + str(self.maxVoices) + "."

      else:

         if not self.paused[voice]:
            print "This voice is already playing!"

         else:
            self.lineOuts[voice].start()   # resume playing
            self.isPaused[voice] = False   # remember sample is NOT paused


   def stop(self, voice=0):
      """
      Stop the specified voice.
      """

      if voice < 0 or voice >= self.maxVoices:

         print "Voice (" + str(voice) + ") should range from 0 to " + str(self.maxVoices) + "."
         return None

      else:
         self.lineOuts[voice].stop()


   def stopAll(self):
      """
      Stop all voices.
      """

      for voice in range(self.maxVoices):
         self.lineOuts[voice].stop()


   def fadeOut(self, delay=10.0):
      """
      Slowly lowers each voice's volume to zero
      """
      for voice in range(self.maxVoices):
         self.voices[voice].fadeOut( delay )

      sleep(delay + 1)   # wait for delay time as to not stop the line outs too early

      for voice in range(self.maxVoices):  # now stop the line outs
         self.lineOuts[voice].stop()


   def isPaused(self, voice=0):
      """
      Return True if the player is paused.  Returns None, if error.
      """

      if voice < 0 or voice >= self.maxVoices:

         print "Voice (" + str(voice) + ") should range from 0 to " + str(self.maxVoices) + "."
         return None

      else:

         return self.isPaused[voice]


   def getVolume(self, voice=0):
      """
      Return coresponding player's current volume (volume ranges from 0 - 127).  Returns None, if error.
      """

      if voice < 0 or voice >= self.maxVoices:

         print "Voice (" + str(voice) + ") should range from 0 to " + str(self.maxVoices) + "."
         return None

      else:

         return self.volumes[voice]


   def setVolume(self, volume, voice=0, delay=0.0002):
      """
      Set corresponding voice's volume (volume ranges from 0 - 127).
      """

      if volume < 0 or volume > 127:
         print "Volume (" + str(volume) + ") should range from 0 to 127."
      elif delay < 0.0:
         print "Delay (" + str(delay) + ") should be at least 0.0"
      else:

         if voice < 0 or voice >= self.maxVoices:
            
            print "Voice (" + str(voice) + ") should range from 0 to " + str(self.maxVoices) + "."

         else:
            self.volumes[voice] = volume                                  # remember new volume
            amplitude = mapValue(self.volumes[voice], 0, 127, 0.0, 1.0)   # map volume to amplitude
            self.voices[voice].setVolume( amplitude )


   def getPanning(self, voice=0):
      """
      Return voice's current panning (panning ranges from 0 - 127).  Returns None, if error.
      """

      if voice < 0 or voice >= self.maxVoices:

         print "Voice (" + str(voice) + ") should range from 0 to " + str(self.maxVoices) + "."
         return None

      else:

         return self.pannings[voice]


   def setPanning(self, panning, voice=0):
      """
      Set panning of a voice (panning ranges from 0 - 127).
      """

      if panning < 0 or panning > 127:
         print "Panning (" + str(panning) + ") should range from 0 to 127."
      else:

         if voice < 0 or voice >= self.maxVoices:
            
            print "Voice (" + str(voice) + ") should range from 0 to " + str(self.maxVoices) + "."

         else:

            self.pannings[voice] = panning                       # remember it

            panValue = mapValue(panning, 0, 127, -1.0, 1.0)      # map panning from 0,127 to -1.0,1.0

            self.panLefts[voice].pan.set(panValue)               # and set it
            self.panRights[voice].pan.set(panValue)


   def resetVoices(self):
      # loop through all voices, stop them, and reset them to their defaults
      for voice in range( self.maxVoices):
         if self.playing(voice):
            self.stop(voice)      # stop each playing voice

         # proceed to reset defaults
         self.paused[voice]            = False
         #self.voicesPitches[voice]     = self.samplePitch
         #self.voicesFrequencies[voice] = self.referenceFrequency
         self.pannings[voice]          = self.setPanning(63, voice)     # setPanning also resets self.panLefts[voice] and self.panRights[voice]
         self.volumes[voice]           = self.setVolume(127, voice)     # setVolume also resets self.linearRamps[voice]

   ### functions associated with allocating and deallocating a voice to play a specific pitch - done to simulating a polyhonic MIDI synthesizer ####

   # NOTE: Here we are simulating a MIDI synthesizer, which is polyphonic, i.e., allows several pitches to sound simultaneously on a given channel.
   # We accomplish this by utilizing the various voices now available within an AudioSample, by associating each sounding pitch with a single voice.
   # Different pitches are associated with different voices.  We can reserve or allocate a voice to sound a specific pitch, and we can release that
   # voice (presumably after the pitch has stopped sounding).  This allows us to easily play polyphonic Scores via Play.audio() - very useful / powerful!!!

   ### Also see Play.audio()

   def allocateVoiceForPitch(self, pitch):
      """
      If pitch is currently sounding, it returns the voice that plays this pitch.
      If pitch is NOT currently sounding, it returns the next available free voice,
      and allocates as associated with this pitch.
      Returns None, if pitch is NOT sounding, and all voices / players are occupied.
      """

      if (type(pitch) == int) and (0 <= pitch <= 127):   # a MIDI pitch?
         # yes, so convert pitch from MIDI number (int) to Hertz (float)
         pitch = noteToFreq(pitch)

      elif type(pitch) != float:                                   # if reference pitch a frequency (a float, in Hz)?

         raise TypeError("Pitch (" + str(pitch) + ") should be an int (range 0 and 127) or float (such as 440.0).")

      # now, assume pitch contains a frequency (float)

      # is pitch currently sounding?
      if self.pitchSounding.has_key(pitch):

         voiceForThisPitch = self.pitchSounding[pitch]   # get voice already allocated for this pitch

      else:   # pitch does not have a voice already allocated, so...

         voiceForThisPitch = self.getNextFreeVoice()     # get next free voice (if any)

         # if a free voice exists...
         if voiceForThisPitch != None:

            self.pitchSounding[pitch] = voiceForThisPitch   # and allocate it!

      # now, return voice for this pitch (it could be None, if pitch is not sounding and no free voices exist!)
      return voiceForThisPitch


   def deallocateVoiceForPitch(self, pitch):
      """
      It assumes this pitch is currently sounding, and returns the voice that plays this pitch.
      If this pitch is NOT currently sounding, it returns the next available free voice.
      Returns None, if the pitch is NOT sounding, and all voices / players are occupied.
      """

      if (type(pitch) == int) and (0 <= pitch <= 127):   # a MIDI pitch?
         # yes, so convert pitch from MIDI number (int) to Hertz (float)
         pitch = noteToFreq(pitch)

      elif type(pitch) != float:                                   # if reference pitch a frequency (a float, in Hz)?

         raise TypeError("Pitch (" + str(pitch) + ") should be an int (range 0 and 127) or float (such as 440.0).")

      # now, assume pitch contains a frequency (float)

      # is pitch currently sounding?
      if self.pitchSounding.has_key(pitch):

         del self.pitchSounding[pitch]   # deallocate voice for this pitch

      else:   # pitch is not currently sounding, so...

         print "But pitch", pitch, "is currently not sounding!!!"


   def getNextFreeVoice(self):
      """
      Return the next available voice, i.e., a player that is not currently playing.
      Returns None, if all voices / players are occupied.
      """

      # find all free voices (not currently playing)
      freeVoices = [voice for voice in range(self.maxVoices) if not voice in self.pitchSounding.values()]

      if len(freeVoices) > 0:   # are there some free voices
         freeVoice = freeVoices[0]
      else:
          freeVoice = None

      return freeVoice


   # Calculate frequency in Hertz based on MIDI pitch. Middle C is 60.0. You
   # can use fractional pitches so 60.5 would give you a pitch half way
   # between C and C#.  (by Phil Burk (C) 2009 Mobileer Inc)
   def __convertPitchToFrequency__(self, pitch):
      """
      Convert MIDI pitch to frequency in Hertz.
      """

      concertA = 440.0
      return concertA * 2.0 ** ((pitch - 69) / 12.0)

   def __convertFrequencyToPitch__(self, freq):
      """
      Converts pitch frequency (in Hertz) to MIDI pitch.
      """

      concertA = 440.0
      return log(freq / concertA, 2.0) * 12.0 + 69

   # following conversions between frequencies and semitones based on code
   # by J.R. de Pijper, IPO, Eindhoven
   # see http://users.utu.fi/jyrtuoma/speech/semitone.html
   def __getSemitonesBetweenFrequencies__(self, freq1, freq2):
      """
      Calculate number of semitones between two frequencies.
      """

      semitones = (12.0 / log(2)) * log(freq2 / freq1)
      return int(semitones)

   def __getFrequencyChangeBySemitones__(self, freq, semitones):
      """
      Calculates frequency change, given change in semitones, from a frequency.
      """

      freqChange = (exp(semitones * log(2) / 12) * freq) - freq
      return freqChange


   def __getSynthesizer__(self):
      """
      Returns the synthesizer for this instrument
      """
      return self.synth


class SampleInstrument(AudioInstrument):
   """
   This class encapsulates shared functionality between AudioSample and LiveSample. It also possesses
   two inner classes that are passed to the super constructor depending on mono or stereo output.
   """

   from com.jsyn.unitgen import VariableRateMonoReader, VariableRateStereoReader, SequentialDataReader

   def __init__(self, channels, samplePitch, voices, volume, voiceClass, *voiceClassArgs):
      # SampleInstrument.__init__(self, channels, samplePitch, voices, voiceClass, *voiceClassArgs)
      # define locally used variables
      self.samplePitch   = samplePitch               # remember the reference pitch from the constructor
      sampleFrequency = None                        # Set reference frequency to None. This will be appropriately reassigned later
      
      voiceClass = self.Voice

      # check if the reference is a midi pitch (int) or a frequency (float)
      # If the reference is neither an int or a float, this is an error. Catch this error in the else block
      if (type(samplePitch) == int) and (0 <= samplePitch <= 127):         # is reference pitch in MIDI (an int)?
         sampleFrequency = self.__convertPitchToFrequency__(samplePitch)   # convert the MIDI pitch to a float frequency for use in polyphony pipeline
      elif type(referencePitch) == float:                                  # if reference pitch a frequency (a float, in Hz)?
         sampleFrequency = samplePitch                                     # correctly assign the float frequency
         samplePitch     = self.__convertFrequencyToPitch__(samplePitch)   # convert the float frequency to MIDI pitch, reassign referencePitch, use in the polyphony pipeline
      else:
         raise TypeError("Reference pitch (" + str(referencePitch) + ") should be an int (range 0 and 127) or float (such as 440.0).")
         

      AudioInstrument.__init__(self, channels, voices, volume, voiceClass, *voiceClassArgs)

      framerate = self.synthesizer.getFrameRate()
      
      # ensure the sample is playing at correct pitch by syncing its playback rate and the synth framerate
      for voice in range(self.maxVoices):
         self.voices[voice].__syncFramerate__( framerate )


   def play(self, voice=0, start=0, size=-1):
      """
      Play the corresponding sample once from the millisecond 'start' until the millisecond 'start'+'size'
      (size == -1 means to the end). If 'start' and 'size' are omitted, play the complete sample.
      """

      if voice < 0 or voice >= self.maxVoices:

         print "Voice (" + str(voice) + ") should range from 0 to " + str(self.maxVoices) + "."

      else:
         # for faster response, we restart playing (as opposed to queue at the end)
         if self.isPlaying(voice):      # is another play is on?
            self.stop(voice)            # yes, so stop it

         self.loop(voice, 1, start, size)


   def loop(self, voice=0, times = -1, start=0, size=-1):
      """
      Repeat the corresponding sample indefinitely (times = -1), or the specified number of times
      from millisecond 'start' until millisecond 'start'+'size' (size == -1 means to the end).
      If 'start' and 'size' are omitted, repeat the complete sample.
      """

      if voice < 0 or voice >= self.maxVoices:

         print "Voice (" + str(voice) + ") should range from 0 to " + str(self.maxVoices) + "."

      else:

         startFrames = self.__msToFrames__(start)
         sizeFrames = self.__msToFrames__(size)

         # should this be here?  ***
         self.lineOuts[voice].start()

         if size == -1:    # to the end?
            sizeFrames = self.sample.getNumFrames() - startFrames  # calculate number of frames to the end

         if times == -1:   # loop forever?
            self.voices[voice].samplePlayer.dataQueue.queueLoop( self.sample, startFrames, sizeFrames )

         else:             # loop specified number of times
            self.voices[voice].samplePlayer.dataQueue.queueLoop( self.sample, startFrames, sizeFrames, times-1 )


   def stop(self, voice=0):
      """
      Stop playing the corresponding sample any further and restart it from the beginning.
      """

      if voice < 0 or voice >= self.maxVoices:

         print "Voice (" + str(voice) + ") should range from 0 to " + str(self.maxVoices) + "."

      else:

         self.voices[voice].samplePlayer.dataQueue.clear()
         self.paused[voice] = False  # remember this voice is NOT paused


   def isPlaying(self, voice=0):
      """
      Returns True if the corresponding sample is still playing.  In case of error, returns None.
      """

      print not self.paused[voice]

      if voice < 0 or voice >= self.maxVoices:

         print "Voice (" + str(voice) + ") should range from 0 to " + str(self.maxVoices) + "."
         return None

      else:

         return self.voices[voice].samplePlayer.dataQueue.hasMore()


   def getFrequency(self, voice=0):
      """
      Return sample's playback frequency.  Returns None if error.
      """

      if voice < 0 or voice >= self.maxVoices:

         print "Voice (" + str(voice) + ") should range from 0 to " + str(self.maxVoices) + "."
         return None

      else:
         return self.voicesFrequencies[voice]


   def setFrequency(self, freq, voice=0):
      """
      Set sample's playback frequency.
      """

      if voice < 0 or voice >= self.maxVoices:
   
         print "Voice (" + str(voice) + ") should range from 0 to " + str(self.maxVoices) + "."

      else:
         #self.voices[voice].setFrequency( freq )
         rateChangeFactor = float(freq) / self.voicesFrequencies[voice]                         # calculate change on playback rate

         self.voicesFrequencies[voice] = freq                                                   # remember new frequency
         self.voicesPitches[voice]     = self.__convertFrequencyToPitch__(freq)                 # and corresponding pitch

         self.voices[voice].setFrequency( rateChangeFactor )


   def getPitch(self, voice=0):
      """
      Return voice's current pitch (it may be different from the default pitch).
      """

      if voice < 0 or voice >= self.maxVoices:

         print "Voice (" + str(voice) + ") should range from 0 to " + str(self.maxVoices) + "."
         return None

      else:

         return self.voicesPitches[voice]


   def setPitch(self, voice=0):
      """
      Set voice's playback pitch.
      """

      if voice < 0 or voice >= self.maxVoices:

         print "Voice (" + str(voice) + ") should range from 0 to " + str(self.maxVoices) + "."

      else:
         self.setFrequency(self.__convertPitchToFrequency__(pitch), voice)   # update playback frequency (this changes the playback rate)


   def __setPlaybackRate__(self, newRate, voice=0):
      """
      Set the corresponding sample's playback rate (e.g., 44100.0 Hz).
      """

      if voice < 0 or voice >= self.maxVoices:

         print "Voice (" + str(voice) + ") should range from 0 to " + str(self.maxVoices) + "."
         return None

      else:

         self.voices[voice].rate.set( newRate )


   def __getPlaybackRate__(self, voice=0):
      """
      Return the corresponding sample's playback rate (e.g., 44100.0 Hz).
      """

      if voice < 0 or voice >= self.maxVoices:

         print "Voice (" + str(voice) + ") should range from 0 to " + str(self.maxVoices) + "."
         return None

      else:

         return self.voices[voice].rate.get()


   def __msToFrames__(self, milliseconds):
      """
      Converts milliseconds to frames based on the frame rate of the sample
      """

      return int(self.sample.getFrameRate() * (milliseconds / 1000.0))



class LiveSample(SampleInstrument):
   """
   Encapsulates a sound object created from live sound via the computer microphone (or line-in),
   which can be played once, looped, paused, resumed, stopped, copied and erased.
   The first parameter, maxSizeInSeconds, is the recording capacity (default is 30 secs).
   The larger this value, the more memory the object occupies, so this needs to be handled carefully.
   Finally, we can set/get its volume (0-127), panning (0-127), pitch (0-127), and frequency (in Hz).
   """

   def __init__(self, maxRecordingTime=30, samplePitch=A4, voices=16, volume=127):
      # import LiveSample specific classes. We need JSyn here because LiveSample needs access to
      # audioDeviceManager. ChannelIn and LineIn allow input from a microphone. FixedRateMonoWriter
      # and FixedRateStereoWriter allow recording from that input. FloatSample holds this recorded audio
      from com.jsyn import JSyn
      from com.jsyn.unitgen import ChannelIn, LineIn, FixedRateMonoWriter, FixedRateStereoWriter, VariableRateMonoReader, VariableRateStereoReader
      from com.jsyn.data import FloatSample      
      
      voiceClass = self.Voice
      

      self.maxRecordingTime        = maxRecordingTime
      self.actualRecordingTime     = None  # initialize to None, not zero.
      self.beginRecordingTimeStamp = None
      self.endRecordingTimeStamp   = None
      self.isRecording             = False

      self.samplePitch             = samplePitch   # remember the pitch

      self.sampleSize = maxRecordingTime * 1000 # convert seconds into milliseconds
      maxLoopTime     = self.__msToFrames__( self.sampleSize, framerate )

      # create time stamp variables
      self.beginRecordingTimeStamp = None    # holds timestamp of when we start recording into the sample
      self.endRecordingTimeStamp   = None    # holds timestamp of when we stop recording into the sample
      self.isRecording             = False   # boolean flag that is only true when the sample is being written to
      self.recordedSampleSize      = None    # holds overall length of time of the sample rounded to nearest int

      self.sample = FloatSample( maxLoopTime, channels )   # holds recorded audio
      
      channels = self.__getInputChannels__()   # get the number of input channels from the default input device 

      voiceClassArgs = []
      voiceClassArgs.append(channels)
      voiceClassArgs.append(samplePitch)
      
      # ensure mono or stereo audio input
      if not (channels == 1 or channels == 2):    # not mono or stereo audio?
         raise TypeError( "Can only record from mono or stereo input." )
      else:
         if channels == 2:    # stereo audio input?
            # If input is stereo, we must use a LineIn. LineIn assumes stereo and we have stereo in this case.
            self.lineIn = LineIn()                                    # create input line (stereo)
            self.recorder = FixedRateStereoWriter()                   # captures incoming audio (stereo)
            self.lineIn.output.connect( 0, self.recorder.input, 0 )   # connect line input to the sample writer (recorder)
            self.lineIn.output.connect( 0, self.recorder.input, 1 )

         elif channels == 1:  # mono audio input?
            # If input is mono, we must use a single channelIn. LineIn assumes stereo. For simplicity, we still name the variable lineIn.
            self.lineIn = ChannelIn()                                   # create input line (mono)
            self.recorder = FixedRateMonoWriter()                       # captures incoming audio (mono)
            self.lineIn.output.connect( 0, self.recorder.input, 0 )     # connect channel input to the sample writer (recorder)

      # Now that LiveSample specific information has been set, initialize the Instrument
      SampleInstrument.__init__( self, channels, samplePitch, voices, volume, voiceClass, *voiceClassArgs)

      # add LiveSample specific data to the synthesizer
      self.synth.add( self.lineIn )
      self.synth.add( self.recorder )

      # deleted the now unnecessary synth

      # start the synth correctly
      self.synthesizer.startSynth()
      
      # remember that this Instrument has been created and is active (so that it can be stopped by JEM, if desired)
      __ActiveAudioSamples__.append(self)
      __ActiveAudioInstruments__.append(self)
   
      
   # LiveSample has it's own play function because we need to check if anything exists to play
   def play(self, voice=0, start=0, size=-1):
      """
      Play the corresponding sample once from the millisecond 'start' until the millisecond 'start'+'size'
      (size == -1 means to the end). If 'start' and 'size' are omitted, play the complete sample.
      """
      if voice < 0 or voice >= self.maxVoices:

         print "Voice (" + str(voice) + ") should range from 0 to " + str(self.maxVoices) + "."

      else:
         if self.recordedSampleSize == None:
            print "Sample is empty!  You need to record before you can play."
         else:
            # for faster response, we restart playing (as opposed to queue at the end)
            if self.isPlaying(voice):      # is the sample already playing?
               self.stop(voice)            # yes, so stop it

            self.loop(voice, 1, start, size)

   # LiveSample has a specific loop function because it requires more error checking than other audio sources.
   # LiveSample must be sure all durations and framerates are acceptable before looping can be successful.
   def loop(self, voice=0, times = -1, start=0, size=-1):
      """
      Repeat the corresponding sample indefinitely (times = -1), or the specified number of times
      from millisecond 'start' until millisecond 'start'+'size' (size == -1 means to the end).
      If 'start' and 'size' are omitted, repeat the complete sample.
      """

      if voice < 0 or voice >= self.maxVoices:

         print "Voice (" + str(voice) + ") should range from 0 to " + str(self.maxVoices) + "."

      else:
         if self.recordedSampleSize == None: # is the sample currently empty?
            print "Sample is empty!  You need to record before you can loop."
            return -1

         sampleTotalDuration = (self.recordedSampleSize / self.synth.getFrameRate()) * 1000 # total time of sample in milliseconds

         # is specified start time within the total duration of sample?
         if start < 0 or start > sampleTotalDuration:
            print "Start time provided (" + str(start) + ") should be between 0 and sample duration (" + str(sampleTotalDuration) + ")."
            return -1

         # does the size specified exceed the total duration of the sample or is size an invalid value?
         if size == 0 or start + size > sampleTotalDuration:
            print "Size (" + str(size) + ") exceeds total sample duration (" + str(sampleTotalDuration) + "), given start ("+ str(start) + ")."
            return -1

         # was the size specified less than the lowest value allowed?
         if size <= -1:
            size = self.recordedSampleSize # play to the end of the sample
         else:
            size = (size/1000) * self.framerate # convert milliseconds into frames
            start = (start/1000) * self.framerate

         # loop the sample continuously?
         if times == -1:
            self.voices[voice].samplePlayer.dataQueue.queueLoop(self.sample, start, size)

         if times == 0:
            print "But, don't you want to play the sample at least once?"
            return -1

         else:
            # Subtract 1 from number of times a sample should be looped.
            # 'times' is the number of loops of the sample after the initial playing.
            self.voices[voice].samplePlayer.dataQueue.queueLoop(self.sample, start, size, times - 1)

         self.lineOuts[voice].start()   # starts playing the voice


   def startRecording(self):
      """
      Writes lineIn data to the sample data structure.
      Gets a time stamp so that, when we stop, we may calculate the duration of the recording.
      """

      # make sure sample is empty
      if self.recordedSampleSize != None:
         print "Warning: cannot record over an existing sample.  Use erase() first, to clear it."

      else:   # sample is empty, so it's OK to record
         print "Recording..."

         # make sure we are not already recording
         if not self.isRecording:

            # get timestamp of when we started recording,
            # so, later, we can calculate duration of recording
            self.beginRecordingTimeStamp = self.synth.createTimeStamp()

            # start recording into the sample
            # (self.recorder will update self.sample - the latter is passive, just a data holder)
            self.recorder.dataQueue.queueOn( self.sample )    # connect the writer to the sample

            self.recorder.start()                             # and write into it

            self.isRecording = True  # remember that recording has started

         else:   # otherwise, we are already recording, so let them know
            print "But, you are already recording..."


   def stopRecording(self):
      """
      Stops the writer from recording into the sample data structure.
      Also, gets another time stamp so that, now, we may calculate the duration of the recording.
      """

      # make sure we are currently recording
      if not self.isRecording:
         print "But, you are not recording!"

      else:
         print "Stopped recording."

         # stop writer from recording into the sample
         self.recorder.dataQueue.queueOff( self.sample )
         self.recorder.stop()

         self.isRecording = False  # remember that recording has stopped

         # now, let's calculate duration of recording

         # get a new time stamp
         self.endRecordingTimeStamp =  self.synth.createTimeStamp()

         # calculate number of frames in the recorded sample
         # (i.e., total duration in seconds x framerate)
         startTime = self.beginRecordingTimeStamp.getTime()  # get start time
         endTime = self.endRecordingTimeStamp.getTime()      # get end time
         recordingTime = endTime - startTime                 # recording duration (in seconds)

         # if we have recorded more than we can store, then we will truncate
         # (that's the least painful solution...)
         recordingCapacity = self.sampleSize / 1000   # convert to seconds
         if recordingTime > recordingCapacity:

         # let them know
            exceededSeconds = recordingTime-recordingCapacity  # calculate overun
            print "Warning: Recording too long (by", round(exceededSeconds, 2), " secs)... truncating!"

                # truncate extra recording (by setting sample duration to max recording capacity)
            sampleDuration = self.sampleSize / 1000
         else:
            # sample duration is within the recording capacity
            sampleDuration = recordingTime

         framerate = self.synth.getFrameRate()
         # let's remember duration of recording (convert to frames - an integer)
         self.recordedSampleSize = int(framerate * sampleDuration)


   # erase makes use of both self.recorder and self.sample and self.referencePitch. We will need these.
   def erase(self):
      """
      Erases all contents of the LiveSample.
      """

      # is sample currently recording?
      if self.isRecording:
         print "Cannot erase while recording!"

      self.resetVoices()   # reset all voices to their defaults

      # Now that individual voices have been stopped and reset, we can reset the source recorder by
      # clearing the dataQueue. Now, recording of the sample will start at the beginning
      self.recorder.dataQueue.clear()

      # rewrite audio data within sample frame by frame (0.0 means empty frame - no sound)
      for i in range(self.sample.getNumFrames()):
         self.sample.writeDouble(i, 0.0)

      # set sample size to empty
      self.recordedSampleSize = None


   def __getInputChannels__(self):
      """
      Creates a temportary synth to poll the audio card for input device information.
      The number of input channels is necessary to determine which recording unit
      we need to use.
      """
      temporarySynth      =   JSyn.createSynthesizer()
      audioDeviceManager  = temporarySynth.getAudioDeviceManager()                  # create an audioDeviceManager to access import and output devices
      
      inputPortID         = audioDeviceManager.getDefaultInputDeviceID()            # use default audio input
      inputChannels       = audioDeviceManager.getMaxInputChannels( inputPortID )   # get the max number of channels for default input device
      
      del audioDeviceManager
      del temporarySynth
      
      return inputChannels
      

   def __msToFrames__(self, milliseconds, framerate):
      """
      Converts milliseconds to frames based on the frame rate of the sample
      """
      return int(framerate * (milliseconds / 1000.0))
      
      
   class Voice(SynthUnit):
      def __init__(self, synth, channels, samplePitch=A4):
         from com.jsyn.unitgen import VariableRateMonoReader, VariableRateStereoReader
      
         SynthUnit.__init__(self, synth)
         
         if channels == 1:
            self.samplePlayer = VariableRateMonoReader()
         elif channels == 2:
            self.samplePlayer = VariableRateStereoReader()
         else:
            raise("Can only play mono or stereo samples.")
      
      
         self.samplePlayer.output.connect(self.inputA)
         self.inputB.set(1.0)
         self.samplePitch = samplePitch
      
         synth.add(self.samplePlayer)
         synth.add(self)
         
         
      def setFrequency(self, rateChangeFactor):
         """
         Changes the frequency/pitch of the sample.
         """
         self.__setPlaybackRate__(self.__getPlaybackRate__() * rateChangeFactor)   # and set new playback rate
      
      
      def __getPlaybackRate__(self):
         """
         Returns the current playback rate of the sample player.
         """
         return self.samplePlayer.rate.get()
      
      
      def __setPlaybackRate__(self, newRate):
         """
         Changes frequency/pitch by changing the sample players' playback rate.
         """
         self.samplePlayer.rate.set( newRate )
      
      
      def __syncFramerate__(self, framerate):
         """
         Sets the playback rate of the sample player to the framerate of the synth.
         """
         self.samplePlayer.rate.set( framerate )


class AudioSample2(SampleInstrument):
   """
   Encapsulates a sound object created from an external audio file, which can be played once,
   looped, paused, resumed, and stopped.  Also, each sound has a MIDI pitch associated with it
   (default is A4), so we can play different pitches with it (through pitch shifting).
   The soud object allows for polyphony - the default is 16 different voices, which can be played,
   pitch-shifted, looped, etc. indepedently from each other.
   Finally, we can set/get its volume (0-127), panning (0-127), pitch (0-127), and frequency (in Hz).
   Ideally, an audio object will be created with a specific pitch in mind.
   Supported data formats are WAV or AIF files (16, 24 and 32 bit PCM, and 32-bit float).
   """

   def __init__(self, filename, samplePitch=A4, voices=16, volume=127):
      # import AudioSample specific jSyn classes here. We need os to ensure a source
      # file exists. SampleLoader retrieves the sample and stores it in FloatSample
      import os
      from com.jsyn.data import FloatSample
      from com.jsyn.util import SampleLoader
      from com.jsyn.unitgen import VariableRateMonoReader, VariableRateStereoReader

      # do we have a file?
      if not os.path.isfile(filename):
         raise ValueError("File '" + str(filename) + "' does not exist.")
      
      voiceClass = self.Voice
      
      # load and create the audio sample
      SampleLoader.setJavaSoundPreferred( False )             # use internal jSyn sound processes
      datafile = File(filename)                               # get sound file
      self.sample = SampleLoader.loadFloatSample( datafile )  # load it as a a jSyn sample
      channels = self.sample.getChannelsPerFrame()            # get number of channels in sample
      
      print "channels in Audio =", channels
      
      voiceClassArgs = []
      voiceClassArgs.append(channels)
      voiceClassArgs.append(samplePitch)

      framerate = self.sample.getFrameRate()                  # get framerate from the SAMPLE, not the synthesizer

      # call the super constructor with
      SampleInstrument.__init__(self, channels, samplePitch, voices, volume, voiceClass, *voiceClassArgs)
      
                  #def __init__(self, channels, samplePitch, voices, volume, voiceClass, *voiceClassArgs):
      
      self.synthesizer.startSynth()

      # also, the original audio sample uses the SAMPLE's framerate, not the synth's
      # self.player.rate.set( self.sample.getFrameRate()
      
      # remember that this Instrument has been created and is active (so that it can be stopped by JEM, if desired)
      __ActiveAudioSamples__.append(self)
      __ActiveAudioInstruments__.append(self)

   def play(self, voice=0, start=0, size=-1):
      """
      Play the corresponding sample once from the millisecond 'start' until the millisecond 'start'+'size'
      (size == -1 means to the end). If 'start' and 'size' are omitted, play the complete sample.
      """

      if voice < 0 or voice >= self.maxVoices:

         print "Voice (" + str(voice) + ") should range from 0 to " + str(self.maxVoices) + "."

      else:

         # for faster response, we restart playing (as opposed to queue at the end)
         if self.isPlaying(voice):      # is another play is on?
            self.stop(voice)            # yes, so stop it

         self.loop(voice, 1, start, size)


   def loop(self, voice=0, times = -1, start=0, size=-1):
      """
      Repeat the corresponding sample indefinitely (times = -1), or the specified number of times
      from millisecond 'start' until millisecond 'start'+'size' (size == -1 means to the end).
      If 'start' and 'size' are omitted, repeat the complete sample.
      """

      if voice < 0 or voice >= self.maxVoices:

         print "Voice (" + str(voice) + ") should range from 0 to " + str(self.maxVoices) + "."

      else:

         startFrames = self.__msToFrames__(start)
         sizeFrames = self.__msToFrames__(size)

         if size == -1:    # to the end?
            sizeFrames = self.sample.getNumFrames() - startFrames  # calculate number of frames to the end

         if times == -1:   # loop forever?
            self.voices[voice].samplePlayer.dataQueue.queueLoop( self.sample, startFrames, sizeFrames )

         else:             # loop specified number of times
            self.voices[voice].samplePlayer.dataQueue.queueLoop( self.sample, startFrames, sizeFrames, times-1 )

         self.lineOuts[voice].start()

   def isPlaying(self, voice=0):
      """
      Returns True if the corresponding sample is still playing.  In case of error, returns None.
      """

      print not self.paused[voice]

      if voice < 0 or voice >= self.maxVoices:

         print "Voice (" + str(voice) + ") should range from 0 to " + str(self.maxVoices) + "."
         return None

      else:

         return self.voices[voice].samplePlayer.dataQueue.hasMore()


   def stop(self, voice=0):
      """
      Stop playing the corresponding sample any further and restart it from the beginning.
      """

      if voice < 0 or voice >= self.maxVoices:

         print "Voice (" + str(voice) + ") should range from 0 to " + str(self.maxVoices) + "."

      else:

         self.voices[voice].samplePlayer.dataQueue.clear()
         self.paused[voice] = False  # remember this voice is NOT paused
   
   class Voice(SynthUnit):
      def __init__(self, synth, channels, samplePitch=A4):
         from com.jsyn.unitgen import VariableRateMonoReader, VariableRateStereoReader
      
         SynthUnit.__init__(self, synth)
         print "channels =", channels
         if channels == 1:
            self.samplePlayer = VariableRateMonoReader()
         elif channels == 2:
            self.samplePlayer = VariableRateStereoReader()
         else:
            raise("Can only play mono or stereo samples.")
      
      
         self.samplePlayer.output.connect(self.inputA)
         self.inputB.set(1.0)
         self.samplePitch = samplePitch
      
         synth.add(self.samplePlayer)
         synth.add(self)
         
         
      def setFrequency(self, rateChangeFactor):
         """
         Changes the frequency/pitch of the sample.
         """
         self.__setPlaybackRate__(self.__getPlaybackRate__() * rateChangeFactor)   # and set new playback rate
      
      
      def __getPlaybackRate__(self):
         """
         Returns the current playback rate of the sample player.
         """
         return self.samplePlayer.rate.get()
      
      
      def __setPlaybackRate__(self, newRate):
         """
         Changes frequency/pitch by changing the sample players' playback rate.
         """
         self.samplePlayer.rate.set( newRate )
      
      
      def __syncFramerate__(self, framerate):
         """
         Sets the playback rate of the sample player to the framerate of the synth.
         """
         self.samplePlayer.rate.set( framerate )
   


################################################################
### Wave Instruments ###

class WaveInstrument(AudioInstrument):
   """
   Encapsulates shared behavior of all oscillating instruments.
   """

   def __init__(self, voices, voiceClass, *voiceClassArgs):
      """
      Initialize the needed arguments for the super constructor and call it.
      """

      # Initialize arguments needed for Instrument super class with defaults
      channels       = 1         # oscillating instruments have one channel
      volume         = 127

      # build basic infrastructure for voices
      AudioInstrument.__init__(self, channels, voices, volume, voiceClass, *voiceClassArgs)


   def start(self, voice=0):
      """
      Begin playing the specified voice.
      """

      if voice < 0 or voice >= self.maxVoices:

         print "Voice (" + str(voice) + ") should range from 0 to " + str(self.maxVoices) + "."
         return None

      else:
         self.lineOuts[voice].start()


   def loop(self, voice=0):
      """
      Calls the start() function because oscillators do not require looping.
      """

      self.start(voice)


   def getFrequency(self, frequency, voice=0):
      """
      Returns the frequency of the specified voice. Returns None if invalid voice is given.
      """

      if voice < 0 or voice >= self.maxVoices:

         print "Voice (" + str(voice) + ") should range from 0 to " + str(self.maxVoices) + "."
         return None

      else:
         return self.voicesFrequencies[voice]


   def setFrequency(self, frequency, voice=0):
      """
      Changes the frequency (i.e., pitch) of the specified voice.
      """

      self.voices[voice].setFrequency( frequency )                              # set frequency of this voice
      self.voicesFrequencies[voice] = frequency
      self.voicesPitches[voice] = self.__convertFrequencyToPitch__( frequency ) # also adjust pitch accordingly (since they are coupled)


   def isPlaying(self, voice=0):
      """
      Returns true if voice is playing. Returns None otherwise.
      """

      if voice < 0 or voice >= self.maxVoices:

         print "Voice (" + str(voice) + ") should range from 0 to " + str(self.maxVoices) + "."
         return None

      else:
         return self.voices[voice].playing
   
   def getAmplitude(self, voice):
      return self.voices[voice].getAmplitude()
   
   def getInputB(self, voice):
      return self.voices[voice].getInputB()


class SinewaveInstrument(WaveInstrument):
   """
   Encapsulates an oscillating sine wave.
   """
   def __init__(self, frequency=440.0, volume=127, filters=[], voices=16, envelope=None):


      if volume < 0 or volume > 127:
         print "Volume (" + str(volume) + ") should range from 0 to 127."
      else:

         if envelope == None:
            self.envelope = Envelope([20],[1.0], 5, 0.8, 15)
         else:
            self.envelope = envelope

         voiceClass = self.Voice

         voiceClassArgs = []
         voiceClassArgs.append( frequency )
         voiceClassArgs.append( volume )
         voiceClassArgs.append( filters )

         WaveInstrument.__init__(self, voices, voiceClass, *voiceClassArgs)   # call super constructor with the correct list of arguments

         self.synthesizer.startSynth()
         
         # remember that this Instrument has been created and is active (so that it can be stopped by JEM, if desired)
         __ActiveAudioSamples__.append(self)
         __ActiveAudioInstruments__.append(self)

   def getEnvelope(self):
      """
      Returns the instruments current envelope.
      """
      return self.envelope

   def setEnvelope(self, envelope):
      """
      Sets a new envelope for this instrument.
      """
      # do we need sanity checking here for valid envelopes?
      self.envelope = envelope


   class Voice(SynthUnit):
      def __init__(self, synth, frequency, volume, filters):
         from com.jsyn.unitgen import SineOscillator
         SynthUnit.__init__(self, synth)
      
         for unit in filters:
            self.addUnit(unit, synth)
            
         amplitude = mapValue(volume, 0, 127, 0.0, 1.0)
         self.oscillator = SineOscillator()
         self.setFrequency( frequency )


         self.oscillator.output.connect( self.inputA )
         self.oscillator.amplitude.set( amplitude )
         self.inputB.set(1.0)                           # set inputB to 1.0 to preserve maxVolume

         synth.add(self.oscillator)
         synth.add(self)
         

      def setFrequency(self, frequency):
         """
         Changes the frequency (i.e., pitch) of the specified voice.
         """
         self.oscillator.frequency.set( frequency )

      def getFrequency(self):
         """
         Returns the current frequency of the oscillator as a float.
         """
         return self.oscillator.frequency.get()
      
      def getAmplitude(self):
         return self.oscillator.amplitude.get()
   
      def getInputB(self):
         return self.inputB.get()


class SquarewaveInstrument(WaveInstrument):
   """
   Encapsulates an oscillating square wave. Defaults to a frequency of 440.0 (A4).
   """
   from com.jsyn.unitgen import SquareOscillator

   def __init__(self, frequency=440.0, volume=127, voices=16, envelope=None):

      if volume < 0 or volume > 127:
         print "Volume (" + str(volume) + ") should range from 0 to 127."
      else:

         if envelope == None:
            self.envelope = Envelope([20],[1.0], 5, 0.8, 15)
         else:
            self.envelope = envelope

         voiceClass = self.Voice   # class to create each voice

         voiceClassArgs = []
         voiceClassArgs.append(frequency)
         voiceClassArgs.append(volume)

         WaveInstrument.__init__(self, voices, voiceClass, *voiceClassArgs)
         
         self.synthesizer.startSynth()
               
         # remember that this Instrument has been created and is active (so that it can be stopped by JEM, if desired)
         __ActiveAudioSamples__.append(self)
         __ActiveAudioInstruments__.append(self)

   def getEnvelope(self):
      """
      Returns the instruments current envelope.
      """
      return self.envelope

   def setEnvelope(self, envelope):
      """
      Sets a new envelope for this instrument.
      """
      # do we need sanity checking here for valid envelopes?
      self.envelope = envelope


   class Voice(SynthUnit):
      def __init__(self, synth, frequency, volume):
         from com.jsyn.unitgen import SquareOscillator
         SynthUnit.__init__(self, synth)

         amplitude = mapValue( volume, 0, 127, 0.0, 1.0)
         self.amplitude  = amplitude
         self.oscillator = SquareOscillator()
         self.setFrequency(frequency)

         self.oscillator.output.connect( self.inputA )
         self.oscillator.amplitude.set( amplitude )
         self.inputB.set(1.0)

         synth.add(self.oscillator)
         synth.add(self)

      def setFrequency(self, frequency):
         """
         Changes the frequency (i.e., pitch) of the specified voice.
         """
         self.oscillator.frequency.set( frequency )

      def getFrequency(self):
         """
         Returns the current frequency of the oscillator as a float.
         """
         return self.oscillator.frequency.get()


class TrianglewaveInstrument(WaveInstrument):
   """
   Encapsulates an oscillating triangle wave. Defaults to a frequency of 440.0 (A4).
   """

   from com.jsyn.unitgen import TriangleOscillator

   def __init__(self, frequency=440.0, volume=127, voices=16, envelope=None):

      if volume < 0 or volume > 127:
         print "Volume (" + str(volume) + ") should range from 0 to 127."
      else:
         if envelope == None:
            self.envelope = Envelope([20],[1.0], 5, 0.8, 15)
         else:
            self.envelope = envelope

         voiceClass = self.Voice   # class to create each voice
         voiceClassArgs = []
         voiceClassArgs.append(frequency)
         voiceClassArgs.append(volume)

         WaveInstrument.__init__(self, voices, voiceClass, *voiceClassArgs)

         self.synthesizer.startSynth()
         
         # remember that this Instrument has been created and is active (so that it can be stopped by JEM, if desired)
         __ActiveAudioSamples__.append(self)
         __ActiveAudioInstruments__.append(self)

   def getEnvelope(self):
      """
      Returns the instruments current envelope.
      """
      return self.envelope

   def setEnvelope(self, envelope):
      """
      Sets a new envelope for this instrument.
      """
      # do we need sanity checking here for valid envelopes?
      self.envelope = envelope


   class Voice(SynthUnit):
      def __init__(self, synth, frequency, volume):
         from com.jsyn.unitgen import TriangleOscillator

         print 'in triangle voice'
         print "volume =", volume
      
         SynthUnit.__init__(self, synth)

         amplitude = mapValue( volume, 0, 127, 0.0, 1.0)
         print "amplitude =", amplitude
         self.amplitude  = amplitude
         self.oscillator = TriangleOscillator()
         self.setFrequency( frequency )
      

         self.oscillator.output.connect( self.inputA )
         self.oscillator.amplitude.set( self.amplitude )   # set max volume for voice
         self.inputB.set(1.0)                              # set inputB to 1 so given volume become max volume

         synth.add(self.oscillator)
         synth.add(self)

      def setFrequency(self, frequency):
         """
         Changes the frequency (i.e., pitch) of the specified voice.
         """
         self.oscillator.frequency.set( frequency )

      def getFrequency(self):
         """
         Returns the current frequency of the oscillator as a float.
         """
         return self.oscillator.frequency.get()
      
      def getAmplitude(self):
         return self.oscillator.amplitude.get()
   
      def getInputB(self):
         return self.inputB.get()


### FM Synthesis Instrument ###

class FMSynthesisInstrument(WaveInstrument):
   """
   Encapsulates a frequency modulated sinewave.
   The frequency of the *carrier* wave, equals centerFrequency/timbreQuality.
   Using a ratio like this preserves the timbre of the instrument you have just
   created.
   """
   def __init__(self, frequency, timbreRatio, volume=127, voices=16, envelope=None):
      """
      Specify the class needed to play the voice, then call the super constructor. Lastly, start the synth.
      """
      from com.jsyn import JSyn
      
      if volume < 0 or volume > 127:
         print "Volume (" + str(volume) + ") should range from 0 to 127."
      else:

         if envelope == None:
            self.envelope = Envelope([20],[1.0], 5, 0.8, 15)
         else:
            self.envelope = envelope
            
            
         voiceClass = self.Voice     # class to create each voice

         voiceClassArgs = []               # create empty list to hold parameters
         voiceClassArgs.append(frequency)     # append each parameter to the list
         voiceClassArgs.append(timbreRatio)   # append each parameter to the list
         voiceClassArgs.append(volume)        # append each parameter to the list

         WaveInstrument.__init__(self, voices, voiceClass, *voiceClassArgs)   # call super constructor with the correct list of arguments

         self.synthesizer.startSynth()
         
         # add this instrument to the global list for external tracking by JEM
         __ActiveAudioSamples__.append(self)
         __ActiveAudioInstruments__.append(self)


   def getEnvelope(self):
      """
      Returns the instruments current envelope.
      """
      return self.envelope


   def setEnvelope(self, envelope):
      """
      Sets a new envelope for this instrument.
      """
      # do we need sanity checking here for valid envelopes?
      self.envelope = envelope


   class Voice(SynthUnit):
      """
      Extending SynthUnit provides access to the amplitude attribute - needed by all players.
      """

      def __init__(self, synth, frequency, timbreRatio, volume):
         """
         This constructor establishes a pattern for instrument creation.
            1. Call the super constructor
            2. Define a `createInstrument` method that does the heavy lifting
            3. add self to synth
         """
         from com.jsyn.unitgen import SineOscillator, Multiply

         # first, let's call superconstructor to create basic circuit (output port, and amplitude control)
         SynthUnit.__init__(self, synth)

         self.timbreRatio = timbreRatio
         # now, create the specific instrument (i.e., build circuitry responsible for this timbre)

         self.carrier    = SineOscillator()   # create carrier wave
         self.modulator  = SineOscillator()   # create modulator wave
         self.multiplier = Multiply()         # create multiplier linking carrier and modulator

         # we now have the necessary self.frequency and self.divisor
         # so we get up the rest of what is needed for FMSynthesis

         self.carrier    = SineOscillator()   # create carrier wave
         self.modulator  = SineOscillator()   # create modulator wave
         self.multiplier = Multiply()         # create multiplier linking carrier and modulator

         self.modulator.output.connect( self.multiplier.inputA )        # connect modulator output to one of multiplier's inputs
         self.multiplier.output.connect( self.carrier.frequency )       # connect multiplier's output to control carrier frequency

         self.carrier.output.connect( self.inputA )   # connect instrument's final unit output to SynthUnit's inputA

         amplitude = mapValue( volume, 0, 127, 0.0, 1.0)   # map volume (0-127) to amplitude (0.0-1.0)
         self.carrier.amplitude.set(amplitude)             # set carrier amplitude to control max volume
         #self.inputB.set(amplitude)
         self.modulator.amplitude.set(1.0)                 # keep modulator amplitude at 1.0 to preserve timbre
         
         # circuit is built, so set it's base frequency
         self.setFrequency(frequency)


         # add all units to synth (including self)
         synth.add( self.carrier )
         synth.add( self.modulator )
         synth.add( self.multiplier )
         synth.add( self )


      def setFrequency(self, frequency):
         self.modulator.frequency.set( frequency / self.timbreRatio )
         #self.carrier.frequency.set( frequency )
         self.multiplier.inputB.set( frequency )

      def getFrequency(self):
         """
         Returns the current frequency of the oscillator as a float.
         """
         return self.multiplier.inputB.get()


class AdditiveInstrument(AudioInstrument):
   """
   Encapualtes an additive synthesis instrument. A list of instruments are provided and
   one voice of each is instantiated. A paralell list of amplitudes corresponds to how much 
   that particular intrument affects the sound. 
   
   No middle layer is needed for AdditiveSynthesis. Thus, it extends directly from Instrument.
   """

   def __init__(self, instrumentList, volumesList, volume=127, voices=16):
      
      channels = 1   # assume one input channel for now.
      
      voiceClass = self.Voice
      voiceClassArgs = []
      voiceClassArgs.append(volumesList)
      
      AudioInstrument.__init__(self, channels, voices, volume, voiceClass, *voiceClassArgs)
      
      for instrument in instrumentList:
         for i in range(len(instrument.voices)): 
            self.voices[i].initializeVoice( self.synth, instrument.voices[i] )
         
      self.synthesizer.startSynth()
      
   
   def stopAll(self):
      """
      Allow each voice to control its own stop all.
      """
      for voice in self.voices:
         voice.stopAll()
         
   def start(self, voice=0):
      """
      Begin playing the specified voice.
      """

      if voice < 0 or voice >= self.maxVoices:

         print "Voice (" + str(voice) + ") should range from 0 to " + str(self.maxVoices) + "."
         return None

      else:
         self.lineOuts[voice].start()


   def loop(self, voice=0):
      """
      Calls the start() function because oscillators do not require looping.
      """

      self.start(voice)


   def getFrequency(self, frequency, voice=0):
      """
      Returns the frequency of the specified voice. Returns None if invalid voice is given.
      """

      if voice < 0 or voice >= self.maxVoices:

         print "Voice (" + str(voice) + ") should range from 0 to " + str(self.maxVoices) + "."
         return None

      else:
         return self.voicesFrequencies[voice]


   def setFrequency(self, frequency, voice=0):
      """
      Changes the frequency (i.e., pitch) of the specified voice.
      """

      self.voices[voice].setFrequency( frequency )                              # set frequency of this voice
      self.voicesFrequencies[voice] = frequency
      self.voicesPitches[voice] = self.__convertFrequencyToPitch__( frequency ) # also adjust pitch accordingly (since they are coupled)


   def isPlaying(self, voice=0):
      """
      Returns true if voice is playing. Returns None otherwise.
      """

      if voice < 0 or voice >= self.maxVoices:

         print "Voice (" + str(voice) + ") should range from 0 to " + str(self.maxVoices) + "."
         return None

      else:
         return self.voices[voice].playing


   class Voice(SynthUnit):
      def __init__(self, synth, volumesList, volume=127):
         """
         The addititive synthesis voice is a compound voice consisting of one or more
         sub voices. These sub voices are one instance of a voice for each instrument 
         in the instrument list. 
         """
         
         self.subVoices = []
         self.volumesList = volumesList   # do something with this later
         
         SynthUnit.__init__(self, synth)   # intialize the synth unit so we have access to inputA and inputB.
         
         synth.add(self)
         
      
      def initializeVoice(self, synth, subvoice):
         """
         Take in a voice from the and connect it to self.inputA. This should only be 
         called once at creation time. Thus, it is safe to append to the components
         list here.
         """
         self.subVoices.append( subvoice )        # append this subvoice to the list of subvoices
         synth.add( subvoice )                    # add the subvoice to synth
         subvoice.output.connect( self.inputA )   # connect the output of this subvoice to the input of this voice
         
      def setFrequency(self, frequency):
         """
         Loop through each component voice and change its frequency to the
         desired frequency of the composite voice.
         """
         
         for subvoice in self.subVoices:
            subvoice.setFrequency( frequency )
      
      def stopAll(self):
         """
         Stops all sub voices.
         """
         for subvoice in self.subVoices:
            subvoice.stop()
      


