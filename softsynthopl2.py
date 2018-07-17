#!/usr/bin/python3

# AKAI Synth - SoundBlaster FM based synthesizer with AKAI controller
#
# OPL2-type software synthesizer
#
# Author: Stefan Haun <tux@netz39.de>

import mido

import sounddevice

import math
import numpy as np

# local modules
from midiproc import MidiMessageProcessorBase
from knobpanel import KnobPanelListener


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


# Sample frequency
samples = 44100


global_hull = np.array([])

def update_hull(duration):
    global global_hull
    
    global_hull = calculate_hull(hull_t_attack,
                                 hull_t_decay,
                                 hull_t_release,
                                 hull_a_sustain,
                                 duration)
    return


def playsine(f):
    w = 2 * np.pi * f
    
    length = global_hull.size
    
    t = np.linspace(0, w*length/samples, num=length)
    
    sine = np.sin(t)
    
    sounddevice.play(sine*global_hull, samples)
    
    return


def beep_on_note(note):
    freq = note2freq(note)
    playsine(freq)
    
    return;


def calculate_hull(t_attack,
                   t_decay,
                   t_release,
                   a_sustain,
                   duration):
    t_sustain = duration - t_attack - t_decay
    if t_sustain < 0:
        t_sustain = 0

    # construct the hull curve
    hull_attack  = np.linspace(0, 1, 
                               num=samples * t_attack)
    hull_decay   = np.linspace(1, a_sustain, 
                               num = samples * t_decay)
    hull_sustain = np.linspace(a_sustain, a_sustain, 
                               num = samples * t_sustain)
    hull_release = np.linspace(a_sustain, 0, num = 
                               samples * t_release)
    
    new_hull = hull_attack
    new_hull = np.append(new_hull, hull_decay)
    new_hull = np.append(new_hull, hull_sustain)
    new_hull = np.append(new_hull, hull_release)
    
    return new_hull


class HullCurveControls(KnobPanelListener):
    # Hull curve parameters
    hull_t_attack  = 0.05    # time s
    hull_t_decay   = 0.10    # time s
    hull_t_release = 0.25    # time s
    hull_a_sustain = 0.90    # amplitude
    
    duration = 0.25
    
    def __init__(self, knob_panel):
        super().__init__()
        self.kp = knob_panel
        
        self.kp.add_knob_value_listener(self)
        
        # Knob to value mapping
        self.knob_map = np.linspace(0, 1.7, num=128)
        self.knob_map = np.power(10, self.knob_map)
        self.knob_map -= 1
        self.knob_map /= 9

        
        # TODO can we get the values here?
        # use the knob panel and observer mechanism to set the initial values
        self.kp.set_target_value(4, 12) # Attack
        self.kp.set_target_value(5, 21) # Decay
        self.kp.set_target_value(6, 115) # Sustain
        self.kp.set_target_value(7, 39) # Release
        
        self.update_hull()
        
        return
    
    
    def adapt_knob_values(self, idx, value):
        # set the values according to Knob
        
        if idx == 4: #attack time
            self.hull_t_attack = self.knob_map[value]
            print("Changed attack time to ", self.hull_t_attack, "s.");
        
        if idx == 5: #decay time
            self.hull_t_decay = self.knob_map[value]
            print("Changed decay time to ", self.hull_t_decay, "s.");
        
        if idx == 6: #sustain amplitude
            self.hull_a_sustain = value/127
            print("Changed sustain amplitude to ", self.hull_a_sustain*100, "%.");
        
        if idx == 7: #release time
            self.hull_t_release = self.knob_map[value]
            print("Changed release time to ", self.hull_t_release, "s.");
        
        return
    
    
    def update_hull(self):
        global global_hull
        
        global_hull = calculate_hull(self.hull_t_attack,
                                     self.hull_t_decay,
                                     self.hull_t_release,
                                     self.hull_a_sustain,
                                     self.duration)
        return
    
    
    def process_knob_value_change(self, idx, value):
        # set the values according to Knob
        self.adapt_knob_values(idx, value)
        
        self.update_hull()
        
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


# kate: space-indent on; indent-width 4; mixedindent off; indent-mode python; indend-pasted-text false; remove-trailing-space off
