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

class WaveSource:
    def __init__(self,
                 chid=None,
                 samplerate=None,
                 blocksize=None,
                 done_callback=None):
        self.chid = chid
        self.samplerate = samplerate
        self.blocksize = blocksize
        self.done_callback = done_callback
    
    
    def get_chid(self):
        return self.chid
    
    
    def get_samplerate(self):
        return self.samplerate
    
    
    def get_blocksize(self):
        return self.blocksize
    
    
    def done(self):
        if self.done_callback is not None:
            self.done_callback(self.get_chid())
        return
    
    
    def get(self):
        pass


class ChannelQueue(WaveSource):
    # the *_callback gets the channel number as argument
    def __init__(self, 
                 blocksize=441,
                 chid=0,
                 last_callback=None,
                 empty_callback=None):
        super(ChannelQueue,self).__init__(chid,
                                          None,
                                          blocksize,
                                          empty_callback)
        
        self.channel_lock = threading.RLock()
        
        self.sample_queue = asyncio.Queue()
        self.current = None
        self.index = 0

        # this is an arbitrary number which is passed to callback functions
        self.last_callback = last_callback
        return
    
    
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
        
        if not isinstance(wave, np.ndarray):
            raise ValueError("Wave of type {0} is not a numpy ndarray!".format(type(wave)))
        
        self._lock()
        
        # Raises QueueFull if no slot is available
        self.sample_queue.put_nowait(wave)
        
        self._release()
        return
    
    
    def stop(self):
        """Stop emitting samples, graceful with blocksize"""
        self._lock()
        
        # clear current sample or replace by smoothing
        if (self.get_blocksize() > 0) and (not self.empty()):
            stop_hull = np.linspace(1.0, 0.0, num=self.get_blocksize())
            self.current = self.get() * stop_hull
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
        
        self.stop()
        self.enqueue(wave)
        
        self._release()
        return
    
    
    def get(self):
        self._lock()
        
        samples = np.array([])
        
        # fill the samples until we've run out
        while (not self.empty()) and len(samples) < self.get_blocksize():
            count = self.get_blocksize() - len(samples)
            
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
                    if self.empty():
                        self.done()
        
        # padding
        if len(samples) < self.get_blocksize():
            samples = np.append(samples, 
                                [0] * (self.get_blocksize() - len(samples)))
        
        
        self._release()
        return samples
        
        
    def _next(self):
        """Take next sample array from the queue"""
        empty = False
        self._lock()
        
        last = False
        
        if self.sample_queue.empty():
            self.current = None
            empty = True
        else:
            self.current = self.sample_queue.get_nowait()
            self.index = 0
            last = self.sample_queue.empty()
            
        self._release()
        
        if  last and self.last_callback is not None:
            self.last_callback(self.get_chid())
        
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
        unused = [c for c in range(1, self.channels+1) if c not in self.order]
        
        if len(unused) > 0:
            ch = unused[0]
        else:
            # if not available use the channel that has been used for the longest time
            ch = self.order[0]
        
        self.channel_lock.release()
        return ch
    
    
    def reserve_channel(self, 
                        ch=None):
        self._check_channel_arg(ch)
        self.channel_lock.acquire()

        result = None
        
        
        if ch is None:
            result = self._find_free_channel()
        elif is_available_channel(ch):
            result = ch
        
        if result is not None:
            self._put_ch_to_order(result)

        
        self.channel_lock.release()
        return result
    
    
    def release_channel(self,
                        ch):
        self._check_channel_arg(ch)
        
        self._remove_ch_from_order(ch)
        
        return
    
    
    def is_available_channel(self,
                             ch):
        self._check_channel_arg(ch)
        self.channel_lock.acquire()
        
        result = ch is None or ch in self.ch
        
        self.channel_lock.release()
        return result
    
    
    def _check_channel_arg(self, ch):
        if ch is not None and (ch < 1 or ch > self.channels):
            raise ValueError("Channel number must between 1 and the configured bounds({0}): {1}".format(self.channels, ch))
        
        return
    
    
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
             channel=None,
             replace=True):

        c = self.reserve_channel()
        
        if replace:
            self.ch[c-1].replace(wave, blocksize=self.blocksize)
        else:
            self.ch[c-1].enqueue(wave)
        
        return c
    
    
    def channel_empty_callback(self, channel_number):
        self.release_channel(channel_number)
        
        if self.empty_callback is not None:
            self.empty_callback(channel_number)
        
        return
    
    
    def sd_callback(self, outdata, frames, time, status):
        if status:
            print(status)
            
        output = np.array([0]*self.blocksize, dtype='float64')
        
        for i in self.order:
            output += self.ch[i-1].get(self.blocksize, pad=True)
            
        output /= self.channels
        
        outdata[:, 0] = output

        return


class WaveSink:
    # the empty_callback gets the channel number as argument
    def __init__(self,
                 samplerate=44100,
                 blocksize=441,
                 channels=1):
        super().__init__()
        
        self.samplerate = samplerate
        self.blocksize = blocksize
        self.channels = channels
        
        self.channel_lock = threading.RLock()
        
        # available channels
        self.ch = [None] * channels
        
        return
    
    
    def find_free_channel(self):
        self.channel_lock.acquire()

        idx = None
        
        for i in range(0, self.channels):
            if self.ch[i] is None:
                idx = i
                break
        
        self.channel_lock.release()
        return idx
    
    
    def set_channel_source(self, idx, wave_source):
        self._check_channel_arg(idx)
        self.channel_lock.acquire()
        
        if not self.is_available_channel(idx):
            raise ValueError("Channel {0} is already in use!".format(idx))
        
        self.ch[idx] = wave_source
        
        self.channel_lock.release()
        return
    
    
    def release_channel(self,
                        idx):
        self._check_channel_arg(idx)
        
        self.ch[idx] = None
        
        return
    
    
    def is_available_channel(self,
                             idx):
        self._check_channel_arg(idx)
        self.channel_lock.acquire()
        
        result = self.ch[idx] is None
        
        self.channel_lock.release()
        return result
    
    
    def _check_channel_arg(self, idx):
        if idx < 0 or idx >= self.channels:
            raise ValueError("Channel number must between 0 and the configured bounds({0}): {1}".format(self.channels, idx))
        
        return
    
    
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
    
    
    def sd_callback(self, outdata, frames, time, status):
        if status:
            print(status)
            
        output = np.array([0]*self.blocksize, dtype='float64')
        
        for ch in self.ch:
            if ch is not None:
                output += ch.get()
            
        output /= self.channels
        
        outdata[:, 0] = output

        return


# kate: space-indent on; indent-width 4; mixedindent off; indent-mode python; indend-pasted-text false; remove-trailing-space off
