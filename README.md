# AKAI Synth

[![standard-readme compliant](https://img.shields.io/badge/readme%20style-standard-brightgreen.svg?style=flat-square)](https://github.com/RichardLitt/standard-readme)

> AKAI APC Key 25 based synthesizer in the style of SoundBlaster FM (YM3812)

Project goals:

* Emulate a synthesizer in the style of the Yamaha YM3812 chip, as used on SoundBlaster devices.
* Provide a controller for the AKAI APC Key 25 MIDI keyboard/controller to setup and use the synthesizer
* Be a testbed for more cool stuff on computer music.

## Install

There are some library dependencies to enable MIDI access and sound output.

### On Debian 

Install the following packages (version numbers denote package versions with have been tested, anything below can and anything above should work):
* python3-mido:1.1.18-1
* libasound2-dev:1.1.3-5
* libjack-dev:0.125.0-2
* libportmidi0:1:217-6

```
sudo apt-get install python3-mido libasound2-dev libjack-dev libportmidi0
```

The following additional python libraries are needed:
* python-rtmidi
* sounddevice

Install als:
```
pip3 install --user python-rtmidi
pip3 install --user sounddevice
```

Be careful about package names, there are variants around the rtmidi package. Make sure to install exactly the stated package.

### Anywhere else

Make sure that to install the exact dependencies, as there are some variants around the rtmidi package. If there are caveats on certain systems, feel free to add a sub-section here and hand in a PR. Contributions are mist appreciated.

## Usage

Attach the MIDI Controller via USB and start the application:

```
python3 AKAI_Synth.py
```

Press any key to quit.

## Status
This is a very basic first go:
* Control pads and knobs can be read from and written to. There is also a UI around showing where the knobs should be, as their positions cannot be set via MIDI.
* The synthesizer has basic generator cells and can add/fm them together.
* Sound generation is live and cached. Optimization pending.


## Roadmap
Immediate roadmap:
* Extend the synthesizer to support all functions of the YM3812
* Be able to store, edit and load more instruments
* Add the ability to create loops and record into loops
* Add the ability to play pre-defined samples
* Introduce virtual controllers and command routing for the knobs/control panel
* Add a cool number display on the control pad when knobs are turned
* If no MIDI controller is available, use the default MIDI input. This allows more complex MIDI routing and playbacks.
* Persist settings and created instruments
* Allow to tune the system to other (native) instruments

Further out:
* Add a Web-based UI to show settings on a screen and allow a more complex control of the sythesizer
* Add more complex music generation, taking scales, chords and genres into account
* Find a way to adapt playback/generation speed to other people in the ensemble, e.g. by monitoring keyboard input
* Analyze the music generation and allow to generate further music on the fly, e.g. by calculating the chroma vectors, finding rhythms, …
* Allow to record, sound-effect and playback other band members
