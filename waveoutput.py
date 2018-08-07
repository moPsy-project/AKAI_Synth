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
    # the empty_callback gets the channel number as argument
    def __init__(self,
                 samplerate=44100,
                 blocksize=441,
                 channels=1,
                 empty_callback=None):
        super().__init__()
        
        self.samplerate = samplerate
        self.blocksize = blocksize
        self.channels = channels
        self.empty_callback = empty_callback
        
        # order in which channels have been used
        self.order = [] 
        
        self.channel_lock = threading.RLock()
        
        # available channels
        self.ch = []
        for i in range(1, channels+1):
            self.ch.append(
                ChannelQueue(channel_number = i,
                             empty_callback = self.channel_empty_callback))
        
        return
    
    
    def _remove_ch_from_order(self, ch):
        self.channel_lock.acquire()
        
        self.order = [c for c in self.order if c != ch]
        
        self.channel_lock.release()
        return
    
    
    def _put_ch_to_order(self, ch):
        self.channel_lock.acquire()

        self._remove_ch_from_order(ch)
        self.order.append(ch)
        
        self.channel_lock.release()
        return
    
    def _find_free_channel(self):
        self.channel_lock.acquire()

        ch = 0
        
        # try an unused channel
        unused = [c for c in range(0, self.channels) if c not in self.order]
        
        if len(unused) > 0:
            ch = unused[0]
        else:
            # if not available use the channel that has been used for the longest time
            ch = self.order[0]
        
        self.channel_lock.release()
        return ch
        
    
    def start(self):
        self.stream = sounddevice.OutputStream(
                samplerate = self.samplerate,
                blocksize = self.blocksize,
                #channels=self.channels,
                # this does not work too well,
                # we better mix ourselves
                channels=1,
                callback=self.sd_callback)
        
        self.stream.start()
        
        return
    
    def stop(self):
        self.stream.stop()
        self.stream = None
        
        return
    
    
    def play(self,
             wave,
             channel=0,
             replace=True):

        # take the channel that has been used last
        self.channel_lock.acquire()

        c = 0
        if c == 0:
            c = self._find_free_channel()
        else:
            c = channel-1
        self._put_ch_to_order(c)
            
        self.channel_lock.release()
        
        if replace:
            self.ch[c].replace(wave, blocksize=self.blocksize)
        else:
            self.ch[c].enqueue(wave)
        
        return c
    
    
    def channel_empty_callback(self, channel_number):
        self._put_ch_to_order(channel_number-1)
        
        if self.empty_callback is not None:
            self.empty_callback(channel_number)
        
        return
    
    
    def sd_callback(self, outdata, frames, time, status):
        if status:
            print(status)
            
        output = np.array([0]*self.blocksize, dtype='float64')
        
        for i in self.order:
            output += self.ch[i].get(self.blocksize, pad=True)
            
        output /= self.channels
        
        outdata[:, 0] = output

        return


# kate: space-indent on; indent-width 4; mixedindent off; indent-mode python; indend-pasted-text false; remove-trailing-space off
