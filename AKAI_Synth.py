#!/usr/bin/python3

# AKAI Synth - SoundBlaster FM based synthesizer with AKAI controller
#
# Author: Stefan Haun <tux@netz39.de>

import signal
import sys


def sigint_handler(signal, frame):
    print("SIGINT received. Exit.")
    sys.exit(0)


if __name__ == '__main__':
    signal.signal(signal.SIGINT, sigint_handler)
    
    print("Hello World!")



# kate: space-indent on; indent-width 4; mixedindent off; indent-mode python; indend-pasted-text false; remove-trailing-space off
