# Sp1NY

<p align="center">
**THIS TOOL IS (for now) A PROTOTYPE AND IN ITS REALLY EARLY STAGE OF DEVELOPMENT**
</p>

You should expect limited performances as well as unstable use.
We released this prototype for the Show and Tell of INTERSPEECH 2023 in order to collect the need of the community and define the directions to take to reach a useful tool.
We are making all the effort we can to improve this prototype to obtain a stable version of Sp1NY.

![A screenshot of Sp1NY](/sp1ny.png)

## Pre-requisites

It is necesary to have Qt and PortAudio installed on your system.

## Installation

To install Sp1NY, simply clone the repository and use pip:

```sh
pip install -e .
```

## Running examples

### Basic

```sh
spiny -w examples/arctic_a0002.wav
```

### With annotations


```sh
spiny -w examples/arctic_a0002.wav -a examples/arctic_a0002.lab
```

### With raw coefficients

```sh
spiny -w examples/arctic_as.wav -c examples/arctic_as.neur -d -50 -f 6.4
```

- the option `-d` indicates the dimension of the raw data; "-50" indicates a shape of (-1, 50)
- the option `-f` indicates the frameshift in milliseconds

## Standalone application

Ready-to-use builds for Windows, macOS (Apple Silicon and Intel) and Linux are attached to each
[release](https://github.com/sigmedia/sp1ny/releases); no Python installation is needed.

- **Windows**: unzip `spiny-windows-x86_64.zip` and run `spiny\spiny.exe`.
- **macOS**: open `spiny-macos-*.dmg` and drag `Sp1NY.app` to your Applications. The application is not
  signed, so the first time, right-click it and choose *Open*.
- **Linux**: extract `spiny-linux-x86_64.tar.gz` and run `spiny/spiny`. PortAudio must be installed
  (`sudo apt install libportaudio2` on Debian/Ubuntu).

Started without arguments, the application asks for an audio file; the command line options above work too.
The Wavelet plugin is not included in these builds.

To build it yourself (in an environment where Sp1NY is installed):

```sh
pip install pyinstaller praat-parselmouth
cd packaging && pyinstaller --noconfirm spiny.spec
```

The application is created in `packaging/dist`.

## License

Sp1NY is released under the MIT License, see [LICENSE](LICENSE).
