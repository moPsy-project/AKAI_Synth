#!/usr/bin/python3

# AKAI Synth - SoundBlaster FM based synthesizer with AKAI controller
#
# Midi message processing
#
# Author: Stefan Haun <tux@netz39.de>
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSES/MIT.txt

import mido

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


# kate: space-indent on; indent-width 4; mixedindent off; indent-mode python; indend-pasted-text false; remove-trailing-space off
