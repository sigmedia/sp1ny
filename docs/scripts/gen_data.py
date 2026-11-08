"""Generate a synthetic recording with dense annotations and raw coefficients for the benchmark

usage: python gen_data.py OUT_DIR NAME DURATION_S

It writes OUT_DIR/NAME.wav (16 kHz), OUT_DIR/NAME.json (three annotation tiers with mean segment
durations of 70, 200 and 350 ms) and OUT_DIR/NAME.neur (50-dimensional float32 coefficients every 5 ms).
"""

from __future__ import annotations

import json
import sys

import numpy as np
import soundfile as sf

SAMPLING_RATE = 16000


def make_tier(rng: np.random.Generator, duration: float, mean: float) -> list[dict]:
    """Draw a tier of contiguous segments with exponentially distributed durations

    Parameters
    ----------
    rng : np.random.Generator
        The random generator
    duration : float
        The duration covered by the tier, in seconds
    mean : float
        The mean duration of a segment, in seconds

    Returns
    -------
    list(dict)
        The segments, in the spiny JSON format
    """
    bounds = np.cumsum(rng.exponential(mean, int(duration / mean * 1.2)))
    bounds = bounds[bounds < duration]
    starts = np.concatenate([[0.0], bounds])
    ends = np.concatenate([bounds, [duration]])
    return [
        {"start_time": float(s), "end_time": float(e), "label": f"x{i % 50}"}
        for i, (s, e) in enumerate(zip(starts, ends))
    ]


def main(out_dir: str, name: str, duration: float) -> None:
    """Write the recording, its annotations and its coefficients

    Parameters
    ----------
    out_dir : str
        The output directory
    name : str
        The base name of the files
    duration : float
        The duration of the recording, in seconds
    """
    rng = np.random.default_rng(0)
    t = np.arange(int(SAMPLING_RATE * duration)) / SAMPLING_RATE
    vibrato = 120 + 30 * np.sin(2 * np.pi * 0.5 * t)
    signal = (0.3 * np.sin(2 * np.pi * vibrato * t) + 0.02 * rng.standard_normal(t.size)).astype(np.float32)
    del t, vibrato
    sf.write(f"{out_dir}/{name}.wav", signal, SAMPLING_RATE)

    annotations = {
        "phones": make_tier(rng, duration, 0.07),
        "syllables": make_tier(rng, duration, 0.2),
        "words": make_tier(rng, duration, 0.35),
    }
    with open(f"{out_dir}/{name}.json", "w") as f_out:
        json.dump({"version": 1, "annotations": annotations, "ignored": []}, f_out)

    np.zeros((int(duration / 0.005), 50), dtype=np.float32).tofile(f"{out_dir}/{name}.neur")
    print(name, {tier: len(segments) for tier, segments in annotations.items()}, signal.size)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], float(sys.argv[3]))
