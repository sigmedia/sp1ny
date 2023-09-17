# Sp1NY

<p align="center">
**THIS TOOL IS (for now) A PROTOTYPE AND IN ITS REALLY EARLY STAGE OF DEVELOPMENT**
</p>

You should expect limited performances as well as unstable use.
We released this prototype for the Show and Tell of INTERSPEECH 2023 in order to collect the need of the community and define the directions to take to reach a useful tool.
We are making all the effort we can to improve this prototype to obtain a stable version of Sp1NY.

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
