#!/usr/bin/python3

# AKAI Synth - SoundBlaster FM based synthesizer with AKAI controller
#
# Knob Panel control
#
# Author: Stefan Haun <tux@netz39.de>

import mido

# local modules
from midiproc import MidiMessageProcessorBase
from dispatchpanel import DispatchPanelListener
import dispatchpanel


class KnobPanelListener:
    def __init(self):
        return
    
    def process_knob_value_change(self, idx, value):
        pass


# This control controls the knobs and tracks their status
# via eight dispatch panel buttons.
#
# Differences between internal target values and knob values are
# displayed via colors.
#
# Button colors are:
#   OFF         Knob is not in sync with internal value
#   GREEN       Knob and value are in sync
#   GREEN BLINK Value will follow knob, but they are out of sync
#   RED         Knob value is greater than target
#   YELLOW      Knob value is lower than target
#
# To use the knob value as target value, press the dispatch panel 
# button. This will activate tracking and use a value as soon as
# it is available.
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
            self.set_target_value(i, 0)
        
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
        if not self.knob_sync[idx]:
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
        color = dispatchpanel.COL_OFF
        
        if self.midi_values[idx] == None:
            # without a value, blink if synchronized
            color = dispatchpanel.COL_GREEN_BLINK if self.knob_sync[idx] else dispatchpanel.COL_OFF
        elif self.midi_values[idx] > self.target_values[idx]:
            # red if knob is greater than target
            color = dispatchpanel.COL_RED
        elif self.midi_values[idx] < self.target_values[idx]:
            # yellow of knob is lower than target
            color = dispatchpanel.COL_YELLOW
        else:
            # green if both are equal
            color = dispatchpanel.COL_GREEN
        
        self.dp.setColor(self.DISPATCH_NOTES[idx], color)
        
        return
    
    
    def process_button_pressed(self, note):
        # check if relevant
        if not note in self.DISPATCH_NOTES:
            return
        
        idx = self.DISPATCH_NOTES.index(note)
        
        # set synced
        self.knob_sync[idx] = True
        
        # set midi value to target value, if available
        value = self.midi_values[idx]
        if value != None:
            self.set_target_value(idx, value)
        else:
            # needs to be called explicitly heres
            self._update_color(idx)
        
        return
    
    
    def add_knob_value_listener(self, listener):
        if listener:
            self.knob_value_listeners.append(listener)
        return
    
    
    def _dispatch_knob_value_change(self, idx, value):
        for l in self.knob_value_listeners:
            l.process_knob_value_change(idx, value)
        return


# kate: space-indent on; indent-width 4; mixedindent off; indent-mode python; indend-pasted-text false; remove-trailing-space off
