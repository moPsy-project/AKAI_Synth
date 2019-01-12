#!/usr/bin/python3

# AKAI Synth - SoundBlaster FM based synthesizer with AKAI controller
#
# FloppyDriver based synthesizer
#
# Author: Stefan Haun <tux@netz39.de>
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSES/MIT.txt


import mido

import serial

from midiproc import MidiMessageProcessorBase

SCALE_TONE_VALUES = [
    261.626, # C4 (Middle C)
    277.183, # C#4 / Db4
    293.665, # D4
    311.127, # D#4 / Eb4
    329.628, # E4
    349.228, # F4
    369.994, # F#4 / Gb4
    391.995, # G4
    415.305, # G#4 / Ab4
    440.000, # A4
    466.164, # A#4, Bb4
    493.883, # B
]

class FloppySequencer(MidiMessageProcessorBase):
    def __init__(self,
                 device,
                 ch=2):
        super().__init__()
        
        self.device = device
        self.ch = ch
        
        self.ser = serial.Serial(device)
        self.ser.write([100, 0, 0])
        
        return
    
    
    def match(self, msg):
        return (msg.type=='note_on' or msg.type=='note_off') and msg.channel==1
    
    
    def process(self, msg):
        if msg.type=='note_on':
            value=((100-24-msg.note)*10)
            print("Setting floppy to {0}.\n".format(value))
            self.set_pwm(value)
#            self.dispatch_strike(msg.note)
        
        if msg.type=='note_off':
            self.set_pwm(0)
#            self.dispatch_release(msg.note)

        return
    
    def set_pwm(self, value):
        self.ser.write([self.ch, value//256, value%256])
        return


# kate: space-indent on; indent-width 4; mixedindent off; indent-mode python; indend-pasted-text false; remove-trailing-space off
