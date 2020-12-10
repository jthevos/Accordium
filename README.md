# Accordium

This is a composer's aid where touching colors on an iPad will produce polyphonic chords.

Colors available come from a 12 tone color wheel that is split into
1. Shades
2. Tints
3. Hues
4. Tones

This instrument assumes 12-tone equal temperament as its musical base.

Timbre chosen is arbitrary; however, a Frequency Modulated Synthesized timbre using a 3:1 ratio
between and carrier and modulator waves was the aesthetic choice.

Requirements:
1. [JythonMusic](https://jythonmusic.me/)
2. An iPad or iPhone with [TouchOSC](https://hexler.net/products/touchosc) installed

Messages are sent from the iPad to the computer using the Open Sound Control
protocol.
