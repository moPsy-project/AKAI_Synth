#!/usr/bin/python3

# AKAI Synth - SoundBlaster FM based synthesizer with AKAI controller
#
# OPL2-type software synthesizer
#
# Author: Stefan Haun <tux@netz39.de>
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSES/MIT.txt

import mido

import sounddevice

import math
import copy
import numpy as np
from scipy import signal

import threading

# local modules
from midiproc import MidiMessageProcessorBase
from knobpanel import KnobPanelListener
from dispatchpanel import DispatchPanelListener
import dispatchpanel

from waveoutput import WaveSource
from waveoutput import WaveSink


# Source: https://upload.wikimedia.org/wikipedia/commons/a/ad/Piano_key_frequencies.png
SCALE_TONE_FREQUENCIES = [
    261.626, # C4 (Middle C)
    277.183, # C#4 / Db4
    293.665, # D4
    311.127, # D#4 / Eb4
    329.628, # E4
    349.228, # F4
    369.994, # F#4 / Gb4
    391.995, # G4
    415.305, # G#4 / Ab4
    440.000, # A4
    466.164, # A#4, Bb4
    493.883, # B
]

class FixedWaveSequencer(WaveSource):
    """Sequence a fixed wave once"""
    def __init__(self,
                 samples,
                 blocksize,
                 loop_once=False):
        super(FixedWaveSequencer, 
              self).__init__(blocksize=blocksize)
        
        self.samples = np.array(samples)
        
        self.idx = 0
        
        return
    
    
    # Note: using python generators sample-wise is too slow!!
    def get(self):
        """return the next self.blocksize samples"""
        
        wave = np.array([], dtype='float64')
        
        if self.idx < len(self.samples):
            e = self.idx + self.get_blocksize()
            if e > len(self.samples):
                e = len(self.samples)
            wave = np.append(wave, self.samples[self.idx:e])
            self.idx = e
        
        # calculate remaining samples
        remain = self.get_blocksize() - len(wave)
        
        if remain > 0:
            # fill with silence
            wave = np.append(wave,
                             np.array([0] * remain, dtype='float64'))
        
        return wave
    
    
    def finished(self):
        """State if the sequencer is done with its samples"""
        return self.idx >= len(self.samples)


class FixedWaveLoopSequencer(WaveSource):
    """Loop through a fixed wave"""
    def __init__(self,
                 samples,
                 blocksize):
        super(FixedWaveLoopSequencer, 
              self).__init__(blocksize=blocksize)
        
        self.samples = np.array(samples)
        
        # repeat samples to at least match the block size,
        # so that there is at most one wrap-around during get
        while len(self.samples) < self.get_blocksize():
            self.samples = np.append(self.samples,
                                     samples)
        
        self.idx = 0
        
        return
    
    
    # Note: using python generators sample-wise is too slow!!
    def get(self):
        """return the next self.blocksize samples"""
        
        wave = np.array([], dtype='float64')
        
        # add up tp blocksize samples to the wave, if available
        e = self.idx + self.get_blocksize()
        if e > len(self.samples):
            e = len(self.samples)
        wave = np.append(wave, self.samples[self.idx:e])
        self.idx = e
        
        # calculate remaining samples
        remain = self.get_blocksize() - len(wave)
        
        if remain > 0:
            # remain is guaranteed to be < len(samples)
            wave = np.append(wave,
                             self.samples[0:remain])
            # update index
            self.idx = remain
        
        return wave


class EnvelopeParameters:
    """Parameters for wave envelope"""
    
    def __init__(self):
        super().__init__()
        
        # Attach time in ms
        self.attack = 0
        
        # Decay time in ms
        self.decay = 0
        
        # Sustain niveau in % of attack amplitude
        self.sustain = 0
        
        # Release time  in ms
        self.release = 0
        
        # True if note can be sustained
        self.hold = False
        
        return
    
    
    def get_attack(self):
        return self.attack
    
    
    def set_attack(self, value):
        old = self.attack
        self.attack = value
        return old
    
    
    def get_decay(self):
        return self.decay
    
    
    def set_decay(self, value):
        old = self.decay
        self.decay = value
        return old
    
    
    def get_sustain(self):
        return self.sustain
    
    
    def set_sustain(self, value):
        old = self.sustain
        self.sustain = value
        return old
    
    
    def get_release(self):
        return self.release
    
    
    def set_release(self, value):
        old = self.release
        self.release = value
        return old
    
    
    def is_hold(self):
        return self.hold
    
    
    def set_hold(self, value):
        old = self.hold
        self.hold = value
        return old


class EnvelopeState:
    def __init__(self):
        self.phase = EnvelopeSequencer.PHASE_INIT
        self.idx = 0
        self.struck = False
        self.released = True
        
        self.amp = 0
        
        return


class EnvelopeSequencer(WaveSource):
    PHASE_INIT = 0
    PHASE_ATTACK = 1
    PHASE_DECAY = 2
    PHASE_SUSTAIN = 3
    PHASE_RELEASE = 4
    PHASE_TUNEDOWN = 5
    PHASE_DONE = 6
    
    
    def __init__(self,
                 generator,
                 blocksize = 441,
                 samplerate = 44100,
                 phase_callback = None,
                 done_callback = None):
        super(EnvelopeSequencer, 
              self).__init__(blocksize=blocksize,
                             samplerate=samplerate,
                             done_callback=done_callback)
        
        self.generator = generator
        self.phase_callback = phase_callback
        
        self.state = EnvelopeState()
        
        return
    
    
    def __del__(self):
        pass
    
    
    def get(self):
        fragment = None
        
        if self.generator is None:
            fragement = np.array([], dtype='float64')
        else:
            # store old state
            _state = copy.deepcopy(self.state)
            
            fragment = self.generator.generate(self.state, self.get_blocksize())
            
            # handle the strike flag
            if self.state.struck == True:
                if self.state.phase not in [EnvelopeSequencer.PHASE_INIT,
                                      EnvelopeSequencer.PHASE_DONE]:
                    #print(fragment)
                    r = int(self.get_samplerate() * 0.007)
                    if r > self.get_blocksize():
                        r = self.get_blocksize()
                    
                    fragment = np.append(np.linspace(fragment[0], 0, num=r), [0]*(self.get_blocksize()-r))
                    
                    
                    print("setting linspace from {0} to {1}".format(fragment[0], fragment[-1]))
                    #print(fragment)

                self.state.phase = EnvelopeSequencer.PHASE_ATTACK
                self.state.idx = 0
                self.state.released = False
            
                # reset the strike flag
                self.state.struck = False
                
            
            # handle callbacks
            if _state.phase != self.state.phase:
                if self.phase_callback is not None:
                    self.phase_callback(self, _state.phase, self.state.phase)
                    
                if self.state.phase == EnvelopeSequencer.PHASE_DONE:
                    self.done()
        
        if len(fragment) != self.get_blocksize():
            print("FRAGMENT LENGTH MISMATCH:", len(fragment))
        return fragment
    
    
    def reset(self):
        self.state.phase = EnvelopeSequencer.PHASE_INIT
        self.state.idx = 0
        
        return
    
    
    def strike(self):
        self.state.struck = True
        
        return
    
    
    def release(self):
        self.state.released = True
        
        return
    
    
    def tunedown(self):
        self.state.phase = EnvelopeSequencer.PHASE_TUNEDOWN
    
    
    def is_finished(self):
        return self.state.phase == EnvelopeSequencer.PHASE_DONE


class EnvelopeGenerator:
    def __init__(self,
                 samplerate = 44100,
                 parameter_callback = None):
        super().__init__()
        self.samplerate = samplerate
        self.parameter_callback = parameter_callback
        
        self.set_parameters(EnvelopeParameters())
        
        self.env_strike = None
        self.env_release = None
        
        return
    
    
    def __del__(self):
        pass
    
    
    def get_parameters(self):
        return self.p
    
    
    def set_parameters(self, parameters):
        self.p = parameters
        
        self.cache_attack = np.array([], dtype='float64')
        self.cache_decay = np.array([], dtype='float64')
        self.cache_release = np.array([], dtype='float64')
        
        return
        
        
    def generate(self,
                 state,
                 blocksize):
        n_attack = math.ceil(self.samplerate * self.p.get_attack())
        n_decay = math.ceil(self.samplerate *  self.p.get_decay())
        n_release = math.ceil(self.samplerate * self.p.get_release())
        
        wave = np.array([], dtype='float64')
        
        # Init phase is handled together with the Done phase
        # Intermediate phase transitions do not have an effect here,
        # as the index idx is not moved, except when all envelope 
        # parameters are zero, then we transistion to Done (which 
        # still would not make a difference.
        
        
        # Handle Attack phase
        if state.phase == EnvelopeSequencer.PHASE_ATTACK:
            wave, self.cache_attack, state.idx = self._append_env_fragment(
                             wave, self.cache_attack,
                             n_attack, state.idx,
                             0, 1,
                             blocksize)
        
            # Check phase transition
            if state.idx == n_attack:
                state.phase = EnvelopeSequencer.PHASE_DECAY
                state.idx = 0
        
        # Handle Decay phase
        if state.phase == EnvelopeSequencer.PHASE_DECAY:
            wave, self.cache_decay, state.idx = self._append_env_fragment(
                             wave, self.cache_decay,
                             n_decay, state.idx,
                             1, self.p.get_sustain(),
                             blocksize)
        
            # Check phase transistion
            if state.idx == n_decay:
                state.phase = EnvelopeSequencer.PHASE_SUSTAIN if self.p.is_hold() else EnvelopeSequencer.PHASE_RELEASE
                state.idx = 0
        
        # Stustain phase
        if state.phase == EnvelopeSequencer.PHASE_SUSTAIN:
            # pad with the sustain value
            
            # use a linear space so that in-process changes of the amplitude to not create cracks
            _fragment = np.linspace(state.amp,
                                    self.p.get_sustain(),
                                    blocksize - len(wave))
            wave = np.append(wave, _fragment)
            
            # index does not matter here
            
            # Check phase transition
            if state.released == True:
                state.phase = EnvelopeSequencer.PHASE_RELEASE
        
            # this phase can only be left via outside intervention
        
        # Release phase
        if state.phase == EnvelopeSequencer.PHASE_RELEASE:
            wave, self.cache_release, state.idx = self._append_env_fragment(
                             wave, self.cache_release,
                             n_release, state.idx,
                             self.p.get_sustain(), 0,
                             blocksize)
        
            # Check phase transistion
            if state.idx == n_release:
                state.phase = EnvelopeSequencer.PHASE_TUNEDOWN
                state.idx = 0
        
        # Tunedown phase
        if state.phase == EnvelopeSequencer.PHASE_TUNEDOWN:
            # complete tunedown in 7 ms
            loss = 1/7
            
            # calculate loss per sample
            samples_p_ms = self.samplerate / 1000
            loss_per_sample = loss / samples_p_ms
            
            # how many samples to tune down?
            td_samples = math.ceil(state.amp / loss_per_sample)
            
            # calculate fragment length within remaining block
            fragment_length = blocksize-len(wave)
            
            if td_samples > fragment_length:
                td_samples = fragment_length
            
            a1 = state.amp
            a2 = state.amp - (loss_per_sample * td_samples)
            if a2 < 0:
                a2 = 0
            
            _fragment = np.linspace(a1, a2, num=td_samples)
            wave = np.append(wave, _fragment)

            # Check phase transition
            if a2 == 0:
                state.phase = EnvelopeSequencer.PHASE_DONE

        # Init or Done Phase
        if state.phase in [EnvelopeSequencer.PHASE_INIT, EnvelopeSequencer.PHASE_DONE]:
            # pad with silence
            _fragment = [0] * (blocksize - len(wave))
            wave = np.append(wave, _fragment)
            
            # index does not matter here
        
        # these phases can only be left via outside intervention
        
        # store the last generated amplitude
        state.amp = wave[-1]
        
        return wave
    
    
    def min_envelope_samples(self):
        # duplicate the calculation from gen!
        return math.ceil(self.samplerate * self.p.get_attack()) + math.ceil(self.samplerate * self.p.get_decay()) + math.ceil(self.samplerate * self.p.get_release())
    
    
    def _append_env_fragment(self,
                             wave, cache,
                             num, idx,
                             val_start, val_end,
                             blocksize):
        
        # choose end index based on samples left over
        _end = idx + blocksize - len(wave)
        if _end > num:
            _end = num
        
        # check cache
        if len(cache) < _end:
            _f = self._calculate_env_fragment(val_start, val_end,
                                              num,
                                              len(cache) - 1, _end)
            cache = np.append(cache, _f)

        _fragment = cache[idx:_end]
        
        if len(wave) > 0:
            wave = np.append(wave, _fragment)
        else:
            wave = _fragment
        
        idx = _end
        
        return [wave, cache, idx]
    
    
    def _calculate_env_fragment(self,
                                val_start, val_end,
                                num,  # length of whole segment
                                idx_start, idx_end):
        if idx_start > idx_end:
            raise ValueError("Start index must not be greater than end index!")
        
        if num < 0:
            raise ValueError("Segment length num must not be lower than zero!")
        
        if idx_start == idx_end or num == 0:
            return np.array([], dtype='float64')
        
        _tangent = (val_end - val_start) / num
        _a = val_start + _tangent * idx_start
        _b = val_start + _tangent * idx_end
        
        #_a, _b = np.interp([idx_start, idx_end],
        #                   [0, num], [val_start, val_end])
        
        return np.linspace(_a, _b,
                           num = idx_end - idx_start)


class HullCurveControls(KnobPanelListener):
    def __init__(self, 
                 knob_panel,
                 parameter_callback=None):
        super().__init__()
        self.kp = knob_panel
        self.kp.add_knob_value_listener(self)
        
        self.parameter_callback = parameter_callback
        
        # Hull curve parameters
        self.hull_t_attack  = 0.05    # time s
        self.hull_t_decay   = 0.10    # time s
        self.hull_t_release = 0.25    # time s
        self.hull_a_sustain = 0.90    # amplitude
        
        # Knob to value mapping
        self.knob_map = np.linspace(0, 1.7, num=128)
        self.knob_map = np.power(10, self.knob_map)
        self.knob_map -= 1
        self.knob_map /= 9

        
        # TODO can we get the values here?
        # use the knob panel and observer mechanism to set the initial values
        self.kp.set_target_value(4, 12) # Attack
        self.kp.set_target_value(5, 21) # Decay
        self.kp.set_target_value(6, 115) # Sustain
        self.kp.set_target_value(7, 39) # Release
        
        self.update_hull()
        
        return
    
    
    def adapt_knob_values(self, idx, value):
        # set the values according to Knob
        
        if idx == 4: #attack time
            self.hull_t_attack = self.knob_map[value]
            print("Changed attack time to ", self.hull_t_attack, "s.");
        
        if idx == 5: #decay time
            self.hull_t_decay = self.knob_map[value]
            print("Changed decay time to ", self.hull_t_decay, "s.");
        
        if idx == 6: #sustain amplitude
            self.hull_a_sustain = value/127
            print("Changed sustain amplitude to ", self.hull_a_sustain*100, "%.");
        
        if idx == 7: #release time
            self.hull_t_release = self.knob_map[value]
            print("Changed release time to ", self.hull_t_release, "s.");
        
        return
    
    
    def update_hull(self):
        if self.parameter_callback is not None:
            env_p = EnvelopeParameters()
            env_p.set_attack(self.hull_t_attack)
            env_p.set_decay(self.hull_t_decay)
            env_p.set_release(self.hull_t_release)
            env_p.set_sustain(self.hull_a_sustain)
            env_p.set_hold(True)

            self.parameter_callback(env_p)
        return
    
    
    def process_knob_value_change(self, idx, value):
        # set the values according to Knob
        self.adapt_knob_values(idx, value)
        
        self.update_hull()
        
        return

class ModulationIndexControl(KnobPanelListener):
    def __init__(self, 
                 knob_panel,
                 modulation_index_callback=None):
        super().__init__()
        self.kp = knob_panel
        self.kp.add_knob_value_listener(self)
        
        self.modulation_index_callback = modulation_index_callback
        
        # Knob amplitude mapping
        self.knob_amp_map = np.linspace(-0.9, 0, num=64)
        self.knob_amp_map = np.append(self.knob_amp_map,
                                  np.linspace(0, 0.9, num=64))
        
        # Knob to modulation index mapping
        self.knob_midx_map = list(map(lambda x: math.floor(x),
                                  np.linspace(0, 15, num=128)))
        
        # use the knob panel and observer mechanism to set the initial values
        self.amp = [0.5, 0.5]
        self.kp.set_target_value(0, 64)
        self.midx = 1
        self.kp.set_target_value(1, 9) 
        
        return
    
    
    def adapt_knob_values(self, idx, value):
        # set the values according to Knob
        
        if idx == 0: #amplitude distribution
            v = self.knob_amp_map[value]
            self.amp[0] = 1 - v
            self.amp[1] = 1 + v
            
            print("Changed amplitudes to ", self.amp[0], "and", self.amp[1], ".");
        
        if idx == 1: #frequency multiplier
            self.midx = self.knob_midx_map[value]
            if self.modulation_index_callback is not None:
                self.modulation_index_callback(self.midx)
            print("Changed modulation index to ", self.midx, ".");
        
        return
    
    
    def process_knob_value_change(self, idx, value):
        # set the values according to Knob
        self.adapt_knob_values(idx, value)
        
        return
    
    
    def get_amp(self, idx):
        return self.amp[idx]
    
    
    def get_midx(self):
        return self.midx


class WaveControls(DispatchPanelListener):
    MODECOLOR = [dispatchpanel.COL_OFF,
                 dispatchpanel.COL_GREEN,
                 dispatchpanel.COL_YELLOW,
                 dispatchpanel.COL_RED]
    
    WAVENOTES = [22, 23]
    FMNOTE = 21
    MODIDXNOTES = [65, 64]
    
    def __init__(self, 
                 dispatch_panel,
                 waveform_callback=None,
                 fm_callback=None,
                 modidx_callback=None):
        super().__init__()
        
        self.dp = dispatch_panel
        dispatch_panel.add_dispatch_panel_listener(self)
        
        self.waveform_callback = waveform_callback
        self.fm_callback = fm_callback
        self.modidx_callback = modidx_callback
        
        self.waveform=[0,0]
        self.set_waveform(Cell.WAVE_SINE, 0)
        self.set_waveform(Cell.WAVE_SINE, 1)
        
        self.set_fm_mode(True)
        self.set_modidx(0)
        
        return
    
    
    def process_button_pressed(self, note):
        print("note", note)
        
        if note in self.WAVENOTES:
            idx = self.WAVENOTES.index(note)
            # set waveform
            wf = self.waveform[idx] + 1
            if wf >= len(WaveControls.MODECOLOR):
                wf = 0
            self.set_waveform(wf, idx)
        
        if note == self.FMNOTE:
            self.set_fm_mode(not self.fm_mode)
        
        if note == self.MODIDXNOTES[0]:
            self.set_modidx(self.get_modidx()-1)
        if note == self.MODIDXNOTES[1]:
            self.set_modidx(self.get_modidx()+1)
        
        return
    
    
    def set_waveform(self, waveform, idx=0):
        _waveform = self.waveform[idx]
        
        self.waveform[idx] = waveform
        self.dp.setColor(WaveControls.WAVENOTES[idx],
                         WaveControls.MODECOLOR[waveform])
        
        if self.waveform_callback is not None:
            self.waveform_callback(idx, waveform)
        
        return _waveform
    
    
    def get_waveform(self, idx=0):
        return self.waveform[idx]
    
    
    def set_fm_mode(self, fm_mode):
        self.fm_mode = fm_mode
        self.dp.setColor(WaveControls.FMNOTE,
                         dispatchpanel.COL_GREEN if fm_mode else dispatchpanel.COL_YELLOW)
        
        if self.fm_callback is not None:
            self.fm_callback(fm_mode)
        
        return
    
    
    def get_fm_mode(self):
        return self.fm_mode
    
    
    def set_modidx(self, modidx):
        self.modidx = modidx;
        
        # adjust boundaries
        if self.modidx < 0:
            self.modidx = 0
        if self.modidx > 15:
            self.modidx = 15;
        
        # set button colors (only red and off available)
        self.dp.setColor(WaveControls.MODIDXNOTES[0],
                         (dispatchpanel.COL_RED
                          if self.modidx > 0
                          else dispatchpanel.COL_OFF))
        self.dp.setColor(WaveControls.MODIDXNOTES[1],
                         (dispatchpanel.COL_RED
                          if self.modidx < 15
                          else dispatchpanel.COL_OFF))
        
        if self.modidx_callback is not None:
            self.modidx_callback(self.modidx)
        
        print("Modulation index adjusted to {0}.".format(self.modidx))
        return
    
    
    def get_modidx(self):
        return self.modidx



class Cell(WaveSource):
    # wave forms
    WAVE_OFF = 0
    WAVE_SINE = 1
    WAVE_SAWTOOTH = 2
    WAVE_SQUARE = 3
    
    
    def __init__(self,
                 chid=None,
                 modulator = None,
                 samplerate = 44100,
                 blocksize = 441,
                 done_callback = None):
        super(Cell, self).__init__(chid=chid,
                                   samplerate=samplerate,
                                   blocksize=blocksize,
                                   done_callback=done_callback)
        #setting the modulator enables frequency modulation
        self.modulator = modulator
        
        self.waveform = None
        self.frequency = None
        self.midx = 1    # modulation index
        
        self.envelope = EnvelopeGenerator(self.get_samplerate())
        
        
        self.env_gen = EnvelopeSequencer(self.envelope, 
                                         self.get_blocksize(),
                                         self.get_samplerate(),
                                         None,
                                         self._seq_done_callback)
        self.wave_gen = None
        
        return
    
    
    def set_envelope(self, p):
        if not isinstance(p, EnvelopeParameters):
            raise ValueError("EnvelopeParameters expected!")
        
        self.envelope.set_parameters(p)
        
        return
    
    
    def set_frequency(self, f):
        self.frequency = f
        
        self._update_wavegen()

        return
    
    
    def set_waveform(self, waveform):
        self.waveform = waveform
        
        self._update_wavegen()
        
        return
    
    
    def set_modulator(self, modulator):
        self.modulator = modulator
        
        self._update_wavegen()
        
        return
    
    
    def set_midx(self, midx):
        self.midx = 1 if midx is None else midx
        
        return
    
    
    def _update_wavegen(self):
        if self.frequency is None:
            return None
        
        # one period on the chosen frequency
        w = 2 * np.pi * self.frequency
        t = np.linspace(0, 2 * np.pi, 
                        num=self.get_samplerate() // self.frequency)
        
        if self.modulator is not None:
           # When there is a modulator, this is the stored wave
            wave = t
        else:
            wave = self._generate_wave(t)
        
        self.wave_gen = FixedWaveLoopSequencer(wave, 
                                               self.get_blocksize())
        
        return
    
    
    def _generate_wave(self, base):
        if base is None:
            return None
        
        if self.waveform == self.WAVE_SINE:
            wave = np.sin(base)
        elif self.waveform == self.WAVE_SAWTOOTH:
            wave = signal.sawtooth(base)
        elif self.waveform == self.WAVE_SQUARE:
            wave = signal.square(base)
        else: # unknown waveform or NONE
            l = 1 if base is None else len(base)
            wave = np.array([0]*l, dtype='float64')
        
        return wave
    
    
    def strike(self):
        self.env_gen.strike()
        
        return
    
    
    def release(self):
        self.env_gen.release()
        
        return
    
    
    def tunedown(self):
        self.env_gen.tunedown()
    
    
    def stop(self):
        self.env_gen.reset()
        
        return
    
    
    def get(self):
        wave = None
        
        if self.wave_gen is not None:
            if self.modulator is None:
                wave = self.wave_gen.get()
            else:
                t = self.wave_gen.get()
                mod = self.modulator.get()
                wave = self._generate_wave(t+self.midx*mod)
            
            wave *= self.env_gen.get()
        else:
            wave = np.array([0]*self.get_blocksize(), dtype='float64')
        
        return wave
    
    
    def _seq_done_callback(self, seq):
        self.done()
        
        return


class FMChannel(WaveSource):
    CELL_COUNT = 2
    
    
    def __init__(self,
                 chid=None,
                 samplerate=44100,
                 blocksize=441,
                 done_callback = None):
        super(FMChannel, self).__init__(chid=chid,
                                        samplerate=samplerate,
                                        blocksize=blocksize,
                                        done_callback=done_callback)
        
        self.cells = []
        for i in range(0, self.CELL_COUNT):
            self.cells.append(
                Cell(i,
                     None,
                     samplerate, blocksize,
                     self.cell_done_callback))
        
        # set fm
        self.set_fm_mode(True)
        
        self.cell_active = [False]*self.CELL_COUNT
        
        return
    
    
    def set_envelope(self, idx, env_p):
        if idx < 0 or idx > len(self.cells)-1:
            raise ValueError("Cell index {0} is out of bounds!".format(idx))
        
        self.cells[idx].set_envelope(env_p)
        
        return
    
    
    def set_waveform(self, idx, waveform):
        if idx < 0 or idx > len(self.cells)-1:
            raise ValueError("Cell index {0} is out of bounds!".format(idx))
        
        self.cells[idx].set_waveform(waveform)
        
        return
    
    
    def set_frequency(self, frequency):
        for i in range(0, len(self.cells)):
            self.cells[i].set_frequency(frequency)
        
        return
    
    
    def set_midx(self, midx):
        self.cells[0].set_midx(midx)
        
        return
    
    
    def set_fm_mode(self, fm_mode):
        self.fm_mode = fm_mode
        self.cells[0].set_modulator(self.cells[1] if fm_mode else None)
        
        return
    
    
    def strike(self):
        for i in range(0, len(self.cells)):
            self.cells[i].strike()
        
        return
    
    
    def release(self):
        for i in range(0, len(self.cells)):
            self.cells[i].release()
        
        return
    
    
    def tunedown(self):
        for i in range(0, len(self.cells)):
            self.cells[i].tunedown()
        
        return
    
    
    def get(self):
        wave = self.cells[0].get()
        
        if not self.fm_mode:
            wave += self.cells[1].get()
            wave /= 2
        
        return wave
    
    
    def cell_done_callback(self, chid):
        self.cell_active[chid] = False
        
        if not True in self.cell_active:
            self.done()
        
        return


class SineAudioprocessor(MidiMessageProcessorBase,
                         DispatchPanelListener):
    def __init__(self, 
                 dispatch_panel, 
                 knob_panel,
                 sample_frequency=44100):
        super().__init__()
        
        self.sample_frequency = sample_frequency
        
        self.ws = WaveSink(channels=8)
        self.ws.start()
        
        self.fm_channel_lock = threading.RLock()
        
        self.fm_channels = 8
        self.fm_channel = []
        
        for i in range(0, self.fm_channels):
            self.fm_channel.append(
                FMChannel(i,
                          sample_frequency, 441,
                          self.channel_done_callback))
            
            self.ws.set_channel_source(i, self.fm_channel[i])
        
        self.fm_channel_order = []
        self.note2channel = {}
        
        self.hc = HullCurveControls(knob_panel,
                                    parameter_callback=self.update_hull)
        
        self.wc = WaveControls(dispatch_panel,
                               self.waveform_callback,
                               self.fm_mode_callback,
                               self.modulation_index_callback)
        
        return
    
    
    def match(self, msg):
        return (msg.type=='note_on' or msg.type=='note_off') and msg.channel==1
    
    
    def process(self, msg):
        if msg.type=='note_on':
            self.dispatch_strike(msg.note)
        
        if msg.type=='note_off':
            self.dispatch_release(msg.note)

        return
    
    
    def _remove_channel_from_order(self, idx):
        self.fm_channel_lock.acquire()
        
        self.fm_channel_order = [c for c in self.fm_channel_order if c != idx]
        
        self.fm_channel_lock.release()
        return
    
    
    def _put_channel_to_order(self, idx):
        self.fm_channel_lock.acquire()
        
        self._remove_channel_from_order(idx)
        self.fm_channel_order.append(idx)
        
        self.fm_channel_lock.release()
        return
    
    
    def _free_channel(self, idx):
        self.fm_channel_lock.acquire()
        
        self._remove_channel_from_order(idx)
        
        # remove from note dictionary
        i = None
        for n, c in self.note2channel.items():
            if c == idx:
                i = idx
                break
        
        if i is not None:
            del self.note2channel[n]
        
        self.fm_channel_lock.release()
        return
    
    
    def _find_channel(self):
        self.fm_channel_lock.acquire()
        
        idx = 0
        
        # try an unused channel
        unused = [c for c in range(0, self.fm_channels) if c not in self.fm_channel_order]
        
        if len(unused) > 0:
            idx = unused[0]
        else:
            # if not available use the channel that has been used for the longest time
            idx = self.fm_channel_order[0]

        self.fm_channel_lock.release()
        return idx
        
    
    def dispatch_strike(self, note):
        self.fm_channel_lock.acquire()
        
        # find a suitable channel
        idx = None
        
        # check if channel is active
        if note in self.note2channel:
            idx = self.note2channel[note]
            # tune channel down
            self.fm_channel[idx].tunedown()

        # otherwise find a channel
        idx = self._find_channel()
        # free the channel
        self._free_channel(idx)

        
        self._put_channel_to_order(idx)
        self.note2channel[note] = idx
        
        freq = self.note2freq(note)
        self.fm_channel[idx].set_frequency(freq)
        
        self.fm_channel[idx].strike()
        
        self.fm_channel_lock.release()
        return
        
    
    def dispatch_release(self, note):
        self.fm_channel_lock.acquire()
        
        if note in self.note2channel:
            idx = self.note2channel[note]
            self.fm_channel[idx].release()
        
        self.fm_channel_lock.release()
        return
    
    
    def channel_done_callback(self, channel):
        self.fm_channel_lock.acquire()
        
        self._free_channel(channel)
        
        self.fm_channel_lock.release()
        return
    
    
    def note2freq(self, note):
        step = note % 12
        
        octave = note // 12
        coeff = math.pow(2, octave - 4)
        
        return SCALE_TONE_FREQUENCIES[step] * coeff
    
    
    def update_hull(self,
                    env_p):
        for c in range(0, self.fm_channels):
            for i in range(0, FMChannel.CELL_COUNT):
                self.fm_channel[c].set_envelope(i, env_p)
        
        return
    
    
    def waveform_callback(self, idx, waveform):
        for i in range(0, self.fm_channels):
            self.fm_channel[i].set_waveform(idx, waveform)
        
        return
    
    
    def fm_mode_callback(self, fm_mode):
        for i in range(0, self.fm_channels):
            self.fm_channel[i].set_fm_mode(fm_mode)
        
        return
    
    
    def modulation_index_callback(self, midx):
        for i in range(0, self.fm_channels):
            self.fm_channel[i].set_midx(midx)
        
        return


# kate: space-indent on; indent-width 4; mixedindent off; indent-mode python; indend-pasted-text false; remove-trailing-space off
