#!/usr/bin/python3

# AKAI Synth - SoundBlaster FM based synthesizer with AKAI controller
#
# OPL2-type software synthesizer
#
# Author: Stefan Haun <tux@netz39.de>

import mido

import sounddevice

import math
import copy
import numpy as np
from scipy import signal

# local modules
from midiproc import MidiMessageProcessorBase
from knobpanel import KnobPanelListener
from dispatchpanel import DispatchPanelListener
import dispatchpanel

from waveoutput import WaveOutput


wo = WaveOutput(channels=8)
wo.start()

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
            self.parameter_callback(self.hull_t_attack,
                                    self.hull_t_decay,
                                    self.hull_t_release,
                                    self.hull_a_sustain)
        return
    
    
    
    def process_knob_value_change(self, idx, value):
        # set the values according to Knob
        self.adapt_knob_values(idx, value)
        
        self.update_hull()
        
        return


class FrequencyControl(KnobPanelListener):
    def __init__(self, 
                 knob_panel):
        super().__init__()
        self.kp = knob_panel
        self.kp.add_knob_value_listener(self)
        
        # Knob amplitude mapping
        self.knob_amp_map = np.linspace(-0.9, 0, num=64)
        self.knob_amp_map = np.append(self.knob_amp_map,
                                  np.linspace(0, 0.9, num=64))
        
        # Knob to frequency value mapping
        self.knob_fmul_map = np.linspace(1/16, 1, num=64)
        self.knob_fmul_map = np.append(self.knob_fmul_map,
                                  np.linspace(1, 16, num=64))
        
        # use the knob panel and observer mechanism to set the initial values
        self.amp = [0.5, 0.5]
        self.kp.set_target_value(0, 64)
        self.freqmul = 1
        self.kp.set_target_value(1, 64) 
        
        return
    
    
    def adapt_knob_values(self, idx, value):
        # set the values according to Knob
        
        
        if idx == 0: #amplitude distribution
            v = self.knob_amp_map[value]
            self.amp[0] = 1 - v
            self.amp[1] = 1 + v
            
            print("Changed amplitudes to ", self.amp[0], "and", self.amp[1], ".");
        
        if idx == 1: #frequency multiplier
            self.freqmul = self.knob_fmul_map[value]
            print("Changed frequency multiplier to ", self.freqmul, ".");
        
        return
    
    
    def process_knob_value_change(self, idx, value):
        # set the values according to Knob
        self.adapt_knob_values(idx, value)
        
        return
    
    
    def get_amp(self, idx):
        return self.amp[idx]
    
    
    def get_freqmul(self):
        return self.freqmul


class WaveControls(DispatchPanelListener):
    NONE = 0
    
    # wave forms
    SINE = 1
    SAWTOOTH = 2
    SQUARE = 3
    
    # operation modes
    MUL = 1
    ADD = 2
    FOLD = 3
    
    MODECOLOR = [dispatchpanel.COL_OFF,
                 dispatchpanel.COL_GREEN,
                 dispatchpanel.COL_YELLOW,
                 dispatchpanel.COL_RED]
    
    WAVENOTES = [22, 23]
    OPNOTE = 21
    
    def __init__(self, dispatch_panel):
        super().__init__()
        
        self.dp = dispatch_panel
        dispatch_panel.add_dispatch_panel_listener(self)
        
        self.waveform=[0,0]
        self.set_waveform(WaveControls.SINE, 0)
        self.set_waveform(WaveControls.SINE, 1)
        
        self.set_op_mode(WaveControls.FOLD)
        
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
        
        if note == self.OPNOTE:
            op = self.op_mode + 1
            if op >= len(WaveControls.MODECOLOR):
                op = 0
            self.set_op_mode(op)
        
        return
    
    
    def set_waveform(self, waveform, idx=0):
        self.waveform[idx] = waveform
        self.dp.setColor(WaveControls.WAVENOTES[idx],
                         WaveControls.MODECOLOR[waveform])
        return
    
    
    def get_waveform(self, idx=0):
        return self.waveform[idx]
    
    
    def set_op_mode(self, op_mode):
        self.op_mode = op_mode
        self.dp.setColor(WaveControls.OPNOTE,
                         WaveControls.MODECOLOR[op_mode])
    
    
    def get_op_mode(self):
        return self.op_mode


class SineAudioprocessor(MidiMessageProcessorBase,
                         DispatchPanelListener):
    
    def __init__(self, 
                 dispatch_panel, 
                 knob_panel,
                 sample_frequency=44100):
        super().__init__()
        
        self.sample_frequency = sample_frequency
        
        self.duration = 0.25
        self.hull = np.array([])
        
        self.hc = HullCurveControls(knob_panel,
                                    parameter_callback=self.update_hull)
        self.fc = FrequencyControl(knob_panel)
        self.wc = WaveControls(dispatch_panel)
        
        return
    
    
    def match(self, msg):
        return (msg.type=='note_on' or msg.type=='note_off') and msg.channel==1
    
    
    def process(self, msg):
        if msg.type=='note_on':
            self.play_note(msg.note)
        
        return
    
    
    def play_note(self, note):
        freq = self.note2freq(note)
        
        # amplitudes
        a0 = self.fc.get_amp(0)
        a1 = a1 = self.fc.get_amp(1)
        
        # frequency multiplier for the second wave
        fmul = self.fc.get_freqmul()
        
        op_mode = self.wc.get_op_mode()
        
        # generate second wave, use wave0 as basewave in op mode FOLD
        if self.wc.get_waveform(1) == WaveControls.NONE:
            wave1 = 1
        else:
            wave1 = self.genwave(freq*fmul,
                                 self.wc.get_waveform(1))
        # apply amplitude
        wave1 *= a1

        # generate base wave
        if self.wc.get_waveform(0) == WaveControls.NONE:
            wave0 = 1
        else:
            basewave = wave1 if op_mode == WaveControls.FOLD else None
            wave0 = self.genwave(freq, 
                                 self.wc.get_waveform(0), 
                                 basewave)
        # apply amplitude
        wave0 *= a0
        
        
        # combine the waves bases on op mode
        if op_mode == WaveControls.MUL:
            wave = wave0 * wave1
        elif op_mode == WaveControls.ADD:
            wave = wave0 + wave1
            # normalize the amplitude
            wave /= 2
        elif op_mode == WaveControls.FOLD:
            wave = wave0
        else:
            wave = wave0
        
        wave_output = wave
        
        # only play if the result is an actual ndarray
        if isinstance(wave, np.ndarray):
            wo.play(wave_output)
        
        return
    
    
    def note2freq(self, note):
        step = note % 12
        
        octave = note // 12
        coeff = math.pow(2, octave - 4)
        
        return SCALE_TONE_FREQUENCIES[step] * coeff
    
    
    def wave_generator(self, f, waveform):
        # one period on the chosen frequency
        w = 2 * np.pi * f
        t = np.linspace(0, 2 * np.pi, num=self.sample_frequency // f)
        
        if waveform == WaveControls.SINE:
            wave = np.sin(t)
        elif waveform == WaveControls.SAWTOOTH:
            wave = signal.sawtooth(t)
        elif waveform == WaveControls.SQUARE:
            wave = signal.square(t)
        else: # unknown waveform or NONE
            wave = np.array([0], dtype='float64')
        
        gen = FixedWaveLoopSequencer(wave, 411)
        
        return gen
    
    
    def genwave(self, f, waveform, basewave=None):
        length = len(self.hull)
        hgen = FixedWaveSequencer(self.hull, 411)
        
        gen = self.wave_generator(f, waveform)
        
        wave = np.array([], dtype='float64')
        hull = np.array([], dtype='float64')
        while len(wave) < length:
            wave = np.append(wave, gen.get())
            hull = np.append(hull, hgen.get())
        
        return hull * wave
    
    def update_hull(self,
                    attack,
                    decay,
                    release,
                    sustain):
        self.hull = self.calculate_hull(attack,
                                        decay,
                                        release,
                                        sustain,
                                        self.duration)
        return
    
    
    def calculate_hull(self,
                       t_attack,
                       t_decay,
                       t_release,
                       a_sustain,
                       duration):
        t_sustain = duration - t_attack - t_decay
        if t_sustain < 0:
            t_sustain = 0
        
        samples = self.sample_frequency
        
        # construct the hull curve
        hull_attack  = np.linspace(0, 1, 
                                num=samples * t_attack)
        hull_decay   = np.linspace(1, a_sustain, 
                                num = samples * t_decay)
        hull_sustain = np.linspace(a_sustain, a_sustain, 
                                num = samples * t_sustain)
        hull_release = np.linspace(a_sustain, 0, num = 
                                samples * t_release)
        
        new_hull = hull_attack
        new_hull = np.append(new_hull, hull_decay)
        new_hull = np.append(new_hull, hull_sustain)
        new_hull = np.append(new_hull, hull_release)
        
        return new_hull


# kate: space-indent on; indent-width 4; mixedindent off; indent-mode python; indend-pasted-text false; remove-trailing-space off
