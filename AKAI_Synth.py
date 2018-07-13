#!/usr/bin/python3

# AKAI Synth - SoundBlaster FM based synthesizer with AKAI controller
#
# Author: Stefan Haun <tux@netz39.de>

import signal
import sys

import mido

import sounddevice

import math
import numpy as np


COL_OFF          = 0
COL_GREEN        = 1
COL_GREEN_BLINK  = 2
COL_RED          = 3
COL_RED_BLINK    = 4
COL_YELLOW       = 5
COL_YELLOW_BLINK = 6


# Source: https://upload.wikimedia.org/wikipedia/commons/a/ad/Piano_key_frequencies.png
SCALE_TONE_FREQUENCIES = [
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


def note2freq(note):
    step = note % 12
    
    octave = note // 12
    coeff = math.pow(2, octave - 4)
    
    return SCALE_TONE_FREQUENCIES[step] * coeff


def playsine(f, duration):
    w = 2 * np.pi * f
    samples = 44100
    t = np.linspace(0, w*duration, num=samples*duration)
    sine = np.sin(t)
    
    sounddevice.play(sine, samples)
    
    return

def beep_on_note(note):
    freq = note2freq(note)
    playsine(freq, 0.25)
    
    return;


class MidiMessageProcessorBase:
    """Base class for MIDI message processors"""
    
    def __init__(self):
        return
    
    
    def match(self, msg):
        """Return true if the message should be processed."""
        
        return False
    
    
    def process(self, msg):
        """Process the message"""
        
        return


class MidiMessagePrinter(MidiMessageProcessorBase):
    def __init__(self):
        return
    
    
    def match(self, msg):
        return True
    
    
    def process(self, msg):
        print(msg)
        return


class KnobColorProcessor(MidiMessageProcessorBase):
    def __init__(self, apc_out):
        self.apc_out = apc_out
        return
    
    
    def match(self, msg):
        return msg.type=="control_change" and msg.channel==0 and msg.control==48;
    
    
    def process(self, msg):
        self.apc_out.send(mido.Message('note_on', channel=0, note=0, velocity=msg.value//16))
        
        return


class SineAudioprocessor(MidiMessageProcessorBase):
    def __init__(self):
        return
    
    
    def match(self, msg):
        return (msg.type=='note_on' or msg.type=='note_off') and msg.channel==1
    
    
    def process(self, msg):
        if msg.type=='note_on':
            beep_on_note(msg.note)
        
        return


processors = [MidiMessagePrinter(), SineAudioprocessor()]


def apc_midi_msg_in(msg):
    for proc in processors:
        if proc.match(msg):
            proc.process(msg)


def sigint_handler(signal, frame):
    print("SIGINT received. Exit.")
    sys.exit(0)

if __name__ == '__main__':
    signal.signal(signal.SIGINT, sigint_handler)
    
    mido.set_backend('mido.backends.rtmidi')
    
    print(mido.get_input_names())
        
    apc_names = list(filter(lambda n: n[0:10] == 'APC Key 25',
                            mido.get_input_names()))
    print("Available APCs: ", apc_names)
    
    if not apc_names:
        print("Did not find APC controller!")
        sys.exit(-1)
    
    apc_name = apc_names[0]
    print("Using MIDI port ", apc_name);
    
    apc_in = mido.open_input(apc_name,
                             callback=apc_midi_msg_in)
    apc_out = mido.open_output(apc_name)
    
    processors.append(KnobColorProcessor(apc_out))
    
    outport = mido.open_output()
    
    for c in range(0, 5):
        for i in range(0, 8):
            msg = mido.Message('note_on', channel=0, note=c*8+i, velocity=i)
            apc_out.send(msg)
    
    
    input("Press key to finish...")
    
    # Cleanup
    apc_in.close()
    apc_out.close()
    outport.close()



# kate: space-indent on; indent-width 4; mixedindent off; indent-mode python; indend-pasted-text false; remove-trailing-space off
