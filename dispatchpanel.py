#!/usr/bin/python3

# AKAI Synth - SoundBlaster FM based synthesizer with AKAI controller
#
# Dispatch Panel control
#
# Author: Stefan Haun <tux@netz39.de>
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSES/MIT.txt

import mido

# local modules
from midiproc import MidiMessageProcessorBase

COL_OFF          = 0
COL_GREEN        = 1
COL_GREEN_BLINK  = 2
COL_RED          = 3
COL_RED_BLINK    = 4
COL_YELLOW       = 5
COL_YELLOW_BLINK = 6


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
        self.apc_out.send(msg)
    
    
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


# kate: space-indent on; indent-width 4; mixedindent off; indent-mode python; indend-pasted-text false; remove-trailing-space off
