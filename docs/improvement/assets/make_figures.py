"""Generate the SVG figures of the performance report from benchmark.json

usage: python make_figures.py   (run from this directory; writes the *.svg files next to it)

The figures are plain SVG written by hand (no plotting library needed). Colours follow a validated
categorical pair: "before" is orange, "after" is blue; text uses neutral inks, never the series colour.
"""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent

SURFACE = "#fcfcfb"
TEXT = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
GRID = "#e4e3de"
BEFORE = "#eb6834"
AFTER = "#2a78d6"
CAP_MB = 4096
FONT = "font-family='Helvetica, Arial, sans-serif'"

#: Benchmark stages shown in the figures (label, key in benchmark.json)
STAGES = [
    ("Import", "import"),
    ("Load audio", "load_wav"),
    ("Plugins", "discover_plugins"),
    ("Window", "build_window"),
    ("First paint", "first_paint"),
    ("Annotations", "load_annotations"),
    ("Raw data", "select Raw DATA"),
    ("Spectrogram", "select Spectrogram"),
    ("Praat", "select Spectrogram (Praat)"),
    ("Pan", "pan 5s view x10"),
    ("Colormap", "colormap change"),
]


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


def bar(x0: float, y: float, width: float, height: float, color: str, radius: float = 4) -> str:
    """Build a horizontal bar anchored at x0, with a rounded data end (right side only)

    Parameters
    ----------
    x0 : float
        The baseline position
    y : float
        The top of the bar
    width : float
        The length of the bar
    height : float
        The thickness of the bar
    color : str
        The fill colour
    radius : float, optional
        The radius of the rounded end. (default: 4)

    Returns
    -------
    str
        The element
    """
    r = min(radius, width / 2, height / 2)
    x1 = x0 + width
    return (
        f"<path d='M{x0:.1f},{y:.1f} H{x1 - r:.1f} Q{x1:.1f},{y:.1f} {x1:.1f},{y + r:.1f} "
        f"V{y + height - r:.1f} Q{x1:.1f},{y + height:.1f} {x1 - r:.1f},{y + height:.1f} H{x0:.1f} Z' fill='{color}'/>"
    )


def legend(x: float, y: float) -> str:
    """Build the before/after legend

    Parameters
    ----------
    x, y : float
        The position of the first entry

    Returns
    -------
    str
        The elements
    """
    parts = []
    for i, (label, color) in enumerate([("Before (audit-fixes branch)", BEFORE), ("After (perf branch)", AFTER)]):
        dx = x + i * 220
        parts.append(f"<rect x='{dx}' y='{y - 9}' width='12' height='12' rx='3' fill='{color}'/>")
        parts.append(text(dx + 18, y + 1, label, 12, TEXT_SECONDARY))
    return "".join(parts)


def svg(width: int, height: int, body: list[str], title: str) -> str:
    """Wrap elements in an SVG document with an explicit background (readable in light and dark viewers)

    Parameters
    ----------
    width, height : int
        The size in pixels
    body : list(str)
        The elements
    title : str
        The accessible title of the figure

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


def memory_timeline(data: dict) -> str:
    """Resident memory after each benchmark stage on the 10-minute recording

    Parameters
    ----------
    data : dict
        The content of benchmark.json

    Returns
    -------
    str
        The SVG document
    """
    width, height = 860, 440
    left, right, top, bottom = 70, 130, 100, 380
    x_step = (width - left - right) / (len(STAGES) - 1)

    def y_of(mb: float) -> float:
        return bottom - (bottom - top) * mb / CAP_MB

    body = [text(left, 28, "Memory used by spiny on a 10-minute recording", 16, TEXT, weight="bold"), legend(left, 52)]
    for mb in range(0, CAP_MB + 1, 1024):
        y = y_of(mb)
        body.append(
            f"<line x1='{left}' x2='{width - right}' y1='{y:.1f}' y2='{y:.1f}' stroke='{GRID}' stroke-width='1'/>"
        )
        body.append(text(left - 8, y + 4, f"{mb}", 11, TEXT_SECONDARY, "end"))
    body.append(text(left - 50, top - 22, "Resident memory (MB)", 11, TEXT_SECONDARY))
    cap_y = y_of(CAP_MB)
    body.append(
        f"<line x1='{left}' x2='{width - right}' y1='{cap_y:.1f}' y2='{cap_y:.1f}' stroke='{TEXT_SECONDARY}' "
        "stroke-width='1.5' stroke-dasharray='6 4'/>"
    )
    body.append(text(width - right + 8, cap_y + 4, "4 GB cap", 11, TEXT_SECONDARY))
    for i, (label, _) in enumerate(STAGES):
        x = left + i * x_step
        body.append(
            f"<text transform='translate({x:.1f},{bottom + 14}) rotate(30)' {FONT} font-size='11' "
            f"fill='{TEXT_SECONDARY}'>{label}</text>"
        )

    for name, color, run in [("Before", BEFORE, "base_long"), ("After", AFTER, "new_long")]:
        points = [
            (left + i * x_step, y_of(data[run][key]["rss_mb"])) for i, (_, key) in enumerate(STAGES) if key in data[run]
        ]
        path = " ".join(f"{'M' if i == 0 else 'L'}{x:.1f},{y:.1f}" for i, (x, y) in enumerate(points))
        body.append(f"<path d='{path}' fill='none' stroke='{color}' stroke-width='2' stroke-linejoin='round'/>")
        for x, y in points:
            body.append(f"<circle cx='{x:.1f}' cy='{y:.1f}' r='4' fill='{color}' stroke='{SURFACE}' stroke-width='2'/>")
        last_x, last_y = points[-1]
        if run == "base_long":
            # The run was killed by the memory cap while extracting the spectrogram
            kx = left + len(points) * x_step
            body.append(
                f"<path d='M{last_x:.1f},{last_y:.1f} L{kx:.1f},{cap_y:.1f}' stroke='{color}' stroke-width='2' "
                "stroke-dasharray='4 4' fill='none'/>"
            )
            body.append(
                f"<path d='M{kx - 6:.1f},{cap_y - 6:.1f} L{kx + 6:.1f},{cap_y + 6:.1f} "
                f"M{kx - 6:.1f},{cap_y + 6:.1f} L{kx + 6:.1f},{cap_y - 6:.1f}' stroke='{color}' stroke-width='3'/>"
            )
            body.append(text(kx + 10, cap_y + 22, "killed: over 4 GB", 12, TEXT))
            body.append(text(kx + 10, cap_y + 37, "while opening the spectrogram", 11, TEXT_SECONDARY))
            body.append(text(last_x - 6, last_y - 10, f"{data[run]['select Raw DATA']['rss_mb']} MB", 11, TEXT, "end"))
        else:
            body.append(text(last_x + 10, last_y + 4, f"After: {data[run]['colormap change']['rss_mb']} MB", 12, TEXT))
    return svg(width, height, body, "Resident memory per stage on a 10-minute recording, before and after")


def grouped_bars(title: str, rows: list[tuple[str, float | None, float]], unit: str, maximum: float, note: str) -> str:
    """Horizontal grouped bars comparing before and after for each row

    Parameters
    ----------
    title : str
        The figure title
    rows : list(tuple(str, float or None, float))
        (label, before value or None if the run did not finish, after value)
    unit : str
        The unit appended to the value labels
    maximum : float
        The value at the end of the axis
    note : str
        A note printed under the chart

    Returns
    -------
    str
        The SVG document
    """
    width = 860
    left, right, top = 170, 110, 80
    bar_h, gap, group_gap = 14, 2, 22
    height = top + len(rows) * (2 * bar_h + gap + group_gap) + 50
    plot_w = width - left - right

    def x_len(value: float) -> float:
        return plot_w * min(value, maximum) / maximum

    body = [text(24, 28, title, 16, TEXT, weight="bold"), legend(24, 54)]
    for i in range(5):
        x = left + plot_w * i / 4
        body.append(
            f"<line x1='{x:.1f}' x2='{x:.1f}' y1='{top - 8}' y2='{height - 46}' stroke='{GRID}' stroke-width='1'/>"
        )
        value = maximum * i / 4
        body.append(text(x, height - 30, f"{value:g}", 11, TEXT_SECONDARY, "middle"))
    body.append(text(left + plot_w / 2, height - 12, unit, 11, TEXT_SECONDARY, "middle"))

    y = top
    for label, before, after in rows:
        body.append(text(left - 12, y + bar_h + 5, label, 12, TEXT, "end"))
        if before is None:
            body.append(bar(left, y, plot_w, bar_h, BEFORE))
            body.append(text(left + plot_w + 8, y + bar_h - 3, "killed (4 GB)", 11, TEXT))
        else:
            body.append(bar(left, y, max(x_len(before), 2), bar_h, BEFORE))
            body.append(
                text(left + max(x_len(before), 2) + 6, y + bar_h - 3, f"{fmt(before)} {unit_short(unit)}", 11, TEXT)
            )
        ya = y + bar_h + gap
        body.append(bar(left, ya, max(x_len(after), 2), bar_h, AFTER))
        body.append(text(left + max(x_len(after), 2) + 6, ya + bar_h - 3, f"{fmt(after)} {unit_short(unit)}", 11, TEXT))
        y += 2 * bar_h + gap + group_gap
    body.append(text(24, height - 12 + 0, note, 11, TEXT_SECONDARY) if note else "")
    return svg(width, height, body, title)


def fmt(value: float) -> str:
    """Format a value with a precision suited to its magnitude

    Parameters
    ----------
    value : float
        The value

    Returns
    -------
    str
        The formatted value
    """
    if value >= 100:
        return f"{value:.0f}"
    return f"{value:.2f}"


def unit_short(unit: str) -> str:
    """Abbreviate an axis unit for the value labels

    Parameters
    ----------
    unit : str
        The axis unit

    Returns
    -------
    str
        The abbreviation
    """
    return {"Seconds": "s", "Peak memory (MB)": "MB"}.get(unit, unit)


def main() -> None:
    """Write the figures"""
    data = json.loads((HERE / "benchmark.json").read_text())
    (HERE / "memory_timeline_10min.svg").write_text(memory_timeline(data))

    peak = lambda run: max(stage["peak_mb"] for stage in data[run].values())  # noqa: E731
    (HERE / "peak_memory.svg").write_text(
        grouped_bars(
            "Peak memory over the whole benchmark",
            [
                ("2-minute recording", peak("base_short"), peak("new_short")),
                ("10-minute recording", None, peak("new_long")),
            ],
            "Peak memory (MB)",
            CAP_MB,
            "",
        )
    )

    operations = [
        ("Import spiny", "import"),
        ("Load the audio", "load_wav"),
        ("First paint", "first_paint"),
        ("Load annotations", "load_annotations"),
        ("Open spectrogram", "select Spectrogram"),
        ("Pan (10 frames)", "pan 5s view x10"),
        ("Change colormap", "colormap change"),
    ]
    (HERE / "operation_times_2min.svg").write_text(
        grouped_bars(
            "Time of common operations on a 2-minute recording",
            [(label, data["base_short"][key]["s"], data["new_short"][key]["s"]) for label, key in operations],
            "Seconds",
            3.0,
            "",
        )
    )


if __name__ == "__main__":
    main()
