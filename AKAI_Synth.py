#!/usr/bin/python3

# AKAI Synth - SoundBlaster FM based synthesizer with AKAI controller
#
# Author: Stefan Haun <tux@netz39.de>
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSES/MIT.txt

import signal
import sys

import mido

# local modules
from midiproc import MidiMessageProcessorBase, MidiMessagePrinter
from dispatchpanel import DispatchPanel, DispatchPanelListener
from knobpanel import KnobPanel, KnobPanelListener
from softsynthopl2 import HullCurveControls, SineAudioprocessor


processors = [MidiMessagePrinter()]


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
    
    print(f"Midi Inputs : {mido.get_input_names()}")
    print(f"Midi Outputs: {mido.get_output_names()}")
        
    apc_inputs = list(filter(lambda n: n[0:10] == 'APC Key 25',
                            mido.get_input_names()))

    apc_outputs = list(filter(lambda n: n[0:10] == 'APC Key 25',
                            mido.get_output_names()))

    print("Available APCs: ", apc_inputs)
    
    if not apc_inputs:
        print("Did not find APC controller!")
        sys.exit(-1)
    
    apc_in_name = apc_inputs[0]
    apc_out_name = apc_outputs[0]
    print("Using MIDI in port : ", apc_in_name);
    print("Using MIDI out port: ", apc_outputs);
    
    apc_in = mido.open_input(apc_in_name,
                             callback=apc_midi_msg_in)
    apc_out = mido.open_output(apc_out_name)
    
    dp = DispatchPanel(apc_out)
    kp = KnobPanel(dp)
    
    processors.append(SineAudioprocessor(dp, kp))
    processors.append(dp)
    processors.append(kp)
    
    outport = mido.open_output()
    
    input("Press key to finish...")
    
    # Cleanup
    apc_in.close()
    apc_out.close()
    outport.close()


# kate: space-indent on; indent-width 4; mixedindent off; indent-mode python; indend-pasted-text false; remove-trailing-space off
