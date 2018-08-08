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
from scipy import signal


# local modules
from midiproc import MidiMessageProcessorBase
from knobpanel import KnobPanelListener
from dispatchpanel import DispatchPanelListener
import dispatchpanel

from waveoutput import WaveOutput


wo = WaveOutput(channels=8)
wo.start()

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


class HullCurveControls(KnobPanelListener):
    def __init__(self, 
                 knob_panel,
                 parameter_callback=None):
        super().__init__()
        self.kp = knob_panel
        self.kp.add_knob_value_listener(self)
        
        self.parameter_callback = parameter_callback
        
        # Hull curve parameters
        self.hull_t_attack  = 0.05    # time s
        self.hull_t_decay   = 0.10    # time s
        self.hull_t_release = 0.25    # time s
        self.hull_a_sustain = 0.90    # amplitude
        
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
        if self.parameter_callback is not None:
            self.parameter_callback(self.hull_t_attack,
                                    self.hull_t_decay,
                                    self.hull_t_release,
                                    self.hull_a_sustain)
        return
    
    
    def process_knob_value_change(self, idx, value):
        # set the values according to Knob
        self.adapt_knob_values(idx, value)
        
        self.update_hull()
        
        return


class WaveControls(DispatchPanelListener):
    NONE = 0
    
    # wave forms
    SINE = 1
    SAWTOOTH = 2
    SQUARE = 3
    
    # operation modes
    MUL = 1
    ADD = 2
    FOLD = 3
    
    MODECOLOR = [dispatchpanel.COL_OFF,
                 dispatchpanel.COL_GREEN,
                 dispatchpanel.COL_YELLOW,
                 dispatchpanel.COL_RED]
    
    WAVENOTES = [22, 23]
    OPNOTE = 21
    
    def __init__(self, dispatch_panel):
        super().__init__()
        
        self.dp = dispatch_panel
        dispatch_panel.add_dispatch_panel_listener(self)
        
        self.waveform=[0,0]
        self.set_waveform(WaveControls.SINE, 0)
        self.set_waveform(WaveControls.NONE, 1)
        
        self.set_op_mode(WaveControls.MUL)
        
        return
    
    
    def process_button_pressed(self, note):
        print("note", note)
        
        if note in self.WAVENOTES:
            idx = self.WAVENOTES.index(note)
            # set waveform
            wf = self.waveform[idx] + 1
            if wf >= len(WaveControls.MODECOLOR):
                wf = 0
            self.set_waveform(wf, idx)
        
        if note == self.OPNOTE:
            op = self.op_mode + 1
            if op >= len(WaveControls.MODECOLOR):
                op = 0
            self.set_op_mode(op)
        
        return
    
    
    def set_waveform(self, waveform, idx=0):
        self.waveform[idx] = waveform
        self.dp.setColor(WaveControls.WAVENOTES[idx],
                         WaveControls.MODECOLOR[waveform])
        return
    
    
    def get_waveform(self, idx=0):
        return self.waveform[idx]
    
    
    def set_op_mode(self, op_mode):
        self.op_mode = op_mode
        self.dp.setColor(WaveControls.OPNOTE,
                         WaveControls.MODECOLOR[op_mode])
    
    
    def get_op_mode(self):
        return self.op_mode


class SineAudioprocessor(MidiMessageProcessorBase,
                         DispatchPanelListener):
    
    def __init__(self, 
                 dispatch_panel, 
                 knob_panel,
                 sample_frequency=44100):
        super().__init__()
        
        self.sample_frequency = sample_frequency
        
        self.duration = 0.25
        self.hull = np.array([])
        
        self.hc = HullCurveControls(knob_panel,
                                    parameter_callback=self.update_hull)
        self.wc = WaveControls(dispatch_panel)
        
        return
    
    
    def match(self, msg):
        return (msg.type=='note_on' or msg.type=='note_off') and msg.channel==1
    
    
    def process(self, msg):
        if msg.type=='note_on':
            self.play_note(msg.note)
        
        return
    
    
    def play_note(self, note):
        freq = self.note2freq(note)
        
        # frequency multiplier for the second wave
        fmul = 3/2
        
        op_mode = self.wc.get_op_mode()
        
        # generate base wave
        if self.wc.get_waveform(0) == WaveControls.NONE:
            wave0 = 1
        else:
            wave0 = self.genwave(freq, self.wc.get_waveform(0))
        
        # generate second wave, use wave0 as basewave in op mode FOLD
        if self.wc.get_waveform(1) == WaveControls.NONE:
            wave1 = 1
        else:
            basewave = wave0 if op_mode == WaveControls.FOLD else None
            wave1 = self.genwave(freq*fmul, 
                                 self.wc.get_waveform(1),
                                 basewave)
        
        # combine the waves bases on op mode
        if op_mode == WaveControls.MUL:
            wave = wave0 * wave1
        elif op_mode == WaveControls.ADD:
            wave = wave0 + wave1
        elif op_mode == WaveControls.FOLD:
            wave = wave1
        else:
            wave = wave0
        
        wave_output = wave * self.hull
        
        wo.play(wave_output)
        
        return
    
    
    def note2freq(self, note):
        step = note % 12
        
        octave = note // 12
        coeff = math.pow(2, octave - 4)
        
        return SCALE_TONE_FREQUENCIES[step] * coeff
    
    
    def genwave(self, f, waveform, basewave=None):
        w = 2 * np.pi * f
        
        length = self.hull.size
        
        if basewave is None:
            t = np.linspace(0, w*length/self.sample_frequency, num=length)
        else:
            t = basewave
        
        if waveform == WaveControls.SINE:
            wave = np.sin(t)
        elif waveform == WaveControls.SAWTOOTH:
            wave = signal.sawtooth(t)
        elif waveform == WaveControls.SQUARE:
            wave = signal.square(t)
        else: # unknown waveform or NONE
            wave = np.array([0]*length, dtype='float64')
        
        return wave
    
    
    def update_hull(self,
                    attack,
                    decay,
                    release,
                    sustain):
        self.hull = self.calculate_hull(attack,
                                        decay,
                                        release,
                                        sustain,
                                        self.duration)
        return
    
    
    def calculate_hull(self,
                       t_attack,
                       t_decay,
                       t_release,
                       a_sustain,
                       duration):
        t_sustain = duration - t_attack - t_decay
        if t_sustain < 0:
            t_sustain = 0
        
        samples = self.sample_frequency
        
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


# kate: space-indent on; indent-width 4; mixedindent off; indent-mode python; indend-pasted-text false; remove-trailing-space off
