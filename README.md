# PyPraG

## Environment installation

In order to configure the environment for PyPraG, it is advised to use conda.
In order to learn about conda, please refer to the following introduction: https://docs.conda.io/projects/conda/en/latest/user-guide/getting-started.html

To create the conda environment, you can use the following command:

```sh
conda env create -f environment.yml
```

## Running examples

### Basic

```sh
pyprag -w examples/arctic_a0002.wav
```

### With annotations


```sh
pyprag -w examples/arctic_a0002.wav -a examples/arctic_a0002.lab
```

### With raw coefficients

```sh
pyprag -w examples/arctic_as.wav -c examples/arctic_as.neur -d -50 -f 6.4
```

- the option `-d` indicates the dimension of the raw data; "-50" indicates a shape of (-1, 50)
- the option `-f` indicates the frameshift in milliseconds
