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
