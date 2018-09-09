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

## Maintainers
This project is mostly, but not necessary solely, maintained by Stefan Haun (<tux@netz39.de>).

Contributions by:
* Stefan Haun <tux@netz39.de>, known on GitHub as @penguineer

## Contribute
Contributions are welcome. Please consider the roadmap for your contributions. The maintainers are happy to answer questions.

To contribute, fork the repository and create a feature branch. Please do not add commits on the master branch, as these will not be accepted. Create a PR to have your contribution reviewed and eventually accepted into the code base. Write access to this repository is only granted to maintainers. Any contribution should come from a fork via pull request.

Bugs or wished may be reported with an issue. You can also open an issue to state the intention of a certain contribution. Please mark this as an extension and comment in the issue that you are going to work on this.
