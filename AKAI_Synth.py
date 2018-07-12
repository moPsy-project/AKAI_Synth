#!/usr/bin/python3

# AKAI Synth - SoundBlaster FM based synthesizer with AKAI controller
#
# Author: Stefan Haun <tux@netz39.de>

import signal
import sys

import mido

COL_OFF          = 0
COL_GREEN        = 1
COL_GREEN_BLINK  = 2
COL_RED          = 3
COL_RED_BLINK    = 4
COL_YELLOW       = 5
COL_YELLOW_BLINK = 6

def sigint_handler(signal, frame):
    print("SIGINT received. Exit.")
    sys.exit(0)


if __name__ == '__main__':
    signal.signal(signal.SIGINT, sigint_handler)
    
    mido.set_backend('mido.backends.rtmidi')
    
    print(mido.get_input_names())
    
    apc_name = mido.get_input_names()[0]
    apc_name = 'APC Key 25:APC Key 25 MIDI 1 24:0'
    # TODO select from input names
    
    print("Using MIDI port ", apc_name);
    
    inport = mido.open_input(apc_name)
    apc_out = mido.open_output(apc_name)
    outport = mido.open_output()
    
    for c in range(0, 5):
        for i in range(0, 8):
            msg = mido.Message('note_on', channel=0, note=c*8+i, velocity=i)
            apc_out.send(msg)
    
    while (1):
        msg = inport.receive()
        print(msg)
        
        if msg.channel==0 and msg.control==48:
            msg2 = mido.Message('note_on', channel=0, note=0, velocity=msg.value//16)
            apc_out.send(msg2)
        
        outport.send(msg)



# kate: space-indent on; indent-width 4; mixedindent off; indent-mode python; indend-pasted-text false; remove-trailing-space off
