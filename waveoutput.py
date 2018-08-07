#!/usr/bin/python3

# AKAI Synth - SoundBlaster FM based synthesizer with AKAI controller
#
# Wave output and stream management
#
# Author: Stefan Haun <tux@netz39.de>

import sounddevice

import math
import numpy as np

import threading

class WaveOutput:
    o_slice = None
    o_idx = 0
    o_lock = threading.Lock()
    
    
    def __init__(self,
                 samplerate=44100,
                 blocksize=441):
        super().__init__()
        
        self.samplerate = samplerate
        self.blocksize = blocksize
        
        self.stop_hull = np.linspace(1.0, 0.0, num=blocksize)

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
        # acquire lock for the output queue
        self.o_lock.acquire()
        
        # mute the current sample if available
        if self.o_slice:
            print("Prepending a sliencer")
            cur = self.o_slice[self.o_idx]
            silencer = cur * self.stop_hull
            wave = np.insert(wave, 0, silencer)
        
        rem = len(wave) % self.blocksize
        if rem != 0:
            add = self.blocksize - rem
            print("Adding", add, "silence samples")
            wave = np.append(wave, [0]*add)

        slices = len(wave) // self.blocksize

        self.o_slice =  np.split(wave, slices)
        self.o_idx = 0
        
        # release lock for the output queue
        self.o_lock.release()
        
        return
    
    
    def sd_callback(self, outdata, frames, time, status):
        if status:
            print(status)
        
        # acquire lock for the output queue
        self.o_lock.acquire()

        if self.o_slice == None:
            outdata[:, 0] = [0] * len(outdata[:, 0])
        else:
            #print("found data, index", self.o_idx)
            outdata[:, 0] = self.o_slice[self.o_idx]
            
            self.o_idx += 1
            if self.o_idx >= len(self.o_slice):
                self.o_slice = None
        
        # release lock for the output queue
        self.o_lock.release()
        
        return


# kate: space-indent on; indent-width 4; mixedindent off; indent-mode python; indend-pasted-text false; remove-trailing-space off
