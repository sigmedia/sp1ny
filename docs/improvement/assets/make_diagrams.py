"""Generate the SVG diagrams explaining the algorithms of the performance work

usage: python make_diagrams.py   (run from this directory; writes the *.svg files next to it)

The diagrams are plain SVG written by hand, with the same palette as the result figures (make_figures.py):
blue for the data that is kept or computed, orange for what is highlighted (the view, a selection), and
neutral greys for the structure. Text uses neutral inks, never a series colour.
"""

from __future__ import annotations

import math
from pathlib import Path

HERE = Path(__file__).resolve().parent

SURFACE = "#fcfcfb"
TEXT = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
LINE = "#8f8e88"
LIGHT = "#e4e3de"
BLUE = "#2a78d6"
BLUE_LIGHT = "#cfe0f6"
ORANGE = "#eb6834"
ORANGE_LIGHT = "#fbdccf"
FONT = "font-family='Helvetica, Arial, sans-serif'"


def text(
    x: float, y: float, content: str, size: int = 12, color: str = TEXT, anchor: str = "start", weight: str = "normal"
) -> str:
    """Build an SVG text element

    Parameters
    ----------
    x, y : float
        The anchor position
    content : str
        The text
    size : int, optional
        The font size in pixels. (default: 12)
    color : str, optional
        The text colour. (default: TEXT)
    anchor : str, optional
        The SVG text-anchor ("start", "middle" or "end"). (default: "start")
    weight : str, optional
        The font weight. (default: "normal")

    Returns
    -------
    str
        The element
    """
    return (
        f"<text x='{x:.1f}' y='{y:.1f}' {FONT} font-size='{size}' fill='{color}' "
        f"text-anchor='{anchor}' font-weight='{weight}'>{content}</text>"
    )


def rect(
    x: float, y: float, w: float, h: float, fill: str, stroke: str = "none", radius: float = 3, dash: str = ""
) -> str:
    """Build an SVG rectangle

    Parameters
    ----------
    x, y : float
        The top-left corner
    w, h : float
        The size
    fill : str
        The fill colour ("none" for no fill)
    stroke : str, optional
        The stroke colour. (default: "none")
    radius : float, optional
        The corner radius. (default: 3)
    dash : str, optional
        The stroke dash pattern (e.g. "4 3"), empty for a solid stroke. (default: "")

    Returns
    -------
    str
        The element
    """
    dash_attr = f" stroke-dasharray='{dash}'" if dash else ""
    return (
        f"<rect x='{x:.1f}' y='{y:.1f}' width='{w:.1f}' height='{h:.1f}' rx='{radius}' fill='{fill}' "
        f"stroke='{stroke}' stroke-width='1.5'{dash_attr}/>"
    )


def line(x1: float, y1: float, x2: float, y2: float, color: str = LINE, width: float = 1.5, dash: str = "") -> str:
    """Build an SVG line

    Parameters
    ----------
    x1, y1, x2, y2 : float
        The end points
    color : str, optional
        The colour. (default: LINE)
    width : float, optional
        The stroke width. (default: 1.5)
    dash : str, optional
        The stroke dash pattern, empty for a solid line. (default: "")

    Returns
    -------
    str
        The element
    """
    dash_attr = f" stroke-dasharray='{dash}'" if dash else ""
    return (
        f"<line x1='{x1:.1f}' y1='{y1:.1f}' x2='{x2:.1f}' y2='{y2:.1f}' "
        f"stroke='{color}' stroke-width='{width}'{dash_attr}/>"
    )


def arrow(x1: float, y1: float, x2: float, y2: float, color: str = LINE) -> str:
    """Build an arrow from (x1, y1) to (x2, y2)

    Parameters
    ----------
    x1, y1, x2, y2 : float
        The start and the tip
    color : str, optional
        The colour. (default: LINE)

    Returns
    -------
    str
        The elements
    """
    angle = math.atan2(y2 - y1, x2 - x1)
    left = (x2 - 8 * math.cos(angle - 0.4), y2 - 8 * math.sin(angle - 0.4))
    right = (x2 - 8 * math.cos(angle + 0.4), y2 - 8 * math.sin(angle + 0.4))
    return line(x1, y1, x2, y2, color) + (
        f"<path d='M{x2:.1f},{y2:.1f} L{left[0]:.1f},{left[1]:.1f} L{right[0]:.1f},{right[1]:.1f} Z' fill='{color}'/>"
    )


def svg(width: int, height: int, body: list[str], title: str) -> str:
    """Wrap elements in an SVG document with an explicit background

    Parameters
    ----------
    width, height : int
        The size in pixels
    body : list(str)
        The elements
    title : str
        The accessible title of the diagram

    Returns
    -------
    str
        The document
    """
    return (
        f"<svg xmlns='http://www.w3.org/2000/svg' width='{width}' height='{height}' viewBox='0 0 {width} {height}' "
        f"role='img'><title>{title}</title><rect width='{width}' height='{height}' fill='{SURFACE}'/>"
        + "".join(body)
        + "</svg>\n"
    )


def waveform_pyramid() -> str:
    """Min/max pyramid of the waveform and the per-pixel-column reduction

    Returns
    -------
    str
        The SVG document
    """
    width, height = 900, 470
    left, plot_w = 150, 650
    body = [text(24, 30, "Waveform: min/max pyramid and per-pixel envelope", 16, weight="bold")]

    # Samples (a deterministic pseudo-signal)
    samples = [math.sin(i / 3.1) * (0.4 + 0.6 * abs(math.sin(i / 37))) + 0.15 * math.sin(i * 1.7) for i in range(256)]
    y0, amp = 95, 32
    body.append(text(left - 14, y0 + 4, "samples", 12, TEXT, "end"))
    body.append(text(left - 14, y0 + 19, "N × 4 bytes", 11, TEXT_SECONDARY, "end"))
    step = plot_w / len(samples)
    path = " ".join(f"{'M' if i == 0 else 'L'}{left + i * step:.1f},{y0 - amp * s:.1f}" for i, s in enumerate(samples))
    body.append(f"<path d='{path}' fill='none' stroke='{BLUE}' stroke-width='1'/>")

    # Pyramid levels: each element keeps the min and max of `factor` samples
    levels = [
        (16, "level 64", "N/64 × 2 × 4 bytes"),
        (64, "level 1024", "N/1024 × 2 × 4 bytes"),
        (256, "level 16384", "…"),
    ]
    for row, (block, label, size) in enumerate(levels):
        y = 170 + row * 62
        body.append(text(left - 14, y + 4, label, 12, TEXT, "end"))
        body.append(text(left - 14, y + 19, size, 11, TEXT_SECONDARY, "end"))
        for b in range(len(samples) // block):
            chunk = samples[b * block : (b + 1) * block]
            x = left + b * block * step
            w = block * step
            top, bottom = y - amp * 0.8 * max(chunk), y - amp * 0.8 * min(chunk)
            body.append(rect(x + 1, top, w - 2, bottom - top, BLUE_LIGHT, BLUE, radius=2))
        body.append(arrow(left + plot_w + 18, y - 44, left + plot_w + 18, y - 14, LINE))
    body.append(text(left + plot_w + 30, 140, "min / max", 11, TEXT_SECONDARY))
    body.append(text(left + plot_w + 30, 154, "of blocks", 11, TEXT_SECONDARY))

    # Pixel columns: the visible range is cut in columns, each column takes min/max of the level elements in it
    y = 385
    body.append(text(left - 14, y - 16, "screen", 12, TEXT, "end"))
    body.append(text(left - 14, y - 1, "W pixel columns", 11, TEXT_SECONDARY, "end"))
    view_x0, view_x1 = left + 4 * 16 * step, left + 12 * 16 * step
    body.append(rect(view_x0, 152, view_x1 - view_x0, 270, "none", ORANGE, radius=4, dash="5 4"))
    body.append(text(view_x1 + 8, 418, "visible range", 11, TEXT))
    columns = 8
    col_w = (view_x1 - view_x0) / columns
    for c in range(columns):
        chunk = samples[4 * 16 + c * 16 : 4 * 16 + (c + 1) * 16]
        x = view_x0 + c * col_w + col_w / 2
        body.append(line(x, y - amp * 0.8 * max(chunk) - 12, x, y - amp * 0.8 * min(chunk) - 12, BLUE, 3))
    body.append(
        text(
            left,
            450,
            "Each column draws one vertical segment from the minimum to the maximum of its samples, read",
            12,
            TEXT_SECONDARY,
        )
    )
    body.append(
        text(
            left,
            466,
            "from the coarsest level that still has at least one element per column "
            "(here: one level-64 element per column).",
            12,
            TEXT_SECONDARY,
        )
    )
    return svg(width, height + 10, body, "Min/max pyramid of the waveform")


def spectrogram_pipeline() -> str:
    """Block-wise, multi-threaded STFT with a float16 buffer and 8-bit quantization

    Returns
    -------
    str
        The SVG document
    """
    width, height = 900, 500
    body = [text(24, 30, "Spectrogram: one pass by blocks of frames, then 8-bit quantization", 16, weight="bold")]

    # Signal and its frames, grouped in blocks
    body.append(text(24, 70, "signal (zero-padded by n_fft/2 on each side)", 12, TEXT_SECONDARY))
    body.append(rect(24, 78, 852, 22, LIGHT, LINE, radius=3))
    blocks_x = [24 + i * 213 for i in range(4)]
    for i, x in enumerate(blocks_x):
        body.append(rect(x + 3, 106, 207, 18, BLUE_LIGHT, BLUE, radius=3))
        body.append(text(x + 106, 119, f"block {i}: 128 frames", 11, TEXT, "middle"))
    body.append(
        text(
            24,
            142,
            "frame t is centred on sample t·hop; a block needs the samples of its own frames only",
            11,
            TEXT_SECONDARY,
        )
    )

    # Worker threads
    stages = ["frames (view, no copy)", "× window", "rFFT (n_fft)", "|X|  (float32)"]
    for lane in range(2):
        y = 165 + lane * 85
        body.append(text(24, y + 20, f"thread {lane + 1}", 12, TEXT))
        for s, label in enumerate(stages):
            x = 110 + s * 150
            body.append(rect(x, y, 130, 34, BLUE_LIGHT, BLUE, radius=4))
            body.append(text(x + 65, y + 21, label, 11, TEXT, "middle"))
            if s:
                body.append(arrow(x - 20, y + 17, x - 2, y + 17))
        body.append(arrow(110 + 4 * 150 - 20, y + 17, 728, 183))
        body.append(arrow(110 + 4 * 150 - 20, y + 17, 728, 245))
    body.append(
        text(
            24,
            306,
            "(up to 4 threads; numpy releases the GIL during the FFT; each block writes its own rows)",
            11,
            TEXT_SECONDARY,
        )
    )

    # Outputs of a block
    body.append(rect(732, 160, 144, 46, ORANGE_LIGHT, ORANGE, radius=4))
    body.append(text(804, 179, "block maximum", 11, TEXT, "middle"))
    body.append(text(804, 195, "(all bins)", 11, TEXT_SECONDARY, "middle"))
    body.append(rect(732, 222, 144, 46, BLUE_LIGHT, BLUE, radius=4))
    body.append(text(804, 241, "20·log10 |X| of the", 11, TEXT, "middle"))
    body.append(text(804, 257, "kept bins → float16", 11, TEXT, "middle"))

    # After the pass
    body.append(line(24, 320, 876, 320, LIGHT, 1))
    body.append(text(24, 345, "after the pass", 12, TEXT, weight="bold"))
    body.append(rect(24, 360, 250, 54, ORANGE_LIGHT, ORANGE, radius=4))
    body.append(text(149, 382, "M = max of the block maxima", 11, TEXT, "middle"))
    body.append(text(149, 399, "(0 dB reference, as librosa)", 11, TEXT_SECONDARY, "middle"))
    body.append(rect(314, 360, 300, 54, BLUE_LIGHT, BLUE, radius=4))
    body.append(text(464, 382, "d = max(a − 20·log10 M, −80) clipped to [L, H]", 11, TEXT, "middle"))
    body.append(text(464, 399, "code = round((d − L) · 255 / (H − L))", 11, TEXT, "middle"))
    body.append(rect(654, 360, 222, 54, BLUE, BLUE, radius=4))
    body.append(text(765, 382, "uint8 spectrogram", 12, SURFACE, "middle", "bold"))
    body.append(text(765, 399, "1 byte per kept cell", 11, SURFACE, "middle"))
    body.append(arrow(274, 387, 312, 387))
    body.append(arrow(614, 387, 652, 387))
    body.append(
        text(
            24,
            448,
            "Memory: the float16 buffer (2 bytes per kept cell) and the uint8 result (1 byte) during the extraction,",
            12,
            TEXT_SECONDARY,
        )
    )
    body.append(
        text(
            24,
            466,
            "1 byte per kept cell afterwards; each thread only holds the temporaries of one block "
            "(128 × n_fft values).",
            12,
            TEXT_SECONDARY,
        )
    )
    return svg(width, height - 10, body, "Spectrogram extraction pipeline")


def visible_slice() -> str:
    """Visible-slice rendering of the data images and its update rule

    Returns
    -------
    str
        The SVG document
    """
    width, height = 900, 400
    left, right = 60, 840
    body = [
        text(
            24, 30, "Data images: only the visible slice (plus a margin) is given to the image item", 16, weight="bold"
        )
    ]

    def frames_bar(y: float, label: str) -> None:
        body.append(text(left, y - 8, label, 12, TEXT_SECONDARY))
        body.append(rect(left, y, right - left, 20, LIGHT, LINE, radius=3))

    # Case 1: a new slice is computed
    frames_bar(78, "data: all the frames (never copied)")
    view0, view1 = 420, 520
    margin = (view1 - view0) * 0.5
    body.append(rect(view0 - margin, 74, view1 - view0 + 2 * margin, 28, BLUE_LIGHT, BLUE, radius=4))
    body.append(rect(view0, 70, view1 - view0, 36, "none", ORANGE, radius=4, dash="5 4"))
    body.append(text((view0 + view1) / 2, 124, "visible range (w frames)", 11, TEXT, "middle"))
    body.append(text(view0 - margin, 140, "slice = visible range ± w/2", 11, TEXT))
    body.append(text(view0 - margin, 155, "image item ← data[s0:s1]  (a view)", 11, TEXT_SECONDARY))
    body.append(text(view0 - margin, 170, "transform ← translate(s0, 0) · T", 11, TEXT_SECONDARY))

    # Case 2: small pan, still covered → nothing to do
    frames_bar(220, "pan inside the slice: nothing to do")
    body.append(rect(view0 - margin, 216, view1 - view0 + 2 * margin, 28, BLUE_LIGHT, BLUE, radius=4))
    body.append(rect(view0 + 30, 212, view1 - view0, 36, "none", ORANGE, radius=4, dash="5 4"))

    # Case 3: the view leaves the slice (or the slice gets 3 × wider than the view) → new slice
    frames_bar(310, "view leaves the slice (long pan, zoom-out) or slice > 3 × view (zoom-in): new slice")
    body.append(rect(view0 - margin, 306, view1 - view0 + 2 * margin, 28, "none", BLUE, radius=4, dash="3 3"))
    v0, v1 = 600, 700
    body.append(rect(v0 - 50, 306, v1 - v0 + 100, 28, BLUE_LIGHT, BLUE, radius=4))
    body.append(rect(v0, 302, v1 - v0, 36, "none", ORANGE, radius=4, dash="5 4"))
    body.append(
        text(
            left,
            372,
            "The rendering cost is proportional to the slice (at most 3 × the visible frames, then downsampled",
            12,
            TEXT_SECONDARY,
        )
    )
    body.append(text(left, 389, "to the screen), not to the length of the recording.", 12, TEXT_SECONDARY))
    return svg(width, height, body, "Visible-slice rendering of the data images")


def praat_chunks() -> str:
    """Chunked Praat analysis with margins

    Returns
    -------
    str
        The SVG document
    """
    width, height = 900, 330
    left, right = 60, 840
    body = [text(24, 30, "Praat spectrogram: analysis by chunks with margins", 16, weight="bold")]
    body.append(text(left, 64, "signal", 12, TEXT_SECONDARY))
    body.append(rect(left, 72, right - left, 20, LIGHT, LINE, radius=3))
    chunk_w = (right - left) / 3
    for c in range(3):
        x = left + c * chunk_w
        body.append(line(x, 68, x, 96, LINE, 1.5))
        body.append(text(x + chunk_w / 2, 87, f"chunk {c} (30 s)", 11, TEXT, "middle"))
    body.append(line(right, 68, right, 96, LINE, 1.5))

    # Analysed span of the middle chunk and the frames it keeps
    x0, x1 = left + chunk_w, left + 2 * chunk_w
    m = 28
    body.append(rect(x0 - m, 120, chunk_w + 2 * m, 24, ORANGE_LIGHT, ORANGE, radius=4))
    body.append(text(x0 - m + 6, 136, "analysed by Praat: chunk ± 50 ms margin", 11, TEXT))
    for k in range(-2, 24):
        x = x0 + 8 + k * 11
        kept = x0 <= x < x1
        color = BLUE if kept else LINE
        body.append(line(x, 160, x, 186, color, 2.5 if kept else 1.2))
    body.append(
        text(
            x0,
            206,
            "frames whose centre lies in the chunk are kept (blue); the others belong to the neighbours",
            11,
            TEXT,
        )
    )
    body.append(
        text(
            left,
            250,
            "The margin is larger than the analysis window, so the frames near a boundary see the same samples as",
            12,
            TEXT_SECONDARY,
        )
    )
    body.append(
        text(
            left,
            267,
            "on the full signal. Two passes: the first finds the maximum power, the second converts each chunk to",
            12,
            TEXT_SECONDARY,
        )
    )
    body.append(
        text(
            left,
            284,
            "decibels relative to it and quantizes them on 8 bits over a 70 dB range. Only one chunk is in",
            12,
            TEXT_SECONDARY,
        )
    )
    body.append(text(left, 301, "floating point at a time.", 12, TEXT_SECONDARY))
    return svg(width, height, body, "Chunked Praat analysis")


def playback_resampling() -> str:
    """On-the-fly linear interpolation in the audio callback

    Returns
    -------
    str
        The SVG document
    """
    width, height = 900, 320
    left = 80
    body = [text(24, 30, "Playback: resampling block by block in the audio callback", 16, weight="bold")]
    y_src, y_out = 120, 230
    body.append(text(24, y_src + 4, "source", 12, TEXT))
    body.append(text(24, y_src + 19, "(16 kHz)", 11, TEXT_SECONDARY))
    body.append(text(24, y_out + 4, "played", 12, TEXT))
    body.append(text(24, y_out + 19, "(48 kHz)", 11, TEXT_SECONDARY))
    values = [0.2, 0.7, 0.9, 0.4, -0.3, -0.8, -0.5, 0.1]
    src_step = 96
    for i, v in enumerate(values):
        x = left + 20 + i * src_step
        body.append(line(x, y_src, x, y_src - 40 * v, BLUE, 2))
        body.append(
            f"<circle cx='{x:.1f}' cy='{y_src - 40 * v:.1f}' r='4' fill='{BLUE}' stroke='{SURFACE}' stroke-width='2'/>"
        )
    body.append(line(left, y_src, left + 20 + 7 * src_step + 20, y_src, LIGHT, 1))
    body.append(line(left, y_out, left + 20 + 7 * src_step + 20, y_out, LIGHT, 1))
    ratio = 1 / 3
    for p in range(22):
        pos = p * ratio
        i0 = int(pos)
        frac = pos - i0
        v = (1 - frac) * values[i0] + frac * values[min(i0 + 1, len(values) - 1)]
        x = left + 20 + pos * src_step
        highlight = p == 7
        color = ORANGE if highlight else BLUE
        body.append(line(x, y_out, x, y_out - 40 * v, color, 2 if highlight else 1.2))
        if highlight:
            body.append(line(x, y_out - 40 * v, x, y_src + 30, ORANGE, 1, "3 3"))
            body.append(
                text(x + 8, y_out + 22, "p = 7  →  source position 7 × ρ = 2.33: between samples 2 and 3,", 11, TEXT)
            )
            body.append(text(x + 8, y_out + 37, "value = 0.67 · x[2] + 0.33 · x[3]", 11, TEXT))
    body.append(
        text(
            left,
            296,
            "ρ = source rate / played rate. Only the samples of the current block (a few hundred) are computed,",
            12,
            TEXT_SECONDARY,
        )
    )
    body.append(
        text(
            left,
            313,
            "so no resampled copy of the signal is ever stored. Used only when the device rejects the native rate.",
            12,
            TEXT_SECONDARY,
        )
    )
    return svg(width, height + 6, body, "Block-wise resampling during playback")


def main() -> None:
    """Write the diagrams"""
    (HERE / "waveform_pyramid.svg").write_text(waveform_pyramid())
    (HERE / "spectrogram_pipeline.svg").write_text(spectrogram_pipeline())
    (HERE / "visible_slice.svg").write_text(visible_slice())
    (HERE / "praat_chunks.svg").write_text(praat_chunks())
    (HERE / "playback_resampling.svg").write_text(playback_resampling())


if __name__ == "__main__":
    main()
