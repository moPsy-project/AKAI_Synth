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


class DispatchPanelListener():
    def __init__(self):
        return
    
    def process_button_pressed(self, note):
        pass
    
    def process_button_released(self, note):
        pass


class DispatchPanel(MidiMessageProcessorBase):
    listeners = []
    
    def __init__(self, apc_out):
        self.apc_out = apc_out
        return

    def match(self, msg):
        return (msg.type=='note_on' or msg.type=='note_off') and msg.channel==0 and msg.note <= 39

    def process(self, msg):
        if msg.type == 'note_on':
            self._dispatch_button_pressed(msg.note)
        elif msg.type == 'note_off':
            self._dispatch_button_released(msg.note)
        else:
            # TODO exception?
            print("Control panel: Unexpected message", msg)
        
        return
    
    
    def setColor(self, note, color):
        if note > 39:
            return # TODO exception
        
        msg = mido.Message('note_on', channel=0, note=note, velocity=color)
        apc_out.send(msg)
    
    
    def add_dispatch_panel_listener(self, l):
        if l:
            self.listeners.append(l)
        return
    
    
    def _dispatch_button_pressed(self, note):
        for l in self.listeners:
            l.process_button_pressed(note)
        return
    
    
    def _dispatch_button_released(self, note):
        for l in self.listeners:
            l.process_button_released(note)
        return


class KnobPanelListener:
    def __init(self):
        return
    
    def process_knob_value_change(self, idx, value):
        pass
    

class KnobPanel(MidiMessageProcessorBase, DispatchPanelListener):
    DISPATCH_NOTES = [36, 37, 38, 39,
                      28, 29, 30, 31]
    
    KNOB_CONTROLS = [48, 49, 50, 51,
                     52, 53, 54, 55]
    
    # Values obtained by MIDI message
    midi_values = [None, None, None, None,
                   None, None, None, None]
    
    target_values = [0, 0, 0, 0,
                     0, 0, 0, 0]
    
    # true if the knob is in sync,
    # i.e. the target value has been explicitly set by the midi value
    knob_sync = [False, False, False, False,
                 False, False, False, False]
    
    knob_value_listeners = []
    
    def __init__(self, dispatchPanel):
        super().__init__()
        self.dp = dispatchPanel
        
        # TODO can we get the values here?
        # so far knob values are unknown
        for i in range(0, 8):
            self._update_knob_midi_value(i, None)
            self.set_target_value(i, 64)
        
        self.dp.add_dispatch_panel_listener(self)
        
        return
    
    
    def match(self, msg):
        return msg.type=="control_change" and msg.channel==0 and msg.control in self.KNOB_CONTROLS
    
    
    def process(self, msg):
        idx = self.KNOB_CONTROLS.index(msg.control)
        # raises exception on unknown control. We should have filtered this earlier
        
        self._update_knob_midi_value(idx, msg.value)
        
        return
    
    
    def _update_knob_midi_value(self, idx, value):
        if idx >= len(self.midi_values):
            return # TODO exception
        
        # store midi value
        self.midi_values[idx] = value
        
        # check knob synchronization
        if value == None:
            # lose sync if there is no midi value
            self.knob_sync[idx] = False
        elif not self.knob_sync[idx]:
            # sync if midi equals target value
            self.knob_sync[idx] = (value == self.target_values[idx])

        # this is an extra call to notify the listeners
        if self.knob_sync[idx]:
            # adjust target value if in sync
            self.target_values[idx] = value
            # notify listeners
            self._dispatch_knob_value_change(idx, value)
        
        self._update_color(idx)
        return
    
    
    def set_target_value(self, idx, value):
        if idx >= len(self.target_values):
            return # TODO exception
        
        # check if knob will de-sync
        self.knob_sync[idx] = (self.midi_values[idx] == value)
        
        self.target_values[idx] = value
        # notify listeners
        self._dispatch_knob_value_change(idx, value)
        
        self._update_color(idx)
        return
    
    
    def _update_color(self, idx):
        color = COL_OFF
        
        if self.midi_values[idx] == None:
            color = COL_OFF
        elif self.midi_values[idx] > self.target_values[idx]:
            color = COL_RED
        elif self.midi_values[idx] < self.target_values[idx]:
            color = COL_YELLOW
        else:
            color = COL_GREEN
        
        self.dp.setColor(self.DISPATCH_NOTES[idx], color)
        
        return
    
    
    def process_button_pressed(self, note):
        # check if relevant
        if not note in self.DISPATCH_NOTES:
            return
        
        idx = self.DISPATCH_NOTES.index(note)
        
        # set midi value to target value, if available
        value = self.midi_values[idx]
        if value != None:
            self.set_target_value(idx, value)
        
        # else do nothing
        
        return
    
    
    def add_knob_value_listener(self, listener):
        if listener:
            self.knob_value_listeners.append(listener)
        return
    
    
    def _dispatch_knob_value_change(self, idx, value):
        for l in self.knob_value_listeners:
            l.process_knob_value_change(idx, value)
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


class HullCurveControls(MidiMessageProcessorBase):
    # Hull curve parameters
    hull_t_attack  = 0.05    # time s
    hull_t_decay   = 0.10    # time s
    hull_t_release = 0.25    # time s
    hull_a_sustain = 0.90    # amplitude
    
    duration = 0.25
    
    def __init__(self, apc_out):
        self.apc_out = apc_out
        
        # Knob to value mapping
        self.knob_map = np.linspace(0, 1.7, num=128)
        self.knob_map = np.power(10, self.knob_map)
        self.knob_map -= 1
        self.knob_map /= 9

        
        # TODO can we get the values here?
        
        self.update_hull()
        
        return
    
    def match(self, msg):
        return msg.type=="control_change" and msg.channel==0 and msg.control in range(52, 56);
    
    
    def adapt_knob_values(self, msg):
        # set the values according to Knob
        
        if msg.control == 52: #attack time
            self.hull_t_attack = self.knob_map[msg.value]
            print("Changed attack time to ", self.hull_t_attack, "s.");
        
        if msg.control == 53: #decay time
            self.hull_t_decay = self.knob_map[msg.value]
            print("Changed decay time to ", self.hull_t_decay, "s.");
        
        if msg.control == 54: #sustain amplitude
            self.hull_a_sustain = msg.value/127
            print("Changed sustain amplitude to ", self.hull_a_sustain*100, "%.");
        
        if msg.control == 55: #release time
            self.hull_t_release = self.knob_map[msg.value]
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
    
    
    def process(self, msg):
        # set the values according to Knob
        self.adapt_knob_values(msg)
        
        self.update_hull()
        
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
    
    dp = DispatchPanel(apc_out)
    kp = KnobPanel(dp)
    
    processors.append(KnobColorProcessor(apc_out))
    processors.append(HullCurveControls(apc_out))
    processors.append(dp)
    processors.append(kp)
    
    outport = mido.open_output()
    
#    for c in range(0, 5):
#        for i in range(0, 8):
#            msg = mido.Message('note_on', channel=0, note=c*8+i, velocity=i)
#            apc_out.send(msg)
    
    
    input("Press key to finish...")
    
    # Cleanup
    apc_in.close()
    apc_out.close()
    outport.close()



# kate: space-indent on; indent-width 4; mixedindent off; indent-mode python; indend-pasted-text false; remove-trailing-space off
