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
import asyncio

class ChannelQueue:
    # the empty_callback gets the channel number as argument
    def __init__(self, 
                 channel_number=0,
                 empty_callback=None):
        super().__init__()
        
        self.channel_lock = threading.RLock()
        
        self.sample_queue = asyncio.Queue()
        self.current = None
        self.index = 0

        # this is an arbitrary number which is passed to callback functions
        self.channel_number = channel_number
        self.empty_callback = empty_callback
        return
    
    
    def get_channel_number(self):
        return self.channel_number()
    
    
    def _lock(self):
        """Lock the channel for queue operations"""
        self.channel_lock.acquire()
    
    
    def _release(self):
        """Release the channel from queue operations"""
        self.channel_lock.release()
    
    
    def empty(self):
        self._lock()
        
        empty = self.sample_queue.empty() and self.current is None
        
        self._release()
        return empty
    
    
    def enqueue(self, wave):
        """Enqueue waveform array to play list"""
        self._lock()
        
        # Raises QueueFull if no slot is available
        self.sample_queue.put_nowait(wave)
        
        self._release()
        return
    
    
    def stop(self, blocksize=0):
        """Stop emitting samples, graceful with blocksize"""
        self._lock()
        
        # clear current sample or replace by smoothing
        if (blocksize > 0) and (not self.empty()):
            stop_hull = np.linspace(1.0, 0.0, num=blocksize)
            self.current = self.get(blocksize, pad=True) * stop_hull
            self.index = 0
        else:
            self.current = None
        
        # empty out the queue
        while not self.sample_queue.empty():
            self.sample_queue.get_nowait()
        # this function has been called explicitly, so there is no 
        # callback, except from the get function if stop has also
        # emptied the queue
        
        self._release()
        return
    
    
    def replace(self, wave, blocksize=0):
        """Replace current queue with new samples, maybe graceful"""
        self._lock()
        
        self.stop(blocksize)
        self.enqueue(wave)
        
        self._release()
        return
    
    
    def get(self, blocksize, pad=False):
        """Get blocksize samples from the channel, can pad with zero"""
        self._lock()
        
        samples = np.array([])
        
        # fill the samples until we've run out
        while (not self.empty()) and len(samples) < blocksize:
            count = blocksize - len(samples)
            
            # check if next queued array must be used
            if self.current is None:
                self._next()
            
            # take samples if available
            if self.current is not None:
                avail = len(self.current) - self.index
                if avail > count:
                    avail = count
                
                samples = np.append(samples,
                                    self.current[self.index:self.index+avail])
                self.index += avail
                
                # discard block if all samples are used up
                if self.index >= len(self.current):
                    self.current = None
                    # callback if empty
                    if (self.empty_callback is not None) and self.empty():
                        self.empty_callback(self.channel_number)
        
        # padding
        if pad and len(samples) < blocksize:
            samples = np.append(samples, 
                                [0] * (blocksize - len(samples)))
        
        
        self._release()
        return samples
        
        
    def _next(self):
        """Take next sample array from the queue"""
        self._lock()
        
        try:
            self.current = self.sample_queue.get_nowait()
            self.index = 0
        except asyncio.QueueEmpty:
            self.current = None
        
        self._release()
        return self.current
    
    
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
