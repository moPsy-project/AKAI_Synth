#!/usr/bin/python3

# AKAI Synth - SoundBlaster FM based synthesizer with AKAI controller
#
# Wave output and stream management
#
# Author: Stefan Haun <tux@netz39.de>

import sounddevice

import math
import numpy as np

class WaveOutput:
    samplerate = 44100
    blocksize = samplerate // 100
    
    silence = [0] * blocksize
    
    o_slice = None
    o_idx = 0
    
    
    def __init__(self):
        super().__init__()
        
        return
    
    
    def start(self):
        self.stream = sounddevice.OutputStream(
                samplerate = self.samplerate,
                blocksize = self.blocksize,
                channels=1,
                callback=self.sd_callback)
        
        self.stream.start()
        
        return
    
    def stop(self):
        self.stream.stop()
        self.stream = None
        
        return
    
    
    def play(self, wave):
        rem = len(wave) % self.blocksize
        if rem != 0:
            add = self.blocksize - rem
            print("Adding", add, "silence samples")
            wave = np.append(wave, [0]*add)

        slices = len(wave) // self.blocksize

        self.o_slice =  np.split(wave, slices)
        self.o_idx = 0
        
        return
    
    
    def sd_callback(self, outdata, frames, time, status):
        if status:
            print(status)
        
        global wave_output
        if self.o_slice == None:
            outdata[:, 0] = self.silence
        else:
            #print("found data, index", self.o_idx)
            outdata[:, 0] = self.o_slice[self.o_idx]
            
            self.o_idx += 1
            if self.o_idx >= len(self.o_slice):
                self.o_slice = None
        
        
        return


# kate: space-indent on; indent-width 4; mixedindent off; indent-mode python; indend-pasted-text false; remove-trailing-space off
